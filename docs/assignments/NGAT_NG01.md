# Phiếu giao việc — Ngát — NG-01

## Mục tiêu

Tạo bộ theme/component dùng chung để Hoàng Anh làm Login và Ngát làm các màn nghiệp vụ. Dùng nguyên `03_UI_THEME.md` và `../07_DTO_UI_HANDOFF.md` v1; không chờ backend thật.

## Làm ngay

1. `src/cyberhub_manager/ui/theme.py`: Cyber Ops Dark, toàn bộ màu/font/spacing/kích thước theo tài liệu theme; view không hard-code token.
2. Thêm `ui/state.py`: LOADING/READY/EMPTY/ERROR; form có cờ is_submitting riêng. Không trộn ViewState với MachineStatus/AccountStatus.
3. Thêm `ui/formatters.py`: format tiền, datetime UTC → Asia/Ho_Chi_Minh, duration; API theo bản v1.
4. Hoàn thiện `ui/components/form_field.py`, `data_table.py`, `machine_card.py`, `toast.py`.
5. Thêm `ui/components/action_button.py`, `status_badge.py`, `confirm_dialog.py` theo API mục 7 bản v1.
6. Thêm `ui/component_gallery.py` để mở catalog độc lập, không sửa production app.py hay Login chỉ để chạy gallery.
7. Thêm `docs/diagrams/ui_wireflow.md`: luồng Login → App shell → Dashboard/Khách hàng/Hóa đơn/Doanh thu/Quản lý máy → Logout; phân quyền action/menu theo theme và contract.

## Đầu vào và dependency

- Có thể làm theme, layout và component nhận input được tiêm từ ngoài ngay.
- Dùng DTO chính thức tại `domain/dtos.py`, entity/enum của Linh sau khi được bàn giao. Trong lúc chờ có thể tiêm sample từ gallery; không tạo bản sao DTO trong UI.
- Linh bàn giao ServiceBundle và `build_mock_services` trong LI-02. Sau đó nối gallery vào mock chung, không tự thêm mock service khác trong từng view.
- MachineCard đọc customer từ active_session.session, số dư cảnh báo từ active_session.projected_balance. UI không tự tính phí/thời gian làm tròn/số dư tối thiểu.

## Gallery phải cho xem được

- Button bình thường/hover/disabled/busy, input focus/error/password hiện-ẩn, dialog confirm, toast.
- Bảng READY/LOADING/EMPTY/ERROR, cột tiền căn phải, chọn dòng theo ID.
- Card AVAILABLE/IN_USE/MAINTENANCE, có label+icon; card PC02 projected_balance âm.
- Dữ liệu customer ACTIVE/INACTIVE và account ACTIVE/LOCKED hiển thị riêng.
- Role STAFF và MANAGER để thấy thay đổi action quản trị.
- SUCCESS/EMPTY/VALIDATION_ERROR/CONFLICT/UNAVAILABLE lấy từ mock của Linh.
- Thao tác submit thành công hoặc thất bại đều thoát busy; double click không gọi callback hai lần.

## Quy tắc triển khai

- API component theo mục 7 bản v1; callback nhận ID ổn định, không nhận vị trí dòng bảng.
- Nhãn/menu giao diện theo thiết kế đã chốt (tiếng Việt); thông báo phản hồi, validation, lỗi và xác nhận dùng tiếng Anh. Biến/code tiếng Anh; label không được thay bằng placeholder.
- Màu máy và nút theo theme, tiền `25.000 VND`, thời gian `HH:mm dd/MM/yyyy` theo giờ Việt Nam.
- Không import repository/SQL/connection vào UI. Không hiển thị raw exception/traceback.
- UI main thread chỉ xử lý widget; lời gọi chậm được tách phù hợp, kết quả đưa về bằng after. Hủy callback refresh khi đóng view.
- NG-01 không bao gồm làm toàn bộ Login, app shell hoặc màn nghiệp vụ. Login thuộc HA-11; NG-02/NG-03 bắt đầu sau khi chốt foundation contract.

