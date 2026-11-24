"""Shared identity and validation primitives for domain entities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from cyberhub_manager.domain.exceptions import ValidationError


def _require_positive_id(value: int, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError(
            field_errors={field: "ID phải là số nguyên dương"}
        )

def _require_non_blank(value: str, field: str, label: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValidationError(
            field_errors={field: f"{label} không được để trống"}
        )
    return normalized

def _require_positive_amount(value: int, field: str, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError(
            field_errors={field: f"{label} phải là số nguyên lớn hơn 0"}
        )

def _require_datetime(value: datetime, field: str) -> None:
    if not isinstance(value, datetime):
        raise ValidationError(
            field_errors={field: "Thời gian không hợp lệ"}
        )

class Entity(ABC):
    """Lớp trừu tượng cho entity có định danh và mã nghiệp vụ."""

    __slots__ = ("__id", "__code")

    def __init__(self, id: int, code: str) -> None:
        _require_positive_id(id, "id")
        self.__id = id
        self.__code = _require_non_blank(code, "code", "Mã")

    @property
    def id(self) -> int:
        return self.__id

    @property
    def code(self) -> str:
        return self.__code

    def get_id(self) -> int:
        return self.__id

    def get_code(self) -> str:
        return self.__code

    @abstractmethod
    def validate(self) -> None:
        """Kiểm tra invariant riêng của từng entity."""

class Person(Entity, ABC):
    """Lớp trừu tượng dùng chung cho nhân viên và khách hàng."""

    __slots__ = ("__full_name",)

    def __init__(self, id: int, code: str, full_name: str) -> None:
        super().__init__(id, code)
        self.__full_name = self._validated_full_name(full_name)

    @property
    def full_name(self) -> str:
        return self.__full_name

    def get_full_name(self) -> str:
        return self.__full_name

    def change_full_name(self, full_name: str) -> None:
        self.__full_name = self._validated_full_name(full_name)

    @staticmethod
    def _validated_full_name(full_name: str) -> str:
        normalized = _require_non_blank(
            full_name, "full_name", "Họ tên"
        )
        if not 2 <= len(normalized) <= 100:
            raise ValidationError(
                field_errors={
                    "full_name": "Họ tên phải có từ 2 đến 100 ký tự"
                }
            )
        return normalized
