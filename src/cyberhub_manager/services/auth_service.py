"""LI-03 — Linh: AuthService đăng nhập nhân viên.

Service chỉ làm việc qua AuthRepository, security.verify_password và
database.transaction.transaction(); UI không gọi repository hay SQL trực tiếp.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from mysql.connector import Error as MySQLError

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
)
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.security import verify_password


class AuthService:
    """Triển khai AuthServiceProtocol trên MySQL."""

    def __init__(
        self,
        auth_repo: AuthRepository | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
    ) -> None:
        self._auth = auth_repo or AuthRepository()
        self._transaction = transaction_factory

    def login(self, username: str, password: str) -> EmployeeSession:
        # Username được trim; password giữ nguyên như người dùng gõ.
        normalized = username.strip() if isinstance(username, str) else ""
        if not normalized or not isinstance(password, str) or not password:
            raise AuthenticationError()

        try:
            with self._transaction() as conn:
                # Repository chỉ trả nhân viên ACTIVE thuộc cửa hàng ACTIVE.
                record = self._auth.get_active_by_username(conn, normalized)
        except MySQLError as exc:
            raise ServiceUnavailableError() from exc

        # Mọi trường hợp sai dùng chung một thông báo để không lộ username nào tồn tại.
        if record is None or not verify_password(password, record.password_hash):
            raise AuthenticationError()
        return record.session
