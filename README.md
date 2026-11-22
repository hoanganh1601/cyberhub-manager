# CyberHub Manager

**Database scope:** 24 normalized (3NF) business tables (+ 8 read views and 15 integrity triggers) for stores, identity/RBAC, customers, prepaid wallets, workstations, usage sessions, invoices, POS menu/promotions/reversals, and customer order notifications. See the [data model](docs/architecture/DATA_MODEL.md) and [current ERD](docs/diagrams/current_erd.md).

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

Mở `http://127.0.0.1:8000`. Tài khoản nhân viên demo gồm `admin01`, `quanly01`, `nhanvien01`, `bep01`; mật khẩu `demo123`. Cổng khách hàng ở `http://127.0.0.1:8000/customer`; tài khoản `nguyenvanan`, mật khẩu `demo123`. Nhấn `Ctrl+C` trong terminal để dừng server.

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

Migrations are organized by business domain in `sql/001_stores_and_identity.sql` through `sql/009_integrity_triggers.sql` (24 business tables, 8 read views, 15 integrity triggers, plus the technical `schema_migrations` table; 100% InnoDB, `utf8mb4_0900_ai_ci`). Run `python scripts/init_db.py` to initialize a fresh database.
