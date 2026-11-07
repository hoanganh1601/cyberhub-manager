"""Unit tests cho NG-04 — dialog Tạo/Sửa khách hàng, Nạp tiền, Khóa/Mở khóa."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus, PaymentMethod
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui import customers_view as customers_module
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.customers_view import CustomersView
from cyberhub_manager.ui.dialogs.customer_dialog import (
    INVALID_PHONE,
    INVALID_USERNAME,
    PASSWORD_MISMATCH,
    REQUIRED,
    CustomerDialog,
    validate_customer_form,
)
from cyberhub_manager.ui.dialogs.customer_lock_dialog import CustomerLockDialog
from cyberhub_manager.ui.dialogs.topup_dialog import (
    INVALID_AMOUNT,
    MAX_EXCEEDED,
    TopUpDialog,
    parse_amount,
    validate_amount,
)
from cyberhub_manager.ui.theme import STITCH_DANGER

RUNNER = ImmediateTaskRunner()


def _login(username: str = "quanly01"):
    services = build_mock_services()
    session = services.auth.login(username, DEMO_PASSWORD)
    context = ViewContext(services=services, session=session, language="vi", navigate=lambda _k: True)
    return services, session, context


def _customer(services, code: str):
    return next(c for c in services.customers.search_customers("") if c.customer_code == code)


@pytest.fixture(autouse=True)
def _silence_toasts():
    """Toast thật cần cửa sổ hiển thị; trong test chỉ ghi lại lời gọi."""
    with patch("cyberhub_manager.ui.components.toast.ToastManager.show") as toast:
        yield toast


# ----------------------------------------------------------------------
# 1. Hàm thuần
# ----------------------------------------------------------------------
VALID_CREATE = {
    "full_name": "Nguyễn Văn Mới",
    "phone": "0909123456",
    "username": "moi.nv",
    "password": "secret1",
    "confirm_password": "secret1",
}


def test_validate_customer_form_accepts_valid_input() -> None:
    assert validate_customer_form(VALID_CREATE, creating=True) == {}
    assert validate_customer_form({"full_name": "An", "phone": "0909123456"}, creating=False) == {}


@pytest.mark.parametrize(
    ("changes", "field", "message"),
    [
        ({"full_name": ""}, "full_name", REQUIRED),
        ({"full_name": "A"}, "full_name", "Full name must be between 2 and 100 characters."),
        ({"phone": "091234567"}, "phone", INVALID_PHONE),  # 9 số
        ({"phone": "1912345678"}, "phone", INVALID_PHONE),  # không bắt đầu bằng 0
        ({"username": "an"}, "username", INVALID_USERNAME),
        ({"username": "an nv"}, "username", INVALID_USERNAME),
        ({"password": "12345", "confirm_password": "12345"}, "password", "Password must have at least 6 characters."),
        ({"confirm_password": "khac123"}, "confirm_password", PASSWORD_MISMATCH),
    ],
)
def test_validate_customer_form_errors(changes: dict, field: str, message: str) -> None:
    errors = validate_customer_form({**VALID_CREATE, **changes}, creating=True)
    assert errors[field] == message


def test_edit_form_ignores_account_fields() -> None:
    assert validate_customer_form({"full_name": "An", "phone": "0909123456", "username": ""}, creating=False) == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [("50.000", (50_000, None)), ("50,000 VND", (50_000, None)), ("100000000", (100_000_000, None)),
     ("100.000.001", (None, MAX_EXCEEDED)), ("0", (None, INVALID_AMOUNT)), ("-5", (None, INVALID_AMOUNT)),
     ("abc", (None, INVALID_AMOUNT)), ("", (None, INVALID_AMOUNT))],
)
def test_validate_amount(text: str, expected) -> None:
    assert validate_amount(text) == expected


def test_parse_amount() -> None:
    assert parse_amount(" 20.000 đ ") == 20_000
    assert parse_amount("12a") is None


# ----------------------------------------------------------------------
# 2. Dialog Tạo / Sửa khách hàng
# ----------------------------------------------------------------------
def test_create_dialog_creates_customer_and_account(tk_root) -> None:
    services, _, context = _login()
    saved = []
    dialog = CustomerDialog(tk_root, context, runner=RUNNER, on_saved=saved.append)
    for key, value in VALID_CREATE.items():
        dialog.fields[key].set_value(value)
    dialog.submit()
    assert saved and saved[0].full_name == "Nguyễn Văn Mới"
    assert not dialog.winfo_exists()
    created = _customer(services, saved[0].code)
    assert (created.username, created.balance, created.account_status) == ("moi.nv", 0, AccountStatus.ACTIVE)


def test_create_dialog_client_validation_keeps_input(tk_root) -> None:
    services, _, context = _login()
    dialog = CustomerDialog(tk_root, context, runner=RUNNER)
    dialog.fields["phone"].set_value("091234567")
    dialog.fields["username"].set_value("an")
    with patch.object(services.customers, "create_customer") as create:
        dialog.submit()
        create.assert_not_called()
    assert dialog.fields["full_name"]._error_label.cget("text") == REQUIRED
    assert dialog.fields["phone"]._error_label.cget("text") == INVALID_PHONE
    assert dialog.fields["phone"]._box.cget("border_color") == STITCH_DANGER
    assert dialog.fields["phone"].get_value() == "091234567"
    assert not dialog.is_submitting
    dialog.destroy()


def test_create_dialog_maps_duplicate_phone_to_field(tk_root) -> None:
    services, _, context = _login()
    dialog = CustomerDialog(tk_root, context, runner=RUNNER)
    for key, value in {**VALID_CREATE, "phone": _customer(services, "KH001").phone}.items():
        dialog.fields[key].set_value(value)
    dialog.submit()
    assert dialog.winfo_exists()
    assert dialog.fields["phone"]._error_label.cget("text") == "Phone number is already in use."
    dialog.destroy()


def test_password_toggle(tk_root) -> None:
    _, _, context = _login()
    dialog = CustomerDialog(tk_root, context, runner=RUNNER)
    password = dialog.fields["password"]
    password.set_value("secret1")  # ô rỗng đang hiện placeholder thì CTkEntry tạm bỏ ký tự che
    assert password.entry.cget("show") == "•"
    password.toggle_password()
    assert password.entry.cget("show") == "" and password.is_revealed
    dialog.destroy()


def test_edit_dialog_updates_name_and_phone_only(tk_root) -> None:
    services, _, context = _login()
    kh002 = _customer(services, "KH002")
    saved = []
    dialog = CustomerDialog(tk_root, context, customer=kh002, account_code="TK002", runner=RUNNER, on_saved=saved.append)
    assert set(dialog.fields) == {"full_name", "phone"}  # không sửa tên đăng nhập / số dư (CUS-03)
    assert dialog.fields["phone"].get_value() == kh002.phone
    dialog.fields["full_name"].set_value("Lê Thị Bình Mới")
    dialog.submit()
    assert saved and _customer(services, "KH002").full_name == "Lê Thị Bình Mới"


# ----------------------------------------------------------------------
# 3. Dialog Nạp tiền
# ----------------------------------------------------------------------
def test_top_up_dialog_preview_quick_amount_and_method(tk_root) -> None:
    services, _, context = _login()
    kh001 = _customer(services, "KH001")  # số dư 50.000
    dialog = TopUpDialog(tk_root, context, kh001, account_code="TK001", runner=RUNNER)
    assert dialog.method == PaymentMethod.CASH
    dialog.set_amount(20_000)
    assert dialog.amount_field.get_value() == "20.000"
    assert dialog.preview_new_balance == "70.000 VND"
    dialog.set_method(PaymentMethod.TRANSFER)
    assert dialog.method == PaymentMethod.TRANSFER
    dialog.destroy()


def test_top_up_dialog_records_transaction_with_logged_in_employee(tk_root) -> None:
    services, session, context = _login("nhanvien01")
    kh002 = _customer(services, "KH002")
    results = []
    dialog = TopUpDialog(tk_root, context, kh002, runner=RUNNER, on_success=results.append)
    dialog.set_amount(50_000)
    dialog.set_method(PaymentMethod.TRANSFER)
    dialog.submit()
    assert results and results[0].balance_after == kh002.balance + 50_000
    latest = services.wallet.get_history(kh002.customer_id)[0]
    assert (latest.amount, latest.method, latest.employee_id) == (50_000, PaymentMethod.TRANSFER, session.employee_id)
    assert not dialog.winfo_exists()


def test_top_up_dialog_rejects_invalid_amount(tk_root) -> None:
    services, _, context = _login()
    dialog = TopUpDialog(tk_root, context, _customer(services, "KH001"), runner=RUNNER)
    dialog.amount_field.set_value("200.000.000")
    with patch.object(services.wallet, "top_up") as top_up:
        dialog.submit()
        top_up.assert_not_called()
    assert dialog.amount_field._error_label.cget("text") == MAX_EXCEEDED
    dialog.destroy()


def test_locked_account_can_still_top_up(tk_root) -> None:
    services, _, context = _login()
    kh004 = _customer(services, "KH004")  # INACTIVE + LOCKED, số dư -5.000
    results = []
    dialog = TopUpDialog(tk_root, context, kh004, runner=RUNNER, on_success=results.append)
    dialog.set_amount(10_000)
    dialog.submit()
    assert results and results[0].balance_after == 5_000


# ----------------------------------------------------------------------
# 4. Dialog Khóa / Mở khóa
# ----------------------------------------------------------------------
def test_lock_and_unlock_customer(tk_root) -> None:
    services, _, context = _login()
    done = []
    lock = CustomerLockDialog(tk_root, context, _customer(services, "KH001"), runner=RUNNER, on_done=done.append)
    assert lock.locking
    lock.submit()
    kh001 = _customer(services, "KH001")
    assert (kh001.customer_status, kh001.account_status) == (CustomerStatus.INACTIVE, AccountStatus.LOCKED)

    unlock = CustomerLockDialog(tk_root, context, kh001, runner=RUNNER, on_done=done.append)
    assert not unlock.locking
    unlock.submit()
    kh001 = _customer(services, "KH001")
    assert (kh001.customer_status, kh001.account_status) == (CustomerStatus.ACTIVE, AccountStatus.ACTIVE)
    assert len(done) == 2


def test_cancel_lock_changes_nothing(tk_root) -> None:
    services, _, context = _login()
    dialog = CustomerLockDialog(tk_root, context, _customer(services, "KH001"), runner=RUNNER)
    dialog.cancel_button.invoke()
    assert not dialog.winfo_exists()
    assert _customer(services, "KH001").customer_status == CustomerStatus.ACTIVE


def test_staff_lock_is_rejected_by_service(tk_root) -> None:
    services, _, context = _login("nhanvien01")
    dialog = CustomerLockDialog(tk_root, context, _customer(services, "KH001"), runner=RUNNER)
    with patch("cyberhub_manager.ui.dialogs.customer_lock_dialog.notify_error") as notify:
        dialog.submit()
    notify.assert_called_once()
    assert dialog.winfo_exists() and not dialog.is_submitting
    assert _customer(services, "KH001").customer_status == CustomerStatus.ACTIVE
    dialog.destroy()


# ----------------------------------------------------------------------
# 5. Màn Khách hàng tải lại sau thao tác
# ----------------------------------------------------------------------
def test_view_refreshes_and_keeps_selection_after_top_up(tk_root) -> None:
    services, _, context = _login()
    view = CustomersView(tk_root, context, runner=RUNNER)
    view.select(2)
    with patch.object(customers_module, "TopUpDialog") as dialog_cls:
        view.action_buttons["top_up"].invoke()
    on_success = dialog_cls.call_args.kwargs["on_success"]
    result = services.wallet.top_up(2, 15_000, PaymentMethod.CASH, context.session.employee_id)
    on_success(result)
    assert view.selected_customer.customer_id == 2
    assert view.selected_customer.balance == result.balance_after
    assert view._balance_label.cget("text") == "20.000 VND"
    view.destroy()
