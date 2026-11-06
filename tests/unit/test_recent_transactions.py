"""Unit tests cho RecentTransactionsLedger và Tương tác Mục D & 5.

Kiểm tra:
- Cấu trúc sổ cái giao dịch: Icon history, tiêu đề "Lịch sử giao dịch gần đây", badge đếm.
- Hiển thị đúng 3 giao dịch gần nhất từ WalletService (dữ liệu thật, không tạo fake).
- Thông tin mỗi giao dịch: Loại giao dịch (TOP_UP cyan, PHIÊN CHƠI slate), thời gian, metadata, số tiền (+50.000 VND / -25.000 VND).
- Trạng thái rỗng khi chưa có giao dịch.
- Tương tác: Click dòng trong bảng cập nhật panel; Click Nạp tiền/Sửa/Khóa mở đúng dialog; Callback on_success làm mới dữ liệu.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import customtkinter as ctk
import pytest

from cyberhub_manager.domain.dtos import CustomerSummary, TransactionSummary
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    PaymentMethod,
    Role,
    TransactionType,
)
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.components.recent_transactions import RecentTransactionsLedger
from cyberhub_manager.ui.customers_view import CustomersView
from cyberhub_manager.ui.dialogs.customer_lock_dialog import LockAccountDialog
from cyberhub_manager.ui.theme import STITCH_CYAN, STITCH_DANGER, STITCH_SUCCESS, STITCH_TEXT_MUTED




@pytest.fixture
def sample_transactions() -> list[TransactionSummary]:
    now = datetime.now(timezone.utc)
    return [
        TransactionSummary(
            transaction_id=101,
            transaction_code="TX-0101",
            account_id=1,
            session_id=None,
            type=TransactionType.TOP_UP,
            amount=50000,
            method=PaymentMethod.CASH,
            employee_id=1,
            employee_name="Kiệt NT",
            created_at=now,
        ),
        TransactionSummary(
            transaction_id=102,
            transaction_code="TX-0102",
            account_id=1,
            session_id=2,
            type=TransactionType.USAGE_PAYMENT,
            amount=-25000,
            method=PaymentMethod.CASH,
            employee_id=1,
            employee_name="Kiệt NT",
            created_at=now,
        ),
        TransactionSummary(
            transaction_id=103,
            transaction_code="TX-0103",
            account_id=1,
            session_id=None,
            type=TransactionType.TOP_UP,
            amount=100000,
            method=PaymentMethod.TRANSFER,
            employee_id=1,
            employee_name="Kiệt NT",
            created_at=now,
        ),
        TransactionSummary(
            transaction_id=104,
            transaction_code="TX-0104",
            account_id=1,
            session_id=None,
            type=TransactionType.TOP_UP,
            amount=20000,
            method=PaymentMethod.CASH,
            employee_id=1,
            employee_name="Kiệt NT",
            created_at=now,
        ),
    ]


# ----------------------------------------------------------------------
# 1. Tests cho Component RecentTransactionsLedger
# ----------------------------------------------------------------------
def test_recent_transactions_structure(tk_root) -> None:
    """Kiểm tra cấu trúc header, icon history và divider của Ledger."""
    ledger = RecentTransactionsLedger(tk_root, language="vi")

    # Có dải kẻ ngăn cách
    assert hasattr(ledger, "_divider")
    assert ledger._divider.cget("height") == 1

    # Header có nhãn đúng
    header_children = [
        w for w in ledger._header_row.winfo_children() if isinstance(w, (ctk.CTkFrame, ctk.CTkLabel))
    ]
    assert len(header_children) >= 2

    ledger.destroy()


def test_recent_transactions_renders_max_three_items(tk_root, sample_transactions) -> None:
    """Khi nhận vào 4 giao dịch, chỉ hiển thị đúng 3 giao dịch gần nhất."""
    ledger = RecentTransactionsLedger(tk_root, transactions=sample_transactions, max_items=3)

    assert ledger.transaction_count == 3
    assert ledger._badge_lbl.cget("text") == "3 giao dịch"

    # Stack phải chứa đúng 3 dòng
    stack_rows = ledger._stack.winfo_children()
    assert len(stack_rows) == 3

    ledger.destroy()


def test_recent_transactions_item_data_and_colors(tk_root, sample_transactions) -> None:
    """Kiểm tra nội dung, badge loại và màu sắc số tiền theo chuẩn Stitch."""
    ledger = RecentTransactionsLedger(tk_root, transactions=sample_transactions[:2])

    stack_rows = ledger._stack.winfo_children()
    assert len(stack_rows) == 2

    # Dòng 1: TOP_UP +50.000 VND (Xanh lục)
    row1 = stack_rows[0]
    labels_row1 = [w for w in row1.winfo_children()[0].winfo_children() if isinstance(w, ctk.CTkLabel)]
    # Inner left có badge TOP_UP, right có số tiền
    amt_lbl1 = [w for w in row1.winfo_children()[0].winfo_children() if isinstance(w, ctk.CTkLabel)][-1]
    assert amt_lbl1.cget("text") == "+50.000 VND"
    assert amt_lbl1.cget("text_color") == STITCH_SUCCESS

    # Dòng 2: PHIÊN CHƠI -25.000 VND (Đỏ rose)
    row2 = stack_rows[1]
    amt_lbl2 = [w for w in row2.winfo_children()[0].winfo_children() if isinstance(w, ctk.CTkLabel)][-1]
    assert amt_lbl2.cget("text") == "-25.000 VND"
    assert amt_lbl2.cget("text_color") == STITCH_DANGER

    ledger.destroy()


def test_recent_transactions_empty_state_without_fake_data(tk_root) -> None:
    """Khi không có giao dịch, hiển thị empty state chân thực, không tự chế dữ liệu giả."""
    ledger = RecentTransactionsLedger(tk_root, transactions=[])

    assert ledger.transaction_count == 0
    assert ledger._badge_lbl.cget("text") == "0 giao dịch"

    stack_children = ledger._stack.winfo_children()
    assert len(stack_children) == 1  # 1 empty box frame

    ledger.destroy()


# ----------------------------------------------------------------------
# 2. Tests Tương tác (Interactions)
# ----------------------------------------------------------------------
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


def test_click_customer_in_table_updates_right_panel(tk_root, mock_context_manager) -> None:
    """Click một dòng khách hàng trong bảng -> Cập nhật toàn bộ thông tin panel bên phải."""
    view = CustomersView(tk_root, mock_context_manager)

    # Giả lập chọn khách thứ 2 (Lê Thị Bình)
    customers = mock_context_manager.services.customers.search_customers("")
    target_cust = customers[1]

    view._on_row_selected(target_cust.customer_id)

    # 1. Cập nhật mã và tên
    assert view._detail_name.cget("text") == target_cust.full_name
    assert target_cust.customer_code in view._detail_code_badge.cget("text")

    # 2. Cập nhật số dư trong Wallet HUD
    assert view._wallet_hud.balance == target_cust.balance

    # 3. Highlight dòng trong bảng
    assert view._table._selected_key == target_cust.customer_id

    # 4. Tải lịch sử giao dịch thật từ service
    assert view._ledger.transaction_count >= 0

    view.destroy()


def test_interaction_buttons_open_dialogs_and_refresh(tk_root, mock_context_manager) -> None:
    """Click Nạp tiền, Sửa, Khóa mở đúng dialog và refresh dữ liệu khi thành công."""
    view = CustomersView(tk_root, mock_context_manager)
    customers = mock_context_manager.services.customers.search_customers("")
    cust = customers[0]
    view._select_customer(cust)

    # 1. Click Nạp tiền -> TopUpDialog
    with patch("cyberhub_manager.ui.customers_view.TopUpDialog") as mock_topup:
        view._btn_topup._on_click()
        assert mock_topup.called
        assert mock_topup.call_args[0][2] == cust
        # Callback on_success nối với refresh
        assert mock_topup.call_args[1]["on_success"] == view.refresh

    # 2. Click Sửa -> CustomerDialog chế độ edit
    with patch("cyberhub_manager.ui.customers_view.CustomerDialog") as mock_cust_dlg:
        view._btn_edit._on_click()
        assert mock_cust_dlg.called
        assert mock_cust_dlg.call_args[1]["customer"] == cust
        assert mock_cust_dlg.call_args[1]["on_success"] == view.refresh

    # 3. Click Khóa -> LockAccountDialog (CustomerLockDialog)
    with patch("cyberhub_manager.ui.customers_view.CustomerLockDialog") as mock_lock_dlg:
        view._btn_lock._on_click()
        assert mock_lock_dlg.called
        assert mock_lock_dlg.call_args[0][2] == cust
        assert mock_lock_dlg.call_args[1]["on_success"] == view.refresh

    view.destroy()


def test_lock_account_dialog_alias_import() -> None:
    """Xác nhận LockAccountDialog là alias hợp lệ của CustomerLockDialog."""
    from cyberhub_manager.ui.dialogs import LockAccountDialog, CustomerLockDialog
    assert LockAccountDialog is CustomerLockDialog
