# P1 — Desktop và Web

Triển khai trên nhánh `feat/p1-desktop-web`, nền `develop` tại `2424c12`. Không phụ thuộc 5 PR UI cũ.

## Chạy thử ngay, không cần MySQL

Tại thư mục `cyberhub-manager` gốc:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[web,dev]"
python -m cyberhub_manager.app --mock
```

Web trong terminal thứ hai:

```powershell
$env:CYBERHUB_WEB_MODE="demo"
python -m cyberhub_manager.web --port 8000
```

Mở `http://127.0.0.1:8000` cho nhân viên; `http://127.0.0.1:8000/customer` cho khách.
Desktop có nút **Khách hàng · Xem số dư** trên màn đăng nhập.

| Vai trò | Tài khoản demo | Mật khẩu |
|---|---|---|
| Admin | `admin01` | `demo123` |
| Manager | `quanly01` | `demo123` |
| Staff | `nhanvien01` | `demo123` |
| Khách hàng | `nguyenvanan` | `demo123` |

Desktop demo dùng chung dữ liệu trong một lần chạy. Mỗi lần đăng nhập web demo có bộ dữ liệu độc lập;
khởi động lại hoặc đăng nhập mới sẽ tạo lại dữ liệu. Muốn kiểm tra nhân viên nạp tiền và khách thấy ngay
trên máy khác, dùng chế độ MySQL với cùng database. Mật khẩu demo trên không được thêm vào MySQL.

## Quy tắc nghiệp vụ

* `balance` giữ nghĩa **tổng số dư sử dụng** để tương thích P0. `bonus_balance` là ví thưởng;
  `cash_balance = balance - bonus_balance` là số dư chính. Dữ liệu cũ có thưởng bằng 0.
* Mỗi lần nạp chỉ áp dụng một chính sách đang bật, đúng cơ sở hoặc toàn hệ thống, đang hiệu lực.
  Chọn mốc nạp cao nhất không vượt số tiền nạp; nếu bằng mốc thì chính sách cơ sở được ưu tiên.
  Thưởng = phần nguyên của `tiền nạp × phần trăm / 100`, không cộng dồn các mốc.
* Hiệu lực gồm thời điểm bắt đầu, không gồm thời điểm kết thúc. Nhập giờ Việt Nam ở hai giao diện;
  database lưu UTC. Hai chính sách cùng phạm vi, cùng mốc không được chồng thời gian.
* Top-up ghi tiền chính và thưởng bằng hai giao dịch trong cùng transaction. Chính sách được tính lại
  khi lưu; xem trước không giữ chỗ chính sách. Tiền bù nợ ở checkout không được hưởng thưởng nạp.
* Checkout khóa tài khoản, tính lại phí theo giờ server, trừ thưởng trước rồi số dư chính.
  Khoản thưởng đã dùng được chụp vào hóa đơn. Không có thao tác rút/chuyển thưởng thành tiền mặt.
  Tiền thừa chỉ tính từ tiền mặt khách đưa để bù thiếu, không lấy từ ví thưởng.
* Giữ quy tắc P0: khách có thể nạp để trả nợ dù tài khoản bị khóa; không mở phiên mới nếu khách/tài khoản
  không hoạt động; checkout phải bù đúng khoản thiếu để số dư cuối không âm.
* Ví khách dùng chung giữa các cơ sở. Máy, phiên, hóa đơn, doanh thu và chính sách cơ sở được giới hạn
  theo cơ sở đang vận hành. Mã máy và tên đăng nhập vẫn duy nhất toàn hệ thống theo schema hiện có.

## Phân quyền

| Chức năng | STAFF | MANAGER | ADMIN |
|---|---|---|---|
| Tra cứu/tạo/sửa khách, nạp tiền, mở phiên, thanh toán | Cơ sở được giao | Cơ sở được giao | Cơ sở đang chọn |
| Xuất/in hóa đơn, xem doanh thu | Cơ sở được giao | Cơ sở được giao | Cơ sở đang chọn |
| Quản lý máy, khóa/mở khách | Không | Cơ sở được giao | Cơ sở đang chọn |
| Quản lý nhân viên | Không | Chỉ STAFF ở cơ sở được giao | Toàn hệ thống |
| Quản lý khuyến mãi | Không | Chỉ chính sách cơ sở được giao | Cơ sở hoặc toàn hệ thống |
| Thêm/sửa/ngừng cơ sở, đổi cơ sở vận hành | Không | Không | Có |
| Cổng khách hàng | Chỉ chính tài khoản khách được đăng nhập; không có quyền nhân viên |||

