"""Mock WalletService: nạp tiền và xem lịch sử giao dịch."""

from __future__ import annotations

from cyberhub_manager.domain.dtos import TopUpResult, TransactionSummary
from cyberhub_manager.domain.enums import (
    EmployeeStatus,
    PaymentMethod,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import PermissionDeniedError

from .base import (
    MockServiceBase,
    cash_method_error,
    positive_int_error,
    raise_if_errors,
)

MAX_TOP_UP_AMOUNT = 100_000_000


class MockWalletService(MockServiceBase):
    def top_up(
        self,
        customer_id: int,
        amount: int,
        method: PaymentMethod,
        employee_id: int,
    ) -> TopUpResult:
        self._check_scenario("top_up")
        customer = self._data.get_customer(customer_id)
        raise_if_errors(
            {
                "amount": positive_int_error(
                    amount, "Số tiền nạp", maximum=MAX_TOP_UP_AMOUNT
                ),
                "method": cash_method_error(method),
            }
        )
        employee = self._data.employees.get(employee_id)
        if employee is None or employee.status != EmployeeStatus.ACTIVE:
            raise PermissionDeniedError()

        # Cho phép nạp cả khi tài khoản bị khóa để khách trả nợ (ví dụ KH004).
        account = customer.account
        balance_before = account.balance
        transaction = self._new_transaction(
            account_id=account.id,
            employee_id=employee.id,
            session_id=None,
            type=TransactionType.TOP_UP,
            amount=amount,
            method=method,
            at=self._clock.now(),
        )
        account.credit(amount)
        self._data.transactions[transaction.id] = transaction
        return TopUpResult(
            customer_id=customer.id,
            account_id=account.id,
            balance_before=balance_before,
            balance_after=account.balance,
            transaction=self._data.to_transaction_summary(transaction),
        )

    def get_history(self, customer_id: int) -> list[TransactionSummary]:
        self._check_scenario("get_history")
        account_id = self._data.get_customer(customer_id).account.id
        return [
            self._data.to_transaction_summary(transaction)
            for transaction in self._data.transactions_for_account(account_id)
        ]
