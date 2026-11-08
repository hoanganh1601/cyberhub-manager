"""Exercise rendered English copy across screens, modals and chart interaction."""

from datetime import date
from string import Formatter
import tkinter as tk
import unicodedata

import customtkinter as ctk
import pytest

from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.domain.dtos import InvoiceFilters
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.ui.app_shell import AppShell, ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.customers_view import CustomersView
from cyberhub_manager.ui.dashboard_view import DashboardView
from cyberhub_manager.ui.dialogs.checkout_dialog import CheckoutDialog
from cyberhub_manager.ui.dialogs.customer_dialog import CustomerDialog
from cyberhub_manager.ui.dialogs.customer_lock_dialog import CustomerLockDialog
from cyberhub_manager.ui.dialogs.machine_dialog import MachineDialog
from cyberhub_manager.ui.dialogs.open_session_dialog import OpenSessionDialog
from cyberhub_manager.ui.dialogs.payment_success_dialog import PaymentSuccessDialog
from cyberhub_manager.ui.dialogs.topup_dialog import TopUpDialog
from cyberhub_manager.ui.formatters import format_duration, format_money
from cyberhub_manager.ui.i18n import UIStrings
from cyberhub_manager.ui.invoices_view import InvoicesView
from cyberhub_manager.ui.machine_management_view import MachineManagementView
from cyberhub_manager.ui.navigation import NavKey
from cyberhub_manager.ui.reports_view import ReportsView
from cyberhub_manager.ui.ui_copy import ENGLISH
from cyberhub_manager.ui.views import default_view_factories
from cyberhub_manager.ui.window_position import centered_bounds

RUNNER = ImmediateTaskRunner()


@pytest.fixture(autouse=True)
def _hide_render_tests(request):
    """Keep live mouse/keyboard input out of programmatic language-switch checks."""
    if "tk_root" not in request.fixturenames:
        yield
        return
    root = request.getfixturevalue("tk_root")
    state, geometry = root.state(), root.geometry()
    root.withdraw()
    yield
    root.geometry(geometry)
    if state == "normal":
        root.deiconify()


@pytest.fixture
def en_context():
    services = build_mock_services()
    session = services.auth.login("quanly01", "demo123")
    return ViewContext(services, session, "en", lambda _: True)


def widget_copy(widget):
    """Include placeholders and canvas labels, not just navigation text."""
    values = set()
    for key in ("text", "placeholder_text", "values"):
        try:
            value = widget.cget(key)
        except (ValueError, TypeError, tk.TclError, AttributeError):
            continue
        if isinstance(value, str):
            values.add(value)
        elif isinstance(value, (tuple, list)):
            values.update(str(item) for item in value)
    if hasattr(widget, "tooltip_text"):
        values.add(widget.tooltip_text)
        values.add(widget.tooltip.text)
    if isinstance(widget, tk.Canvas):
        for item in widget.find_all():
            if widget.type(item) == "text":
                values.add(widget.itemcget(item, "text"))
    if isinstance(widget, ctk.CTkToplevel):
        values.add(widget.title())
    for child in widget.winfo_children():
        values.update(widget_copy(child))
    return values


def assert_english(widget, context):
    # Names are real business data and must remain intact, including diacritics.
    preserved = {context.session.full_name, context.session.store_name}
    customers = context.services.customers.search_customers("")
    preserved.update(c.full_name for c in customers)
    machines = context.services.machines.list_machines(context.session.store_id)
    preserved.update(m.name for m in machines)
    invoices = context.services.reports.list_invoices(context.session.store_id, InvoiceFilters())
    preserved.update(i.employee_name for i in invoices)
    if context.services.management and str(context.session.role) in ("MANAGER","ADMIN"):
        preserved.update(e.full_name for e in context.services.management.list_employees(context.session))
    leftovers = []
    for value in widget_copy(widget):
        rest = value
        for name in sorted(preserved, key=len, reverse=True):
            rest = rest.replace(name, "")
        if any(unicodedata.combining(ch) for ch in unicodedata.normalize("NFD", rest)) or "đ" in rest.lower():
            leftovers.append(value)
    assert not leftovers, "Untranslated UI copy: " + repr(sorted(leftovers))


@pytest.mark.parametrize("view_type", [DashboardView, CustomersView, MachineManagementView, InvoicesView, ReportsView])
def test_all_business_screens_render_in_english(tk_root, en_context, view_type):
    view = view_type(tk_root, en_context, runner=RUNNER)
    view.pack(fill="both", expand=True)
    tk_root.update()
    assert_english(view, en_context)
    if isinstance(view, ReportsView):
        view._grain_control._buttons_dict["Week"].invoke()
        view._mode_control._buttons_dict["Bar"].invoke()
        assert view._grain == "week" and view._chart_mode == "bar"
        view.select_bucket(view.revenue_chart.buckets[-1])
        assert_english(view, en_context)
        view.set_dates(date(2000, 1, 1), date(2000, 1, 7))
        view.apply_filters()
        assert_english(view, en_context)
    view.destroy()


@pytest.mark.parametrize("kind", ["create_customer", "edit_customer", "top_up", "lock", "unlock",
                                  "add_machine", "edit_machine", "open", "blocked", "checkout_cash", "checkout_transfer", "receipt"])
