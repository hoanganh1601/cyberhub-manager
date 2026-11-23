# Chạy và kiểm tra nhanh

Chạy lệnh tại thư mục gốc repository. Python 3.11 trở lên; trên Windows dùng PowerShell trong terminal VS Code.

## Web demo không cần MySQL

```powershell
python -m pip install -e ".[web]"
$env:CYBERHUB_WEB_MODE="demo"
$env:CYBERHUB_ASSISTANT_ENABLED="false"
python -m cyberhub_manager.web --port 8000
```

Mở `http://127.0.0.1:8000`. Nhân viên demo: `admin01`, `giamdoc01`, `quanly01`, `nhanvien01`, `bep01`; mật khẩu `demo123`. Cổng khách: `/customer`, `nguyenvanan / demo123`. Demo lưu trong bộ nhớ, mất khi server khởi động lại. Chatbot tắt ở lệnh này để không phụ thuộc quota Gemini.

## Web với MySQL 8.4 (25 bảng chuẩn 3NF, migrations `001`–`011`)

1. Sao chép `.env.example` thành `.env`, điền `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` và `CYBERHUB_SECRET_KEY` ổn định từ 32 ký tự. Không commit `.env`.
2. Chạy MySQL của bạn hoặc `docker compose up -d mysql`; kiểm tra port đang dùng trong `.env`.
3. Chạy `python scripts/init_db.py` để áp dụng đầy đủ migrations `sql/001`–`sql/011` (25 bảng, 8 view, 18 trigger).
4. Tạo dữ liệu demo (tùy chọn) bằng `python scripts/seed_db.py` và tạo quản trị viên bằng `python scripts/bootstrap_admin.py`.
5. Chạy web:

```powershell
$env:CYBERHUB_WEB_MODE="mysql"
python -m cyberhub_manager.web --port 8000
```

MySQL không có mật khẩu demo mặc định. Tài khoản seed dùng mật khẩu đã nhập khi seed; quản trị viên mới tạo bằng script bootstrap. Xem [hướng dẫn web](WEB_DEPLOYMENT.md), [mô hình dữ liệu](../architecture/DATA_MODEL.md) và [luồng nghiệp vụ](../architecture/BUSINESS_FLOWS.md).
