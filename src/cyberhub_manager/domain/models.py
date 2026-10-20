"""Các domain model giàu hành vi của CyberHub Manager.

Entity giữ trạng thái bằng thuộc tính private và chỉ cho phép thay đổi thông qua
các phương thức nghiệp vụ. Các property public duy trì contract đọc hiện có với
service, repository và UI.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime

from .enums import (
    AccountStatus,
    CustomerStatus,
    EmployeeStatus,
    InvoiceStatus,
    MachineStatus,
    PaymentMethod,
    Role,
    SessionStatus,
    StoreStatus,
    TransactionType,
)
from .exceptions import ConflictError, ValidationError


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
            and self.__role in {Role.MANAGER, Role.ADMIN}
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


class Account(Entity):
    __slots__ = ("__customer_id", "__username", "__balance", "__status")

    def __init__(
        self,
        id: int,
        code: str,
        customer_id: int,
        username: str,
        balance: int,
        status: AccountStatus,
    ) -> None:
        super().__init__(id, code)
        self.__customer_id = customer_id
        self.__username = username
        self.__balance = balance
        self.__status = status
        self.validate()

    @property
    def customer_id(self) -> int:
        return self.__customer_id

    @property
    def username(self) -> str:
        return self.__username

    @property
    def balance(self) -> int:
        return self.__balance

    @property
    def status(self) -> AccountStatus:
        return self.__status

    def get_customer_id(self) -> int:
        return self.__customer_id

    def get_username(self) -> str:
        return self.__username

    def get_balance(self) -> int:
        return self.__balance

    def get_status(self) -> AccountStatus:
        return self.__status

    def credit(self, amount: int) -> int:
        _require_positive_amount(amount, "amount", "Số tiền cộng")
        self.__balance += amount
        return self.__balance

    def debit(self, amount: int) -> int:
        """Trừ tiền và cho phép số dư âm khi phiên đang chạy."""

        _require_positive_amount(amount, "amount", "Số tiền trừ")
        self.__balance -= amount
        return self.__balance

    def lock(self) -> None:
        self.__status = AccountStatus.LOCKED

    def unlock(self) -> None:
        self.__status = AccountStatus.ACTIVE

    def has_minimum_balance(self, amount: int) -> bool:
        return (
            isinstance(amount, int)
            and not isinstance(amount, bool)
            and amount >= 0
            and self.__status == AccountStatus.ACTIVE
            and self.__balance >= amount
        )

    def validate(self) -> None:
        _require_positive_id(self.__customer_id, "customer_id")
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
        if not isinstance(self.__balance, int) or isinstance(
            self.__balance, bool
        ):
            raise ValidationError(
                field_errors={"balance": "Số dư phải là số nguyên"}
            )
        if not isinstance(self.__status, AccountStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái tài khoản không hợp lệ"}
            )


class Customer(Person):
    __slots__ = ("__phone", "__status", "__account")

    def __init__(
        self,
        id: int,
        code: str,
        full_name: str,
        phone: str,
        status: CustomerStatus,
        account: Account,
    ) -> None:
        super().__init__(id, code, full_name)
        self.__phone = phone
        self.__status = status
        self.__account = account
        self.validate()

    @property
    def phone(self) -> str:
        return self.__phone

    @property
    def status(self) -> CustomerStatus:
        return self.__status

    @property
    def account(self) -> Account:
        return self.__account

    def get_phone(self) -> str:
        return self.__phone

    def get_status(self) -> CustomerStatus:
        return self.__status

    def get_account(self) -> Account:
        return self.__account

    def update_profile(self, full_name: str, phone: str) -> None:
        new_name = self._validated_full_name(full_name)
        new_phone = self._validated_phone(phone)
        self.change_full_name(new_name)
        self.__phone = new_phone

    def activate(self) -> None:
        self.__status = CustomerStatus.ACTIVE
        self.__account.unlock()

    def deactivate(self) -> None:
        self.__status = CustomerStatus.INACTIVE
        self.__account.lock()

    def can_open_session(self) -> bool:
        return (
            self.__status == CustomerStatus.ACTIVE
            and self.__account.status == AccountStatus.ACTIVE
            and self.__account.balance >= 0
        )

    def validate(self) -> None:
        self.__phone = self._validated_phone(self.__phone)
        if not isinstance(self.__status, CustomerStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái khách hàng không hợp lệ"}
            )
        if not isinstance(self.__account, Account):
            raise ValidationError(
                field_errors={"account": "Tài khoản khách hàng không hợp lệ"}
            )
        if self.__account.customer_id != self.id:
            raise ValidationError(
                field_errors={
                    "account": "Tài khoản không thuộc khách hàng này"
                }
            )

    @staticmethod
    def _validated_phone(phone: str) -> str:
        normalized = phone.strip() if isinstance(phone, str) else ""
        if re.fullmatch(r"0[0-9]{9}", normalized) is None:
            raise ValidationError(
                field_errors={
                    "phone": "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0"
                }
            )
        return normalized


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