## Nghiệm thu và bàn giao

- Chạy được `python -m cyberhub_manager.ui.component_gallery` mà không cần Docker hoặc `.env` sau khi cài dependencies.
- Gallery nối được ServiceBundle mock của Linh; bản bàn giao dùng đúng DTO chung (`SessionSummary`, `MachineSummary`, `CustomerSummary`, `CheckoutPreview`).
- Ảnh ở 1280×720 không cắt nút/chữ, có đủ success/empty/loading/error và các trạng thái máy.
- Tab/Enter dùng được; busy/validation giữ input và cho thử lại.
- Bàn giao bảng ngắn gồm component, cách khởi tạo, API/callback và ảnh minh họa để Hoàng Anh dùng làm Login.
- Bàn giao UI wireflow cho Linh/Hoàng Anh đối chiếu trước NG-02.

## Bảng bàn giao kỹ thuật Component dùng chung (Component Catalog)

Tài liệu bàn giao cho Hoàng Anh (dùng triển khai `HA-11 Login`) và Ngát (triển khai các màn nghiệp vụ `NG-02/NG-03`):

| Component | Constructor & Khởi tạo | Props / Thuộc tính | Phương thức & Callback | Trạng thái hỗ trợ | File ảnh minh chứng |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`ActionButton`** | `ActionButton(master, text, kind="primary", command=None, state="normal")` | `kind`: `"primary"`, `"secondary"`, `"success"`, `"danger"`, `"ghost"` | `set_busy(is_busy, busy_text="Processing…")`<br>`set_enabled(enabled)`<br>`is_busy`, `is_enabled` | Normal, Hover, Disabled, Busy (chống double-click) | `docs/screenshots/02_buttons_inputs.png` |
| **`FormField`** | `FormField(master, label, placeholder="", initial_value="", is_password=False)` | `label`, `is_password`, `placeholder` | `get_value() -> str`<br>`set_value(val)`<br>`set_error(msg \| None)`<br>`set_enabled(enabled)`<br>`focus()`<br>`bind_return(callback)` | Normal, Focus (viền Primary), Error (viền Danger đỏ), Disabled, Toggle password, Enter submit | `docs/screenshots/02_buttons_inputs.png` |
| **`DataTable`** | `DataTable(master, columns, rows, on_select=None)` | `columns`: `list[TableColumn]`<br>`rows`: `list[TableRow]` | `set_rows(rows)`<br>`set_state(state, message, on_retry)`<br>`get_selected_key()` | `READY`, `LOADING`, `EMPTY`, `ERROR` (kèm nút Retry), chọn dòng theo ID ổn định | `docs/screenshots/03_data_table.png` |
| **`StatusBadge`** | `StatusBadge(master, status: StrEnum)` | Nhận các enum: `MachineStatus`, `CustomerStatus`, `AccountStatus`, `EmployeeStatus`, `StoreStatus`, `SessionStatus`, `InvoiceStatus`, `Role` | `set_status(status)`<br>`current_status` | Token semantic (`SUCCESS`, `DANGER`, `WARNING`, `INFO`, `NEUTRAL`), phân nhánh loại enum tránh va chạm StrEnum | `docs/screenshots/04_badges_feedback.png` |
| **`MachineCard`** | `MachineCard(master, machine: MachineSummary, actor: EmployeeSession, on_open, on_checkout, on_maintenance)` | `machine`: DTO `MachineSummary`<br>`actor`: DTO `EmployeeSession` | `render(machine, actor)`<br>`set_busy(busy)`<br>`set_on_open(cb)`<br>`set_on_checkout(cb)`<br>`set_on_maintenance(cb)` | `AVAILABLE`, `IN_USE` (bình thường / âm tiền `projected_balance < 0`), `MAINTENANCE`. Nút *Bật lại* chỉ cho `MANAGER`/`ADMIN` | `docs/screenshots/01_machine_cards.png` |
| **`ConfirmDialog`** | `ConfirmDialog.ask(parent, title, message, confirm_label="Confirm", cancel_label="Cancel", is_danger=False)`<br>`ConfirmDialog.alert(parent, title, message, button_label="Close", is_danger=True)` | Modal chặn tương tác cửa sổ cha | `ask()` trả `bool`; `alert()` có một nút đóng và trả `None` | Xác nhận thao tác; cảnh báo conflict hoặc lỗi chặn luồng | `docs/screenshots/04_badges_feedback.png` |
| **`ToastManager`** | `ToastManager.show(parent, message, kind="info", duration_ms=3500)` | Stack góc trên bên phải (`anchor="ne"`, `relx=0.98`, `y` tăng dần) | Tự động biến mất sau `duration_ms` | `info`, `success`, `warning`, `error` | `docs/screenshots/04_badges_feedback.png` |

