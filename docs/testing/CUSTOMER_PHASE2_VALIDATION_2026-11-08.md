# Nghiệm thu web khách hàng đợt 2 — 08/11/2026

Phạm vi theo lựa chọn của người dùng: chỉ xem số máy còn trống theo cơ sở/phòng thường/VIP,
tự cập nhật 5 phút/lần; thêm biểu đồ sử dụng và hồ sơ cá nhân.
Không có nghiệp vụ đặt/giữ chỗ trong đợt này.

## Kết quả

- Toàn bộ unit suite: **1.047 passed**.
- Toàn bộ integration suite trên MySQL 8.4 riêng: **202 passed**.
- Chromium kiểm tra đợt 1: **PASS** sau khi thêm ba mục mới.
- Chromium đợt 2: **PASS**, kiểm tra nhịp đọc API bằng đồng hồ trình duyệt giả lập,
  cơ sở/phòng, cache, biểu đồ, hồ sơ, đổi mật khẩu và phiên cũ, VI/EN, 390px, cấu hình phòng của quản lý.
- JavaScript syntax, Python compile, `pip check`, `git diff --check`: **PASS**.

## Nghiệp vụ đã đối chiếu

1. Số máy chỉ gồm máy active, AVAILABLE và không có usage session ACTIVE.
   Hai nhóm phòng có cả số 0 khi không có máy. Phản hồi khách không chứa mã máy/khách khác.
2. Máy ngừng phục vụ, bảo trì hoặc đang dùng không làm tăng số còn trống.
   Sửa phân phòng không thay đổi trạng thái, đơn giá hoặc ví; chỉ Manager/Admin cùng cơ sở được sửa.
3. Trình duyệt không gọi lại availability trước 300 giây; đến hạn gọi lại.
   Quay lại cơ sở có cache còn hạn không gọi thêm; chọn cơ sở khác có dữ liệu riêng.
4. Thời lượng được phân bổ qua nửa đêm/khung giờ, cắt theo kỳ; loại CANCELLED.
   Tổng ngày, giờ và ngày trong tuần khớp tổng giây; không lấy giới hạn 100 bản ghi làm tổng.
5. Sửa tên/số điện thoại yêu cầu mật khẩu hiện tại, kiểm tra định dạng/trùng số.
   Bỏ qua các trường giả mạo customer_id, balance, role; không thay đổi ví hoặc lịch sử tiền.
6. Mật khẩu mới được băm; phiên bản xác thực tăng, CSRF phiên hiện tại đổi;
   cookie cũ bị từ chối cả khi xuất hóa đơn. Tài khoản khóa hoặc principal giả không đọc/sửa được.

## Database local

Đã xác minh database `.env`: `cyberhub_manager`, cổng 3307, có migration 001–004 và 0 tài khoản.
Đã sao lưu và kiểm tra giải nén/cấu trúc SQL:
`backups/cyberhub_manager-before-customer-phase2-20261108.sql.gz` (gitignore).

Đã áp dụng `005_customer_phase2.sql`, chạy lại SKIP cả 5 migration.
Chỉ thêm ánh xạ phòng và auth_version; không seed hoặc phân loại VIP cho dữ liệu thật.
Smoke app/session chế độ MySQL local trả HTTP 200.

## Ảnh kiểm tra

- [Máy trống desktop](customer-phase2/availability-desktop.png)
- [Sử dụng desktop](customer-phase2/usage-desktop.png)
- [Hồ sơ desktop](customer-phase2/profile-desktop.png)
- [Máy trống mobile](customer-phase2/availability-mobile.png)
- [Sử dụng mobile](customer-phase2/usage-mobile.png)
- [Hồ sơ mobile](customer-phase2/profile-mobile.png)
- [Phân phòng cho quản lý](customer-phase2/room-settings-desktop.png)

Chạy lại: `python scripts/check_customer_phase2_ui.py` (cần Playwright/Chromium cục bộ).
Quy tắc và hướng dẫn: [CUSTOMER_PORTAL_PHASE2.md](../CUSTOMER_PORTAL_PHASE2.md).
