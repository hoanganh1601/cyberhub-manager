"""LI-04 — Linh: WalletService nạp tiền và xem lịch sử giao dịch.

Service chỉ làm việc qua repository và database.transaction.transaction();
UI không gọi repository hay SQL trực tiếp.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone
from cyberhub_manager.domain.p1 import quote_top_up
from cyberhub_manager.domain.loyalty import personalized
from cyberhub_manager.repositories.p1_repository import P1Repository
from cyberhub_manager.services.access import operating_actor

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import (
    EmployeeSession,
    TopUpResult,
    TransactionSummary,
)
from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.domain.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.models import Customer
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.services.db_errors import retry_on_transient, translate_db_errors


MAX_TOP_UP_AMOUNT = 100_000_000
TOP_UP_METHODS = frozenset({PaymentMethod.CASH, PaymentMethod.TRANSFER})

# "TX-" + 17 ký tự hex = 20 ký tự, vừa cột account_transactions.code VARCHAR(20).
TRANSACTION_CODE_PREFIX = "TX-"
TRANSACTION_CODE_HEX_LENGTH = 17


# Trả phiên đăng nhập hiện tại; None nghĩa là chưa đăng nhập.
ActorProvider = Callable[[], EmployeeSession | None]


def new_transaction_code() -> str:
    return TRANSACTION_CODE_PREFIX + uuid4().hex[:TRANSACTION_CODE_HEX_LENGTH]

def _is_positive_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _amount_error(amount: object) -> str | None:
    # bool là lớp con của int nên phải loại riêng: True không phải 1 VND.
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        return "Số tiền nạp phải là số nguyên lớn hơn 0"
    if amount > MAX_TOP_UP_AMOUNT:
        return "Số tiền nạp không được vượt quá 100.000.000"
    return None


def _method_error(method: object) -> str | None:
    if (
        not isinstance(method, PaymentMethod)
        or method not in TOP_UP_METHODS
    ):
        return "Phương thức chỉ được là tiền mặt hoặc chuyển khoản"
    return None


def _validate_top_up(amount: object, method: object) -> None:
    """Gom mọi lỗi trường vào một ValidationError để UI đánh dấu cùng lúc."""

    errors = {
        "amount": _amount_error(amount),
        "method": _method_error(method),
    }
    field_errors = {field: message for field, message in errors.items() if message}
    if field_errors:
        raise ValidationError(field_errors=field_errors)


class WalletService:
    """Triển khai WalletServiceProtocol trên MySQL."""

    def __init__(
        self,
        customer_repo: CustomerRepository | None = None,
        account_repo: AccountRepository | None = None,
        auth_repo: AuthRepository | None = None,
        actor_provider: ActorProvider | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
        promotion_repo=None,
        clock=None,
    ) -> None:
        self._customers = customer_repo or CustomerRepository()
        self._accounts = account_repo or AccountRepository()
        self._auth = auth_repo or AuthRepository()
        # Không có provider thì không có phiên đăng nhập, mọi thao tác bị từ chối.
        self._actor_provider = actor_provider
        self._transaction = transaction_factory
        self._promotions = promotion_repo or P1Repository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def preview_top_up(self, customer_id, amount, employee_id):
        with translate_db_errors(), self._transaction() as conn:
            actor = self._require_actor(conn,employee_id)
            customer=self._get_customer(conn,customer_id)
            return self._customer_quote(conn,customer,amount,actor.store_id)

    def _customer_quote(self,conn,customer,amount,store_id):
        policies=self._promotions.list_promotions(conn,store_id,lock='share')
        if str(customer.status)!='ACTIVE' or str(customer.account.status)!='ACTIVE':
            policies=[p for p in policies if not personalized(p)]
        member=self._promotions.loyalty_summary(conn,customer.id,current=True) if any(personalized(p) for p in policies) else None
        return quote_top_up(amount,policies,store_id,self._clock(),customer_id=customer.id,member=member)

    @retry_on_transient
    def top_up(
        self,
        customer_id: int,
        amount: int,
        method: PaymentMethod,
        employee_id: int,
    ) -> TopUpResult:
        _validate_top_up(amount, method)

        if not _is_positive_id(employee_id):
            raise PermissionDeniedError()

        # employee_id không tồn tại vi phạm FK fk_account_transactions_employee => từ chối quyền.
        with translate_db_errors(on_foreign_key=PermissionDeniedError):
            with self._transaction() as conn:
                # Xác thực actor trước khi đọc khách hay đụng tới số dư.
                actor = self._require_actor(conn, employee_id)
                customer = self._get_customer(conn, customer_id)

                # Khóa dòng account trước khi đọc số dư để hai lần nạp đồng
                # thời không ghi đè nhau. Account LOCKED vẫn được nạp để trả nợ.
                account = self._accounts.get_by_id(
                    conn, customer.account.id, for_update=True
                )
                if account is None:
                    raise NotFoundError("Không tìm thấy tài khoản của khách hàng")
                balance_before = account.balance
                quote = self._customer_quote(conn,customer,amount,actor.store_id)
                bonus_transaction = None

                if not self._accounts.credit_balance(conn, account.id, amount):
                    raise NotFoundError("Không tìm thấy tài khoản của khách hàng")
                transaction_id = self._accounts.insert_top_up_transaction(
                    conn,
                    code=new_transaction_code(),
                    account_id=account.id,
                    employee_id=actor.employee_id,
                    amount=amount,
                    method=method,
                )
                summary = self._get_created_transaction(
                    conn, account.id, transaction_id
                )
                self._accounts.tag_transaction_store(conn,transaction_id,actor.store_id)
                if quote.bonus_amount:
                    if not self._accounts.credit_bonus(conn,account.id,quote.bonus_amount):
                        raise NotFoundError()
                    bonus_id = self._accounts.insert_bonus_transaction(conn,code=new_transaction_code(),account_id=account.id,
                        employee_id=actor.employee_id,amount=quote.bonus_amount,store_id=actor.store_id,promotion_id=quote.promotion.id)
                    bonus_transaction = self._get_created_transaction(conn,account.id,bonus_id)

        return TopUpResult(
            customer_id=customer.id,
            account_id=account.id,
            balance_before=balance_before,
            balance_after=balance_before + amount + quote.bonus_amount,
            transaction=summary,
            bonus_amount=quote.bonus_amount,
            bonus_balance_after=account.bonus_balance+quote.bonus_amount,
            bonus_transaction=bonus_transaction,
        )

    def get_history(self, customer_id: int) -> list[TransactionSummary]:
        with translate_db_errors():
            with self._transaction() as conn:
                self._require_actor(conn)
                customer = self._get_customer(conn, customer_id)
                return self._accounts.list_transactions(conn, customer.account.id)

    def _get_customer(self, conn: Any, customer_id: int) -> Customer:
        if _is_positive_id(customer_id):
            customer = self._customers.get_by_id(conn, customer_id)
            if customer is not None:
                return customer
        raise NotFoundError("Không tìm thấy khách hàng")

    def _require_actor(
        self, conn: Any, employee_id: int | None = None
    ) -> EmployeeSession:
        actor = self._actor_provider() if self._actor_provider else None
        if actor is None:
            raise PermissionDeniedError()
        if employee_id is not None and (
            not _is_positive_id(employee_id) or employee_id != actor.employee_id
        ):
            raise PermissionDeniedError()
        # Tra lại DB: nhân viên/cửa hàng có thể đã bị khóa hoặc nhân viên đã chuyển cửa hàng.
        current = operating_actor(conn,self._auth,actor)
        return current

    def _get_created_transaction(
        self, conn: Any, account_id: int, transaction_id: int
    ) -> TransactionSummary:
        # Dòng account đang bị khóa nên giao dịch mới nhất chính là giao dịch vừa ghi.
        latest = self._accounts.list_transactions(conn, account_id, limit=1)
        if not latest or latest[0].transaction_id != transaction_id:
            # Raise trong transaction để rollback cả số dư lẫn giao dịch.
            raise RuntimeError("Không đọc lại được giao dịch vừa tạo")
        return latest[0]
