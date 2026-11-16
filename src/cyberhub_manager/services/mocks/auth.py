"""Mock AuthService dùng tài khoản demo giả trong fixtures."""

from __future__ import annotations

import hmac

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import EmployeeStatus
from cyberhub_manager.domain.exceptions import AuthenticationError, ConflictError, PermissionDeniedError, ValidationError
from cyberhub_manager.security import hash_password, verify_password

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
            or expected is None and employee.id not in self._data.employee_password_hashes
            or not isinstance(password, str)
            or not (verify_password(password,self._data.employee_password_hashes[employee.id])
                    if employee.id in self._data.employee_password_hashes else
                    hmac.compare_digest(password.encode("utf-8"), expected.encode("utf-8")))
            or employee.status != EmployeeStatus.ACTIVE
            or str(self._data.get_store(employee.store_id).status) != "ACTIVE"
        ):
            raise AuthenticationError()
        return self._data.to_employee_session(employee)

    def change_password(self, actor, current_password: str, new_password: str):
        employee = self._data.employees.get(getattr(actor, "employee_id", None))
        if employee is None or employee.role != actor.role:
            raise PermissionDeniedError()
        password_hash = self._data.employee_password_hashes.get(employee.id)
        expected = self._data.employee_passwords.get(employee.username)
        valid = verify_password(current_password, password_hash) if password_hash else (
            isinstance(current_password, str) and expected is not None and hmac.compare_digest(current_password, expected)
        )
        if not valid:
            raise AuthenticationError("Mật khẩu hiện tại không đúng")
        if not isinstance(new_password, str) or len(new_password) < 8 or len(new_password.encode()) > 72:
            raise ValidationError(field_errors={"new_password": "Mật khẩu mới phải từ 8 ký tự và tối đa 72 byte"})
        if current_password == new_password:
            raise ConflictError("Mật khẩu mới phải khác mật khẩu hiện tại")
        self._data.employee_password_hashes[employee.id] = hash_password(new_password)
        self._data.employee_passwords.pop(employee.username, None)
        self._data.employee_auth_versions[employee.id] = self._data.employee_auth_versions.get(employee.id, 0) + 1
        self._data.employee_must_change_password[employee.id] = False
        self._data.management_audit.append((employee.id, employee.store_id, "EMPLOYEE_PASSWORD_CHANGE", employee.id))
        return self._data.to_employee_session(employee)
