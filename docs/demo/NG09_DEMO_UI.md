# NG-09 — Demo UI: kịch bản, evidence và bàn giao

Tài liệu cho cả nhóm khi chuẩn bị buổi nghiệm thu: chạy demo thế nào, trình diễn theo thứ tự nào,
ảnh evidence nằm ở đâu, giới hạn nào cần nói trước, và việc gì còn phải làm ở LI-09 / HA-09.

## 1. Chạy demo

| Cách | Lệnh | Dùng khi |
|---|---|---|
| Desktop mock (có đăng nhập, không cần MySQL) | `python -m cyberhub_manager.app --mock` | `quanly01 / demo123` hoặc `nhanvien01 / demo123`; thêm `--lang en` để mở tiếng Anh |
| Desktop thật (MySQL + đăng nhập) | `docker compose up -d mysql` → migrate + seed theo `tests/manual/CHECKLIST.md` → `cyberhub-manager` | Đăng nhập `demo.manager` hoặc `demo.staff01` bằng mật khẩu đã chọn khi seed |
| Web demo | `python -m pip install -e ".[web]"` → `python -m cyberhub_manager.web --port 8000` | Mở `http://localhost:8000`; tài khoản mock giống desktop, dữ liệu tách theo phiên đăng nhập |

HA-11 đã nối Login ↔ AppShell và nguồn actor đáng tin cậy cho sáu service. Web MySQL dùng chung bootstrap/nghiệp vụ;
cấu hình triển khai trong [WEB_DEPLOYMENT.md](../WEB_DEPLOYMENT.md). Không nhầm mật khẩu seed với mật khẩu MySQL.

Dữ liệu mock (đồng hồ cố định 16:00 ngày 18/10/2026 giờ Việt Nam, đơn giá 10.000 VND/giờ, số dư tối thiểu 5.000 VND):

| Mã | Khách | Tình trạng dùng để demo |
|---|---|---|
| KH001 | Nguyễn Văn An | Đủ tiền, không có phiên → mở phiên thành công |
| KH002 | Lê Thị Bình | Đang chơi PC02, số dư 5.000 < phí 15.000 → checkout cần bù 10.000 |
| KH003 | Trần Quốc Cường | Tài khoản bị khóa → không mở được phiên, vẫn nạp được tiền |
| KH004 | Phạm Thị Dung | Ngừng hoạt động, số dư âm -5.000 (đỏ) |
| KH005 | Hoàng Văn Em | Đang chơi PC05, đủ tiền → checkout trừ thẳng số dư |
| PC03 | — | Đang bảo trì |

## 2. Kịch bản demo (~10 phút)

Đăng nhập bằng tài khoản quản lý. Mỗi bước ghi mã test case nghiệm thu tương ứng trong `tests/manual/CHECKLIST.md`.

