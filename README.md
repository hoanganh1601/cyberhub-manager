# CyberHub Manager

**Database scope:** 22 business tables for store, employee, customer, account, machine, usage, invoice, POS, and customer order notifications. See the [data model](docs/architecture/DATA_MODEL.md) and [current ERD](docs/diagrams/current_erd.md).

The Python application uses Flask, CustomTkinter, and MySQL. Its active flows cover store/customer/employee management, machines and sessions, invoices, wallet transactions, and POS.

Start with the [documentation index](docs/README.md), [quickstart](docs/guides/QUICKSTART.md), and [data model](docs/architecture/DATA_MODEL.md).

## Chạy ứng dụng web

Chạy các lệnh tại thư mục gốc repository bằng PowerShell. Cần Python 3.11 trở lên.

### Chế độ demo

Chế độ demo chạy không cần MySQL và lưu dữ liệu trong bộ nhớ; dữ liệu sẽ mất khi dừng server.

```powershell
python -m pip install -e ".[web]"
$env:CYBERHUB_WEB_MODE = "demo"
$env:CYBERHUB_ASSISTANT_ENABLED = "false"
python -m cyberhub_manager.web --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000`. Tài khoản nhân viên demo gồm `admin01`, `quanly01`, `nhanvien01`, `bep01`, `thukho01`; mật khẩu `demo123`. Cổng khách hàng ở `http://127.0.0.1:8000/customer`; tài khoản `nguyenvanan`, mật khẩu `demo123`. Nhấn `Ctrl+C` trong terminal để dừng server.

### Chế độ MySQL

1. Sao chép `.env.example` thành `.env`, rồi điền thông tin MySQL và một `CYBERHUB_SECRET_KEY` ổn định dài ít nhất 32 ký tự.
2. Khởi động MySQL cục bộ hoặc chạy `docker compose up -d mysql`.
3. Tạo/cập nhật schema bằng `python scripts/init_db.py`.
4. Nếu cần dữ liệu mẫu, chạy `python scripts/seed_db.py` và nhập mật khẩu theo lời nhắc.
5. Chạy web:

```powershell
$env:CYBERHUB_WEB_MODE = "mysql"
python -m cyberhub_manager.web --host 127.0.0.1 --port 8000
```

Sau đó mở `http://127.0.0.1:8000`. Không có mật khẩu mặc định cho tài khoản MySQL; mật khẩu tài khoản seed là mật khẩu đã nhập khi chạy seed. Xem thêm [hướng dẫn chạy nhanh](docs/guides/QUICKSTART.md).

## Database migration

Migration `030_scope_to_20_tables.sql` drops `customer_email_tokens`, `customer_mail_outbox`, `customer_security_audit`, and `customer_store_links`. It also removes email activation/recovery and customer-to-store filtering. Back up existing data before applying migration 030.

Migration `031_customer_order_notifications.sql` restores durable customer notifications for menu-order status changes. A fresh database ends with 22 business tables plus the technical `schema_migrations` table.
