"""Kho dữ liệu trong bộ nhớ dùng chung cho sáu mock service của một bundle.

Bản ghi nội bộ dùng lại entity LI-01. Dữ liệu trả ra ngoài luôn là DTO hoặc
bản sao entity để UI không thể thay đổi kho dữ liệu ngoài service.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from cyberhub_manager.domain.dtos import (
    ActiveSessionSummary,
    CustomerSummary,
    EmployeeSession,
    InvoiceDetail,
    InvoiceSummary,
    MachineSummary,
    SessionSummary,
    TransactionSummary,
)
from cyberhub_manager.domain.enums import MachineStatus
from cyberhub_manager.domain.exceptions import ConflictError, NotFoundError
from cyberhub_manager.domain.models import (
    Account,
    AccountTransaction,
    Customer,
    Employee,
    Invoice,
    Machine,
    Store,
    UsageSession,
)

VN_TZ = timezone(timedelta(hours=7))
"""Asia/Ho_Chi_Minh không có giờ mùa hè; tránh phụ thuộc gói tzdata trên Windows."""

_CODE_FORMATS: dict[str, tuple[str, int]] = {
    "store": ("CH", 2),
    "employee": ("NV", 3),
    "customer": ("KH", 3),
    "account": ("TK", 3),
    "machine": ("PC", 2),
    "session": ("PH", 4),
    "transaction": ("GD", 4),
    "invoice": ("HD", 4),
}


def local_date(value: datetime) -> date:
    """Ngày địa phương Việt Nam của một mốc UTC."""

    return value.astimezone(VN_TZ).date()


def copy_account(account: Account) -> Account:
    return Account(
        id=account.id,
        code=account.code,
        customer_id=account.customer_id,
        username=account.username,
        balance=account.balance,
        status=account.status,
    )


def copy_customer(customer: Customer) -> Customer:
    return Customer(
        id=customer.id,
        code=customer.code,
        full_name=customer.full_name,
        phone=customer.phone,
        status=customer.status,
        account=copy_account(customer.account),
    )


def copy_machine(
    machine: Machine, *, updated_at: datetime | None = None
) -> Machine:
    return Machine(
        id=machine.id,
        code=machine.code,
        store_id=machine.store_id,
        name=machine.name,
        status=machine.status,
        hourly_rate=machine.hourly_rate,
        is_active=machine.is_active,
        updated_at=updated_at or machine.updated_at,
    )


class MockDataStore:
    def __init__(self) -> None:
        self.stores: dict[int, Store] = {}
        self.employees: dict[int, Employee] = {}
        self.employee_passwords: dict[str, str] = {}
        self.customers: dict[int, Customer] = {}
        self.machines: dict[int, Machine] = {}
        self.sessions: dict[int, UsageSession] = {}
        self.transactions: dict[int, AccountTransaction] = {}
        self.invoices: dict[int, Invoice] = {}
        self._last_ids: dict[str, int] = {}

    # ----- Sinh id và mã -------------------------------------------------

    def next_id(self, kind: str) -> int:
        """Cấp id mới; chỉ gọi sau khi mọi kiểm tra của operation đã qua."""

        self._last_ids[kind] = self._last_ids.get(kind, 0) + 1
        return self._last_ids[kind]

    @staticmethod
    def make_code(kind: str, entity_id: int) -> str:
        prefix, width = _CODE_FORMATS[kind]
        return f"{prefix}{entity_id:0{width}d}"

    # ----- Tra cứu -------------------------------------------------------

    def get_store(self, store_id: int) -> Store:
        return self._get(self.stores, store_id, "Không tìm thấy cửa hàng")

    def get_employee(self, employee_id: int) -> Employee:
        return self._get(
            self.employees, employee_id, "Không tìm thấy nhân viên"
        )

    def get_customer(self, customer_id: int) -> Customer:
        return self._get(
            self.customers, customer_id, "Không tìm thấy khách hàng"
        )

    def get_machine(self, machine_id: int) -> Machine:
        return self._get(self.machines, machine_id, "Không tìm thấy máy")

    def get_session(self, session_id: int) -> UsageSession:
        return self._get(
            self.sessions, session_id, "Không tìm thấy phiên sử dụng"
        )

    def get_invoice(self, invoice_id: int) -> Invoice:
        return self._get(self.invoices, invoice_id, "Không tìm thấy hóa đơn")

    def find_employee_by_username(self, username: str) -> Employee | None:
        key = username.casefold()
        return next(
            (
                employee
                for employee in self.employees.values()
                if employee.username.casefold() == key
            ),
            None,
        )

    def customer_by_account_id(self, account_id: int) -> Customer:
        for customer in self.customers.values():
            if customer.account.id == account_id:
                return customer
        raise NotFoundError("Không tìm thấy tài khoản")

    def is_phone_taken(
        self, phone: str, *, exclude_customer_id: int | None = None
    ) -> bool:
        return any(
            customer.phone == phone and customer.id != exclude_customer_id
            for customer in self.customers.values()
        )

    def is_account_username_taken(self, username: str) -> bool:
        key = username.casefold()
        return any(
            customer.account.username.casefold() == key
            for customer in self.customers.values()
        )

    def is_machine_code_taken(self, code: str) -> bool:
        key = code.casefold()
        return any(
            machine.code.casefold() == key
            for machine in self.machines.values()
        )

    def active_session_for_machine(
        self, machine_id: int
    ) -> UsageSession | None:
        return next(
            (
                session
                for session in self.sessions.values()
                if session.machine_id == machine_id and session.is_active()
            ),
            None,
        )

    def active_session_for_customer(
        self, customer_id: int
    ) -> UsageSession | None:
        return next(
            (
                session
                for session in self.sessions.values()
                if session.customer_id == customer_id and session.is_active()
            ),
            None,
        )

    def machine_has_history(self, machine_id: int) -> bool:
        return any(
            session.machine_id == machine_id
            for session in self.sessions.values()
        )

    def transactions_for_account(
        self, account_id: int
    ) -> list[AccountTransaction]:
        """Giao dịch của một tài khoản, mới nhất trước."""

        return sorted(
            (
                transaction
                for transaction in self.transactions.values()
                if transaction.account_id == account_id
            ),
            key=lambda transaction: (transaction.created_at, transaction.id),
            reverse=True,
        )

    # ----- Ghi -----------------------------------------------------------

    def touch_machine(self, machine_id: int, at: datetime) -> Machine:
        """Thay entity máy bằng bản mới có updated_at=at.

        Machine không có method đổi updated_at nên dựng lại entity.
        """

        machine = copy_machine(self.get_machine(machine_id), updated_at=at)
        self.machines[machine_id] = machine
        return machine

    # ----- Chuyển sang DTO -----------------------------------------------

    def to_employee_session(self, employee: Employee) -> EmployeeSession:
        store = self.get_store(employee.store_id)
        return EmployeeSession(
            employee_id=employee.id,
            employee_code=employee.code,
            full_name=employee.full_name,
            username=employee.username,
            store_id=store.id,
            store_code=store.code,
            store_name=store.name,
            role=employee.role,
        )

    def to_customer_summary(self, customer: Customer) -> CustomerSummary:
        account = customer.account
        return CustomerSummary(
            customer_id=customer.id,
            customer_code=customer.code,
            full_name=customer.full_name,
            phone=customer.phone,
            account_id=account.id,
            username=account.username,
            balance=account.balance,
            customer_status=customer.status,
            account_status=account.status,
        )

    def to_session_summary(self, session: UsageSession) -> SessionSummary:
        customer = self.get_customer(session.customer_id)
        machine = self.get_machine(session.machine_id)
        return SessionSummary(
            session_id=session.id,
            session_code=session.code,
            customer_id=customer.id,
            customer_code=customer.code,
            customer_name=customer.full_name,
            machine_id=machine.id,
            machine_code=machine.code,
            machine_name=machine.name,
            started_at=session.started_at,
            hourly_rate=session.hourly_rate,
            status=session.status,
        )

    def to_active_session_summary(
        self, session: UsageSession, at: datetime
    ) -> ActiveSessionSummary:
        balance = self.get_customer(session.customer_id).account.balance
        estimated_cost = session.calculate_cost(at)
        return ActiveSessionSummary(
            session=self.to_session_summary(session),
            account_balance=balance,
            elapsed_seconds=session.elapsed_seconds(at),
            estimated_cost=estimated_cost,
            projected_balance=balance - estimated_cost,
            as_of=at,
        )

    def to_machine_summary(
        self, machine: Machine, at: datetime
    ) -> MachineSummary:
        active_session = None
        if machine.status == MachineStatus.IN_USE:
            session = self.active_session_for_machine(machine.id)
            if session is None:
                raise ConflictError("Dữ liệu máy và phiên không nhất quán")
            active_session = self.to_active_session_summary(session, at)
        return MachineSummary(
            machine_id=machine.id,
            machine_code=machine.code,
            store_id=machine.store_id,
            name=machine.name,
            status=machine.status,
            hourly_rate=machine.hourly_rate,
            is_active=machine.is_active,
            updated_at=machine.updated_at,
            active_session=active_session,
        )

    def to_transaction_summary(
        self, transaction: AccountTransaction
    ) -> TransactionSummary:
        employee = self.get_employee(transaction.employee_id)
        return TransactionSummary(
            transaction_id=transaction.id,
            transaction_code=transaction.code,
            account_id=transaction.account_id,
            session_id=transaction.session_id,
            type=transaction.type,
            amount=transaction.amount,
            method=transaction.method,
            employee_id=employee.id,
            employee_name=employee.full_name,
            created_at=transaction.created_at,
        )

    def to_invoice_summary(self, invoice: Invoice) -> InvoiceSummary:
        customer = self.get_customer(invoice.customer_id)
        employee = self.get_employee(invoice.employee_id)
        store = self.get_store(invoice.store_id)
        return InvoiceSummary(
            invoice_id=invoice.id,
            invoice_code=invoice.code,
            session_id=invoice.session_id,
            customer_id=customer.id,
            customer_name=customer.full_name,
            employee_id=employee.id,
            employee_name=employee.full_name,
            store_id=store.id,
            store_name=store.name,
            usage_cost=invoice.usage_cost,
            settlement_amount=invoice.settlement_amount,
            total_amount=invoice.total_amount,
            status=invoice.status,
            created_at=invoice.created_at,
        )

    def to_invoice_detail(self, invoice: Invoice) -> InvoiceDetail:
        session = self.get_session(invoice.session_id)
        if session.ended_at is None:
            raise ConflictError("Hóa đơn tham chiếu phiên chưa kết thúc")
        return InvoiceDetail(
            invoice=self.to_invoice_summary(invoice),
            session=self.to_session_summary(session),
            ended_at=session.ended_at,
            billed_minutes=session.calculate_billed_minutes(session.ended_at),
        )

    # ----- Nội bộ --------------------------------------------------------

    @staticmethod
    def _get(items: dict, item_id: int, message: str):
        item = items.get(item_id)
        if item is None:
            raise NotFoundError(message)
        return item
