# CyberHub Web — chạy local và triển khai

Ứng dụng web dùng Flask + HTML/CSS/JavaScript, logo và font được đóng gói trong repo.
Không cần Node, Tk, DISPLAY hoặc Windows để chạy server. Desktop CustomTkinter vẫn chạy
bằng lệnh cũ. Hai UI gọi chung `services/bootstrap.py` và các service/repository hiện có.

## Chạy ngay trên máy hiện tại

Trong thư mục repo, dùng Python >= 3.11:

```bash
source .venv/bin/activate
python -m pip install -e '.[web,dev]'
python -m cyberhub_manager.web --host 0.0.0.0 --port 8000
```

Mở `http://localhost:8000`. Máy khác cùng mạng mở `http://<IP-máy-server>:8000`.
Đây là địa chỉ mạng nội bộ; nó không phải một website public trên Internet.
Trên Windows dùng `.venv\Scripts\Activate.ps1` thay cho lệnh `source`.

Hoặc chạy bằng Docker (Gunicorn, không cần cài Python trên host):

```bash
docker build -f Dockerfile.web -t cyberhub-manager-web .
docker run -d --name cyberhub-web-preview -p 8000:8000 cyberhub-manager-web
```

Trên máy Linux hiện tại dùng `docker --context default` nếu Docker CLI đang chọn
context Docker Desktop nhưng Desktop không chạy. Dừng bản preview bằng
`docker --context default stop cyberhub-web-preview`.

Mặc định là **demo**: `quanly01 / demo123` cho quản lý, `nhanvien01 / demo123` cho nhân viên.
Mỗi phiên đăng nhập có bộ dữ liệu riêng. Dữ liệu này mất sau logout, hết hạn 8 giờ hoặc
server khởi động lại. Demo không dùng MySQL và không dùng để lưu dữ liệu thật.

## Chức năng

- Login/logout; chuyển toàn bộ nhãn và thông báo VI/EN.
- Tổng quan máy, tìm kiếm/lọc, tự làm mới mỗi 15 giây.
- Khách hàng: tạo, sửa, khóa/mở, số dư, nạp tiền và lịch sử.
- Quản lý máy: thêm, sửa đơn giá, bật/tắt bảo trì, ngừng sử dụng.
- Mở phiên qua preview điều kiện của service; checkout và biên nhận.
- Hóa đơn: lọc ngày/trạng thái, tìm mã/khách hàng, chi tiết, sao chép mã.
- Doanh thu: thống kê và biểu đồ, chỉ cộng hóa đơn PAID theo ngày UTC+7.
- Bố cục co giãn cho desktop, tablet và điện thoại.

Phương thức P0: `CASH` và `TRANSFER`, chuyển khoản được thu ngân xác nhận thủ công.
Chưa tích hợp cổng ngân hàng, QR động hay webhook xác nhận thanh toán.
Không có đăng ký nhân viên public; tài khoản nhân viên được quản trị/seed như desktop.

`settlement_amount` bằng đúng số thiếu do service tính. Tiền mặt khách đưa và tiền thừa
chỉ được tính ở UI; không cộng phần dư vào ví. Checkout tính lại trong transaction;
nếu số thiếu đã thay đổi, UI tải preview mới để người dùng xem và xác nhận lại.

## Render — bản demo nhanh

Repo đã có `render.yaml` để chạy bằng Gunicorn và kiểm tra `/healthz`.

1. Trong Render chọn **New → Blueprint**, kết nối repo GitHub này.
2. Chọn nhánh `develop`, file `render.yaml`, kiểm tra tài nguyên rồi Deploy.
3. Blueprint tạo `CYBERHUB_SECRET_KEY` riêng và bật cookie Secure cho HTTPS.
4. Sau khi trạng thái Live, mở URL `https://<tên-service>.onrender.com` do Render cấp.

Nếu tạo **Web Service** thủ công:

| Trường | Giá trị |
|---|---|
| Branch | `develop` |
| Runtime | Python 3 |
| Build | `pip install ".[web]"` |
| Start | `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 --access-logfile - cyberhub_manager.web.wsgi:app` |
| Health check | `/healthz` |
| Python | `3.13.14` |
| `CYBERHUB_WEB_MODE` | `demo` |
| `CYBERHUB_SECRET_KEY` | Chuỗi bí mật ngẫu nhiên >= 32 ký tự |
| `CYBERHUB_COOKIE_SECURE` | `true` |
| `CYBERHUB_TRUST_PROXY` | `true`, khi chạy sau reverse proxy của nền tảng |

