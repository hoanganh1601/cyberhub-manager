"""Mock SessionService: xem trước/mở phiên và xem trước/hoàn tất checkout.

Phí dùng lại công thức của UsageSession (SES-07); số dư tối thiểu đủ 30 phút
(SES-01); số phút ước tính theo SES-04. Mock không mô phỏng locking SQL.
"""

from __future__ import annotations

from datetime import datetime

from cyberhub_manager.domain.dtos import (
    CheckoutPreview,
    CheckoutResult,
    EmployeeSession,
    OpenSessionPreview,
    SessionSummary,
)
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    PaymentMethod,
    SessionStatus,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    InsufficientBalanceError,
    SettlementRequiredError,
    ValidationError,
)
from cyberhub_manager.domain.models import (
    Customer,
    Invoice,
    Machine,
    UsageSession,
)

from .base import MockServiceBase, cash_method_error, raise_if_errors

MINIMUM_SESSION_MINUTES = 30


def minimum_balance(hourly_rate: int) -> int:
    """Số dư tối thiểu đủ chơi MINIMUM_SESSION_MINUTES phút, làm tròn lên."""

    return (MINIMUM_SESSION_MINUTES * hourly_rate + 59) // 60


def _conflict(field: str, message: str) -> ConflictError:
    return ConflictError(message, field_errors={field: message})