Quyền được kiểm tra ở service, không chỉ ẩn nút. Không tự khóa, hạ quyền hoặc chuyển cơ sở của chính mình.
Hệ thống phải còn quản trị viên hoạt động; không ngừng cơ sở đang vận hành, có phiên mở hoặc có Admin hoạt động.
Ngừng/khóa giữ nguyên lịch sử, không xóa tài khoản hay cơ sở. Mật khẩu mới được băm bcrypt; để trống khi sửa
nhân viên sẽ giữ mật khẩu hiện tại. Thay đổi quản trị được ghi `management_audit`, không ghi mật khẩu.

## Nâng cấp database đang dùng

1. Sao lưu database bằng quy trình backup hiện tại và đóng các ứng dụng cũ trước khi migrate.
2. Giữ `.env` hiện có. Chạy `python scripts/init_db.py` để áp dụng migration P1 và `004_customer_notifications.sql`.
   Không sửa checksum của migration 001/002. MySQL DDL tự commit, nên phục hồi bản sao lưu nếu migration
   bị gián đoạn; không tự chạy lại phần ALTER đã áp dụng khi chưa kiểm tra `schema_migrations`.
3. Nếu chưa có Admin, tạo **tài khoản mới** qua công cụ bootstrap, dùng mã cơ sở đang hoạt động:

```powershell
python scripts/bootstrap_admin.py --database cyberhub_manager --store MA_CO_SO --username admin.user --name "Quản trị CyberHub"
```

Công cụ hỏi mật khẩu riêng, đối chiếu đúng database và từ chối nếu đã có Admin hoạt động.
Không tự nâng quyền nhân viên cũ. Sau đó Admin thêm nhân viên/cơ sở/chính sách trên giao diện.

Desktop MySQL: `python -m cyberhub_manager.app`.
Web MySQL: đặt `CYBERHUB_WEB_MODE=mysql` và `CYBERHUB_SECRET_KEY` ngẫu nhiên ổn định tối thiểu 32 ký tự,
rồi chạy `python -m cyberhub_manager.web`. Hai bản phải dùng cùng cấu hình MySQL để chia sẻ dữ liệu.
Giữ thiết lập HTTPS/cookie/proxy trong hướng dẫn triển khai web hiện có khi đưa lên hosting.

## Kiểm tra UI

1. Admin: mở **Khuyến mãi**, tạo mốc 100.000 / 10%, hiệu lực bao gồm hiện tại, đúng cơ sở hoặc toàn hệ thống.
2. **Khách hàng → Nạp tiền**: nhập 100.000; xem trước thưởng 10.000; xác nhận và kiểm tra hai ví/lịch sử.
3. Mở phiên rồi thanh toán: phí nhỏ hơn hoặc bằng 10.000 phải dùng hoàn toàn ví thưởng; phí lớn hơn dùng thêm ví chính.
4. **Hóa đơn → Xuất/In**: HTML/CSV; cửa sổ biên lai dùng Ctrl+P để in hoặc lưu PDF. Hóa đơn hủy có nhãn riêng.
5. Admin bấm tên cơ sở ở thanh trên, chọn cơ sở khác; danh sách máy/hóa đơn/doanh thu đổi theo cơ sở.
6. Tạo nhân viên STAFF và thử đăng nhập. Manager không được cấp MANAGER/ADMIN hoặc sửa nhân viên cơ sở khác.
7. Khách đăng nhập cổng riêng: xem ví và xuất/in hóa đơn của mình. Desktop hiển thị 100 bản ghi gần nhất;
   web có dashboard, ưu đãi, lịch sử phân trang toàn bộ dữ liệu và thông báo theo [hướng dẫn đợt 1](CUSTOMER_PORTAL_PHASE1.md).
8. Chuyển VI/EN ở các màn mới; kiểm tra cửa sổ desktop 1100×650 và web trên điện thoại.

Không có chính sách khuyến mãi mặc định tự kích hoạt trên dữ liệu thật. Tài khoản/cơ sở mẫu chỉ ở chế độ demo.
