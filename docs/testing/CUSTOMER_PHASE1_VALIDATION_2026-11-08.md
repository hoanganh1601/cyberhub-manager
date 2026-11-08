# Nghiệm thu web khách hàng — đợt 1, 08/11/2026

Triển khai trên nhánh `feat/p1-desktop-web`, tiếp nối P1 desktop/web.
Hướng dẫn chạy và quy tắc: [CUSTOMER_PORTAL_PHASE1.md](../CUSTOMER_PORTAL_PHASE1.md).

## Phạm vi đã kiểm tra

- Dashboard: ví chính/khuyến mãi, chi tiêu PAID, tiền nạp TOP_UP, thời gian thực trong kỳ,
  phiên đang chơi, biểu đồ 7/30/90 ngày có ngày trống và chọn cột.
- Không cộng hai lần tiền bù; VOID không làm tăng chi tiêu; phần bonus_used giữ đúng ảnh chụp hóa đơn.
- Lịch sử quá 100 bản ghi: phân trang và thống kê toàn bộ dữ liệu, không lấy tổng từ trang đang xem.
- Ranh giới 00:00 giờ Việt Nam; phiên đi qua ranh giới kỳ chỉ tính phần giao nhau.
- Ưu đãi: mốc cao nhất, không cộng dồn, ưu tiên local khi cùng mốc; kết thúc không bao gồm;
  chọn cơ sở; xem trước không làm đổi ví hoặc tạo giao dịch.
- Thông báo: giao dịch/ưu đãi/cảnh báo, đọc lặp không tạo trùng; không đọc hộ tài khoản khác;
  sự kiện mới hoặc mức cảnh báo chuyển từ thấp sang hết số dư vẫn chưa đọc.
- MySQL: trạng thái đọc tồn tại qua khởi tạo lại service, khóa tài khoản thu hồi quyền ngay.
- HTTP: phân biệt khách/nhân viên, từ chối tham số giả và CSRF sai/thiếu.
- Chromium: đăng nhập, đổi kỳ, khuyến mãi/xem trước, chuyển cơ sở, VI/EN, lọc lịch sử rỗng,
  in hóa đơn, đọc thông báo và tải lại; bốn màn không tràn ngang ở 390px, không có lỗi JavaScript.
- Đăng nhập `lethibinh` kiểm tra phiên PC02, số dư dự kiến âm và thông báo đã hết số dư.

## Kết quả tự động

- Toàn bộ unit suite: **1.026 passed** trước khi bổ sung thêm tình huống chuyển mức cảnh báo.
- Nhóm kiểm tra nghiệp vụ/API khách hàng cuối cùng: **27 passed**, bao gồm tình huống cảnh báo bổ sung.
- Nhóm hồi quy web/P1/nghiệp vụ cuối cùng: **88 passed**.
- Integration MySQL: **200 passed**; chạy trên container MySQL 8.4 riêng, cổng 3317,
  database `cyberhub_manager_test`. Hai kiểm tra tài liệu schema được cập nhật theo migration 004.
- Bộ kiểm tra trình duyệt `scripts/check_customer_portal_ui.py`: **PASS**.
- Python compile, JavaScript syntax, `pip check`, `git diff --check`: **PASS**.

## Database local

Đã xác nhận `.env` trỏ `cyberhub_manager` tại 3307, có migration 001–003 và chưa có tài khoản.
Sao lưu trước nâng cấp: `backups/cyberhub_manager-before-customer-phase1-20261108.sql.gz`
(bản sao lưu local, được gitignore).

Đã áp dụng `004_customer_notifications.sql`; chạy lại công cụ migration cho kết quả SKIP cả bốn migration.
Migration chỉ thêm bảng read receipts, không seed ưu đãi/tài khoản hoặc cập nhật số dư thật.
Đã kiểm tra giải nén và cấu trúc SQL của bản sao lưu. Preview demo local mở tại
`http://127.0.0.1:8000/customer`; database local thực chưa có tài khoản.

## Ảnh kiểm tra

- [Tổng quan desktop](customer-phase1/overview-desktop.png)
- [Ưu đãi desktop](customer-phase1/offers-desktop.png)
- [Lịch sử desktop](customer-phase1/history-desktop.png)
- [Thông báo desktop](customer-phase1/notifications-desktop.png)
- [Tổng quan mobile](customer-phase1/home-mobile.png)
- [Ưu đãi mobile](customer-phase1/offers-mobile.png)
- [Lịch sử mobile](customer-phase1/history-mobile.png)
- [Thông báo mobile](customer-phase1/notifications-mobile.png)
- [Phiên chơi và cảnh báo mobile](customer-phase1/live-session-mobile.png)

Thông báo là trong ứng dụng khi mở trang, không phải push/email. Tiền nạp được xác nhận tại quầy;
công cụ ưu đãi chỉ xem trước. In vật lý cần kiểm tra trên máy in thực tế; đã kiểm tra mở biên lai HTML.
