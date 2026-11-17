# Web khách hàng — đợt 1

Cổng `/customer` được nâng cấp với bốn màn: **Tổng quan cá nhân**, **Ưu đãi dành cho bạn**,
**Lịch sử của tôi**, **Thông báo**. Dùng chung dịch vụ và dữ liệu P1 của desktop;
giao diện hỗ trợ VI/EN, điện thoại và cập nhật mỗi 30 giây khi trang đang mở.

## Chạy thử nhanh

Chạy từ thư mục `cyberhub-manager` gốc:

```powershell
$env:CYBERHUB_WEB_MODE="demo"
.\.venv\Scripts\python.exe -m cyberhub_manager.web --port 8000
```

Mở <http://127.0.0.1:8000/customer>, đăng nhập `nguyenvanan` / `demo123`.
Tài khoản `lethibinh` / `demo123` có phiên đang chơi và cảnh báo thiếu số dư.
Tài khoản `hoangvanem` / `demo123` có phiên đang chơi và hóa đơn thanh toán có tiền bù.

Cổng khách hàng demo có hai ưu đãi mẫu 100.000/10% và 200.000/20%, tự tạo trong
workspace demo đó. Dữ liệu demo độc lập giữa các lần đăng nhập, không ghi vào MySQL.
Khởi động lại server hoặc đăng nhập lại tạo workspace demo mới, gồm trạng thái thông báo mới.

## Nghiệp vụ được áp dụng

| Phần | Quy tắc |
|---|---|
| Số dư | Tổng số dư = số dư chính + khuyến mãi. Chưa trừ phí phiên đang chơi. |
| Chi tiêu | Tổng `usage_cost` của hóa đơn **PAID**, trong khoảng ngày đang chọn. Loại **VOID**. |
| Tiền bù | Đã nằm trong phí hóa đơn, không cộng thêm vào chi tiêu hoặc thống kê tiền nạp. |
| Tiền nạp | Chỉ cộng giao dịch **TOP_UP**; loại **PROMOTION**, **DEBT_SETTLEMENT** và **USAGE_PAYMENT**. |
| Khuyến mãi đã dùng | Tổng `bonus_used` được chụp trên các hóa đơn PAID trong kỳ. Phần còn lại là tiền chính và tiền bù. |
| Thời gian sử dụng | Số giây thực tế của phiên ACTIVE/COMPLETED nằm trong kỳ; phiên qua ranh giới chỉ tính phần giao nhau. Không tính CANCELLED. |
| Phiên đang chơi | Tính phí theo quy tắc làm tròn phút/VND hiện có; hiển thị số dư dự kiến và thời gian còn lại ước tính. |
| Biểu đồ | Chọn 7/30/90 ngày; bao gồm ngày không phát sinh; đổi giữa phí sử dụng và tiền nạp; chạm cột xem giá trị. |
| Phạm vi | Thống kê toàn bộ hoạt động của chính khách trên các cơ sở. Bộ chọn cơ sở ở Ưu đãi chỉ đổi ưu đãi và kết quả xem trước. |
| Ngày | Giờ Việt Nam (UTC+7), bộ lọc lịch sử bao gồm cả hai ngày. Phiên lọc theo ngày bắt đầu. |

Ưu đãi chỉ hiện khi cơ sở đang hoạt động và chính sách có hiệu lực `[bắt đầu, kết thúc)`.
Mỗi lần nạp áp dụng **một mốc cao nhất đủ điều kiện**, không cộng dồn nhiều chính sách.
Nếu cùng mốc, chính sách của cơ sở được ưu tiên hơn chính sách toàn hệ thống.
Số tiền thưởng làm tròn xuống đến VND. Các lần nạp riêng không cộng dồn để đạt mốc.

Công cụ **Xem quyền lợi** dùng cùng hàm tính thưởng với nhân viên. Nó không tạo giao dịch,
không tăng số dư và không giữ ưu đãi. Nhân viên xác nhận tiền nạp tại quầy, tính lại ưu đãi
tại thời điểm đó. Tiền thưởng được dùng trước và không đổi thành tiền mặt.

