"""Counter registration and one-time customer email activation/recovery."""

import base64
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import os
import re
import secrets

from dotenv import load_dotenv

from cyberhub_manager.infrastructure.database.transaction import transaction
from cyberhub_manager.domain.exceptions import ConflictError, PermissionDeniedError, ValidationError
from cyberhub_manager.domain.p1 import Permission
from cyberhub_manager.infrastructure.repositories.account_repository import AccountRepository
from cyberhub_manager.infrastructure.repositories.customer_repository import CustomerRepository
from cyberhub_manager.infrastructure.repositories.customer_email_repository import CustomerEmailRepository
from cyberhub_manager.infrastructure.security import hash_password
from cyberhub_manager.infrastructure.db_errors import translate_db_errors

from cyberhub_manager.application.services.customer_service import (
    _clean, _full_name_error, _phone_error, _username_error, _password_error,
    _raise_if_errors, _new_code, CUSTOMER_CODE_PREFIX, ACCOUNT_CODE_PREFIX,
)

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def token_secret():
    load_dotenv()
    secret = os.getenv("CYBERHUB_EMAIL_TOKEN_SECRET") or os.getenv("CYBERHUB_SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("Customer email tokens require a stable secret of at least 32 characters")
    return secret.encode("utf-8")


def token_from_nonce(nonce: str) -> str:
    digest = hmac.new(token_secret(), bytes.fromhex(nonce), "sha256").digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def token_hash(token: str) -> str:
    return sha256(token.encode("ascii")).hexdigest()


def normalized_email(value):
    email = _clean(value).lower()
    if len(email) > 254 or not _EMAIL.fullmatch(email):
        raise ValidationError(field_errors={"email": "Email không hợp lệ"})
    return email


class CustomerEmailService:
    def __init__(self, customer_service, repo=None, customer_repo=None,
                 account_repo=None, transaction_factory=transaction):
        self._service = customer_service
        self._repo = repo or CustomerEmailRepository()
        self._customers = customer_repo or CustomerRepository()
        self._accounts = account_repo or AccountRepository()
        self._transaction = transaction_factory

    def _issue(self, conn, account_id, purpose, *, cooldown=False):
        if cooldown and self._repo.recent_token(conn, account_id, purpose):
            return False
        nonce = secrets.token_hex(32)
        ttl = int(os.getenv("CYBERHUB_EMAIL_TOKEN_MINUTES", "30"))
        if not 5 <= ttl <= 1440:
            raise RuntimeError("CYBERHUB_EMAIL_TOKEN_MINUTES must be 5..1440")
        self._repo.issue_token(conn, account_id, purpose,
                               token_hash(token_from_nonce(nonce)), nonce, ttl)
        return True

    def register_at_counter(self, full_name, phone, email, username):
        name, phone, username = _clean(full_name), _clean(phone), _clean(username)
        email = normalized_email(email)
        _raise_if_errors({"full_name": _full_name_error(name),
                          "phone": _phone_error(phone),
                          "username": _username_error(username)})
        token_secret()  # Validate before writing an account that cannot be activated.
        with translate_db_errors(duplicates={
            "uq_customers_email": ("email", "Email đã được sử dụng"),
            "uq_customers_phone": ("phone", "Số điện thoại đã được sử dụng"),
            "uq_accounts_username": ("username", "Tên đăng nhập đã được sử dụng"),
        }), self._transaction() as conn:
            actor = self._service._require_actor(conn, permission=Permission.CREATE_CUSTOMERS)
            customer_id = self._customers.create(
                conn, code=_new_code(CUSTOMER_CODE_PREFIX), full_name=name, phone=phone)
            self._repo.set_email(conn, customer_id, email)
            account_id = self._accounts.create(
                conn, code=_new_code(ACCOUNT_CODE_PREFIX), customer_id=customer_id,
                username=username, password_hash=None)
            self._repo.mark_pending(conn, account_id)
            self._customers.link_store(conn, customer_id, actor.store_id, "COUNTER")
            self._issue(conn, account_id, "ACTIVATE")
            self._repo.audit(conn, account_id, "COUNTER_REGISTER", actor)
            return {"customer_id": customer_id, "account_id": account_id,
                    "email_status": "QUEUED"}

    def activate(self, token, password):
        if not isinstance(token, str) or len(token) != 43 or not token.isascii():
            raise ValidationError(field_errors={"token": "Liên kết không hợp lệ"})
        error = _password_error(password)
        if error:
            raise ValidationError(field_errors={"password": error})
        password_digest = hash_password(password)
        with self._transaction() as conn:
            record = self._repo.token_by_hash(conn, token_hash(token), lock=True)
            if (record is None or record["purpose"] != "ACTIVATE" or record["used_at"] is not None
                    or record["expires_at"] <= datetime.now(timezone.utc).replace(tzinfo=None)
                    or record["web_login_enabled"]):
                raise ConflictError("Liên kết kích hoạt đã hết hạn hoặc đã sử dụng")
            self._repo.activate(conn, record["id"], record["account_id"], password_digest)
            self._repo.audit(conn, record["account_id"], "EMAIL_ACTIVATED")
        return {"activated": True}

    def request_reset(self, email):
        generic = {"accepted": True}
        try:
            email = normalized_email(email)
        except ValidationError:
            return generic
        with self._transaction() as conn:
            account = self._repo.account_by_email(conn, email, lock=True)
            if account and account["web_login_enabled"] and account["email_verified_at"]:
                if self._issue(conn, account["account_id"], "RESET", cooldown=True):
                    self._repo.audit(conn, account["account_id"], "PASSWORD_RESET_REQUEST")
        return generic

    def resend_activation(self, email):
        generic = {"accepted": True}
        try:
            email = normalized_email(email)
        except ValidationError:
            return generic
        with self._transaction() as conn:
            account = self._repo.account_by_email(conn, email, lock=True)
            if account and not account["web_login_enabled"]:
                if self._issue(conn, account["account_id"], "ACTIVATE", cooldown=True):
                    self._repo.audit(conn, account["account_id"], "ACTIVATION_RESEND")
        return generic

    def reset_password(self, token, password):
        if not isinstance(token, str) or len(token) != 43 or not token.isascii():
            raise ValidationError(field_errors={"token": "Liên kết không hợp lệ"})
        error = _password_error(password)
        if error:
            raise ValidationError(field_errors={"password": error})
        password_digest = hash_password(password)
        with self._transaction() as conn:
            record = self._repo.token_by_hash(conn, token_hash(token), lock=True)
            if (record is None or record["purpose"] != "RESET" or record["used_at"] is not None
                    or record["expires_at"] <= datetime.now(timezone.utc).replace(tzinfo=None)
                    or not record["web_login_enabled"]):
                raise ConflictError("Liên kết đặt lại mật khẩu đã hết hạn hoặc đã sử dụng")
            self._repo.reset_password(conn, record["id"], record["account_id"], password_digest)
            self._repo.audit(conn, record["account_id"], "PASSWORD_RESET")
        return {"reset": True}
