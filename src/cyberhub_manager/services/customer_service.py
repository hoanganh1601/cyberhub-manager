"""LI-03 — Linh: CustomerService tạo, xem, tìm, sửa và đổi trạng thái khách.

Service chỉ làm việc qua CustomerRepository, AccountRepository và
database.transaction.transaction(); UI không gọi repository hay SQL trực tiếp.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any
from uuid import uuid4

from mysql.connector import Error as MySQLError
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import CustomerSummary, EmployeeSession
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus, Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.domain.models import Customer
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.security import hash_password

MANAGER_ROLES = frozenset({Role.MANAGER, Role.ADMIN})
ActorProvider = Callable[[], EmployeeSession | None]

# "CUS-"/"ACC-" + 16 ký tự hex = 20 ký tự, vừa cột code VARCHAR(20).
CUSTOMER_CODE_PREFIX = "CUS-"
ACCOUNT_CODE_PREFIX = "ACC-"
CODE_HEX_LENGTH = 16

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_BYTES = 72  # bcrypt chỉ nhận tối đa 72 byte UTF-8.

PHONE_TAKEN = "Số điện thoại đã được sử dụng"
USERNAME_TAKEN = "Tên đăng nhập đã được sử dụng"

# Tên UNIQUE constraint trong sql/001_initial_schema.sql -> field lỗi cho UI.
_DUPLICATE_FIELDS = (
    ("uq_customers_phone", "phone", PHONE_TAKEN),
    ("uq_accounts_username", "username", USERNAME_TAKEN),
)

_PHONE_PATTERN = re.compile(r"0[0-9]{9}")
_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.]{4,30}")


# ----- Validate từng trường, trả thông báo lỗi hoặc None --------------------


def _clean(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _full_name_error(value: str) -> str | None:
    if not 2 <= len(value) <= 100:
        return "Họ tên phải có từ 2 đến 100 ký tự"
    return None


def _phone_error(value: str) -> str | None:
    if _PHONE_PATTERN.fullmatch(value) is None:
        return "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0"
    return None


def _username_error(value: str) -> str | None:
    if _USERNAME_PATTERN.fullmatch(value) is None:
        return (
            "Tên đăng nhập phải dài 4-30 ký tự và chỉ gồm "
            "chữ, số, dấu gạch dưới hoặc dấu chấm"
        )
    return None


def _password_error(value: object) -> str | None:
    if not isinstance(value, str) or len(value) < MIN_PASSWORD_LENGTH:
        return "Mật khẩu phải có ít nhất 6 ký tự"
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "Mật khẩu quá dài"
    return None


def _raise_if_errors(errors: dict[str, str | None]) -> None:
    """Gom mọi lỗi trường vào một ValidationError để UI đánh dấu cùng lúc."""

    field_errors = {field: message for field, message in errors.items() if message}
    if field_errors:
        raise ValidationError(field_errors=field_errors)


def _is_positive_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _new_code(prefix: str) -> str:
    return prefix + uuid4().hex[:CODE_HEX_LENGTH]


def _conflict_from(exc: IntegrityError) -> ConflictError | None:
    """Đổi lỗi trùng UNIQUE của MySQL thành ConflictError có field cho UI."""

    if exc.errno != errorcode.ER_DUP_ENTRY:
        return None
    for constraint, field, message in _DUPLICATE_FIELDS:
        if constraint in str(exc):
            return ConflictError(message, field_errors={field: message})
    return None


class CustomerService:
    """Triển khai CustomerServiceProtocol trên MySQL."""

    def __init__(
        self,
        customer_repo: CustomerRepository | None = None,
        account_repo: AccountRepository | None = None,
        auth_repo: AuthRepository | None = None,
        actor_provider: ActorProvider | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
    ) -> None:
        self._customers = customer_repo or CustomerRepository()
        self._accounts = account_repo or AccountRepository()
        self._auth = auth_repo or AuthRepository()
        self._actor_provider = actor_provider
        self._transaction = transaction_factory

    def create_customer(
        self,
        full_name: str,
        phone: str,
        username: str,
        password: str,
    ) -> Customer:
        full_name = _clean(full_name)
        phone = _clean(phone)
        username = _clean(username)
        _raise_if_errors(
            {
                "full_name": _full_name_error(full_name),
                "phone": _phone_error(phone),
                "username": _username_error(username),
                "password": _password_error(password),
            }
        )
        # Hash trước khi mở transaction để không giữ connection trong lúc bcrypt chạy.
        password_hash = hash_password(password)

        with self._database() as conn:
            # Customer và account cùng một transaction: lỗi ở account thì rollback cả customer.
            self._require_actor(conn)
            customer_id = self._customers.create(
                conn,
                code=_new_code(CUSTOMER_CODE_PREFIX),
                full_name=full_name,
                phone=phone,
            )
            self._accounts.create(
                conn,
                code=_new_code(ACCOUNT_CODE_PREFIX),
                customer_id=customer_id,
                username=username,
                password_hash=password_hash,
            )
            return self._get_customer(conn, customer_id)

    def get_customer(self, customer_id: int) -> Customer:
        with self._database() as conn:
            self._require_actor(conn)
            return self._get_customer(conn, customer_id)

    def search_customers(self, keyword: str) -> list[CustomerSummary]:
        with self._database() as conn:
            self._require_actor(conn)
            return self._customers.search(conn, _clean(keyword))

    def update_customer(
        self,
        customer_id: int,
        full_name: str,
        phone: str,
    ) -> Customer:
        full_name = _clean(full_name)
        phone = _clean(phone)
        _raise_if_errors(
            {
                "full_name": _full_name_error(full_name),
                "phone": _phone_error(phone),
            }
        )

        with self._database() as conn:
            self._require_actor(conn)
            self._get_customer(conn, customer_id)
            # Không dựa vào rowcount: MySQL trả 0 khi dữ liệu mới giống dữ liệu cũ.
            self._customers.update_profile(
                conn, customer_id, full_name=full_name, phone=phone
            )
            return self._get_customer(conn, customer_id)

    def set_customer_status(
        self,
        customer_id: int,
        status: CustomerStatus,
        actor: EmployeeSession,
    ) -> Customer:
        if not isinstance(status, CustomerStatus):
            raise ValidationError(
                field_errors={
                    "status": "Trạng thái khách hàng không hợp lệ"
                }
            )

        account_status = (
            AccountStatus.ACTIVE
            if status == CustomerStatus.ACTIVE
            else AccountStatus.LOCKED
        )

        with self._database() as conn:
            self._require_actor(
                conn,
                actor,
                manager_only=True,
            )

            customer = self._get_customer(conn, customer_id)

            # Update customer and account atomically.
            self._customers.set_status(
                conn,
                customer.id,
                status,
            )
            self._accounts.set_status(
                conn,
                customer.account.id,
                account_status,
            )

            return self._get_customer(conn, customer.id)

    def _require_actor(
        self,
        conn: Any,
        requested_actor: EmployeeSession | None = None,
        *,
        manager_only: bool = False,
    ) -> EmployeeSession:
        """Validate the current actor against the active database record."""

        actor = (
            self._actor_provider()
            if self._actor_provider is not None
            else None
        )

        if (
            not isinstance(actor, EmployeeSession)
            or not _is_positive_id(actor.employee_id)
            or not _is_positive_id(actor.store_id)
        ):
            raise PermissionDeniedError()

        if requested_actor is not None and (
            not isinstance(requested_actor, EmployeeSession)
            or requested_actor.employee_id != actor.employee_id
            or requested_actor.store_id != actor.store_id
        ):
            raise PermissionDeniedError()

        current_actor = self._auth.get_active_session_by_id(
            conn,
            actor.employee_id,
        )

        if current_actor is None or current_actor.store_id != actor.store_id:
            raise PermissionDeniedError()

        if manager_only and current_actor.role not in MANAGER_ROLES:
            raise PermissionDeniedError()

        return current_actor

    @contextmanager
    def _database(self) -> Iterator[Any]:
        """Mở transaction và đổi lỗi MySQL thành lỗi nghiệp vụ theo contract."""

        try:
            with self._transaction() as conn:
                yield conn
        except IntegrityError as exc:
            conflict = _conflict_from(exc)
            if conflict is not None:
                raise conflict from exc
            raise ServiceUnavailableError() from exc
        except MySQLError as exc:
            raise ServiceUnavailableError() from exc

    def _get_customer(self, conn: Any, customer_id: int) -> Customer:
        if _is_positive_id(customer_id):
            customer = self._customers.get_by_id(conn, customer_id)
            if customer is not None:
                return customer
        raise NotFoundError("Không tìm thấy khách hàng")
