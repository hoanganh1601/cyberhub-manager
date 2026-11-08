# Web khách hàng — đợt 2

Đợt này gồm **Máy trống**, **Sử dụng**, **Hồ sơ** trên cổng `/customer`, cùng phần
phân loại máy cho quản lý. Theo lựa chọn đã chốt, mục máy trống chỉ công bố số lượng
phòng thường/VIP tại cơ sở, không tạo đơn đặt hoặc giữ chỗ.

## Chạy và kiểm tra

Tại thư mục `cyberhub-manager` gốc:

```powershell
$env:CYBERHUB_WEB_MODE="demo"
.\.venv\Scripts\python.exe -m cyberhub_manager.web --port 8000
```

Mở <http://127.0.0.1:8000/customer>, tài khoản demo `nguyenvanan` / `demo123`.
Trên điện thoại, thanh điều hướng cuộn ngang để chọn đủ các mục.

1. **Máy trống**: cơ sở Cầu Giấy mẫu có 12 máy thường và 5 máy VIP còn trống.
   Chuyển cơ sở Hà Đông mẫu để kiểm tra trường hợp chưa có máy.
2. **Sử dụng**: chọn 7/30/90 ngày, chọn cột biểu đồ, xem phân bố 24 giờ, các ngày trong tuần và cơ sở.
3. **Hồ sơ**: thử đổi họ tên/số điện thoại bằng mật khẩu hiện tại; thử số trùng hoặc sai mật khẩu.
4. Đổi mật khẩu, kiểm tra phiên hiện tại vẫn truy cập được. Với dữ liệu MySQL, phiên cũ ở trình duyệt
   khác phải đăng nhập lại, mật khẩu mới dùng cho lần đăng nhập sau.
5. Chuyển VI/EN và kiểm tra cả ba màn ở độ rộng điện thoại 390px.

Demo có dữ liệu riêng từng lần đăng nhập; đăng xuất rồi đăng nhập tạo dữ liệu mẫu mới,
bao gồm mật khẩu demo ban đầu. Dùng MySQL để kiểm tra dữ liệu tồn tại giữa các lần đăng nhập và
chia sẻ với desktop/nhân viên.

## Số máy trống

- Chỉ cho xem cơ sở ACTIVE; tổng hợp riêng `STANDARD` (phòng thường) và `VIP`.
- Chỉ tính máy `is_active=1`, `status=AVAILABLE` và không có phiên ACTIVE.
  Máy bảo trì, đang dùng hoặc đã ngừng phục vụ không được tính là còn trống.
- Không công bố mã/tên từng máy, khách đang sử dụng hoặc thông tin phiên của người khác.
- Đọc khi mở màn hình/chọn cơ sở; tự cập nhật **mỗi 300 giây**. Không đi theo nhịp 30 giây của dashboard.
- Bộ nhớ đệm theo tài khoản và cơ sở; chuyển qua màn khác rồi quay lại trong 5 phút dùng lại số liệu còn hạn.
  Nút làm mới hoặc tải lại trang cho phép chủ động lấy ảnh chụp mới.
- Hiển thị thời điểm số liệu và lần cập nhật tiếp theo. Khi quay lại tab trình duyệt sau thời gian dài,
  lấy lại nếu dữ liệu quá 5 phút. Lỗi kết nối giữ mốc cũ và báo chưa cập nhật, không giả số 0.
- Số lượng là ảnh chụp tại thời điểm đọc; việc sắp xếp máy diễn ra tại quầy khi khách đến.

## Quản lý phân loại phòng

Web nhân viên: đăng nhập Manager/Admin → **Quản lý máy → Phân phòng máy**.
Chọn phòng thường hoặc VIP cho từng máy; lưu ngay và ghi `management_audit`.

Chỉ phân phòng máy tại cơ sở đang vận hành của người quản lý. STAFF và khách không có quyền sửa.
Máy còn phiên chạy phải kết thúc phiên trước khi đổi phòng. API kiểm tra lại quyền và trạng thái máy,
không dựa vào nút ẩn/khóa trên giao diện.

Máy chưa được phân loại được tính là phòng thường. Migration không tự suy đoán phòng VIP từ
đơn giá/tên máy hoặc tự phân loại dữ liệu thật. Phân loại không đổi đơn giá, trạng thái máy hoặc số dư.
Ánh xạ phòng được lưu trong `machine_room_types`; desktop/web dùng chung database sẽ có chung số máy.

## Biểu đồ sử dụng

- Lấy toàn bộ các phiên của chính khách có thời gian giao với kỳ, không giới hạn 100 bản ghi.
- Tính giây thực tế của ACTIVE/COMPLETED, không tính CANCELLED; phiên đang chạy chỉ tính tới thời điểm đọc.
- Chỉ lấy phần giao với kỳ 7/30/90 ngày và chia qua từng giờ/ngày theo giờ Việt Nam (UTC+7).
- Biểu đồ ngày có cả ngày 0 phút; phân bố 24 giờ là thời gian thực sự nằm trong từng khung giờ,
  không quy toàn bộ thời lượng cho giờ bắt đầu.
- Số phiên/trung bình/phiên dài nhất chỉ tính phần thời gian trong kỳ; không làm tròn thành phút tính tiền.
- Thống kê theo ngày trong tuần và cơ sở; không thay thế báo cáo chi tiêu/hóa đơn PAID của đợt 1.

## Hồ sơ và mật khẩu

Khách chỉ sửa họ tên/số điện thoại của chính mình, xác nhận bằng mật khẩu hiện tại.
Họ tên 2–100 ký tự; điện thoại 10 chữ số, bắt đầu bằng 0 và duy nhất toàn hệ thống.
Không cho sửa mã, username, trạng thái, vai trò hoặc số dư qua API hồ sơ.

Đổi mật khẩu yêu cầu mật khẩu hiện tại và xác nhận khớp. Dùng cùng giới hạn tài khoản khách hiện có:
tối thiểu 6 ký tự, tối đa 72 byte UTF-8; mật khẩu mới khác mật khẩu cũ. Lưu bcrypt.
`accounts.auth_version` tăng sau đổi mật khẩu; phiên hiện tại nhận phiên bản mới và CSRF mới,
các phiên cũ bị từ chối ở mọi API khách hàng, kể cả xuất hóa đơn. Các form không lưu mật khẩu vào
localStorage và không bị tự cập nhật khi đang nhập thông tin.

## Cập nhật MySQL

Giữ `.env`, sao lưu database theo quy trình hiện có, chạy:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
```

Migration `005_customer_phase2.sql` thêm ánh xạ phòng và phiên bản xác thực; không thay đổi số dư
hoặc tự tạo tài khoản/ưu đãi thật. Khởi động lại web sau khi migrate.

Kiểm tra trình duyệt tùy chọn, cần Playwright/Chromium cục bộ:

```powershell
.\.venv\Scripts\python.exe scripts/check_customer_phase2_ui.py
```

Script dùng HTTP server tạm và dữ liệu demo riêng; kiểm tra nhịp 5 phút bằng đồng hồ trình duyệt giả lập.