1. **Tổng quan** (AC-01, AC-14): 5 KPI, tab lọc theo trạng thái, card máy có thời gian và số dư dự kiến; tự làm mới 15 giây.
2. **Khách hàng → Tạo khách hàng** (AC-04, AC-06): nhập SĐT 9 số, mật khẩu không khớp → viền đỏ + lỗi dưới ô; nhập hợp lệ → Toast, khách mới số dư 0 VND.
3. **Mở phiên cho khách mới** (AC-12): từ Tổng quan bấm "Mở phiên" trên PC01, gõ SĐT khách mới → hộp đỏ thiếu số dư, nút xác nhận bị khóa, có nút **Nạp tiền**.
4. **Nạp tiền ngay trong dialog** (AC-08): nạp 50.000 → dialog tự kiểm tra lại, chuyển xanh → Enter mở phiên (AC-11). Card PC01 chuyển "Đang dùng".
5. **Không cho mở phiên sai điều kiện** (AC-13): mở phiên với KH002 (đang chơi PC02) → hộp đỏ "Khách hàng đang có phiên khác…"; với KH003 → "Tài khoản khách hàng đã bị khóa".
6. **Thanh toán PC05** (AC-15): bản 1 cột, số dư đủ, nút đỏ → hóa đơn "Thanh toán thành công".
7. **Thanh toán PC02** (AC-16, AC-17): cần bù 10.000. Tiền mặt: nhập 9.000 (còn thiếu) rồi 20.000 (thừa 10.000); hoặc Chuyển khoản QR: phải tick xác nhận.
8. **Hóa đơn** (AC-18): hóa đơn vừa tạo đứng đầu danh sách, chi tiết đủ mã phiên, máy, thời lượng, tiền bù; lọc tab "Đã hủy" thấy hóa đơn VOID của KH004.
9. **Doanh thu** (AC-19): 4 KPI, bảng theo ngày có "HÔM NAY" và tỷ trọng %, chỉ tính hóa đơn ĐÃ THANH TOÁN; nhập "Đến ngày" nhỏ hơn "Từ ngày" → báo lỗi ngay trên ô.
10. **Quản lý máy** (AC-09, AC-10): thêm/sửa máy, bật/tắt bảo trì, ngừng sử dụng; máy đang dùng không bảo trì / ngừng sử dụng được.
11. **Khóa khách** (AC-07): khóa rồi mở khóa KH001; đăng nhập bằng nhân viên → không có nút Khóa, không có menu Quản lý máy (AC-03).
12. **Lỗi dịch vụ** (AC-20 → AC-22): trên môi trường demo riêng, ngắt MySQL (trên mock xem ảnh 18) → thông báo an toàn theo ngôn ngữ VI/EN đang chọn + nút Thử lại, không traceback; bật lại và thử lại.

Phím tắt nên giới thiệu: **Ctrl+F** tới ô tìm kiếm · **Esc** xóa ô tìm kiếm · **F5** làm mới màn hiện tại · **Ctrl+1..5** chuyển menu · trong dialog **Enter** xác nhận, **Esc** hủy.

## 3. Bộ ảnh evidence

Ảnh nằm ở `docs/screenshots/ng09/`, chụp lại bằng `python scripts/capture_ui_screens.py` (dữ liệu mock; không chạm chuột/bàn phím khi script chạy).
Ảnh mock là evidence cho **giao diện**; kết quả AC chính thức vẫn phải chạy trên app thật (mục 4).

| Ảnh | Nội dung | AC |
|---|---|---|
| `01_dashboard_manager.png` | Tổng quan, vai trò quản lý | AC-01, AC-14 |
| `02_dashboard_staff.png` | Tổng quan, vai trò nhân viên (không có menu Quản lý máy) | AC-03 |
| `03_customers.png` | Danh sách + chi tiết + giao dịch gần đây | AC-08 |
| `04_customer_create_validation.png` | Lỗi validation từng ô | AC-06 |
| `05_top_up.png` | Nạp tiền: chọn nhanh, phương thức, số dư mới | AC-08 |
| `06_customer_lock_confirm.png` | Xác nhận khóa khách | AC-07 |
| `07_machines.png` | Quản lý máy | AC-09, AC-10 |
| `08_open_session_eligible.png` | Mở phiên — đủ điều kiện | AC-11 |
| `09_open_session_insufficient.png` | Mở phiên — thiếu số dư, CTA Nạp tiền | AC-12 |
| `10_open_session_blocked.png` | Mở phiên — tài khoản bị khóa, không cho mở | AC-07, AC-13 |
| `11_checkout_balance_only.png` | Thanh toán trừ thẳng số dư | AC-15 |
| `12_checkout_cash.png` | Thanh toán cần bù — tiền mặt, tiền thừa | AC-16, AC-17 |
| `13_checkout_transfer_qr.png` | Thanh toán cần bù — chuyển khoản QR | AC-17 |
| `14_payment_receipt.png` | Hóa đơn sau thanh toán | AC-18 |
| `15_invoices.png` | Màn Hóa đơn + chi tiết | AC-18 |
| `16_reports.png` | Màn Doanh thu | AC-19 |
| `17_empty_search.png` | Empty state | AC-20 |
| `18_service_error_retry.png` | Error state + Retry, không lộ lỗi nội bộ | AC-20, AC-21, AC-22 |

