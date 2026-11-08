"""Native P1 pages and forms must render and save through the shared services."""

from dataclasses import replace
import pytest
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.p1_views import (
    ManagementView,
    ManagementForm,
    CustomerPortalView,
)


@pytest.fixture
def context():
    bundle = build_mock_services(p1=True)
    actor = bundle.auth.login("admin01", "demo123")
    return ViewContext(bundle, actor, "en", lambda _: True)


@pytest.mark.parametrize("kind", ["stores", "employees", "promotions"])
def test_management_pages_and_forms(tk_root, context, kind):
    view = ManagementView(tk_root, context, kind=kind, runner=ImmediateTaskRunner())
    view.pack(fill="both", expand=True)
    tk_root.update_idletasks()
    assert len(view.items) == len(
        getattr(context.services.management, "list_" + kind)(context.session)
    )
    form = ManagementForm(
        tk_root, context, kind, stores=view.stores, runner=ImmediateTaskRunner()
    )
    if kind == "stores":
        values = dict(code="CH03", name="Third store", address="Address")
    elif kind == "employees":
        values = dict(
            full_name="New employee", username="newemployee", password="secret123"
        )
    else:
        values = dict(code="TIER10", name="10% reward")
    for key, value in values.items():
        form.fields[key].set_value(value)
    form.submit()
    assert not form.winfo_exists(), (
        form.error_label.cget("text") if form.winfo_exists() else ""
    )
    view.destroy()


def test_customer_workspace_readonly(tk_root, context):
    principal = context.services.portal.login("nguyenvanan", "demo123")
    view = CustomerPortalView(
        tk_root,
        context.services,
        principal,
        language="en",
        runner=ImmediateTaskRunner(),
    )
    view.pack(fill="both", expand=True)
    tk_root.update_idletasks()
    assert len(view.body.winfo_children()) == 4
    view.destroy()
