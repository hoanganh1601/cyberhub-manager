"""NG-09 — Chụp bộ ảnh evidence cho các màn và trạng thái UI chính (dữ liệu mock, không cần MySQL).

Chạy (cần màn hình thật, không chạy được trên CI headless):
    python scripts/capture_ui_screens.py                          # ghi vào docs/screenshots/ng09
    python scripts/capture_ui_screens.py --out path/khac --only 06,10

Không chạm chuột/bàn phím trong lúc script chạy (cửa sổ cần ở trên cùng để chụp đúng).
Danh sách ảnh và test case nghiệm thu tương ứng: docs/demo/NG09_DEMO_UI.md.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import customtkinter as ctk
from PIL import ImageGrab

from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.ui.app_shell import AppShell, ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.dialogs import checkout_dialog as checkout_module
from cyberhub_manager.ui.dialogs.checkout_dialog import CheckoutDialog
from cyberhub_manager.ui.dialogs.customer_dialog import CustomerDialog
from cyberhub_manager.ui.dialogs.customer_lock_dialog import CustomerLockDialog
from cyberhub_manager.ui.dialogs.open_session_dialog import OpenSessionDialog
from cyberhub_manager.ui.dialogs.payment_success_dialog import PaymentSuccessDialog
from cyberhub_manager.ui.dialogs.topup_dialog import TopUpDialog
from cyberhub_manager.ui.navigation import NavKey
from cyberhub_manager.ui.theme import SHELL_HEIGHT, SHELL_WIDTH, load_stitch_fonts, setup_theme
from cyberhub_manager.ui.views import default_view_factories

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots" / "ng09"
RUNNER = ImmediateTaskRunner()
SETTLE_MS = 1500


@dataclass
class Shot:
    code: str
    name: str
    build: Callable[["Studio"], Any]  # trả widget cần chụp (root hoặc dialog)


class Studio:
    """Giữ root, shell và bộ service mock cho từng ảnh."""

    def __init__(self, out: Path) -> None:
        setup_theme()
        self.out = out
        self.root = ctk.CTk()
        load_stitch_fonts()
        self.root.geometry(f"{SHELL_WIDTH}x{SHELL_HEIGHT}+0+0")
        self.root.attributes("-topmost", True)
        self.shell: AppShell | None = None
        self.services: Any = None
        self.session: Any = None

    # --- dựng dữ liệu / shell ------------------------------------------
    def login(self, username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS) -> ViewContext:
        self.services = build_mock_services(scenario)
        self.session = build_mock_services().auth.login(username, DEMO_PASSWORD)
        return ViewContext(services=self.services, session=self.session, language="vi", navigate=lambda _k: True)

    def open_shell(self, key: NavKey, username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS) -> Any:
        if self.shell is not None:
            self.shell.destroy()
        self.login(username, scenario)
        self.shell = AppShell(self.root, self.services, self.session, on_logout=lambda: None, view_factories=default_view_factories())
        self.shell.pack(fill="both", expand=True)
        self.shell.navigate(key)
        return self.root

    def context(self) -> ViewContext:
        return ViewContext(services=self.services, session=self.session, language="vi", navigate=lambda _k: True)

    def machine(self, code: str) -> Any:
        return next(m for m in self.services.machines.list_machines(self.session.store_id) if m.machine_code == code)

    def customer(self, code: str) -> Any:
        return next(c for c in self.services.customers.search_customers("") if c.customer_code == code)

    def dialog(self, dialog: Any) -> Any:
        dialog.geometry("+40+30")
        dialog.attributes("-topmost", True)
        return dialog

    # --- chụp ----------------------------------------------------------
    def grab(self, widget: Any, path: Path) -> None:
        widget.update()
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        ImageGrab.grab(bbox=(x, y, x + widget.winfo_width(), y + widget.winfo_height()), all_screens=True).save(path, optimize=True)


# ----------------------------------------------------------------------
# Danh sách ảnh (mã khớp bảng trong docs/demo/NG09_DEMO_UI.md)
# ----------------------------------------------------------------------
def _low_balance_customer(s: Studio) -> Any:
    created = s.services.customers.create_customer("Trần Minh Quân", "0987654321", "quan.tm", "secret1")
    s.services.wallet.top_up(created.id, 2_000, PaymentMethod.CASH, s.session.employee_id)
    return next(c for c in s.services.customers.search_customers("0987654321"))


def _customer_validation(s: Studio) -> Any:
    dialog = CustomerDialog(s.root, s.context(), runner=RUNNER)
    dialog.fields["phone"].set_value("091234567")
    dialog.fields["username"].set_value("an")
    dialog.fields["password"].set_value("secret12")
    dialog.fields["confirm_password"].set_value("secret13")
    dialog.submit()
    return s.dialog(dialog)


def _top_up(s: Studio) -> Any:
    dialog = TopUpDialog(s.root, s.context(), s.customer("KH001"), account_code="TK001", runner=RUNNER)
    dialog.set_amount(50_000)
    return s.dialog(dialog)


def _open_ok(s: Studio) -> Any:
    dialog = OpenSessionDialog(s.root, s.context(), s.machine("PC01"), runner=RUNNER)
    dialog.select_customer(s.customer("KH001"))
    return s.dialog(dialog)


def _open_low(s: Studio) -> Any:
    dialog = OpenSessionDialog(s.root, s.context(), s.machine("PC01"), runner=RUNNER)
    dialog.select_customer(_low_balance_customer(s))
    return s.dialog(dialog)


def _open_blocked(s: Studio) -> Any:
    dialog = OpenSessionDialog(s.root, s.context(), s.machine("PC01"), runner=RUNNER)
    dialog.select_customer(s.customer("KH003"))
    return s.dialog(dialog)


def _checkout(code: str, method: PaymentMethod | None = None, cash: str = "") -> Callable[[Studio], Any]:
    def build(s: Studio) -> Any:
        dialog = CheckoutDialog(s.root, s.context(), s.machine(code), runner=RUNNER)
        if method is not None:
            dialog.set_method(method)
        if cash:
            dialog.set_cash_given(cash)
        return s.dialog(dialog)

    return build


def _receipt(s: Studio) -> Any:
    result = s.services.sessions.complete_checkout(s.machine("PC02").machine_id, s.session, 10_000, PaymentMethod.CASH)
    return s.dialog(PaymentSuccessDialog(s.root, result, username="lethibinh", method=PaymentMethod.CASH, cash_given=20_000))


def _lock(s: Studio) -> Any:
    return s.dialog(CustomerLockDialog(s.root, s.context(), s.customer("KH001"), account_code="TK001", runner=RUNNER))


def _shell_then(key: NavKey, username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS, search: str = ""):
    def build(s: Studio) -> Any:
        root = s.open_shell(key, username, scenario)
        if search:
            s.shell.current_view.handle_search(search)
        return root

    return build


def _with_shell(key: NavKey, build_dialog: Callable[[Studio], Any]) -> Callable[[Studio], Any]:
    def build(s: Studio) -> Any:
        s.open_shell(key)
        return build_dialog(s)

    return build


SHOTS = [
    Shot("01", "dashboard_manager", _shell_then(NavKey.DASHBOARD)),
    Shot("02", "dashboard_staff", _shell_then(NavKey.DASHBOARD, "nhanvien01")),
    Shot("03", "customers", _shell_then(NavKey.CUSTOMERS)),
    Shot("04", "customer_create_validation", _with_shell(NavKey.CUSTOMERS, _customer_validation)),
    Shot("05", "top_up", _with_shell(NavKey.CUSTOMERS, _top_up)),
    Shot("06", "customer_lock_confirm", _with_shell(NavKey.CUSTOMERS, _lock)),
    Shot("07", "machines", _shell_then(NavKey.MACHINES)),
    Shot("08", "open_session_eligible", _with_shell(NavKey.DASHBOARD, _open_ok)),
    Shot("09", "open_session_insufficient", _with_shell(NavKey.DASHBOARD, _open_low)),
    Shot("10", "open_session_blocked", _with_shell(NavKey.DASHBOARD, _open_blocked)),
    Shot("11", "checkout_balance_only", _with_shell(NavKey.DASHBOARD, _checkout("PC05"))),
    Shot("12", "checkout_cash", _with_shell(NavKey.DASHBOARD, _checkout("PC02", PaymentMethod.CASH, "20.000"))),
    Shot("13", "checkout_transfer_qr", _with_shell(NavKey.DASHBOARD, _checkout("PC02", PaymentMethod.TRANSFER))),
    Shot("14", "payment_receipt", _with_shell(NavKey.DASHBOARD, _receipt)),
    Shot("15", "invoices", _shell_then(NavKey.INVOICES)),
    Shot("16", "reports", _shell_then(NavKey.REPORTS)),
    Shot("17", "empty_search", _shell_then(NavKey.CUSTOMERS, search="không-có-khách-này")),
    Shot("18", "service_error_retry", _shell_then(NavKey.CUSTOMERS, scenario=MockScenario.UNAVAILABLE)),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--only", default="", help="mã ảnh, cách nhau dấu phẩy (vd. 06,10)")
    args = parser.parse_args()
    wanted = {code.strip() for code in args.only.split(",") if code.strip()}
    shots = [shot for shot in SHOTS if not wanted or shot.code in wanted]
    args.out.mkdir(parents=True, exist_ok=True)

    studio = Studio(args.out)
    # Ảnh hóa đơn mở từ dialog thanh toán thật: không tự bật thêm hóa đơn khi chụp màn xác nhận.
    checkout_module.PaymentSuccessDialog = lambda *a, **k: None  # type: ignore[assignment]

    def step(index: int = 0) -> None:
        if index == len(shots):
            studio.root.destroy()
            return
        shot = shots[index]
        target = shot.build(studio)

        def capture() -> None:
            path = args.out / f"{shot.code}_{shot.name}.png"
            studio.grab(target, path)
            print(f"  {path.name}")
            if target is not studio.root:
                target.destroy()
            step(index + 1)

        studio.root.after(SETTLE_MS, capture)

    print(f"Chụp {len(shots)} ảnh vào {args.out}")
    studio.root.after(800, step)
    studio.root.mainloop()


if __name__ == "__main__":
    main()