## Checklist nghiệm thu giao diện thật (Windows @ 1280×720)

- [x] **Kích thước & Layout:** Mở ứng dụng ở độ phân giải tối thiểu `1280×720`, kiểm tra tỉ lệ DPI 100% và 125%/150%:
  - Lưới `StatusBadge` xếp 2 dòng × 5 cột, không bị tràn hay cắt chữ.
  - Hàng nút Action và Dialog hiển thị đầy đủ, không bị rớt dòng.
- [x] **Nút Disabled & Busy:** Tab 2 hiển thị rõ ràng nút ở trạng thái `disabled` và nút chuyển sang `busy` (*"Processing..."*), tự động phục hồi nhãn gốc sau tác vụ.
- [x] **Điều hướng bàn phím:** Dùng phím `Tab` để nhảy tuần tự qua các FormField và `Enter` để kích hoạt submit (đã triển khai `FormField.bind_return()` và gắn trên 4 trường form Demo tạo khách hàng; test `test_form_field_bind_return` xác nhận binding được đăng ký).
- [x] **Kịch bản Mock:** Đổi qua 5 kịch bản (`SUCCESS`, `EMPTY`, `VALIDATION_ERROR`, `CONFLICT`, `UNAVAILABLE`) kiểm chứng xử lý dữ liệu và thông báo lỗi:
  - `SUCCESS`: Thao tác mở máy, nạp dữ liệu DataTable, submit tạo khách hàng đều thành công.
  - `EMPTY`: Danh sách máy và DataTable khách hàng hiển thị ViewState.EMPTY ("No matching data found").
  - `VALIDATION_ERROR`: Submit form Demo tạo khách hàng (Tab 2) kích hoạt `create_customer` ném `ValidationError`, hiển thị lỗi viền đỏ và text tiếng Anh đúng từng trường (`phone`, `password`), bắn Toast tiếng Anh tổng quát, giữ nguyên dữ liệu nhập và phục hồi `is_busy=False` qua `finally`.
  - `CONFLICT`: Trùng trường form hiển thị lỗi tại field và một Toast tiếng Anh; tranh chấp máy/phiên hiển thị Warning Dialog tiếng Anh rồi refresh danh sách máy, không hiện Toast trùng nội dung.
  - `UNAVAILABLE`: DataTable và lưới máy bắt lỗi `ServiceUnavailableError`, hiển thị thông báo lỗi tiếng Anh kèm nút Retry.
- [] **Ảnh minh chứng bàn giao:** Đã cập nhật ảnh thể hiện source mới nhất (sau khi đổi thông báo tiếng Anh, thêm form Demo tạo khách hàng, và hoàn thiện action bảo trì):
  - `docs/screenshots/01_machine_cards.png`: Thẻ PC02 âm tiền, phân quyền STAFF/MANAGER.
  - `docs/screenshots/02_buttons_inputs.png`: Form Demo tạo khách hàng kết nối ServiceBundle, nút disabled/busy, trường mật khẩu hiện/ẩn và các nút thao tác.
  - `docs/screenshots/03_data_table.png`: Bảng 4 trạng thái ViewState, căn phải cột tiền.
  - `docs/screenshots/04_badges_feedback.png`: 10 biến thể StatusBadge, Toast 4 màu, ConfirmDialog.
