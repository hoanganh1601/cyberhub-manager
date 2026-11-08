# Nghiệm thu avatar và thành viên — 09/11/2026

Phạm vi: menu avatar góc phải, cập nhật/xóa ảnh, hồ sơ/đổi mật khẩu qua menu; điểm thưởng,
hạng thành viên và ưu đãi theo hạng/điểm/từng khách. Chính sách mặc định đã được người dùng chọn:
10.000 VND chi tiêu hợp lệ = 1 điểm; các mốc hạng 0/1/3/5 triệu VND, cho phép cấu hình.

## Kết quả

- Toàn bộ unit suite: **1.068 passed**.
- Toàn bộ integration suite, MySQL 8.4 riêng ở cổng 3317: **205 passed**.
- Sau khi bổ sung khóa đọc hiện hành ở bước xác nhận nạp: **83 unit + 7 integration passed**.
- Kiểm tra trình duyệt đợt 1/2: **PASS** sau khi chuyển hồ sơ vào avatar và thêm ưu đãi cá nhân.
- Kiểm tra trình duyệt đợt 3: **PASS** — menu/bàn phím, tải/xóa ảnh, hồ sơ, điểm/hạng,
  quote riêng, cấu hình Admin, điều kiện đối tượng, EN và 390px; không có JavaScript error.
- Python compile, JavaScript syntax, `pip check`, schema dictionary và `git diff --check`: **PASS**.

## Các tình huống nghiệp vụ

1. Chỉ phần `usage_cost - bonus_used` tạo điểm/chi tiêu hạng; TOP_UP không tạo điểm,
   settlement không được cộng lại. Làm tròn xuống từng hóa đơn.
2. Điểm/đơn vị/phiên bản được chụp trong transaction tạo hóa đơn; đổi cấu hình không đổi điểm cũ.
3. VOID có hiệu lực 0 điểm/chi tiêu xét hạng, giữ snapshot trong lịch sử; hạng và điều kiện ưu đãi giảm theo.
4. Mốc hạng đúng ở 1/3/5 triệu; cấu hình toàn hệ thống chỉ Admin được sửa, kiểm tra version chống ghi đè.
   Tạm dừng tích điểm giữ điểm cũ và vẫn tính chi tiêu hạng.
5. Khách chỉ xem/nhận ưu đãi đủ hạng, điểm, đối tượng, cơ sở và thời gian; không lộ ưu đãi riêng của người khác.
   Quote của khách/nhân viên và xác nhận nạp thống nhất; không cộng chồng chính sách.
6. Avatar được giải mã thật, kiểm tra kích thước/định dạng/animation, chuẩn hóa WebP 512×512;
   upload sai không ghi đè ảnh cũ. Multipart trên 16 KB được nhận ở route ảnh, vẫn giới hạn 2 MB.
7. Ảnh thuộc tài khoản, không nhận account_id từ client; khóa tài khoản/phiên cũ bị từ chối đọc/ghi.
   GET ảnh trả image/webp, no-store, nosniff. Ảnh tồn tại qua khởi tạo lại service MySQL.
8. Menu avatar giữ trạng thái khi thay đổi kích thước; Esc đóng, phím mũi tên chọn mục;
   hồ sơ không còn là tab chính trùng lặp. Giữ chức năng hồ sơ/mật khẩu đợt 2.
9. Xác nhận nạp đọc khóa chia sẻ chính sách và dữ liệu hóa đơn hiện hành sau khi khóa ví,
   tránh dùng snapshot cũ để xét điểm/hạng khi có thay đổi đồng thời.

## Database local

Đã xác minh `.env` trỏ `cyberhub_manager` tại 3307, migration 001–005 và 0 tài khoản.
Sao lưu local: `backups/cyberhub_manager-before-customer-phase3-20261109.sql.gz` (gitignore),
đã giải nén và kiểm tra cấu trúc SQL/thông báo hoàn tất dump.
Đã áp dụng migration 006, chạy lại công cụ migration SKIP cả 6 phiên bản.
Không tạo tài khoản/ưu đãi mẫu hoặc ghi tiền vào dữ liệu thật.

## Ảnh kiểm tra

- [Menu avatar desktop](customer-phase3/account-menu-desktop.png)
- [Cập nhật ảnh desktop](customer-phase3/avatar-editor-desktop.png)
- [Hồ sơ desktop](customer-phase3/profile-desktop.png)
- [Thành viên desktop](customer-phase3/membership-desktop.png)
- [Ưu đãi cá nhân](customer-phase3/personal-offer-desktop.png)
- [Thành viên mobile](customer-phase3/membership-mobile.png)
- [Menu avatar mobile](customer-phase3/account-menu-mobile.png)
- [Cấu hình thành viên](customer-phase3/membership-settings-desktop.png)

Ảnh avatar trong test là fixture chữ VA, không phải ảnh khách thật.
Hướng dẫn/quy tắc đầy đủ: [CUSTOMER_PORTAL_PHASE3.md](../CUSTOMER_PORTAL_PHASE3.md).
