"""Hợp đồng service dùng chung giữa service thật, mock và UI.

Mọi Protocol ở đây chỉ mô tả chữ ký, kiểu trả về và exception đã thống nhất
trong docs/07_DTO_UI_HANDOFF.md (mục 5, 6). Module không chứa logic nghiệp vụ,
không import UI, MySQL connector, config hay database.

Ngoài các exception liệt kê ở từng hàm, mọi operation đều có thể raise
ServiceUnavailableError khi không truy cập được nguồn dữ liệu.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from cyberhub_manager.domain.dtos import (
    CheckoutPreview,
    CheckoutResult,
    CustomerSummary,
    DailyRevenue,
    EmployeeSession,
    InvoiceDetail,
    InvoiceFilters,
    InvoiceSummary,
    MachineArchiveResult,
    MachineSummary,
    OpenSessionPreview,
    SessionSummary,
    TopUpResult,
    TransactionSummary,
)
from cyberhub_manager.domain.enums import CustomerStatus, PaymentMethod
from cyberhub_manager.domain.models import Customer, Machine
from cyberhub_manager.domain.p1 import (
    CustomerSession,
    StoreSummary,
    EmployeeSummary,
    Promotion,
    TopUpQuote,
)


@runtime_checkable
class AuthServiceProtocol(Protocol):
    def login(self, username: str, password: str) -> EmployeeSession:
        """Đăng nhập nhân viên; username được trim, password giữ nguyên.

        Raises:
            AuthenticationError: sai thông tin hoặc nhân viên không ACTIVE.
        """
        ...


@runtime_checkable
class CustomerServiceProtocol(Protocol):
    def create_customer(
        self,
        full_name: str,
        phone: str,
        username: str,
        password: str,
    ) -> Customer:
        """Tạo khách hàng và tài khoản trong cùng một thao tác.

        Raises:
            ValidationError: full_name, phone, username, password không hợp lệ.
            ConflictError: phone hoặc username đã được sử dụng.
        """
        ...

    def get_customer(self, customer_id: int) -> Customer:
        """Raises:
        NotFoundError: không tồn tại khách hàng.
        """
        ...

    def search_customers(self, keyword: str) -> list[CustomerSummary]:
        """Tìm gần đúng theo mã khách, họ tên, số điện thoại hoặc username.

        Không có kết quả trả []; keyword rỗng trả toàn bộ.
        """
        ...

    def update_customer(
        self,
        customer_id: int,
        full_name: str,
        phone: str,
    ) -> Customer:
        """Raises:
        NotFoundError: không tồn tại khách hàng.
        ValidationError: full_name hoặc phone không hợp lệ.
        ConflictError: phone đã thuộc khách hàng khác.
        """
        ...

    def set_customer_status(
        self,
        customer_id: int,
        status: CustomerStatus,
        actor: EmployeeSession,
    ) -> Customer:
        """INACTIVE đồng thời khóa account; ACTIVE đồng thời mở account.

        Không tự kết thúc phiên đang chạy.

        Raises:
            PermissionDeniedError: actor không phải MANAGER/ADMIN.
            NotFoundError: không tồn tại khách hàng.
        """
        ...


@runtime_checkable
class WalletServiceProtocol(Protocol):
    def preview_top_up(
        self, customer_id: int, amount: int, employee_id: int
    ) -> TopUpQuote:
        """Quote the highest eligible promotion without changing balances."""
        ...

    def top_up(
        self,
        customer_id: int,
        amount: int,
        method: PaymentMethod,
        employee_id: int,
    ) -> TopUpResult:
        """Nạp tiền; method chỉ nhận CASH hoặc TRANSFER.

        Raises:
            ValidationError: amount hoặc method không hợp lệ.
            NotFoundError: không tồn tại khách hàng.
            PermissionDeniedError: employee_id không hợp lệ với phiên đăng nhập.
        """
        ...

    def get_history(self, customer_id: int) -> list[TransactionSummary]:
        """Lịch sử giao dịch mới nhất trước; chưa có giao dịch trả [].

        Raises:
            NotFoundError: không tồn tại khách hàng.
        """
        ...


@runtime_checkable
class MachineServiceProtocol(Protocol):
    def list_machines(self, store_id: int) -> list[MachineSummary]:
        """Danh sách máy vận hành của cửa hàng, chỉ gồm máy is_active=True."""
        ...

    def create_machine(
        self,
        code: str,
        store_id: int,
        name: str,
        hourly_rate: int,
        actor: EmployeeSession,
    ) -> Machine:
        """Raises:
        PermissionDeniedError: actor không phải MANAGER/ADMIN hoặc khác cửa hàng.
        ValidationError: code, name hoặc hourly_rate không hợp lệ.
        ConflictError: code đã tồn tại.
        """
        ...

    def update_machine(
        self,
        machine_id: int,
        name: str,
        hourly_rate: int,
        actor: EmployeeSession,
    ) -> Machine:
        """Đổi giá không ảnh hưởng giá snapshot của phiên đang chạy.

        Raises:
            PermissionDeniedError: actor không phải MANAGER/ADMIN hoặc khác cửa hàng.
            NotFoundError: không tồn tại máy.
            ValidationError: name hoặc hourly_rate không hợp lệ.
        """
        ...

    def set_maintenance(
        self,
        machine_id: int,
        enabled: bool,
        actor: EmployeeSession,
    ) -> Machine:
        """Raises:
        PermissionDeniedError: actor không phải MANAGER/ADMIN hoặc khác cửa hàng.
        NotFoundError: không tồn tại máy.
        ConflictError: máy đang IN_USE hoặc đã ngừng sử dụng.
        """
        ...

    def archive_machine(
        self,
        machine_id: int,
        actor: EmployeeSession,
    ) -> MachineArchiveResult:
        """Máy chưa có lịch sử trả DELETED; có lịch sử trả ARCHIVED.

        Raises:
            PermissionDeniedError: actor không phải MANAGER/ADMIN hoặc khác cửa hàng.
            NotFoundError: không tồn tại máy.
            ConflictError: máy đang IN_USE.
        """
        ...


@runtime_checkable
class SessionServiceProtocol(Protocol):
    def preview_open(
        self,
        customer_id: int,
        machine_id: int,
        actor: EmployeeSession,
    ) -> OpenSessionPreview:
        """Chỉ thiếu số dư thì trả can_open=False kèm blocked_reason.

        Raises:
            NotFoundError: không tồn tại khách hàng hoặc máy.
            PermissionDeniedError: máy thuộc cửa hàng khác.
            ConflictError: khách/tài khoản bị khóa, máy không AVAILABLE
                hoặc khách đang có phiên khác.
        """
        ...

    def open_session(
        self,
        customer_id: int,
        machine_id: int,
        actor: EmployeeSession,
    ) -> SessionSummary:
        """Kiểm tra lại toàn bộ điều kiện của preview_open trước khi mở.

        Raises:
            NotFoundError: không tồn tại khách hàng hoặc máy.
            PermissionDeniedError: máy thuộc cửa hàng khác.
            ConflictError: khách/tài khoản bị khóa, máy bận
                hoặc khách đang có phiên khác.
            InsufficientBalanceError: số dư thấp hơn mức tối thiểu.
        """
        ...

    def preview_checkout(
        self,
        machine_id: int,
        current_time: datetime,
    ) -> CheckoutPreview:
        """Ước tính phí tại current_time (UTC); không thay đổi dữ liệu.

        Raises:
            NotFoundError: không tồn tại máy.
            PermissionDeniedError: chưa đăng nhập hợp lệ hoặc máy khác cửa hàng.
            ConflictError: máy không có phiên ACTIVE.
            ValidationError: current_time trước thời điểm bắt đầu phiên.
        """
        ...

    def complete_checkout(
        self,
        machine_id: int,
        actor: EmployeeSession,
        settlement_amount: int,
        method: PaymentMethod | None,
    ) -> CheckoutResult:
        """Không cần bù: settlement_amount=0, method=None.

            Cần bù: settlement_amount phải bằng đúng settlement_required
            từ preview mới nhất; method bắt buộc là CASH hoặc TRANSFER.
            Tiền khách đưa và tiền thừa không thuộc service contract.

        Raises:
            NotFoundError: không tồn tại máy.
            PermissionDeniedError: máy thuộc cửa hàng khác.
            ConflictError: máy không có phiên ACTIVE.
            ValidationError: settlement_amount hoặc method không hợp lệ.
            SettlementRequiredError: tiền bù không đủ; dữ liệu chưa thay đổi.
        """
        ...


@runtime_checkable
class ReportServiceProtocol(Protocol):
    def list_invoices(
        self,
        store_id: int,
        filters: InvoiceFilters,
    ) -> list[InvoiceSummary]:
        """Lọc theo ngày địa phương Asia/Ho_Chi_Minh, bao gồm hai đầu mốc.

        Raises:
            ValidationError: date_from lớn hơn date_to.
            PermissionDeniedError: chưa đăng nhập hợp lệ hoặc store_id khác cửa hàng.
        """
        ...

    def get_invoice(self, invoice_id: int) -> InvoiceDetail:
        """Raises:
        NotFoundError: không tồn tại hóa đơn.
        PermissionDeniedError: chưa đăng nhập hợp lệ hoặc hóa đơn khác cửa hàng.
        """
        ...

    def daily_revenue(
        self,
        store_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DailyRevenue]:
        """Chỉ cộng hóa đơn PAID; chỉ trả những ngày có hóa đơn.

        Raises:
            ValidationError: date_from lớn hơn date_to.
            PermissionDeniedError: chưa đăng nhập hợp lệ hoặc store_id khác cửa hàng.
        """
        ...


class ManagementServiceProtocol(Protocol):
    def loyalty_settings(self, actor: EmployeeSession): ...
    def update_loyalty_settings(self, actor: EmployeeSession, settings): ...
    def list_machine_rooms(self, actor: EmployeeSession) -> list[dict]: ...
    def set_machine_room(self, actor: EmployeeSession, machine_id: int, room_type: str) -> dict: ...
    def validate_actor(self, actor: EmployeeSession) -> EmployeeSession: ...
    def list_stores(self, actor: EmployeeSession) -> list[StoreSummary]: ...
    def switch_store(
        self, actor: EmployeeSession, store_id: int
    ) -> EmployeeSession: ...
    def save_store(
        self,
        actor: EmployeeSession,
        store_id: int | None,
        code: str,
        name: str,
        address: str,
        status: str = "ACTIVE",
    ) -> StoreSummary: ...
    def list_employees(self, actor: EmployeeSession) -> list[EmployeeSummary]: ...
    def save_employee(
        self,
        actor: EmployeeSession,
        employee_id: int | None,
        store_id: int,
        full_name: str,
        username: str,
        role: str = "STAFF",
        status: str = "ACTIVE",
        password: str = "",
    ) -> EmployeeSummary: ...
    def list_promotions(self, actor: EmployeeSession) -> list[Promotion]: ...
    def save_promotion(
        self, actor: EmployeeSession, policy: Promotion
    ) -> Promotion: ...


class PortalServiceProtocol(Protocol):
    def member(self, principal: CustomerSession, page: int = 1) -> dict: ...
    def avatar(self, principal: CustomerSession) -> dict: ...
    def update_avatar(self, principal: CustomerSession, content: bytes) -> dict: ...
    def remove_avatar(self, principal: CustomerSession) -> dict: ...
    def login(self, username: str, password: str) -> CustomerSession: ...
    def validate(self, principal: CustomerSession) -> CustomerSession: ...
    def snapshot(self, principal: CustomerSession) -> dict: ...
    def dashboard(self, principal: CustomerSession, days: int = 30, store_id: int | None = None) -> dict: ...
    def history(self, principal: CustomerSession, kind: str = "transactions", status: str = "all", date_from: str | None = None, date_to: str | None = None, page: int = 1, page_size: int = 10) -> dict: ...
    def promotion_quote(self, principal: CustomerSession, store_id: int, amount: int) -> dict: ...
    def notifications(self, principal: CustomerSession) -> dict: ...
    def mark_notifications_read(self, principal: CustomerSession, keys: list[str]) -> dict: ...
    def availability(self, principal: CustomerSession, store_id: int) -> dict: ...
    def usage_analysis(self, principal: CustomerSession, days: int = 30) -> dict: ...
    def profile(self, principal: CustomerSession) -> dict: ...
    def update_profile(self, principal: CustomerSession, full_name: str, phone: str, current_password: str) -> dict: ...
    def change_password(self, principal: CustomerSession, current_password: str, new_password: str, confirmation: str) -> CustomerSession: ...
    def invoice(self, principal: CustomerSession, invoice_id: int) -> InvoiceDetail: ...


@dataclass(frozen=True)
class ServiceBundle:
    """Sáu service được tiêm vào UI; view không tự khởi tạo service."""

    auth: AuthServiceProtocol
    customers: CustomerServiceProtocol
    wallet: WalletServiceProtocol
    machines: MachineServiceProtocol
    sessions: SessionServiceProtocol
    reports: ReportServiceProtocol
    management: ManagementServiceProtocol | None = None
    portal: PortalServiceProtocol | None = None