Free web service của Render có thể ngủ khi không truy cập; demo trong bộ nhớ sẽ mất
khi service restart/spin down. Không dùng demo để lưu nghiệp vụ thật.
Nguồn: [Render Flask](https://render.com/docs/deploy-flask),
[Render Free](https://render.com/docs/free).

## Railway — phù hợp khi dùng MySQL thật

Railway có template MySQL cùng project; thuận tiện giữ backend Python và MySQL
trong một mạng riêng. Đây là lý do đề xuất Railway cho giai đoạn dữ liệu thật,
không phải khẳng định mọi trường hợp đều rẻ hơn Render. Kiểm tra gói và chi phí trước khi tạo tài nguyên.

1. Tạo project, Deploy from GitHub repo, chọn repo này và nhánh `develop`.
2. `railway.json` chọn `Dockerfile.web`; không cần build frontend riêng.
3. Nếu chỉ demo, đặt các biến web giống bảng trên và Generate Domain.
4. Nếu dùng dữ liệu thật, thêm MySQL vào cùng project, đặt `CYBERHUB_WEB_MODE=mysql`.
5. Ánh xạ các biến của service MySQL vào web service:

```dotenv
MYSQL_HOST=${{MySQL.MYSQLHOST}}
MYSQL_PORT=${{MySQL.MYSQLPORT}}
MYSQL_DATABASE=${{MySQL.MYSQLDATABASE}}
MYSQL_USER=${{MySQL.MYSQLUSER}}
MYSQL_PASSWORD=${{MySQL.MYSQLPASSWORD}}
```

`MySQL` là tên service; thay nếu bạn đặt tên khác. Dùng endpoint mạng riêng cho app,
không công khai root credential trong mã nguồn hoặc trình duyệt. Chọn cấu hình MySQL
8.4 tương thích schema và kiểm tra version trước khi chạy migration.

Nguồn: [Railway MySQL](https://docs.railway.com/databases/mysql),
[Railway config as code](https://docs.railway.com/config-as-code).

## Chuyển sang MySQL thật trên Render hoặc Railway

1. Dùng database riêng đã được backup nếu có dữ liệu. Đặt đủ 5 biến `MYSQL_*` như `.env.example`.
2. Đặt `CYBERHUB_WEB_MODE=mysql`, `CYBERHUB_SECRET_KEY` cố định, cookie Secure trên HTTPS.
3. Dùng shell/one-off command của nền tảng, trong `/app` nếu dùng Docker:

```bash
python -c 'from scripts.init_db import run_migrations; run_migrations()'
```

Migration không tự chạy khi khởi động web. Script ghi checksum và phát hiện schema
đã áp dụng dở dang; nếu báo bảng tồn tại thì cần kiểm tra dữ liệu trước, không reset tự động.

4. Nếu database mới và cần tài khoản ban đầu, chạy seed trong shell tương tác:

```bash
python -c 'from scripts.seed_db import run_seed; run_seed()'
```

Chương trình hỏi mật khẩu demo riêng. Xem hướng dẫn seed trong README để biết phạm vi;
không dùng mật khẩu demo public cho dữ liệu thật.
5. Khởi động/redeploy web rồi đăng nhập bằng nhân viên ACTIVE thuộc cửa hàng ACTIVE.

Render hỗ trợ MySQL dưới dạng private Docker service có persistent disk, hoặc kết nối
MySQL ngoài. Không đổi sang Render Postgres chỉ bằng thay biến môi trường: schema,
connector và repository hiện dùng MySQL.
Nguồn: [Render MySQL](https://render.com/docs/deploy-mysql).

Chạy local với dữ liệu thật (sau khi đã export đủ biến MySQL):

```bash
export CYBERHUB_WEB_MODE=mysql
export CYBERHUB_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m cyberhub_manager.web
```

`.env` được đọc khi cấu hình MySQL khởi tạo; các biến điều khiển web ở trên nên được
export trong shell hoặc đặt trong dashboard hosting trước khi start process.

## Phiên đăng nhập, quyền và giới hạn vận hành

- Cookie được ký, HttpOnly, SameSite=Lax; mọi lệnh ghi yêu cầu CSRF token, kể cả login.
- Chế độ MySQL đọc lại nhân viên ACTIVE từ DB mỗi request, dùng role/store hiện tại.
  Các service nhận actor từ request-local context; không dùng một actor global chung nhiều người.
- Server lấy `employee_id`, `store_id`, quyền từ phiên đã xác thực; bỏ qua actor/store do client tự truyền.
- Mật khẩu/hash không xuất hiện trong DTO trả về. Request body không được ghi vào access log.
- Có giới hạn thử login, khóa đồng thời theo workspace demo, giới hạn 64 workspace demo đang hoạt động.
- Lệnh Gunicorn dùng **1 worker, 4 threads, 1 instance**. Demo và rate limit đang ở bộ nhớ
  process; chưa hỗ trợ scale nhiều worker/replica. Trước khi scale, cần session/demo store
  và rate limiter dùng Redis/database, cùng kiểm tra tải cho pool MySQL.
- `CYBERHUB_ALLOWED_HOSTS` nhận danh sách hostname phân cách dấu phẩy nếu muốn giới hạn host.
- `/healthz` kiểm tra process web; không xác nhận database còn kết nối hoặc đã migrate.

## Kiểm thử

```bash
python -m pip install -e '.[web,dev]'
python -m pytest tests/unit/test_web_app.py -q
```

Test API không cần MySQL/desktop. Các test web được skip nếu chưa cài extra `web`.
Test MySQL thật nằm ở `tests/integration/test_web_mysql.py`, dùng database test đã được
chuẩn bị theo README; fixture tạo và dọn chính xác dữ liệu riêng của nó.

Kiểm tra trình duyệt: login VI/EN; tạo/sửa khách; nạp tiền sau khi xác nhận nhận đủ;
khóa/mở khách; mở phiên; checkout đủ số dư; checkout bù tiền; tra hóa đơn; xem doanh thu;
đăng nhập STAFF xác nhận không quản lý được máy; thử ở 1280×720 và chiều rộng 390px.

Để publish tự động từ cuộc chat, cần cài/kết nối Render hoặc Railway bằng tài khoản
của chủ dự án. Merge/push GitHub không tự tạo một tài khoản hay service trên hosting.
