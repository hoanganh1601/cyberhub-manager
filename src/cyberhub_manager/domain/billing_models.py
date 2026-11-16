"""Wallet transaction and invoice domain entities."""

from __future__ import annotations

from datetime import datetime

from .enums import InvoiceStatus, PaymentMethod, TransactionType
from .exceptions import ConflictError, ValidationError
from .model_base import Entity, _require_datetime, _require_positive_id


class AccountTransaction(Entity):
    __slots__ = (
        "__account_id",
        "__employee_id",
        "__session_id",
        "__type",
        "__amount",
        "__method",
        "__created_at",
    )

    def __init__(
        self,
        id: int,
        code: str,
        account_id: int,
        employee_id: int,
        session_id: int | None,
        type: TransactionType,
        amount: int,
        method: PaymentMethod,
        created_at: datetime,
    ) -> None:
        super().__init__(id, code)
        self.__account_id = account_id
        self.__employee_id = employee_id
        self.__session_id = session_id
        self.__type = type
        self.__amount = amount
        self.__method = method
        self.__created_at = created_at
        self.validate()

    @property
    def account_id(self) -> int:
        return self.__account_id

    @property
    def employee_id(self) -> int:
        return self.__employee_id

    @property
    def session_id(self) -> int | None:
        return self.__session_id

    @property
    def type(self) -> TransactionType:
        return self.__type

    @property
    def amount(self) -> int:
        return self.__amount

    @property
    def method(self) -> PaymentMethod:
        return self.__method

    @property
    def created_at(self) -> datetime:
        return self.__created_at

    def get_amount(self) -> int:
        return self.__amount

    def get_type(self) -> TransactionType:
        return self.__type

    def is_credit(self) -> bool:
        return self.__amount > 0

    def is_debit(self) -> bool:
        return self.__amount < 0

    def validate(self) -> None:
        _require_positive_id(self.__account_id, "account_id")
        _require_positive_id(self.__employee_id, "employee_id")
        if self.__session_id is not None:
            _require_positive_id(self.__session_id, "session_id")
        if not isinstance(self.__type, TransactionType):
            raise ValidationError(
                field_errors={"type": "Loại giao dịch không hợp lệ"}
            )
        if (
            not isinstance(self.__amount, int)
            or isinstance(self.__amount, bool)
            or self.__amount == 0
        ):
            raise ValidationError(
                field_errors={"amount": "Số tiền giao dịch phải khác 0"}
            )
        if not isinstance(self.__method, PaymentMethod):
            raise ValidationError(
                field_errors={"method": "Phương thức thanh toán không hợp lệ"}
            )
        credit_types = {
            TransactionType.TOP_UP,
            TransactionType.PROMOTION,
            TransactionType.DEBT_SETTLEMENT,
        }
        if self.__type in credit_types and self.__amount <= 0:
            raise ValidationError(
                field_errors={"amount": "Giao dịch cộng tiền phải có số tiền dương"}
            )
        if (
            self.__type == TransactionType.USAGE_PAYMENT
            and self.__amount >= 0
        ):
            raise ValidationError(
                field_errors={"amount": "Giao dịch sử dụng phải có số tiền âm"}
            )
        allowed_methods = {
            TransactionType.TOP_UP: {
                PaymentMethod.CASH,
                PaymentMethod.TRANSFER,
            },
            TransactionType.DEBT_SETTLEMENT: {
                PaymentMethod.CASH,
                PaymentMethod.TRANSFER,
            },
            TransactionType.USAGE_PAYMENT: {
                PaymentMethod.ACCOUNT_BALANCE
            },
            TransactionType.PROMOTION: {PaymentMethod.PROMOTION},
        }
        if self.__method not in allowed_methods[self.__type]:
            raise ValidationError(
                field_errors={
                    "method": "Phương thức không phù hợp với loại giao dịch"
                }
            )
        _require_datetime(self.__created_at, "created_at")

class Invoice(Entity):
    __slots__ = (
        "__session_id",
        "__customer_id",
        "__employee_id",
        "__store_id",
        "__usage_cost",
        "__settlement_amount",
        "__total_amount",
        "__status",
        "__created_at",
    )

    def __init__(
        self,
        id: int,
        code: str,
        session_id: int,
        customer_id: int,
        employee_id: int,
        store_id: int,
        usage_cost: int,
        settlement_amount: int,
        total_amount: int,
        status: InvoiceStatus,
        created_at: datetime,
    ) -> None:
        super().__init__(id, code)
        self.__session_id = session_id
        self.__customer_id = customer_id
        self.__employee_id = employee_id
        self.__store_id = store_id
        self.__usage_cost = usage_cost
        self.__settlement_amount = settlement_amount
        self.__total_amount = total_amount
        self.__status = status
        self.__created_at = created_at
        self.validate()

    @property
    def session_id(self) -> int:
        return self.__session_id

    @property
    def customer_id(self) -> int:
        return self.__customer_id

    @property
    def employee_id(self) -> int:
        return self.__employee_id

    @property
    def store_id(self) -> int:
        return self.__store_id

    @property
    def usage_cost(self) -> int:
        return self.__usage_cost

    @property
    def settlement_amount(self) -> int:
        return self.__settlement_amount

    @property
    def total_amount(self) -> int:
        return self.__total_amount

    @property
    def status(self) -> InvoiceStatus:
        return self.__status

    @property
    def created_at(self) -> datetime:
        return self.__created_at

    def get_total_amount(self) -> int:
        return self.__total_amount

    def get_status(self) -> InvoiceStatus:
        return self.__status

    def is_paid(self) -> bool:
        return self.__status == InvoiceStatus.PAID

    def void(self) -> None:
        if self.__status == InvoiceStatus.VOID:
            raise ConflictError("Hóa đơn đã bị hủy")
        self.__status = InvoiceStatus.VOID

    def validate(self) -> None:
        _require_positive_id(self.__session_id, "session_id")
        _require_positive_id(self.__customer_id, "customer_id")
        _require_positive_id(self.__employee_id, "employee_id")
        _require_positive_id(self.__store_id, "store_id")
        money_fields = {
            "usage_cost": self.__usage_cost,
            "settlement_amount": self.__settlement_amount,
            "total_amount": self.__total_amount,
        }
        for field, value in money_fields.items():
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValidationError(
                    field_errors={field: "Giá trị tiền phải là số nguyên không âm"}
                )
        if self.__settlement_amount > self.__usage_cost:
            raise ValidationError(
                field_errors={
                    "settlement_amount": "Tiền bù không được lớn hơn phí sử dụng"
                }
            )
        if self.__total_amount != self.__usage_cost:
            raise ValidationError(
                field_errors={
                    "total_amount": "Tổng tiền phải bằng phí sử dụng"
                }
            )
        if not isinstance(self.__status, InvoiceStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái hóa đơn không hợp lệ"}
            )
        _require_datetime(self.__created_at, "created_at")
