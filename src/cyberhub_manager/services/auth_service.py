"""LI-03 — Linh: AuthService đăng nhập nhân viên.

Service chỉ làm việc qua AuthRepository, security.verify_password và
database.transaction.transaction(); UI không gọi repository hay SQL trực tiếp.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.p1_repository import P1Repository
from cyberhub_manager.security import hash_password, verify_password
from cyberhub_manager.services.db_errors import translate_db_errors


class AuthService:
    """Triển khai AuthServiceProtocol trên MySQL."""

    def __init__(
        self,
        auth_repo: AuthRepository | None = None,
        audit_repo: P1Repository | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
    ) -> None:
        self._auth = auth_repo or AuthRepository()
        self._audit = audit_repo or P1Repository()
        self._transaction = transaction_factory

    def login(self, username: str, password: str) -> EmployeeSession:
        # Username được trim; password giữ nguyên như người dùng gõ.
        normalized = username.strip() if isinstance(username, str) else ""
        if not normalized or not isinstance(password, str) or not password:
            raise AuthenticationError()

        with translate_db_errors():
            with self._transaction() as conn:
                # Repository chỉ trả nhân viên ACTIVE thuộc cửa hàng ACTIVE.
                record = self._auth.get_active_by_username(conn, normalized)

        # Mọi trường hợp sai dùng chung một thông báo để không lộ username nào tồn tại.
        if record is None or not verify_password(password, record.password_hash):
            raise AuthenticationError()
        return record.session

    def change_password(
        self,
        actor: EmployeeSession,
        current_password: str,
        new_password: str,
    ) -> EmployeeSession:
        if not isinstance(current_password, str) or not current_password:
            raise AuthenticationError("Mật khẩu hiện tại không đúng")
        if not isinstance(new_password, str) or len(new_password) < 8 or len(new_password.encode()) > 72:
            raise ValidationError(
                field_errors={"new_password": "Mật khẩu mới phải từ 8 ký tự và tối đa 72 byte"}
            )
        if current_password == new_password:
            raise ConflictError("Mật khẩu mới phải khác mật khẩu hiện tại")
        with translate_db_errors(), self._transaction() as conn:
            record = self._auth.get_active_record_by_id(conn, actor.employee_id)
            if record is None or record.session.role != actor.role:
                raise PermissionDeniedError()
            if not verify_password(current_password, record.password_hash):
                raise AuthenticationError("Mật khẩu hiện tại không đúng")
            self._auth.change_password(conn, actor.employee_id, hash_password(new_password))
            self._audit.audit(conn, record.session, "EMPLOYEE_PASSWORD_CHANGE", actor.employee_id)
            updated = self._auth.get_active_session_by_id(conn, actor.employee_id)
            if updated is None:
                raise PermissionDeniedError()
            return updated
