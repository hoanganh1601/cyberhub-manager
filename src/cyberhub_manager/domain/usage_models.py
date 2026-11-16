"""Usage-session domain model and live cost estimation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import SessionStatus
from .exceptions import ConflictError, ValidationError
from .model_base import (
    Entity,
    _require_datetime,
    _require_positive_amount,
    _require_positive_id,
)

# SES-01: s? d? t?i thi?u ?? ch?i 30 ph?t.
MINIMUM_SESSION_MINUTES = 30


def minimum_balance(hourly_rate: int) -> int:
    """Số dư tối thiểu đủ chơi MINIMUM_SESSION_MINUTES phút, làm tròn lên."""

    return (MINIMUM_SESSION_MINUTES * hourly_rate + 59) // 60

def estimate_play_minutes(balance: int, hourly_rate: int) -> int:
    """SES-04: floor(số dư × 60 / đơn giá giờ); số dư âm thì 0 phút."""

    return max(0, balance * 60 // hourly_rate)

class UsageSession(Entity):
    __slots__ = (
        "__customer_id",
        "__machine_id",
        "__opened_by",
        "__closed_by",
        "__started_at",
        "__ended_at",
        "__hourly_rate",
        "__cost",
        "__status",
    )

    def __init__(
        self,
        id: int,
        code: str,
        customer_id: int,
        machine_id: int,
        opened_by: int,
        closed_by: int | None,
        started_at: datetime,
        ended_at: datetime | None,
        hourly_rate: int,
        cost: int | None,
        status: SessionStatus,
    ) -> None:
        super().__init__(id, code)
        self.__customer_id = customer_id
        self.__machine_id = machine_id
        self.__opened_by = opened_by
        self.__closed_by = closed_by
        self.__started_at = started_at
        self.__ended_at = ended_at
        self.__hourly_rate = hourly_rate
        self.__cost = cost
        self.__status = status
        self.validate()

    @property
    def customer_id(self) -> int:
        return self.__customer_id

    @property
    def machine_id(self) -> int:
        return self.__machine_id

    @property
    def opened_by(self) -> int:
        return self.__opened_by

    @property
    def closed_by(self) -> int | None:
        return self.__closed_by

    @property
    def started_at(self) -> datetime:
        return self.__started_at

    @property
    def ended_at(self) -> datetime | None:
        return self.__ended_at

    @property
    def hourly_rate(self) -> int:
        return self.__hourly_rate

    @property
    def cost(self) -> int | None:
        return self.__cost

    @property
    def status(self) -> SessionStatus:
        return self.__status

    def is_active(self) -> bool:
        return self.__status == SessionStatus.ACTIVE

    def elapsed_seconds(self, at: datetime) -> int:
        _require_datetime(at, "current_time")
        if at < self.__started_at:
            raise ValidationError(
                field_errors={
                    "current_time": "Thời gian tính không được trước lúc bắt đầu"
                }
            )
        return int((at - self.__started_at).total_seconds())

    def calculate_billed_minutes(self, at: datetime) -> int:
        seconds = self.elapsed_seconds(at)
        return max(1, (seconds + 59) // 60)

    def calculate_cost(self, at: datetime) -> int:
        minutes = self.calculate_billed_minutes(at)
        return (minutes * self.__hourly_rate + 59) // 60

    def complete(self, employee_id: int, ended_at: datetime) -> int:
        if not self.is_active():
            raise ConflictError("Phiên sử dụng không còn hoạt động")
        _require_positive_id(employee_id, "employee_id")
        calculated_cost = self.calculate_cost(ended_at)
        self.__closed_by = employee_id
        self.__ended_at = ended_at
        self.__cost = calculated_cost
        self.__status = SessionStatus.COMPLETED
        return calculated_cost

    def cancel(self, employee_id: int, ended_at: datetime) -> None:
        if not self.is_active():
            raise ConflictError("Phiên sử dụng không còn hoạt động")
        _require_positive_id(employee_id, "employee_id")
        self.elapsed_seconds(ended_at)
        self.__closed_by = employee_id
        self.__ended_at = ended_at
        self.__status = SessionStatus.CANCELLED

    def validate(self) -> None:
        _require_positive_id(self.__customer_id, "customer_id")
        _require_positive_id(self.__machine_id, "machine_id")
        _require_positive_id(self.__opened_by, "opened_by")
        if self.__closed_by is not None:
            _require_positive_id(self.__closed_by, "closed_by")
        _require_datetime(self.__started_at, "started_at")
        if self.__ended_at is not None:
            _require_datetime(self.__ended_at, "ended_at")
            if self.__ended_at < self.__started_at:
                raise ValidationError(
                    field_errors={
                        "ended_at": "Thời gian kết thúc không được trước lúc bắt đầu"
                    }
                )
        _require_positive_amount(
            self.__hourly_rate, "hourly_rate", "Đơn giá"
        )
        if self.__cost is not None and (
            not isinstance(self.__cost, int)
            or isinstance(self.__cost, bool)
            or self.__cost < 0
        ):
            raise ValidationError(
                field_errors={"cost": "Chi phí phải là số nguyên không âm"}
            )
        if not isinstance(self.__status, SessionStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái phiên không hợp lệ"}
            )
        if self.__status == SessionStatus.ACTIVE and (
            self.__ended_at is not None
            or self.__cost is not None
            or self.__closed_by is not None
        ):
            raise ValidationError(
                field_errors={"status": "Phiên ACTIVE chưa được có dữ liệu kết thúc"}
            )
        if self.__status == SessionStatus.COMPLETED and (
            self.__ended_at is None
            or self.__cost is None
            or self.__closed_by is None
        ):
            raise ValidationError(
                field_errors={"status": "Phiên COMPLETED thiếu dữ liệu kết thúc"}
            )
        if self.__status == SessionStatus.CANCELLED and self.__ended_at is None:
            raise ValidationError(
                field_errors={"status": "Phiên CANCELLED phải có thời gian kết thúc"}
            )

@dataclass(frozen=True)
class LiveEstimate:
    """Tạm tính của phiên đang chạy tại một thời điểm (SES-05)."""

    as_of: datetime
    elapsed_seconds: int
    estimated_cost: int
    projected_balance: int

def estimate_live_usage(
    session: UsageSession, balance: int, now: datetime
) -> LiveEstimate:
    """Dùng cùng công thức SES-07 với checkout; projected_balance < 0 là cảnh báo SES-06."""

    # Đồng hồ máy app có thể lệch vài giây so với started_at; không để thời gian âm.
    at = max(now, session.started_at)
    cost = session.calculate_cost(at)
    return LiveEstimate(
        as_of=at,
        elapsed_seconds=session.elapsed_seconds(at),
        estimated_cost=cost,
        projected_balance=balance - cost,
    )
