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
- Text tiếng Việt, biến/code tiếng Anh; label không được thay bằng placeholder.
- Màu máy và nút theo theme, tiền `25.000 VND`, thời gian `HH:mm dd/MM/yyyy` theo giờ Việt Nam.
- Không import repository/SQL/connection vào UI. Không hiển thị raw exception/traceback.
- UI main thread chỉ xử lý widget; lời gọi chậm được tách phù hợp, kết quả đưa về bằng after. Hủy callback refresh khi đóng view.
- NG-01 không bao gồm làm toàn bộ Login, app shell hoặc màn nghiệp vụ. Login thuộc HA-11; NG-02/NG-03 bắt đầu sau khi chốt foundation contract.

## Nghiệm thu và bàn giao

- Chạy được `python -m cyberhub_manager.ui.component_gallery` mà không cần Docker hoặc `.env` sau khi cài dependencies.
- Gallery nối được ServiceBundle mock của Linh; trong giai đoạn đầu có thể demo component tĩnh, nhưng bản bàn giao cuối phải dùng đúng DTO chung.
- Ảnh ở 1280×720 không cắt nút/chữ, có đủ success/empty/loading/error và các trạng thái máy.
- Tab/Enter dùng được; busy/validation giữ input và cho thử lại.
- Gửi bảng ngắn gồm component, cách khởi tạo, API/callback và ảnh minh họa để Hoàng Anh dùng làm Login.
- Bàn giao UI wireflow cho Linh/Hoàng Anh đối chiếu trước NG-02.

Nhánh gợi ý: `feature/NG-01-theme-components` từ develop. Nếu LI-01/LI-02 chưa có trên develop, vẫn làm phần không phụ thuộc import DTO trước; đồng bộ khi Linh bàn giao, không chép nguyên các file domain từ nhánh khác vào nhánh UI.
