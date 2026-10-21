"""Mock AuthService dùng tài khoản demo giả trong fixtures."""

from __future__ import annotations

import hmac

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import EmployeeStatus
from cyberhub_manager.domain.exceptions import AuthenticationError

from .base import MockServiceBase, clean_text


class MockAuthService(MockServiceBase):
    def login(self, username: str, password: str) -> EmployeeSession:
        self._check_scenario("login")
        normalized = clean_text(username)
        employee = (
            self._data.find_employee_by_username(normalized)
            if normalized
            else None
        )
        expected = (
            self._data.employee_passwords.get(employee.username)
            if employee is not None
            else None
        )
        # Password không trim; mọi trường hợp sai dùng chung một thông báo.
        if (
            employee is None
            or expected is None
            or not isinstance(password, str)
            or not hmac.compare_digest(password, expected)
            or employee.status != EmployeeStatus.ACTIVE
        ):
            raise AuthenticationError()
        return self._data.to_employee_session(employee)
