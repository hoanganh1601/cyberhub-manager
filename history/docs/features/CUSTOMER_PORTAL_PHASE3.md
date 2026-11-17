# Web khách hàng — avatar và thành viên (đợt 3)

Hồ sơ chuyển vào menu ảnh đại diện tròn ở góc phải. Menu có chỉnh sửa hồ sơ, cập nhật ảnh,
thành viên, đổi mật khẩu và đăng xuất. Mục **Thành viên** trên thanh điều hướng hiển thị
điểm, hạng, tiến độ và lịch sử điểm theo hóa đơn.

## Chạy thử

Từ thư mục `cyberhub-manager` gốc:

```powershell
$env:CYBERHUB_WEB_MODE="demo"
.\.venv\Scripts\python.exe -m cyberhub_manager.web --port 8000
```

Mở <http://127.0.0.1:8000/customer>, tài khoản `nguyenvanan` / `demo123`.
Trong demo, tài khoản này có 5 điểm từ hai hóa đơn hợp lệ tổng 50.000 VND; hạng Đồng.
Một ưu đãi mẫu riêng cho khách này yêu cầu 5 điểm, nạp từ 300.000 tặng 25%.
Khách khác không xem/nhận ưu đãi đó. Ưu đãi mẫu chỉ ở workspace demo, không seed dữ liệu thật.

## Avatar và hồ sơ

1. Bấm avatar góc phải → **Cập nhật ảnh đại diện**.
2. Chọn JPEG/PNG/WebP tĩnh tối đa 2 MB và 16 triệu điểm ảnh; xem trước rồi lưu.
3. Ảnh được xoay theo EXIF, căn giữa thành vuông, chuyển WebP 512×512 và bỏ metadata gốc.
   Ảnh có nền trong suốt được ghép nền tối; không lưu tên hoặc đường dẫn file người dùng.
4. Ảnh cập nhật ở avatar góc phải, trong menu và trong hồ sơ; có thể xóa để trở lại chữ viết tắt.
5. Menu dùng được bằng bàn phím: Enter để mở, ↑/↓ để chọn, Esc để đóng.

Ảnh lưu trong MySQL theo tài khoản, chỉ chủ tài khoản đang hoạt động được đọc/ghi.
API không nhận ID tài khoản khác làm đích; POST/DELETE cần CSRF. Ảnh sai định dạng không ghi đè ảnh cũ.
Phản hồi ảnh có `no-store` và `nosniff`; tài khoản khóa hoặc phiên đã bị thu hồi không đọc lại được ảnh.
Giới hạn upload lớn hơn chỉ áp dụng cho route avatar, các JSON API giữ giới hạn nhỏ hiện có.

## Chính sách được người dùng phê duyệt

- Mỗi **10.000 VND phí chơi hợp lệ trên từng hóa đơn PAID = 1 điểm**, làm tròn xuống.
- Phí hợp lệ = `usage_cost - bonus_used`: tính phần tiền chính/tiền bù, không tính phần dùng từ ví thưởng.
- Tiền nạp không tạo điểm; tiền bù đã nằm trong phí hóa đơn nên không cộng lần nữa.
- Điểm không phải tiền trong ví, không quy đổi tiền mặt và không bị trừ khi xem/nhận ưu đãi.
- Hạng theo tổng chi tiêu hợp lệ của các hóa đơn PAID trên toàn hệ thống:

| Hạng | Mốc mặc định |
|---|---:|
| Đồng / Bronze | 0 VND |
| Bạc / Silver | 1.000.000 VND |
| Vàng / Gold | 3.000.000 VND |
| Kim cương / Diamond | 5.000.000 VND |

Mã nội bộ hạng Kim cương là `PLATINUM`. Không có thời hạn điểm/hạng hoặc giao dịch tiêu điểm trong đợt này.

Điểm, phần phí hợp lệ, số VND/điểm và phiên bản cấu hình được chụp trong **cùng transaction lập hóa đơn**.
Mỗi phiên chỉ có một hóa đơn nên không ghi nhận trùng. Hóa đơn VOID giữ ảnh chụp để giải thích lịch sử,
nhưng có hiệu lực 0 điểm và 0 chi tiêu xét hạng. Nếu hủy làm tổng giảm, hạng/điều kiện ưu đãi cũng giảm ngay.

Migration tính số liệu mở đầu cho hóa đơn đã có theo quy tắc 10.000 VND/điểm; chỉ thêm metadata,
không cộng tiền vào ví. Các hóa đơn mới chụp quy tắc tại thời điểm checkout trên cả desktop và web.

## Cấu hình quản trị

Web nhân viên: Admin → **Khuyến mãi → Cấu hình thành viên**.

- Đổi số VND/điểm và ba mốc hạng tăng dần.
- Bật/tắt tích điểm cho hóa đơn mới. Tắt không xóa điểm cũ; chi tiêu hợp lệ vẫn được tính cho hạng.
- Đổi tỷ lệ không tính lại điểm cũ; đổi mốc hạng phân loại lại theo chi tiêu hợp lệ hiện có.
- Mỗi lần lưu tăng `version`, ghi audit, từ chối ghi đè khi form cũ dùng phiên bản đã lỗi thời.
- Cấu hình toàn hệ thống chỉ Admin được sửa; Manager/Staff không được tự đổi.

## Ưu đãi cá nhân hóa

Trong form tạo/sửa khuyến mãi, Manager/Admin chọn:

- Hạng tối thiểu.
- Điểm tối thiểu.
- Một khách hàng riêng hoặc tất cả khách đủ điều kiện.

Mọi điều kiện phải đồng thời đúng; vẫn kiểm tra cơ sở hoạt động, khoảng hiệu lực và mốc tiền nạp.
Khách chỉ thấy chính sách đủ điều kiện, kể cả trong thông báo. Xem trước của khách/nhân viên và lúc
xác nhận nạp dùng cùng logic; dữ liệu hạng/điểm do máy chủ đọc lại, không nhận từ client.
Tài khoản ngừng hoạt động/khóa chỉ được nhận ưu đãi công khai khi nhân viên nạp để trả nợ theo nghiệp vụ cũ.

Thứ tự lựa chọn một chính sách: mốc nạp cao nhất → riêng cơ sở trước toàn hệ thống → riêng khách trước
ưu đãi theo hạng/điểm → hạng cao hơn → điểm cao hơn → ID mới hơn. Không cộng chồng thưởng.
Chính sách cùng mốc/phạm vi và cùng đối tượng không được trùng thời gian; đối tượng khác nhau được phép tồn tại.
Sửa chính sách cá nhân hóa bằng form desktop hiện có giữ nguyên các điều kiện đối tượng;
chỉnh điều kiện hạng/điểm/khách tại form web.

## Database và kiểm tra

Giữ `.env`, sao lưu bằng quy trình hiện có rồi chạy:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
```

Migration `006_customer_membership_avatar.sql` thêm cấu hình, ảnh đại diện, metadata điểm và điều kiện đối tượng.
Khởi động lại desktop/web sau cập nhật; hai bản cùng MySQL dùng chung quy tắc điểm và ưu đãi.
Demo tạo dữ liệu mới cho mỗi lần đăng nhập; dùng MySQL để kiểm tra ảnh/mật khẩu/điểm tồn tại lâu dài.

Kiểm tra trình duyệt tùy chọn (Playwright + Chromium):

```powershell
.\.venv\Scripts\python.exe scripts/check_customer_membership_ui.py
```
