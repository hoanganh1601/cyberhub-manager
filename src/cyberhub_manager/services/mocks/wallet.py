"""Mock WalletService: nạp tiền và xem lịch sử giao dịch."""

from __future__ import annotations

from cyberhub_manager.domain.dtos import TopUpResult, TransactionSummary
from cyberhub_manager.domain.enums import (
    EmployeeStatus,
    PaymentMethod,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.domain.p1 import quote_top_up
from cyberhub_manager.domain.loyalty import personalized

from .base import (
    MockServiceBase,
    cash_method_error,
    positive_int_error,
    raise_if_errors,
)

MAX_TOP_UP_AMOUNT = 100_000_000


class MockWalletService(MockServiceBase):
    def preview_top_up(self, customer_id, amount, employee_id):
        employee = self._data.get_employee(employee_id)
        customer=self._data.get_customer(customer_id)
        store_id = getattr(self._data,"operating_stores",{}).get(employee_id,employee.store_id)
        if employee.status!=EmployeeStatus.ACTIVE or str(self._data.get_store(store_id).status)!="ACTIVE":
            raise PermissionDeniedError()
        policies=list(self._data.promotions.values())
        if str(customer.status)!='ACTIVE' or str(customer.account.status)!='ACTIVE':
            policies=[p for p in policies if not personalized(p)]
        from .p1 import MemoryP1Repository
        member=MemoryP1Repository(self._data).loyalty_summary(None,customer.id) if any(personalized(p) for p in policies) else None
        return quote_top_up(amount,policies,store_id,self._clock.now(),customer_id=customer.id,member=member)

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
        quote = self.preview_top_up(customer_id,amount,employee_id)
        transaction = self._new_transaction(
            account_id=account.id,
            employee_id=employee.id,
            session_id=None,
            type=TransactionType.TOP_UP,
            amount=amount,
            method=method,
            at=self._clock.now(),
        )
        bonus_transaction = None
        bonus = None
        if quote.bonus_amount:
            bonus = self._new_transaction(account.id,employee.id,None,TransactionType.PROMOTION,
                                          quote.bonus_amount,PaymentMethod.PROMOTION,self._clock.now())
            bonus_transaction = self._data.to_transaction_summary(bonus)
        # Prepare both records before mutating the wallet.
        account.credit(amount)
        self._data.transactions[transaction.id] = transaction
        store_id = self._data.operating_stores.get(employee_id,employee.store_id)
        self._data.transaction_stores[transaction.id] = store_id
        if bonus:
            account.credit_bonus(quote.bonus_amount)
            self._data.transactions[bonus.id] = bonus
            self._data.transaction_stores[bonus.id] = store_id
        return TopUpResult(
            customer_id=customer.id,
            account_id=account.id,
            balance_before=balance_before,
            balance_after=account.balance,
            transaction=self._data.to_transaction_summary(transaction),
            bonus_amount=quote.bonus_amount,
            bonus_balance_after=account.bonus_balance,
            bonus_transaction=bonus_transaction,
        )

    def get_history(self, customer_id: int) -> list[TransactionSummary]:
        self._check_scenario("get_history")
        account_id = self._data.get_customer(customer_id).account.id
        return [
            self._data.to_transaction_summary(transaction)
            for transaction in self._data.transactions_for_account(account_id)
        ]