def test_all_dialogs_inherit_english(tk_root, en_context, kind):
    services = en_context.services
    customers = services.customers.search_customers("")
    customer = next(c for c in customers if c.customer_code == "KH001")
    machines = services.machines.list_machines(en_context.session.store_id)
    available = next(m for m in machines if m.machine_code == "PC01")
    busy = next(m for m in machines if m.machine_code == "PC02")
    if kind in ("create_customer", "edit_customer"):
        dialog = CustomerDialog(tk_root, en_context, customer=customer if kind == "edit_customer" else None, runner=RUNNER)
    elif kind == "top_up":
        dialog = TopUpDialog(tk_root, en_context, customer, runner=RUNNER)
        dialog.set_amount(50000)
        dialog.set_method(PaymentMethod.TRANSFER)
    elif kind in ("lock", "unlock"):
        if kind == "unlock":
            customer = next(c for c in customers if c.customer_code == "KH004")
        dialog = CustomerLockDialog(tk_root, en_context, customer, runner=RUNNER)
    elif kind in ("add_machine", "edit_machine"):
        dialog = MachineDialog(tk_root, en_context, machine=available if kind == "edit_machine" else None, runner=RUNNER)
    elif kind in ("open", "blocked"):
        if kind == "blocked":
            customer = next(c for c in customers if c.customer_code == "KH004")
        dialog = OpenSessionDialog(tk_root, en_context, available, customer=customer, runner=RUNNER)
    elif kind.startswith("checkout"):
        dialog = CheckoutDialog(tk_root, en_context, busy, runner=RUNNER)
        if kind == "checkout_transfer":
            dialog.set_method(PaymentMethod.TRANSFER)
        else:
            dialog.set_cash_given("20000")
    else:
        result = services.sessions.complete_checkout(busy.machine_id, en_context.session, 10000, PaymentMethod.CASH)
        dialog = PaymentSuccessDialog(tk_root, result, language="en", method=PaymentMethod.CASH, cash_given=20000)
    tk_root.update()
    assert_english(dialog, en_context)
    dialog.destroy()


def test_switching_languages_rebuilds_content_and_preserves_business_names(tk_root, en_context):
    shell = AppShell(tk_root, en_context.services, en_context.session, on_logout=lambda: None,
                     view_factories={key: (lambda parent, context, cls=cls: cls(parent, context, runner=RUNNER))
                                     for key, cls in default_view_factories().items()}, language="vi")
    shell.pack(fill="both", expand=True)
    for key in shell.nav_keys:
        assert shell.navigate(key)
        assert shell.current_key == key
        shell.set_language("en")
        assert shell.current_key == key
        tk_root.update()
        assert shell.current_key == key
        assert_english(shell, en_context)
        shell.set_language("vi")
        assert shell.current_view._context.language == "vi"
    shell.destroy()


def test_centered_bounds_respects_offset_monitor_and_edges():
    assert centered_bounds((300, 100, 1200, 800), (600, 480), (0, 0, 1920, 1040)) == (600, 480, 600, 260)
    w, h, x, y = centered_bounds((-1800, 80, 1400, 900), (800, 650), (-1920, 0, 0, 1080))
    assert (x + w / 2, y + h / 2) == (-1100, 530)
    w, h, x, y = centered_bounds((1700, 900, 1200, 800), (800, 650), (0, 0, 1920, 1040))
    assert x >= 12 and y >= 32 and x + w <= 1908 and y + h <= 1024


def test_customer_edit_is_larger_and_centered_on_root(tk_root, en_context):
    tk_root.deiconify()
    tk_root.geometry("1200x740+90+40")
    tk_root.update()
    inner = ctk.CTkFrame(tk_root, width=200, height=200)
    inner.place(x=0, y=0)
    customer = en_context.services.customers.search_customers("")[0]
    dialog = CustomerDialog(inner, en_context, customer=customer, runner=RUNNER)
    # Windows/CTk can remap the native window more than 80ms after creation.
    # Wait for mapping and stable dimensions before measuring physical pixels.
    settled = tk.BooleanVar(tk_root, False)
    previous = [None,0,0]
    def wait_for_layout():
        size = dialog.winfo_width(),dialog.winfo_height()
        previous[2] += 1
        previous[1] = previous[1]+1 if dialog.winfo_ismapped() and size==previous[0] and size[1]>300 else 0
        previous[0] = size
        if previous[1]>=4 or previous[2]>=60:
            settled.set(True)
        else:
            tk_root.after(25,wait_for_layout)
    tk_root.after(25,wait_for_layout)
    tk_root.wait_variable(settled)
    tk_root.update()
    scale = dialog._get_window_scaling()
    assert abs(dialog.winfo_width() - 620 * scale) <= 2
    assert abs(dialog.winfo_rootx() + dialog.winfo_width() / 2 - tk_root.winfo_rootx() - tk_root.winfo_width() / 2) <= 3
    assert abs(dialog.winfo_rooty() + dialog.winfo_height() / 2 - tk_root.winfo_rooty() - tk_root.winfo_height() / 2) <= 3
    dialog.destroy()


def test_catalog_preserves_placeholders_and_business_data():
    fields = lambda s: {field for _, field, _, _ in Formatter().parse(s) if field}
    for source, target in ENGLISH.items():
        assert fields(source) == fields(target), source
    assert UIStrings("en")("Mã TK: {v0}", v0="Nguyễn Văn An") == "Account ID: Nguyễn Văn An"
    assert format_duration(5400, "en") == "1 hr 30 min"
    assert format_money(50000, "en") == "50,000 VND"
    assert UIStrings("en")("{v0} đơn", v0=1) == "1 invoice"
    assert UIStrings("en")("{v0} đơn", v0=3) == "3 invoices"


def test_staff_dashboard_has_english_maintenance_note(tk_root):
    services = build_mock_services()
    session = services.auth.login("nhanvien01", "demo123")
    context = ViewContext(services, session, "en", lambda _: True)
    view = DashboardView(tk_root, context, runner=RUNNER)
    assert_english(view, context)
    assert "▲  Under maintenance" in widget_copy(view)
    view.destroy()
