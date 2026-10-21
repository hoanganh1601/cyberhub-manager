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

        Cần bù thì method bắt buộc là CASH hoặc TRANSFER.

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
        """
        ...

    def get_invoice(self, invoice_id: int) -> InvoiceDetail:
        """Raises:
            NotFoundError: không tồn tại hóa đơn.
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
        """
        ...


@dataclass(frozen=True)
class ServiceBundle:
    """Sáu service được tiêm vào UI; view không tự khởi tạo service."""

    auth: AuthServiceProtocol
    customers: CustomerServiceProtocol
    wallet: WalletServiceProtocol
    machines: MachineServiceProtocol
    sessions: SessionServiceProtocol
    reports: ReportServiceProtocol