class MockSessionService(MockServiceBase):
    def preview_open(
        self,
        customer_id: int,
        machine_id: int,
        actor: EmployeeSession,
    ) -> OpenSessionPreview:
        self._require_actor(actor)
        self._check_scenario("preview_open")
        customer, machine = self._check_can_open(customer_id, machine_id, actor)
        balance = customer.account.balance
        rate = machine.hourly_rate
        required = minimum_balance(rate)
        can_open = balance >= required
        return OpenSessionPreview(
            customer_id=customer.id,
            machine_id=machine.id,
            balance=balance,
            hourly_rate=rate,
            minimum_balance=required,
            estimated_minutes=max(0, balance * 60 // rate),
            can_open=can_open,
            blocked_reason=(
                None
                if can_open
                else f"Số dư chưa đủ cho {MINIMUM_SESSION_MINUTES} phút sử dụng"
            ),
            as_of=self._clock.now(),
        )

    def open_session(
        self,
        customer_id: int,
        machine_id: int,
        actor: EmployeeSession,
    ) -> SessionSummary:
        employee = self._require_actor(actor)
        self._check_scenario("open_session")
        customer, machine = self._check_can_open(customer_id, machine_id, actor)
        balance = customer.account.balance
        required = minimum_balance(machine.hourly_rate)
        if balance < required:
            raise InsufficientBalanceError(
                details={
                    "balance": balance,
                    "minimum_balance": required,
                    "required_top_up": required - balance,
                }
            )

        now = self._clock.now()
        session_id = self._data.next_id("session")
        session = UsageSession(
            id=session_id,
            code=self._data.make_code("session", session_id),
            customer_id=customer.id,
            machine_id=machine.id,
            opened_by=employee.id,
            closed_by=None,
            started_at=now,
            ended_at=None,
            hourly_rate=machine.hourly_rate,
            cost=None,
            status=SessionStatus.ACTIVE,
        )
        machine.start_session()
        self._data.touch_machine(machine.id, now)
        self._data.sessions[session_id] = session
        return self._data.to_session_summary(session)

    def preview_checkout(
        self,
        machine_id: int,
        current_time: datetime,
    ) -> CheckoutPreview:
        self._check_scenario("preview_checkout")
        if not isinstance(current_time, datetime) or current_time.tzinfo is None:
            raise ValidationError(
                field_errors={"current_time": "Thời gian tính phí phải có timezone"}
            )
        session = self._active_session_on(machine_id)
        return self._build_checkout_preview(session, current_time)

    def complete_checkout(
        self,
        machine_id: int,
        actor: EmployeeSession,
        settlement_amount: int,
        method: PaymentMethod | None,
    ) -> CheckoutResult:
        employee = self._require_actor(actor)
        self._check_scenario("complete_checkout")
        machine = self._data.get_machine(machine_id)
        self._require_store(actor, machine.store_id)
        session = self._active_session_on(machine_id)
        self._validate_settlement_input(settlement_amount, method)

        # Tính lại tại thời điểm hoàn tất; preview trước đó chỉ là ước tính.
        now = self._clock.now()
        preview = self._build_checkout_preview(session, now)
        if settlement_amount < preview.settlement_required:
            message = "Tiền bù chưa đủ để số dư không âm"
            raise SettlementRequiredError(
                field_errors={"settlement_amount": message},
                details={
                    "settlement_required": preview.settlement_required,
                    "usage_cost": preview.usage_cost,
                    "balance_before": preview.balance_before,
                },
            )
        if settlement_amount > preview.usage_cost:
            raise ValidationError(
                field_errors={
                    "settlement_amount": "Tiền bù không được lớn hơn phí sử dụng"
                }
            )

        # Dựng mọi bản ghi mới trước; chỉ thay đổi kho khi tất cả đã hợp lệ.
        account = self._data.get_customer(session.customer_id).account
        cost = preview.usage_cost
        new_transactions = []
        if settlement_amount:
            new_transactions.append(
                self._new_transaction(
                    account.id,
                    employee.id,
                    session.id,
                    TransactionType.DEBT_SETTLEMENT,
                    settlement_amount,
                    method,
                    now,
                )
            )
        new_transactions.append(
            self._new_transaction(
                account.id,
                employee.id,
                session.id,
                TransactionType.USAGE_PAYMENT,
                -cost,
                PaymentMethod.ACCOUNT_BALANCE,
                now,
            )
        )
        invoice_id = self._data.next_id("invoice")
        invoice = Invoice(
            id=invoice_id,
            code=self._data.make_code("invoice", invoice_id),
            session_id=session.id,
            customer_id=session.customer_id,
            employee_id=employee.id,
            store_id=machine.store_id,
            usage_cost=cost,
            settlement_amount=settlement_amount,
            total_amount=cost,
            status=InvoiceStatus.PAID,
            created_at=now,
        )

        session.complete(employee.id, now)
        machine.finish_session()
        self._data.touch_machine(machine.id, now)
        if settlement_amount:
            account.credit(settlement_amount)
        account.debit(cost)
        for transaction in new_transactions:
            self._data.transactions[transaction.id] = transaction
        self._data.invoices[invoice_id] = invoice
        return CheckoutResult(
            invoice=self._data.to_invoice_detail(invoice),
            balance_after=account.balance,
        )

    # ----- Nội bộ --------------------------------------------------------

    def _check_can_open(
        self,
        customer_id: int,
        machine_id: int,
        actor: EmployeeSession,
    ) -> tuple[Customer, Machine]:
        """Mọi điều kiện mở phiên trừ số dư; vi phạm thì raise exception."""

        customer = self._data.get_customer(customer_id)
        machine = self._data.get_machine(machine_id)
        self._require_store(actor, machine.store_id)
        if customer.status != CustomerStatus.ACTIVE:
            raise _conflict("customer_id", "Khách hàng đã ngừng hoạt động")
        if customer.account.status != AccountStatus.ACTIVE:
            raise _conflict("customer_id", "Tài khoản khách hàng đã bị khóa")
        if self._data.active_session_for_customer(customer.id) is not None:
            raise _conflict("customer_id", "Khách hàng đang có phiên khác")
        if not machine.is_active:
            raise _conflict("machine_id", "Máy đã ngừng sử dụng")
        if machine.status == MachineStatus.MAINTENANCE:
            raise _conflict("machine_id", "Máy đang bảo trì")
        if machine.status == MachineStatus.IN_USE:
            raise _conflict("machine_id", "Máy đang được sử dụng")
        return customer, machine

    def _active_session_on(self, machine_id: int) -> UsageSession:
        self._data.get_machine(machine_id)
        session = self._data.active_session_for_machine(machine_id)
        if session is None:
            raise _conflict("machine_id", "Máy không có phiên đang hoạt động")
        return session

    def _build_checkout_preview(
        self, session: UsageSession, at: datetime
    ) -> CheckoutPreview:
        balance = self._data.get_customer(session.customer_id).account.balance
        cost = session.calculate_cost(at)
        projected = balance - cost
        return CheckoutPreview(
            session=self._data.to_session_summary(session),
            calculated_at=at,
            elapsed_seconds=session.elapsed_seconds(at),
            billed_minutes=session.calculate_billed_minutes(at),
            usage_cost=cost,
            balance_before=balance,
            projected_balance=projected,
            settlement_required=max(0, -projected),
        )

    @staticmethod
    def _validate_settlement_input(
        settlement_amount: int, method: PaymentMethod | None
    ) -> None:
        if (
            not isinstance(settlement_amount, int)
            or isinstance(settlement_amount, bool)
            or settlement_amount < 0
        ):
            raise_if_errors(
                {"settlement_amount": "Tiền bù phải là số nguyên không âm"}
            )
        if settlement_amount > 0:
            method_error = cash_method_error(method)
        elif method is not None:
            method_error = "Không chọn phương thức khi không có tiền bù"
        else:
            method_error = None
        raise_if_errors({"method": method_error})
