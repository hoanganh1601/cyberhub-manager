"""Machine domain entity."""

from __future__ import annotations

from datetime import datetime

from .enums import MachineStatus
from .exceptions import ConflictError, ValidationError
from .model_base import (
    Entity,
    _require_datetime,
    _require_non_blank,
    _require_positive_amount,
    _require_positive_id,
)


class Machine(Entity):
    __slots__ = (
        "__store_id",
        "__name",
        "__status",
        "__hourly_rate",
        "__is_active",
        "__updated_at",
    )

    def __init__(
        self,
        id: int,
        code: str,
        store_id: int,
        name: str,
        status: MachineStatus,
        hourly_rate: int,
        is_active: bool,
        updated_at: datetime,
    ) -> None:
        super().__init__(id, code)
        self.__store_id = store_id
        self.__name = name
        self.__status = status
        self.__hourly_rate = hourly_rate
        self.__is_active = is_active
        self.__updated_at = updated_at
        self.validate()

    @property
    def store_id(self) -> int:
        return self.__store_id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def status(self) -> MachineStatus:
        return self.__status

    @property
    def hourly_rate(self) -> int:
        return self.__hourly_rate

    @property
    def is_active(self) -> bool:
        return self.__is_active

    @property
    def updated_at(self) -> datetime:
        return self.__updated_at

    def get_store_id(self) -> int:
        return self.__store_id

    def get_name(self) -> str:
        return self.__name

    def get_status(self) -> MachineStatus:
        return self.__status

    def get_hourly_rate(self) -> int:
        return self.__hourly_rate

    def is_available(self) -> bool:
        return (
            self.__is_active
            and self.__status == MachineStatus.AVAILABLE
        )

    def update_info(self, name: str, hourly_rate: int) -> None:
        new_name = _require_non_blank(name, "name", "Tên máy")
        _require_positive_amount(hourly_rate, "hourly_rate", "Đơn giá")
        self.__name = new_name
        self.__hourly_rate = hourly_rate

    def start_session(self) -> None:
        if not self.__is_active:
            raise ConflictError("Máy đã ngừng sử dụng")
        if self.__status != MachineStatus.AVAILABLE:
            raise ConflictError("Máy không ở trạng thái sẵn sàng")
        self.__status = MachineStatus.IN_USE

    def finish_session(self) -> None:
        if self.__status != MachineStatus.IN_USE:
            raise ConflictError("Máy không có phiên đang hoạt động")
        self.__status = MachineStatus.AVAILABLE

    def set_maintenance(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValidationError(
                field_errors={"enabled": "Giá trị bảo trì không hợp lệ"}
            )
        if self.__status == MachineStatus.IN_USE:
            raise ConflictError("Không thể bảo trì máy đang được sử dụng")
        if not self.__is_active:
            raise ConflictError("Không thể thay đổi máy đã ngừng sử dụng")
        self.__status = (
            MachineStatus.MAINTENANCE
            if enabled
            else MachineStatus.AVAILABLE
        )

    def archive(self) -> None:
        if self.__status == MachineStatus.IN_USE:
            raise ConflictError("Không thể ngừng sử dụng máy đang có phiên")
        self.__is_active = False

    def validate(self) -> None:
        _require_positive_id(self.__store_id, "store_id")
        self.__name = _require_non_blank(self.__name, "name", "Tên máy")
        if not isinstance(self.__status, MachineStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái máy không hợp lệ"}
            )
        _require_positive_amount(
            self.__hourly_rate, "hourly_rate", "Đơn giá"
        )
        if not isinstance(self.__is_active, bool):
            raise ValidationError(
                field_errors={"is_active": "Trạng thái sử dụng không hợp lệ"}
            )
        if not self.__is_active and self.__status == MachineStatus.IN_USE:
            raise ValidationError(
                field_errors={
                    "is_active": "Máy đã ngừng sử dụng không thể ở trạng thái IN_USE"
                }
            )
        _require_datetime(self.__updated_at, "updated_at")