Lịch sử có ba loại: giao dịch ví, hóa đơn và phiên sử dụng. Lọc theo ngày/loại/trạng thái,
phân trang ở máy chủ, tra cứu toàn bộ dữ liệu thay vì chỉ 100 bản ghi gần nhất.
Khách chỉ xuất/in hóa đơn thuộc mình, gồm nhãn riêng khi hóa đơn đã hủy.

## Thông báo

- Tiền nạp thành công, tiền khuyến mãi được cộng, hóa đơn PAID/VOID.
- Ưu đãi đang có hiệu lực, theo phạm vi cơ sở hoạt động; thay đổi nội dung chính sách tạo thông báo mới.
- Phiên đang chơi còn tối đa 15 phút ước tính hoặc đã thiếu số dư.
- Khi không có phiên đang chơi: cảnh báo tổng số dư dưới 10.000 VND.

Màn hình giới hạn 50 thông báo: giao dịch/hóa đơn trong 30 ngày gần nhất, cùng ưu đãi và
cảnh báo hiện tại; ưu tiên cảnh báo. Số chưa đọc thuộc danh sách này. Cảnh báo là ước tính,
không tự ngắt máy. Đây là thông báo trong ứng dụng, cập nhật khi mở trang.

Đọc từng thông báo hoặc toàn bộ danh sách đang hiển thị. Trạng thái lưu theo tài khoản
trong `customer_notification_reads`, tồn tại qua đăng xuất/khởi động lại ở chế độ MySQL.
Sự kiện mới đến sau lần đánh dấu vẫn chưa đọc. Mọi thao tác kiểm tra lại quyền sở hữu và
trạng thái tài khoản, POST yêu cầu CSRF; khách không gọi được API nhân viên.

## Chạy cùng dữ liệu thật

Sao lưu bằng quy trình backup hiện có, giữ cấu hình `.env`, rồi chạy:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
```

Migration mới `004_customer_notifications.sql` chỉ thêm bảng lưu trạng thái đọc.
Không tự tạo ưu đãi/tài khoản hoặc thay đổi số dư thật. Các migration đã áp dụng giữ nguyên checksum.
Khởi động lại web sau khi cập nhật, dùng `CYBERHUB_WEB_MODE=mysql` và khóa phiên hiện có.
Desktop và web cùng MySQL sẽ nhìn thấy chung tiền nạp, khuyến mãi và hóa đơn.

## Kiểm tra giao diện

1. Tổng quan: đổi 7/30/90 ngày, đổi loại biểu đồ, chọn từng cột và đối chiếu hóa đơn PAID.
2. Ưu đãi: chọn cơ sở, nhập 150.000 với mốc 100.000/10%; nhận 15.000 tiền thưởng.
   Với mốc tiếp theo 200.000, gợi ý tăng chính lần nạp này 50.000.
3. Lịch sử: lọc riêng tiền nạp/hóa đơn hủy, đổi ngày, xem trang tiếp và thử xuất/in hóa đơn.
4. Thông báo: đánh dấu đã đọc, tải lại; với MySQL, đăng xuất/đăng nhập lại vẫn giữ trạng thái đọc.
5. Thử `lethibinh` để xem cảnh báo thiếu số dư phiên chơi; đối chiếu phí và thời gian dự kiến.
6. Chuyển EN ở cả bốn màn, kiểm tra màn hình điện thoại 390px và các trường hợp chưa có dữ liệu.

Kiểm tra tự động trình duyệt tùy chọn (cần Playwright và Chromium cài cục bộ):

```powershell
.\.venv\Scripts\python.exe scripts/check_customer_portal_ui.py
```

Công cụ tạo HTTP server ở cổng tạm và tự đóng sau kiểm tra, chỉ dùng demo.
