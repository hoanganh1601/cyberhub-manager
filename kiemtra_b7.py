"""Kiểm tra nhanh Bước 7: tạo Dashboard với dữ liệu mock và in kết quả."""
from unittest.mock import patch

import customtkinter as ctk

from cyberhub_manager.domain.enums import MachineStatus
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui import dashboard_view
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner

services = build_mock_services()
session = services.auth.login("quanly01", DEMO_PASSWORD)
codes = {m.machine_code: m.machine_id for m in services.machines.list_machines(session.store_id)}

root = ctk.CTk()
context = ViewContext(services=services, session=session, language="vi", navigate=lambda key: True)
view = dashboard_view.DashboardView(root, context, runner=ImmediateTaskRunner())

print("1. Trang thai :", view.state.value)
print("2. KPI        :", {k: v.cget("text") for k, v in view._kpi_labels.items()})
print("3. Chan trang :", view._count_label.cget("text"))

view.set_status_filter(MachineStatus.IN_USE)
print("4. Tab dang dung:", view._tab_buttons[MachineStatus.IN_USE].cget("text"), "->", len(view.visible_machine_ids), "may")
view.set_status_filter(None)

view.handle_search("pc03")
print("5. Tim 'pc03' :", len(view.visible_machine_ids), "may")
view.handle_search("")

card = view.card_for(codes["PC02"])
print("6. Nut PC02   :", card.action_button.cget("text"))

with patch.object(dashboard_view.ToastManager, "show") as toast:
    view.card_for(codes["PC01"])._on_click()
    print("7. Mo phien PC01 ->", toast.call_args.args[1])

with patch.object(dashboard_view.ConfirmDialog, "ask", return_value=True), patch("cyberhub_manager.ui.feedback.ToastManager.show"):
    view.card_for(codes["PC03"])._on_click()
print("8. Sau khi ket thuc bao tri PC03: bao tri =", view._kpi_labels["maintenance"].cget("text"),
      "| may trong =", view._kpi_labels["available"].cget("text"))

print("9. Co lich tu lam moi:", view.has_scheduled_refresh)
view.shutdown()
print("10. Sau shutdown con lich:", view.has_scheduled_refresh)
root.destroy()
