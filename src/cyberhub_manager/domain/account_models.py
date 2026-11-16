"""Customer account and profile domain entities."""

from __future__ import annotations

import re

from .enums import AccountStatus, CustomerStatus
from .exceptions import ValidationError
from .model_base import (
    Entity,
    Person,
    _require_non_blank,
    _require_positive_amount,
    _require_positive_id,
)


class Account(Entity):
    __slots__ = ("__customer_id", "__username", "__balance", "__status", "__bonus_balance")

    def __init__(
        self,
        id: int,
        code: str,
        customer_id: int,
        username: str,
        balance: int,
        status: AccountStatus,
        bonus_balance: int = 0,
    ) -> None:
        super().__init__(id, code)
        self.__customer_id = customer_id
        self.__username = username
        self.__balance = balance
        self.__status = status
        self.__bonus_balance = bonus_balance
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

    @property
    def bonus_balance(self) -> int:
        return self.__bonus_balance

    @property
    def cash_balance(self) -> int:
        return self.__balance - self.__bonus_balance

    def credit_bonus(self, amount: int) -> int:
        _require_positive_amount(amount, "amount", "Tiền khuyến mãi")
        self.__bonus_balance += amount
        self.__balance += amount
        return self.__balance

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
        self.__bonus_balance = max(0, self.__bonus_balance - amount)
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
        if type(self.__bonus_balance) is not int or self.__bonus_balance < 0:
            raise ValidationError(field_errors={"bonus_balance": "Tiền khuyến mãi không được âm"})
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
