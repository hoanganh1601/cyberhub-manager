"""LI-08 — Unit test cho ReportService, dùng repository giả nên không cần MySQL."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from mysql.connector.errors import InterfaceError

from cyberhub_manager.domain.dtos import (
    DailyRevenue,
    EmployeeSession,
    InvoiceDetail,
    InvoiceFilters,
    InvoiceSummary,
)
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    Role,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.domain.models import Account, Customer, Machine, UsageSession
from cyberhub_manager.services.contracts import ReportServiceProtocol
from cyberhub_manager.services.report_service import (
    INCONSISTENT_INVOICE,
    DATE_FROM_REQUIRED,
    DATE_INVALID,
    DATE_RANGE_INVALID,
    DATE_TO_REQUIRED,
    STATUS_INVALID,
    VN_TZ,
    WRONG_STORE,
    ReportService,
    local_dates_to_utc_range,
)

STORE_ID = 1
OTHER_STORE_ID = 2
CREATED_AT = datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc)
STARTED_AT = datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc)
ENDED_AT = STARTED_AT + timedelta(seconds=61)

ROLE_EMPLOYEE_IDS = {Role.ADMIN: 1, Role.MANAGER: 2, Role.STAFF: 3}


def make_actor(role=Role.STAFF, store_id=STORE_ID, *, employee_id=None):
    return EmployeeSession(
        employee_id=ROLE_EMPLOYEE_IDS[role] if employee_id is None else employee_id,
        employee_code="NV001",
        full_name="LI08 Actor",
        username="li08.actor",
        store_id=store_id,
        store_code="CH001",
        store_name="Cửa hàng test",
        role=role,
    )


MANAGER = make_actor(Role.MANAGER)


def make_summary(
    invoice_id=1,
    *,
    store_id=STORE_ID,
    status=InvoiceStatus.PAID,
    cost=6_000,
):
    return InvoiceSummary(
        invoice_id=invoice_id,
        invoice_code=f"INV-{invoice_id:03d}",
        session_id=100 + invoice_id,
        customer_id=5,
        customer_name="Nguyễn Văn A",
        employee_id=3,
        employee_name="LI08 Actor",
        store_id=store_id,
        store_name="Cửa hàng test",
        usage_cost=cost,
        settlement_amount=0,
        total_amount=cost,
        status=status,
        created_at=CREATED_AT,
    )


def make_completed_session(
    *,
    customer_id=5,
    machine_id=7,
    closed_by=3,
    cost=200,
):
    return UsageSession(
        id=101,
        code="SS-101",
        customer_id=customer_id,
        machine_id=machine_id,
        opened_by=3,
        closed_by=closed_by,
        started_at=STARTED_AT,
        ended_at=ENDED_AT,
        hourly_rate=6_000,
        cost=cost,
        status=SessionStatus.COMPLETED,
    )


def make_cancelled_session():
    return UsageSession(
        id=101,
        code="SS-101",
        customer_id=5,
        machine_id=7,
        opened_by=3,
        closed_by=3,
        started_at=STARTED_AT,
        ended_at=ENDED_AT,
        hourly_rate=6_000,
        cost=None,
        status=SessionStatus.CANCELLED,
    )


def make_machine(*, store_id=STORE_ID):
    return Machine(
        id=7,
        code="PC07",
        store_id=store_id,
        name="Máy 07",
        status=MachineStatus.AVAILABLE,
        hourly_rate=12_000, # Giá hiện tại khác giá snapshot của phiên.
        is_active=True,
        updated_at=ENDED_AT,
    )


def make_customer():
    return Customer(
        id=5,
        code="KH005",
        full_name="Nguyễn Văn A",
        phone="0900000005",
        status=CustomerStatus.ACTIVE,
        account=Account(
            id=10,
            code="ACC005",
            customer_id=5,
            username="khach05",
            balance=0,
            status=AccountStatus.ACTIVE,
        ),
    )


# ----- Đồ giả ----------------------------------------------------------------
class FakeDatabase:
    def __init__(self, *, employees, invoices=()):
        self.employees = {employee.employee_id: employee for employee in employees}
        self.invoices = list(invoices)
        self.transactions = 0
        self.list_calls = []
        self.summary_calls = []
        self.revenue_calls = []
        self.lookups = []
        self.sessions = {}
        self.machines = {}
        self.customers = {}
        self.error = None
        self.audits = []

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield object()


class FakeAuthRepository:
    def __init__(self, db):
        self.db = db

    def get_active_session_by_id(self, conn, employee_id):
        # Employee/store không ACTIVE thì repository thật trả None.
        return self.db.employees.get(employee_id)


class FakeAuditRepository:
    def __init__(self, db):
        self.db = db

    def audit(self, conn, actor, action, entity_id):
        self.db.audits.append((actor.employee_id, action, entity_id))


class FakeInvoiceRepository:
    def __init__(self, db):
        self.db = db

    def list_by_store(self, conn, store_id, **filters):
        if self.db.error is not None:
            raise self.db.error
        self.db.list_calls.append((store_id, filters))
        return [i for i in self.db.invoices if i.store_id == store_id]

    def daily_revenue_by_store(
        self, conn, store_id, *, created_from_utc, created_before_utc
    ):
        """Mô phỏng đúng SQL của HA-08: chỉ PAID, khoảng nửa mở, gom theo ngày VN."""

        if self.db.error is not None:
            raise self.db.error
        self.db.revenue_calls.append(
            (
                store_id,
                {
                    "created_from_utc": created_from_utc,
                    "created_before_utc": created_before_utc,
                },
            )
        )
        totals = {}
        for invoice in self.db.invoices:
            if (
                invoice.store_id == store_id
                and invoice.status == InvoiceStatus.PAID
                and created_from_utc <= invoice.created_at < created_before_utc
            ):
                day = invoice.created_at.astimezone(VN_TZ).date()
                count, revenue = totals.get(day, (0, 0))
                totals[day] = (count + 1, revenue + invoice.usage_cost)
        return [
            DailyRevenue(date=day, invoice_count=count, revenue=revenue)
            for day, (count, revenue) in sorted(totals.items())
        ]

    def get_summary_by_id(self, conn, invoice_id):
        if self.db.error is not None:
            raise self.db.error
        self.db.summary_calls.append(invoice_id)
        for invoice in self.db.invoices:
            if invoice.invoice_id == invoice_id:
                return invoice
        return None


class FakeLookup:
    """get_by_id giả cho session/machine/customer repository."""

    def __init__(self, db, table):
        self.db = db
        self.table = table

    def get_by_id(self, conn, row_id, *, for_update=False):
        self.db.lookups.append((self.table, row_id))
        return getattr(self.db, self.table).get(row_id)


def build_service(actor=None, *, employees=None, invoices=()):
    """actor là người đang đăng nhập; employees là bản ghi ACTIVE trong DB."""

    actor = actor or make_actor()
    db = FakeDatabase(
        employees=[actor] if employees is None else employees, invoices=invoices
    )
    service = ReportService(
        invoice_repo=FakeInvoiceRepository(db),
        auth_repo=FakeAuthRepository(db),
        audit_repo=FakeAuditRepository(db),
        actor_provider=lambda: actor,
        transaction_factory=db.transaction,
    )
    return service, db


def test_report_service_satisfies_protocol():
    assert isinstance(ReportService(), ReportServiceProtocol)


# ----- Đổi ngày Việt Nam sang UTC ---------------------------------------------
def test_local_dates_convert_to_half_open_utc_range():
    start, end = local_dates_to_utc_range(date(2026, 11, 1), date(2026, 11, 2))

    # 00:00 ngày 01/11 giờ VN = 17:00 ngày 31/10 UTC.
    assert start == datetime(2026, 10, 31, 17, 0, tzinfo=timezone.utc)
    # Tính trọn ngày 02/11: chặn trước 00:00 ngày 03/11 giờ VN.
    assert end == datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc)
    assert start.utcoffset() == end.utcoffset() == timedelta(0)


def test_single_local_day_covers_24_hours():
    start, end = local_dates_to_utc_range(date(2026, 11, 1), date(2026, 11, 1))

    assert (end - start).total_seconds() == 24 * 3600


def test_missing_bound_means_unbounded():
    assert local_dates_to_utc_range(None, None) == (None, None)
    start, end = local_dates_to_utc_range(None, date(2026, 12, 31))
    assert start is None
    # Qua năm mới theo giờ VN vẫn đúng.
    assert end == datetime(2026, 12, 31, 17, 0, tzinfo=timezone.utc)


# ----- list_invoices ----------------------------------------------------------
def test_list_invoices_passes_store_and_utc_range_to_repository():
    invoices = [make_summary(2), make_summary(1)]
    service, db = build_service(invoices=invoices)
    filters = InvoiceFilters(
        date_from=date(2026, 11, 1),
        date_to=date(2026, 11, 2),
        keyword="  INV-001  ",
        customer_id=5,
        status=InvoiceStatus.PAID,
    )

    result = service.list_invoices(STORE_ID, filters)

    assert result == invoices
    assert all(isinstance(item, InvoiceSummary) for item in result)
    assert db.list_calls == [
        (
            STORE_ID,
            {
                "created_from_utc": datetime(2026, 10, 31, 17, tzinfo=timezone.utc),
                "created_before_utc": datetime(2026, 11, 2, 17, tzinfo=timezone.utc),
                "keyword": "INV-001",
                "customer_id": 5,
                "status": InvoiceStatus.PAID,
            },
        )
    ]


@pytest.mark.parametrize("filters", [None, InvoiceFilters()])
def test_list_invoices_without_filters_is_unbounded(filters):
    service, db = build_service()

    service.list_invoices(STORE_ID, filters)

    assert db.list_calls == [
        (
            STORE_ID,
            {
                "created_from_utc": None,
                "created_before_utc": None,
                "keyword": "",
                "customer_id": None,
                "status": None,
            },
        )
    ]


@pytest.mark.parametrize("status", ["PAID", "VOID"])
def test_list_invoices_rejects_status_as_text(status):
    service, db = build_service()

    with pytest.raises(ValidationError) as exc_info:
        service.list_invoices(
            STORE_ID,
            InvoiceFilters(status=status),
        )

    assert exc_info.value.field_errors == {
        "status": STATUS_INVALID,
    }
    assert db.transactions == 0


@pytest.mark.parametrize("role", [Role.STAFF, Role.MANAGER, Role.ADMIN])
def test_every_store_role_can_list_invoices(role):
    service, db = build_service(make_actor(role))

    service.list_invoices(STORE_ID, InvoiceFilters())

    assert len(db.list_calls) == 1


def test_list_invoices_rejects_reversed_date_range_before_database():
    service, db = build_service()
    filters = InvoiceFilters(date_from=date(2026, 11, 2), date_to=date(2026, 11, 1))

    with pytest.raises(ValidationError) as exc_info:
        service.list_invoices(STORE_ID, filters)

    assert exc_info.value.field_errors == {"date_to": DATE_RANGE_INVALID}
    assert db.transactions == 0


@pytest.mark.parametrize(
    ("filters", "field"),
    [
        (InvoiceFilters(date_from="2026-11-01"), "date_from"),
        (InvoiceFilters(date_to=datetime(2026, 11, 1, tzinfo=timezone.utc)), "date_to"),
        (InvoiceFilters(keyword=None), "keyword"),
        (InvoiceFilters(customer_id=0), "customer_id"),
        (InvoiceFilters(customer_id=True), "customer_id"),
        (InvoiceFilters(status="DELETED"), "status"),
    ],
)
def test_list_invoices_rejects_invalid_filters(filters, field):
    service, db = build_service()

    with pytest.raises(ValidationError) as exc_info:
        service.list_invoices(STORE_ID, filters)

    assert field in exc_info.value.field_errors
    assert db.transactions == 0


def test_list_invoices_rejects_non_filter_object():
    service, _ = build_service()

    with pytest.raises(ValidationError):
        service.list_invoices(STORE_ID, {"keyword": "INV"})


@pytest.mark.parametrize("store_id", [0, -1, True, "1", None])
def test_list_invoices_rejects_invalid_store_id(store_id):
    service, db = build_service()

    with pytest.raises(ValidationError) as exc_info:
        service.list_invoices(store_id, InvoiceFilters())

    assert "store_id" in exc_info.value.field_errors
    assert db.transactions == 0


def test_list_invoices_of_other_store_is_denied():
    service, db = build_service(invoices=[make_summary(store_id=OTHER_STORE_ID)])

    with pytest.raises(PermissionDeniedError) as exc_info:
        service.list_invoices(OTHER_STORE_ID, InvoiceFilters())

    assert exc_info.value.message == WRONG_STORE
    assert db.list_calls == []


def test_list_invoices_without_login_is_denied():
    db = FakeDatabase(employees=[])
    service = ReportService(
        invoice_repo=FakeInvoiceRepository(db),
        auth_repo=FakeAuthRepository(db),
        transaction_factory=db.transaction,
    )

    with pytest.raises(PermissionDeniedError):
        service.list_invoices(STORE_ID, InvoiceFilters())
    assert db.list_calls == []


@pytest.mark.parametrize(
    ("actor", "employees"),
    [
        (make_actor(), []),  # employee LOCKED/INACTIVE hoặc store INACTIVE
        (make_actor(), [make_actor(store_id=OTHER_STORE_ID)]),  # đã chuyển store
        (make_actor(Role.MANAGER, employee_id=3), [make_actor(Role.STAFF)]),
    ],
)
def test_list_invoices_rechecks_actor_in_database(actor, employees):
    service, db = build_service(actor, employees=employees)

    with pytest.raises(PermissionDeniedError):
        service.list_invoices(STORE_ID, InvoiceFilters())
    assert db.list_calls == []


def test_provider_returning_invalid_actor_is_denied():
    service, db = build_service()
    service._actor_provider = lambda: replace(make_actor(), employee_id=0)

    with pytest.raises(PermissionDeniedError):
        service.list_invoices(STORE_ID, InvoiceFilters())


def test_database_error_maps_to_service_unavailable():
    service, db = build_service()
    db.error = InterfaceError(msg="mất kết nối")

    with pytest.raises(ServiceUnavailableError):
        service.list_invoices(STORE_ID, InvoiceFilters())


# ----- get_invoice ------------------------------------------------------------
def build_detail_service(actor=None, *, employees=None, invoice=None, **parts):
    """Hóa đơn 1 của phiên 101 (máy 7, khách 5) đã kết thúc sau 61 giây."""
    detail_invoice = (
        make_summary(cost=200)
        if invoice is None
        else invoice
    )

    service, db = build_service(
        actor,
        employees=employees,
        invoices=[detail_invoice],
    )
    db.sessions = {101: parts.get("session", make_completed_session())}
    db.machines = {7: parts.get("machine", make_machine())}
    db.customers = {5: parts.get("customer", make_customer())}
    service._sessions = FakeLookup(db, "sessions")
    service._machines = FakeLookup(db, "machines")
    service._customers = FakeLookup(db, "customers")
    return service, db


def test_get_invoice_returns_detail():
    service, db = build_detail_service()

    detail = service.get_invoice(1)

    assert isinstance(detail, InvoiceDetail)
    assert detail.invoice == make_summary(cost=200)
    session = detail.session
    assert (session.session_id, session.session_code) == (101, "SS-101")
    assert (session.customer_id, session.customer_code, session.customer_name) == (
        5,
        "KH005",
        "Nguyễn Văn A",
    )
    assert (session.machine_id, session.machine_code, session.machine_name) == (
        7,
        "PC07",
        "Máy 07",
    )
    assert session.started_at == STARTED_AT
    assert session.hourly_rate == 6_000
    assert session.status == SessionStatus.COMPLETED
    assert detail.ended_at == ENDED_AT
    assert detail.billed_minutes == 2  # 61 giây => 2 phút


def test_get_invoice_shows_void_invoice():
    service, _ = build_detail_service(
        invoice=make_summary(
            status=InvoiceStatus.VOID,
            cost=200,
        )
    )

    assert service.get_invoice(1).invoice.status == InvoiceStatus.VOID


@pytest.mark.parametrize("invoice_id", [99, 0, -1, True, "1", None])
def test_get_invoice_unknown_or_invalid_id_is_not_found(invoice_id):
    service, _ = build_detail_service()

    with pytest.raises(NotFoundError):
        service.get_invoice(invoice_id)


def test_get_invoice_invalid_id_does_not_open_database():
    service, db = build_detail_service()

    with pytest.raises(NotFoundError):
        service.get_invoice(0)
    assert db.transactions == 0


def test_get_invoice_of_other_store_is_denied():
    service, db = build_detail_service(
        invoice=make_summary(store_id=OTHER_STORE_ID)
    )

    with pytest.raises(PermissionDeniedError) as exc_info:
        service.get_invoice(1)

    assert exc_info.value.message == WRONG_STORE
    assert db.lookups == []  # không đọc phiên, máy, khách của cửa hàng khác


@pytest.mark.parametrize(
    ("actor", "employees"),
    [
        (make_actor(), []),  # employee LOCKED/INACTIVE hoặc store INACTIVE
        (make_actor(Role.MANAGER, employee_id=3), [make_actor(Role.STAFF)]),
    ],
)
def test_get_invoice_rechecks_actor_before_reading(actor, employees):
    service, db = build_detail_service(actor, employees=employees)

    with pytest.raises(PermissionDeniedError):
        service.get_invoice(1)
    assert db.summary_calls == []


def test_get_invoice_without_login_is_denied():
    service, db = build_detail_service()
    service._actor_provider = None

    with pytest.raises(PermissionDeniedError):
        service.get_invoice(1)


@pytest.mark.parametrize("missing", ["sessions", "machines", "customers"])
def test_get_invoice_with_missing_related_row_conflicts(missing):
    service, db = build_detail_service()
    getattr(db, missing).clear()

    with pytest.raises(ConflictError):
        service.get_invoice(1)


@pytest.mark.parametrize(
    ("part_name", "part"),
    [
        ("session", make_cancelled_session()),
        ("session", make_completed_session(cost=201)),
        ("session", make_completed_session(customer_id=6)),
        ("session", make_completed_session(closed_by=2)),
        ("machine", make_machine(store_id=OTHER_STORE_ID)),
    ],
    ids=[
        "session-not-completed",
        "usage-cost-mismatch",
        "customer-mismatch",
        "closing-employee-mismatch",
        "machine-store-mismatch",
    ],
)
def test_get_invoice_rejects_inconsistent_related_data(part_name, part):
    service, _ = build_detail_service(**{part_name: part})

    with pytest.raises(ConflictError) as exc_info:
        service.get_invoice(1)

    assert exc_info.value.message == INCONSISTENT_INVOICE


def test_get_invoice_database_error_maps_to_service_unavailable():
    service, db = build_detail_service()
    db.error = InterfaceError(msg="mất kết nối")

    with pytest.raises(ServiceUnavailableError):
        service.get_invoice(1)


# ----- daily_revenue ----------------------------------------------------------
def invoice_at(invoice_id, created_at, *, status=InvoiceStatus.PAID, cost=6_000):
    return replace(
        make_summary(invoice_id, status=status),
        usage_cost=cost,
        total_amount=cost,
        created_at=created_at,
    )


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_daily_revenue_passes_half_open_utc_range():
    service, db = build_service(MANAGER)

    service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 3))

    assert db.revenue_calls == [
        (
            STORE_ID,
            {
                "created_from_utc": utc(2026, 10, 31, 17),
                "created_before_utc": utc(2026, 11, 3, 17),
            },
        )
    ]


def test_daily_revenue_counts_only_paid_and_respects_vietnam_day_boundaries():
    service, _ = build_service(
        MANAGER,
        invoices=[
            invoice_at(1, utc(2026, 10, 31, 16, 59, 59)),  # 23:59:59 ngày 31/10 VN
            invoice_at(2, utc(2026, 10, 31, 17, 0, 0), cost=1_000),  # 00:00 01/11 VN
            invoice_at(3, utc(2026, 11, 1, 16, 59, 59), cost=2_000),  # 23:59:59 01/11
            invoice_at(4, utc(2026, 11, 1, 5), status=InvoiceStatus.VOID),
            invoice_at(5, utc(2026, 11, 2, 17, 0, 0)),  # 00:00 ngày 03/11 VN
        ]
    )

    result = service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 2))

    # Hóa đơn VOID không được tính; ngày 02/11 không có hóa đơn thì không có dòng.
    assert result == [
        DailyRevenue(date=date(2026, 11, 1), invoice_count=2, revenue=3_000)
    ]
    assert all(isinstance(row.revenue, int) for row in result)


def test_daily_revenue_returns_empty_list_without_invoices():
    service, _ = build_service(MANAGER)

    assert service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 30)) == []


def test_daily_revenue_only_counts_current_store():
    service, _ = build_service(
        MANAGER,
        invoices=[
            invoice_at(1, utc(2026, 11, 1, 3)),
            replace(invoice_at(2, utc(2026, 11, 1, 3)), store_id=OTHER_STORE_ID),
        ]
    )

    result = service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 1))

    assert result == [
        DailyRevenue(date=date(2026, 11, 1), invoice_count=1, revenue=6_000)
    ]


@pytest.mark.parametrize("role", [Role.MANAGER, Role.ADMIN])
def test_manager_and_admin_view_revenue_and_access_is_audited(role):
    service, db = build_service(make_actor(role))

    service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 1))

    assert len(db.revenue_calls) == 1
    assert db.audits == [(ROLE_EMPLOYEE_IDS[role], "REVENUE_VIEW", STORE_ID)]


def test_staff_cannot_view_revenue_but_still_lists_invoices():
    # Đợt 0: nhân viên vẫn cần hóa đơn để thanh toán, nhưng không xem doanh thu.
    service, db = build_service(make_actor(Role.STAFF))

    with pytest.raises(PermissionDeniedError):
        service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 1))
    assert db.revenue_calls == [] and db.audits == []

    service.list_invoices(STORE_ID, InvoiceFilters())
    assert len(db.list_calls) == 1


@pytest.mark.parametrize(
    ("date_from", "date_to", "errors"),
    [
        (None, date(2026, 11, 1), {"date_from": DATE_FROM_REQUIRED}),
        (date(2026, 11, 1), None, {"date_to": DATE_TO_REQUIRED}),
        (date(2026, 11, 2), date(2026, 11, 1), {"date_to": DATE_RANGE_INVALID}),
        ("2026-11-01", date(2026, 11, 1), {"date_from": DATE_INVALID}),
        (date(2026, 11, 1), utc(2026, 11, 2), {"date_to": DATE_INVALID}),
    ],
)
def test_daily_revenue_rejects_invalid_date_range_before_database(
    date_from, date_to, errors
):
    service, db = build_service()

    with pytest.raises(ValidationError) as exc_info:
        service.daily_revenue(STORE_ID, date_from, date_to)

    assert exc_info.value.field_errors == errors
    assert db.transactions == 0


@pytest.mark.parametrize("store_id", [0, True, "1", None])
def test_daily_revenue_rejects_invalid_store_id(store_id):
    service, db = build_service()

    with pytest.raises(ValidationError):
        service.daily_revenue(store_id, date(2026, 11, 1), date(2026, 11, 1))
    assert db.transactions == 0


def test_daily_revenue_of_other_store_is_denied():
    service, db = build_service(MANAGER)

    with pytest.raises(PermissionDeniedError) as exc_info:
        service.daily_revenue(OTHER_STORE_ID, date(2026, 11, 1), date(2026, 11, 1))

    assert exc_info.value.message == WRONG_STORE
    assert db.revenue_calls == []


@pytest.mark.parametrize(
    ("actor", "employees"),
    [
        (make_actor(), []),  # employee LOCKED/INACTIVE hoặc store INACTIVE
        (make_actor(Role.MANAGER, employee_id=3), [make_actor(Role.STAFF)]),
    ],
)
def test_daily_revenue_rechecks_actor_in_database(actor, employees):
    service, db = build_service(actor, employees=employees)

    with pytest.raises(PermissionDeniedError):
        service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 1))
    assert db.revenue_calls == []


def test_daily_revenue_database_error_maps_to_service_unavailable():
    service, db = build_service(MANAGER)
    db.error = InterfaceError(msg="mất kết nối")

    with pytest.raises(ServiceUnavailableError):
        service.daily_revenue(STORE_ID, date(2026, 11, 1), date(2026, 11, 1))
