"""Mock CustomerService: tạo, xem, tìm, sửa và đổi trạng thái khách."""

from __future__ import annotations

from cyberhub_manager.domain.dtos import CustomerSummary, EmployeeSession
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus
from cyberhub_manager.domain.exceptions import ConflictError, ValidationError
from cyberhub_manager.domain.models import Account, Customer

from .base import (
    MockServiceBase,
    clean_text,
    full_name_error,
    password_error,
    phone_error,
    raise_if_errors,
    username_error,
)
from .store import copy_customer

_PHONE_TAKEN = "Số điện thoại đã được sử dụng"
_USERNAME_TAKEN = "Tên đăng nhập đã được sử dụng"


class MockCustomerService(MockServiceBase):
    def create_customer(
        self,
        full_name: str,
        phone: str,
        username: str,
        password: str,
    ) -> Customer:
        self._check_scenario("create_customer")
        full_name = clean_text(full_name)
        phone = clean_text(phone)
        username = clean_text(username)
        raise_if_errors(
            {
                "full_name": full_name_error(full_name),
                "phone": phone_error(phone),
                "username": username_error(username),
                "password": password_error(password),
            }
        )
        conflicts = {}
        if self._data.is_phone_taken(phone):
            conflicts["phone"] = _PHONE_TAKEN
        if self._data.is_account_username_taken(username):
            conflicts["username"] = _USERNAME_TAKEN
        if conflicts:
            raise ConflictError(
                next(iter(conflicts.values())), field_errors=conflicts
            )

        # Mock chỉ kiểm tra password, không lưu; không có đường nào trả password ra.
        customer_id = self._data.next_id("customer")
        account_id = self._data.next_id("account")
        customer = Customer(
            id=customer_id,
            code=self._data.make_code("customer", customer_id),
            full_name=full_name,
            phone=phone,
            status=CustomerStatus.ACTIVE,
            account=Account(
                id=account_id,
                code=self._data.make_code("account", account_id),
                customer_id=customer_id,
                username=username,
                balance=0,
                status=AccountStatus.ACTIVE,
            ),
        )
        self._data.customers[customer_id] = customer
        return copy_customer(customer)

    def get_customer(self, customer_id: int) -> Customer:
        self._check_scenario("get_customer")
        return copy_customer(self._data.get_customer(customer_id))

    def search_customers(self, keyword: str) -> list[CustomerSummary]:
        self._check_scenario("search_customers")
        key = clean_text(keyword).casefold()
        matches = [
            customer
            for customer in self._data.customers.values()
            if not key
            or any(
                key in value.casefold()
                for value in (
                    customer.code,
                    customer.full_name,
                    customer.phone,
                    customer.account.username,
                )
            )
        ]
        matches.sort(key=lambda customer: customer.code)
        return [self._data.to_customer_summary(c) for c in matches]

    def update_customer(
        self,
        customer_id: int,
        full_name: str,
        phone: str,
    ) -> Customer:
        self._check_scenario("update_customer")
        customer = self._data.get_customer(customer_id)
        full_name = clean_text(full_name)
        phone = clean_text(phone)
        raise_if_errors(
            {
                "full_name": full_name_error(full_name),
                "phone": phone_error(phone),
            }
        )
        if self._data.is_phone_taken(phone, exclude_customer_id=customer_id):
            raise ConflictError(_PHONE_TAKEN, field_errors={"phone": _PHONE_TAKEN})

        customer.update_profile(full_name, phone)
        return copy_customer(customer)

    def set_customer_status(
        self,
        customer_id: int,
        status: CustomerStatus,
        actor: EmployeeSession,
    ) -> Customer:
        self._require_manager(actor)
        self._check_scenario("set_customer_status")
        customer = self._data.get_customer(customer_id)
        if not isinstance(status, CustomerStatus):
            raise ValidationError(
                field_errors={"status": "Trạng thái khách hàng không hợp lệ"}
            )

        # Không tự kết thúc phiên đang chạy của khách.
        if status == CustomerStatus.ACTIVE:
            customer.activate()
        else:
            customer.deactivate()
        return copy_customer(customer)