Automated test đi kèm: `tests/unit/test_ng03…test_ng08_*.py`. Riêng `test_ng08_integration.py` chạy hết luồng
tạo khách → nạp tiền → mở phiên → thanh toán → hóa đơn → doanh thu qua UI trên mock.

## 4. Bàn giao cho LI-09 (chạy checklist thủ công)

- Chạy trên **app thật** qua entry point hiện tại; ghi người chạy/ngày/kết quả/evidence vào checklist. Automated test không thay cho ký nghiệm thu thủ công.
- AC-01, AC-02: kiểm tra đăng nhập sai/đúng và đăng xuất; ảnh Login hiện tại ở `docs/screenshots/login-stitch/`. Chụp lại bằng bản release khi ký nghiệm thu.
- AC-13 (trùng phiên do hai quầy) cần 2 cửa sổ app hoặc 2 máy cùng database; trên mock chỉ chụp được trường hợp chặn trước.
- AC-21 (Retry): dừng MySQL (`docker compose stop mysql`) khi đang ở màn, rồi bật lại và bấm Retry.
- AC-23 (double click): bấm liên tục nút xác nhận; nút chuyển "Processing…" và bị khóa tới khi xong.
- AC-24 (ngôn ngữ): ở VI, nhãn, Toast, hộp xác nhận và lỗi vận hành đều tiếng Việt; ở EN đều tiếng Anh. Mã lỗi ổn định, chi tiết kỹ thuật chỉ ghi log. Kiểm tra các luồng chính sau khi đổi ngôn ngữ.

## 5. Ghi chú đóng gói cho HA-09 / HA-11

- `app.py` cung cấp entry point hoàn chỉnh. `services/bootstrap.py` tạo ServiceBundle dùng chung desktop/web, không import Tk; actor bị xóa khi đăng xuất và được đối chiếu DB ở service thật.
- Package-data đã gồm logo PNG, font TTF và giấy phép OFL trong `ui/assets/fonts/`. Giữ các mục này khi build wheel; `load_stitch_fonts()` nạp font desktop.
- App cần màn hình ≥ 1280×720; không chạy headless.
- Phụ thuộc chạy: customtkinter, Pillow, mysql-connector-python, python-dotenv, bcrypt (đã có trong `pyproject.toml`).

## 6. Giới hạn đã biết (nói trước khi demo)

- **Mã QR chuyển khoản là hình minh họa**, không quét được; nhân viên xác nhận thủ công (POC, không tích hợp cổng thanh toán).
- **Font**: Inter / Space Grotesk đã đóng gói; việc hiển thị ở Windows với DPI 100%, 125%, 150% vẫn cần người nghiệm thu kiểm tra.
- **Màn Hóa đơn** không có thiết kế Stitch riêng; dựng theo cùng ngôn ngữ thiết kế với màn Khách hàng.
- Stitch có "Đã lưu trữ", "Hội viên VIP", ngày đăng ký: **không làm** vì ngoài phạm vi P0 / DTO không có dữ liệu.
- Tài khoản bị khóa **vẫn nạp tiền được** để trả nợ (quyết định LI-04), khác câu chữ gốc trong Stitch.
- Ngày lọc báo cáo nhập tay dạng `dd/mm/yyyy` (CustomTkinter không có date picker).
- Chưa có video demo: cần người quay màn hình theo kịch bản mục 2.
- Chạy test UI: không thao tác bàn phím/chuột lên các cửa sổ test bật lên — đóng cửa sổ test giữa chừng sẽ làm các test UI sau đó lỗi.
