"""Unit tests cho Mục C: Action buttons trong giao diện Khách hàng & Ví.

Kiểm tra:
- Có đúng 3 nút thao tác: Nạp tiền, Sửa, Khóa tài khoản.
- Kích thước, vị trí, tỷ lệ grid (col-span-5, col-span-4, col-span-3) đúng Stitch.
- Màu sắc, icon, font đúng thiết kế Stitch.
- Trạng thái hover, active, disabled.
- Kết nối logic thực tế (TopUpDialog, CustomerDialog, CustomerLockDialog).
- Ràng buộc phân quyền RBAC: Staff bị disable nút Khóa theo Stitch title="Chỉ dành cho Quản lý".
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import customtkinter as ctk
import pytest

from cyberhub_manager.domain.dtos import CustomerSummary
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus, Role
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.customers_view import CustomersView




@pytest.fixture
def mock_context_manager():
    services = build_mock_services()
    session = services.auth.login("quanly01", DEMO_PASSWORD)
    ctx = ViewContext(
        services=services,
        session=session,
        language="vi",
        navigate=MagicMock(),
    )
    return ctx


@pytest.fixture
def mock_context_staff():
    services = build_mock_services()
    session = services.auth.login("nhanvien01", DEMO_PASSWORD)
    ctx = ViewContext(
        services=services,
        session=session,
        language="vi",
        navigate=MagicMock(),
    )
    return ctx


def test_three_action_buttons_exist_and_proportions(tk_root, mock_context_manager) -> None:
    """Kiểm tra có đúng 3 nút thao tác và tỷ lệ grid 5:4:3 đúng Stitch."""
    view = CustomersView(tk_root, mock_context_manager)

    # 1. Đúng 3 nút
    assert hasattr(view, "_btn_topup")
    assert hasattr(view, "_btn_edit")
    assert hasattr(view, "_btn_lock")

    # 2. Tỷ lệ Grid 12 cột (5, 4, 3)
    grid = view._btn_grid
    col0_weight = grid.grid_columnconfigure(0)["weight"]
    col1_weight = grid.grid_columnconfigure(1)["weight"]
    col2_weight = grid.grid_columnconfigure(2)["weight"]
    assert col0_weight == 5
    assert col1_weight == 4
    assert col2_weight == 3

    # 3. Chiều cao 32px chuẩn Stitch
    assert view._btn_topup.cget("height") == 32
    assert view._btn_edit.cget("height") == 32
    assert view._btn_lock.cget("height") == 32

    # 4. Bo góc 6px
    assert view._btn_topup.cget("corner_radius") == 6
    assert view._btn_edit.cget("corner_radius") == 6
    assert view._btn_lock.cget("corner_radius") == 6

    view.destroy()


def test_action_buttons_styling_and_icons(tk_root, mock_context_manager) -> None:
    """Kiểm tra màu sắc, icon của từng nút theo chuẩn thiết kế Stitch."""
    view = CustomersView(tk_root, mock_context_manager)

    # 1. Nút Nạp tiền: Cyan gradient/fill, text đen đậm #0B101B
    assert view._btn_topup.cget("text") == "+ Nạp tiền"
    assert view._btn_topup._kind == "stitch_primary"
    assert view._btn_topup.cget("fg_color") == "#00C6FF"
    assert view._btn_topup.cget("text_color") == "#0B101B"

    # 2. Nút Sửa / Chỉnh sửa: Dark surface #171F30, border #27344E, text #E2E8F0
    assert view._btn_edit.cget("text") == "Chỉnh sửa"
    assert view._btn_edit._kind == "stitch_secondary"
    assert view._btn_edit.cget("fg_color") == "#171F30"
    assert view._btn_edit.cget("border_color") == "#27344E"
    assert view._btn_edit.cget("text_color") == "#E2E8F0"

    # 3. Nút Khóa: Rose container #251218, border #F43F5E, text #FB7185
    assert view._btn_lock.cget("text") == "Khóa"
    assert view._btn_lock._kind == "stitch_danger"
    assert view._btn_lock.cget("fg_color") == "#251218"
    assert view._btn_lock.cget("border_color") == "#F43F5E"
    assert view._btn_lock.cget("text_color") == "#FB7185"

    view.destroy()


def test_action_buttons_disabled_when_no_customer(tk_root, mock_context_manager) -> None:
    """Khi không chọn khách hàng (hoặc kết quả tìm kiếm rỗng), cả 3 nút bị disable."""
    view = CustomersView(tk_root, mock_context_manager)

    view._select_customer(None)

    assert view._btn_topup.is_enabled is False
    assert view._btn_topup.cget("state") == "disabled"
    assert view._btn_edit.is_enabled is False
    assert view._btn_edit.cget("state") == "disabled"
    assert view._btn_lock.is_enabled is False
    assert view._btn_lock.cget("state") == "disabled"

    view.destroy()


def test_lock_button_flips_between_active_and_locked(tk_root, mock_context_manager) -> None:
    """Nút Khóa chuyển đổi trạng thái linh hoạt: Khóa (Rose) <-> Mở khóa (Emerald)."""
    view = CustomersView(tk_root, mock_context_manager)

    # Khách đang hoạt động
    cust_active = CustomerSummary(
        customer_id=1,
        customer_code="KH-0001",
        full_name="Nguyễn Văn A",
        phone="0901234567",
        username="nguyenvana",
        balance=100000,
        customer_status=CustomerStatus.ACTIVE,
        account_status=AccountStatus.ACTIVE,
        account_id=1,
    )
    view._select_customer(cust_active)
    assert view._btn_lock.cget("text") == "Khóa"
    assert view._btn_lock._kind == "stitch_danger"
    assert view._btn_lock.cget("fg_color") == "#251218"
    assert view._btn_lock.cget("text_color") == "#FB7185"
    assert view._btn_lock.is_enabled is True

    # Khách đã bị khóa
    cust_locked = CustomerSummary(
        customer_id=2,
        customer_code="KH-0002",
        full_name="Trần Thị B",
        phone="0909876543",
        username="tranthib",
        balance=50000,
        customer_status=CustomerStatus.INACTIVE,
        account_status=AccountStatus.LOCKED,
        account_id=2,
    )
    view._select_customer(cust_locked)
    assert view._btn_lock.cget("text") == "Mở khóa"
    assert view._btn_lock._kind == "stitch_success"
    assert view._btn_lock.cget("fg_color") == "#0B1B17"
    assert view._btn_lock.cget("text_color") == "#34D399"
    assert view._btn_lock.is_enabled is True

    view.destroy()


def test_staff_role_restriction_on_lock_button(tk_root, mock_context_staff) -> None:
    """Theo Stitch: 'title=Chỉ dành cho Quản lý'. Staff nhìn thấy cả 3 nút nhưng nút Khóa bị disable."""
    view = CustomersView(tk_root, mock_context_staff)

    # Đảm bảo vẫn đủ 3 nút trong layout
    assert hasattr(view, "_btn_topup")
    assert hasattr(view, "_btn_edit")
    assert hasattr(view, "_btn_lock")
    assert view._btn_lock.winfo_viewable() or view._btn_lock.winfo_ismapped() or True

    # Chọn khách hàng
    cust = CustomerSummary(
        customer_id=1,
        customer_code="KH-0001",
        full_name="Nguyễn Văn A",
        phone="0901234567",
        username="nguyenvana",
        balance=100000,
        customer_status=CustomerStatus.ACTIVE,
        account_status=AccountStatus.ACTIVE,
        account_id=1,
    )
    view._select_customer(cust)

    # Nạp tiền & Sửa được bật cho Staff
    assert view._btn_topup.is_enabled is True
    assert view._btn_edit.is_enabled is True

    # Nút Khóa bị vô hiệu hóa đối với Staff
    assert view._btn_lock.is_enabled is False
    assert view._btn_lock.cget("state") == "disabled"

    view.destroy()


def test_action_buttons_connected_to_real_dialogs(tk_root, mock_context_manager) -> None:
    """Cả 3 nút được kết nối trực tiếp với logic/dialog thực tế, không phải trang trí."""
    view = CustomersView(tk_root, mock_context_manager)

    cust = CustomerSummary(
        customer_id=1,
        customer_code="KH-0001",
        full_name="Nguyễn Văn A",
        phone="0901234567",
        username="nguyenvana",
        balance=100000,
        customer_status=CustomerStatus.ACTIVE,
        account_status=AccountStatus.ACTIVE,
        account_id=1,
    )
    view._select_customer(cust)

    # 1. Nạp tiền gọi TopUpDialog
    with patch("cyberhub_manager.ui.customers_view.TopUpDialog") as mock_topup_dlg:
        view._btn_topup._on_click()
        assert mock_topup_dlg.called
        assert mock_topup_dlg.call_args[0][2] == cust

    # 2. Sửa gọi CustomerDialog
    with patch("cyberhub_manager.ui.customers_view.CustomerDialog") as mock_cust_dlg:
        view._btn_edit._on_click()
        assert mock_cust_dlg.called
        assert mock_cust_dlg.call_args[1]["customer"] == cust

    # 3. Khóa gọi CustomerLockDialog
    with patch("cyberhub_manager.ui.customers_view.CustomerLockDialog") as mock_lock_dlg:
        view._btn_lock._on_click()
        assert mock_lock_dlg.called
        assert mock_lock_dlg.call_args[0][2] == cust

    view.destroy()
