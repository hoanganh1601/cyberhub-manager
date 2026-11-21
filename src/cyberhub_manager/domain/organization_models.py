"""Store and employee domain entities."""

from __future__ import annotations

import re
from datetime import datetime

from cyberhub_manager.domain.enums import EmployeeStatus, Role, StoreStatus
from cyberhub_manager.domain.exceptions import ValidationError
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.domain.model_base import (
    Entity,
    Person,
    _require_datetime,
    _require_non_blank,
    _require_positive_id,
)


class Store(Entity):
    __slots__ = (
        "__name",
        "__address",
        "__status",
        "__created_at",
        "__updated_at",
    )

    def __init__(
        self,
        id: int,
        code: str,
        name: str,
        address: str,
        status: StoreStatus,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id, code)
        self.__name = name
        self.__address = address
        self.__status = status
        self.__created_at = created_at
        self.__updated_at = updated_at
        self.validate()

    @property
    def name(self) -> str:
        return self.__name

    @property
    def address(self) -> str:
        return self.__address

    @property
    def status(self) -> StoreStatus:
        return self.__status

    @property
    def created_at(self) -> datetime:
        return self.__created_at

    @property
    def updated_at(self) -> datetime:
        return self.__updated_at

    def get_name(self) -> str:
        return self.__name

    def get_address(self) -> str:
        return self.__address

    def get_status(self) -> StoreStatus:
        return self.__status

    def update_info(self, name: str, address: str) -> None:
        new_name = _require_non_blank(name, "name", "Tên cửa hàng")
        new_address = _require_non_blank(
            address, "address", "Địa chỉ cửa hàng"
        )
        self.__name = new_name
        self.__address = new_address

    def activate(self) -> None:
        self.__status = StoreStatus.ACTIVE

    def deactivate(self) -> None:
        self.__status = StoreStatus.INACTIVE

    def validate(self) -> None:
        self.__name = _require_non_blank(
            self.__name, "name", "Tên cửa hàng"
        )
        self.__address = _require_non_blank(
            self.__address, "address", "Địa chỉ cửa hàng"
        )
        if not isinstance(self.__status, StoreStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái cửa hàng không hợp lệ"}
            )
        _require_datetime(self.__created_at, "created_at")
        _require_datetime(self.__updated_at, "updated_at")

class Employee(Person):
    __slots__ = ("__store_id", "__username", "__role", "__status")

    def __init__(
        self,
        id: int,
        code: str,
        full_name: str,
        store_id: int,
        username: str,
        role: Role,
        status: EmployeeStatus,
    ) -> None:
        super().__init__(id, code, full_name)
        self.__store_id = store_id
        self.__username = username
        self.__role = role
        self.__status = status
        self.validate()

    @property
    def store_id(self) -> int:
        return self.__store_id

    @property
    def username(self) -> str:
        return self.__username

    @property
    def role(self) -> Role:
        return self.__role

    @property
    def status(self) -> EmployeeStatus:
        return self.__status

    def get_store_id(self) -> int:
        return self.__store_id

    def get_username(self) -> str:
        return self.__username

    def get_role(self) -> Role:
        return self.__role

    def get_status(self) -> EmployeeStatus:
        return self.__status

    def can_manage_machines(self) -> bool:
        return (
            self.__status == EmployeeStatus.ACTIVE
            and can(self.__role, Permission.MANAGE_MACHINES)
        )

    def can_access_store(self, store_id: int) -> bool:
        return (
            self.__status == EmployeeStatus.ACTIVE
            and self.__store_id == store_id
        )

    def activate(self) -> None:
        self.__status = EmployeeStatus.ACTIVE

    def deactivate(self) -> None:
        self.__status = EmployeeStatus.INACTIVE

    def lock(self) -> None:
        self.__status = EmployeeStatus.LOCKED

    def validate(self) -> None:
        _require_positive_id(self.__store_id, "store_id")
        username = _require_non_blank(
            self.__username, "username", "Tên đăng nhập"
        )
        if re.fullmatch(r"[A-Za-z0-9_.]{4,30}", username) is None:
            raise ValidationError(
                field_errors={
                    "username": (
                        "Tên đăng nhập phải dài 4-30 ký tự và chỉ gồm "
                        "chữ, số, dấu gạch dưới hoặc dấu chấm"
                    )
                }
            )
        self.__username = username
        if not isinstance(self.__role, Role):
            raise ValidationError(
                field_errors={"role": "Vai trò nhân viên không hợp lệ"}
            )
        if not isinstance(self.__status, EmployeeStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái nhân viên không hợp lệ"}
            )
