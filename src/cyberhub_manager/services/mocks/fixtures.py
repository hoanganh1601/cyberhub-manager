"""Dữ liệu demo giả cho mock services theo mục 9 của tài liệu bàn giao.

Số dư khách được tính từ chính lịch sử giao dịch nên luôn khớp với màn lịch sử.
Mọi mốc thời gian là UTC, tính tương đối từ thời điểm `now` của clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from cyberhub_manager.domain.enums import (
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

from .store import MockDataStore

DEMO_PASSWORD = "demo123"
"""Mật khẩu giả cho mọi tài khoản demo; không phải credential MySQL."""

DEMO_ACCOUNTS: tuple[tuple[str, Role], ...] = (
    ("quanly01", Role.MANAGER),
    ("nhanvien01", Role.STAFF),
    ("nhanvien02", Role.STAFF),
)

DEFAULT_HOURLY_RATE = 10_000
MACHINE_COUNT = 20


def seed_empty(data: MockDataStore, now: datetime) -> None:
    """Chỉ có cửa hàng và nhân viên để vẫn đăng nhập được."""

    _FixtureBuilder(data, now).add_store_and_employees()


def seed_success(data: MockDataStore, now: datetime) -> None:
    builder = _FixtureBuilder(data, now)
    store_id, (manager, staff1, staff2) = builder.add_store_and_employees()

    machines = {
        number: builder.add_machine(store_id, number)
        for number in range(1, MACHINE_COUNT + 1)
    }
    an = builder.add_customer("Nguyễn Văn An", "0901000001", "nguyenvanan")
    binh = builder.add_customer("Lê Thị Bình", "0901000002", "lethibinh")
    cuong = builder.add_customer("Trần Quốc Cường", "0901000003", "tranquoccuong")
    dung = builder.add_customer("Phạm Thị Dung", "0901000004", "phamthidung")
    em = builder.add_customer("Hoàng Văn Em", "0901000005", "hoangvanem")

    day = builder.day
    # Lịch sử theo thứ tự thời gian để mã giao dịch/phiên/hóa đơn tăng dần.
    builder.top_up(cuong, 20_000, PaymentMethod.TRANSFER, staff1, day(3, 3))
    builder.top_up(an, 100_000, PaymentMethod.CASH, staff1, day(2, 1, 30))
    builder.completed_session(
        an, machines[4], day(2, 2), minutes=180, opened_by=staff1, closed_by=staff2
    )
    builder.completed_session(
        an, machines[6], day(1, 6), minutes=120, opened_by=staff2, closed_by=staff2
    )
    builder.top_up(dung, 20_000, PaymentMethod.CASH, staff2, day(1, 11, 45))
    # Không bù nợ: KH004 còn -5.000, hóa đơn bị VOID và khách bị ngừng hoạt động.
    builder.completed_session(
        dung,
        machines[8],
        day(1, 12),
        minutes=150,
        opened_by=staff2,
        closed_by=staff2,
        invoice_status=InvoiceStatus.VOID,
    )
    builder.top_up(em, 5_000, PaymentMethod.CASH, staff2, day(1, 15, 50))
    # Kết thúc đúng 17:00 UTC = 00:00 ngày hôm sau theo giờ Việt Nam.
    builder.completed_session(
        em,
        machines[7],
        day(1, 16),
        minutes=60,
        opened_by=staff2,
        closed_by=manager,
        settlement=5_000,
        settlement_method=PaymentMethod.CASH,
    )
    builder.top_up(binh, 5_000, PaymentMethod.CASH, staff1, now - timedelta(minutes=95))
    builder.active_session(binh, machines[2], now - timedelta(minutes=90), staff1)
    builder.top_up(em, 100_000, PaymentMethod.TRANSFER, staff1, now - timedelta(minutes=40))
    builder.active_session(em, machines[5], now - timedelta(minutes=30), staff1)

    data.get_customer(cuong).account.lock()
    data.get_customer(dung).deactivate()
    data.get_machine(machines[3]).set_maintenance(True)


class _FixtureBuilder:
    def __init__(self, data: MockDataStore, now: datetime) -> None:
        self._data = data
        self._now = now
        self._store_id = 0

    def day(self, days_ago: int, hour: int, minute: int = 0) -> datetime:
        """Mốc UTC lúc hour:minute của ngày cách hiện tại days_ago ngày."""

        return (self._now - timedelta(days=days_ago)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

    def add_store_and_employees(self) -> tuple[int, tuple[int, int, int]]:
        data = self._data
        store_id = data.next_id("store")
        created_at = self._now - timedelta(days=30)
        data.stores[store_id] = Store(
            id=store_id,
            code=data.make_code("store", store_id),
            name="CyberHub Cầu Giấy",
            address="144 Xuân Thủy, Cầu Giấy, Hà Nội",
            status=StoreStatus.ACTIVE,
            created_at=created_at,
            updated_at=created_at,
        )
        self._store_id = store_id

        names = ("Trần Minh Quân", "Nguyễn Thu Hà", "Phạm Đức Long")
        employee_ids = []
        for full_name, (username, role) in zip(names, DEMO_ACCOUNTS):
            employee_id = data.next_id("employee")
            data.employees[employee_id] = Employee(
                id=employee_id,
                code=data.make_code("employee", employee_id),
                full_name=full_name,
                store_id=store_id,
                username=username,
                role=role,
                status=EmployeeStatus.ACTIVE,
            )
            data.employee_passwords[username] = DEMO_PASSWORD
            employee_ids.append(employee_id)
        return store_id, tuple(employee_ids)

    def add_machine(self, store_id: int, number: int) -> int:
        data = self._data
        machine_id = data.next_id("machine")
        data.machines[machine_id] = Machine(
            id=machine_id,
            code=data.make_code("machine", number),
            store_id=store_id,
            name=f"Máy {number:02d}",
            status=MachineStatus.AVAILABLE,
            hourly_rate=DEFAULT_HOURLY_RATE,
            is_active=True,
            updated_at=self._now - timedelta(days=30),
        )
        return machine_id

    def add_customer(self, full_name: str, phone: str, username: str) -> int:
        """Tạo khách số dư 0; số dư sau đó chỉ thay đổi qua giao dịch."""

        data = self._data
        customer_id = data.next_id("customer")
        account_id = data.next_id("account")
        account = Account(
            id=account_id,
            code=data.make_code("account", account_id),
            customer_id=customer_id,
            username=username,
            balance=0,
            status=AccountStatus.ACTIVE,
        )
        data.customers[customer_id] = Customer(
            id=customer_id,
            code=data.make_code("customer", customer_id),
            full_name=full_name,
            phone=phone,
            status=CustomerStatus.ACTIVE,
            account=account,
        )
        return customer_id

    def top_up(
        self,
        customer_id: int,
        amount: int,
        method: PaymentMethod,
        employee_id: int,
        at: datetime,
    ) -> None:
        self._data.get_customer(customer_id).account.credit(amount)
        self._add_transaction(
            customer_id, employee_id, None, TransactionType.TOP_UP, amount, method, at
        )

    def active_session(
        self,
        customer_id: int,
        machine_id: int,
        started_at: datetime,
        opened_by: int,
    ) -> None:
        self._new_session(customer_id, machine_id, started_at, opened_by)
        self._data.get_machine(machine_id).start_session()
        self._data.touch_machine(machine_id, started_at)

    def completed_session(
        self,
        customer_id: int,
        machine_id: int,
        started_at: datetime,
        *,
        minutes: int,
        opened_by: int,
        closed_by: int,
        settlement: int = 0,
        settlement_method: PaymentMethod | None = None,
        invoice_status: InvoiceStatus = InvoiceStatus.PAID,
    ) -> None:
        """Phiên đã checkout: cộng tiền bù (nếu có), trừ phí, tạo hóa đơn."""

        data = self._data
        account = data.get_customer(customer_id).account
        session = self._new_session(customer_id, machine_id, started_at, opened_by)
        ended_at = started_at + timedelta(minutes=minutes)
        cost = session.complete(closed_by, ended_at)

        if settlement:
            if settlement_method is None:
                raise ValueError("Fixture thiếu phương thức bù nợ")
            account.credit(settlement)
            self._add_transaction(
                customer_id,
                closed_by,
                session.id,
                TransactionType.DEBT_SETTLEMENT,
                settlement,
                settlement_method,
                ended_at,
            )
        account.debit(cost)
        self._add_transaction(
            customer_id,
            closed_by,
            session.id,
            TransactionType.USAGE_PAYMENT,
            -cost,
            PaymentMethod.ACCOUNT_BALANCE,
            ended_at,
        )

        invoice_id = data.next_id("invoice")
        invoice = Invoice(
            id=invoice_id,
            code=data.make_code("invoice", invoice_id),
            session_id=session.id,
            customer_id=customer_id,
            employee_id=closed_by,
            store_id=self._store_id,
            usage_cost=cost,
            settlement_amount=settlement,
            total_amount=cost,
            status=InvoiceStatus.PAID,
            created_at=ended_at,
        )
        if invoice_status == InvoiceStatus.VOID:
            invoice.void()
        data.invoices[invoice_id] = invoice

    def _new_session(
        self,
        customer_id: int,
        machine_id: int,
        started_at: datetime,
        opened_by: int,
    ) -> UsageSession:
        data = self._data
        session_id = data.next_id("session")
        session = UsageSession(
            id=session_id,
            code=data.make_code("session", session_id),
            customer_id=customer_id,
            machine_id=machine_id,
            opened_by=opened_by,
            closed_by=None,
            started_at=started_at,
            ended_at=None,
            hourly_rate=data.get_machine(machine_id).hourly_rate,
            cost=None,
            status=SessionStatus.ACTIVE,
        )
        data.sessions[session_id] = session
        return session

    def _add_transaction(
        self,
        customer_id: int,
        employee_id: int,
        session_id: int | None,
        type: TransactionType,
        amount: int,
        method: PaymentMethod,
        at: datetime,
    ) -> None:
        data = self._data
        transaction_id = data.next_id("transaction")
        data.transactions[transaction_id] = AccountTransaction(
            id=transaction_id,
            code=data.make_code("transaction", transaction_id),
            account_id=data.get_customer(customer_id).account.id,
            employee_id=employee_id,
            session_id=session_id,
            type=type,
            amount=amount,
            method=method,
            created_at=at,
        )
