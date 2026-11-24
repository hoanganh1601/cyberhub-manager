# CyberHub Manager — Hệ thống quản lý quán Net

CyberHub Manager hỗ trợ vận hành quán net đa cơ sở qua giao diện **Desktop CustomTkinter** và **Web Flask**, dùng chung tầng Application và Domain (Python / MySQL 8.4). Hệ thống bao gồm cổng khách hàng, quản lý máy & phiên sử dụng, ví điện tử & hóa đơn, POS đồ ăn & tồn kho nguyên liệu, ca/két tiền, bảo trì thiết bị, mua hàng & công nợ nhà cung cấp, voucher/game/quảng cáo nhận thưởng, trợ lý RAG Gemini và dự báo doanh thu offline.

- **Bắt đầu tại [tài liệu hiện hành](docs/README.md):** [chạy nhanh](docs/guides/QUICKSTART.md), [kiến trúc bốn tầng](docs/architecture/OVERVIEW.md), [luồng nghiệp vụ](docs/architecture/BUSINESS_FLOWS.md), [mô hình dữ liệu](docs/architecture/DATA_MODEL.md), [ERD hiện hành](docs/diagrams/current_erd.md) và [chứng minh 3NF](docs/architecture/DATABASE_3NF_PROOFS.md).
- **Phân quyền RBAC:** Hỗ trợ 6 vai trò nhân viên (`ADMIN`, `DIRECTOR`, `MANAGER`, `STAFF`, `KITCHEN`, `INVENTORY`) và principal khách hàng riêng (`CUSTOMER`), cùng hai chính sách `CYBERHUB_RBAC_POLICY=legacy` (mặc định) và `separated`. Xem [thiết kế RBAC](docs/RBAC_DESIGN.md) và [ma trận quyền](docs/RBAC_PERMISSION_MATRIX.md).

## Công nghệ

- Python 3.11+
- Flask (Web) & CustomTkinter (Desktop)
- MySQL 8.4 LTS (`mysql-connector-python`, 75 bảng nghiệp vụ chuẩn 3NF, 18 view, 28 trigger)
- pytest
- Docker Desktop & Docker Compose

## Yêu cầu môi trường

Cài đặt trước: Git, Python 3.11+ và Docker Desktop. Kiểm tra nhanh:

```powershell
git --version
python --version
docker --version
docker compose version
```

## Cài đặt trên Windows

### 1. Clone repository & tạo virtual environment

```powershell
git clone <repository-url>
cd cyberhub-manager
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 2. Cài dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip check
```

## Chạy nhanh (Demo không cần MySQL)

### Web demo

```powershell
python -m pip install -e ".[web]"
$env:CYBERHUB_WEB_MODE="demo"
python -m cyberhub_manager.presentation.web --host 0.0.0.0 --port 8000
```

Mở `http://localhost:8000` (nhân viên: `admin01`, `giamdoc01`, `quanly01`, `nhanvien01`, `bep01`, `thukho01` / `demo123`) hoặc `http://localhost:8000/customer` (khách hàng: `nguyenvanan` / `demo123`). Chế độ demo lưu dữ liệu trong bộ nhớ theo từng phiên và mất khi khởi động lại server. Xem [hướng dẫn triển khai web](docs/guides/WEB_DEPLOYMENT.md) cho MySQL thật, Render (`render.yaml`) hoặc Railway (`railway.json` / `Dockerfile.web`).

### Desktop demo

```powershell
python -m cyberhub_manager.app --mock
python -m cyberhub_manager.app --mock --lang en
```

## Cấu hình & vận hành với MySQL 8.4

### 1. Tạo tệp `.env`

```powershell
Copy-Item .env.example .env
```

Cập nhật thông số kết nối trong `.env` (không commit `.env`). Nếu cổng `3306` đã bận, đổi `MYSQL_PORT=3307` trong `.env`.

### 2. Khởi động MySQL bằng Docker

```powershell
docker compose up -d mysql
docker compose ps   # chờ trạng thái healthy
```

Dừng container nhưng giữ nguyên dữ liệu volume:

```powershell
docker compose down
```

### 3. Áp dụng migration & nạp dữ liệu mẫu lần đầu

```powershell
python scripts/init_db.py
python -c "from scripts.seed_db import run_seed; run_seed(expected_database='cyberhub_manager')"
```

- `scripts/init_db.py` áp dụng tuần tự các migration `sql/001`–`032`; chạy lại sẽ tự bỏ qua migration đã áp dụng.
- `seed_db` hỏi mật khẩu demo 2 lần và không tạo trùng bản ghi khi chạy lại.

| Dữ liệu seed | Giá trị |
|---|---|
| Quản lý | `demo.manager` |
| Nhân viên | `demo.staff01`, `demo.staff02` |
| Khách hàng | `DEMO_CUS_01` đến `DEMO_CUS_05`, số dư 0đ |
| Máy trạm | `DEMO_PC_01` đến `DEMO_PC_20`, 10.000đ/giờ |

### 4. Khởi chạy ứng dụng với MySQL thật

```powershell
# Desktop
cyberhub-manager

# Web
$env:CYBERHUB_WEB_MODE="mysql"
python -m cyberhub_manager.presentation.web --port 8000
```

## Kiểm thử tự động

| Loại test | Thư mục | Cần MySQL |
|---|---|---|
| Unit & Desktop UI test | `tests/unit/` | Không |
| Integration test | `tests/integration/` | Có (`cyberhub_manager_test`) |

### Chuẩn bị MySQL test (lần đầu hoặc khi có migration mới)

```powershell
docker compose up -d mysql
python scripts/prepare_test_db.py
```

### Chạy kiểm thử

```powershell
$env:PYTHONPATH="src"
$env:CYBERHUB_RBAC_POLICY="legacy"

# Toàn bộ unit test (không cần MySQL)
python -m pytest tests/unit -q

# Toàn bộ integration test trên cyberhub_manager_test
python -m pytest tests/integration -q

# Kiểm tra kiến trúc 4 tầng & đồng bộ data dictionary
python -m pytest tests/unit/test_layered_architecture.py -q
python scripts/gen_data_dictionary.py --check --database cyberhub_manager_test
```

### Đo hiệu năng & `EXPLAIN` truy vấn

Script chỉ chạy trên `cyberhub_manager_test`, tự tạo dữ liệu có tiền tố `PF...` rồi dọn sạch sau khi đo:

```powershell
$env:MYSQL_DATABASE="cyberhub_manager_test"
python scripts/perf_check.py --scale 0.2
```

### Quy tắc database test

- `cyberhub_manager`: database vận hành/trình diễn, **cấm** dùng cho automated test.
- `cyberhub_manager_test`: database duy nhất cho `tests/integration/` (`tests/conftest.py` tự ép và từ chối mọi database khác).
- `cyberhub_manager_migration_test`: chỉ dùng cho diễn tập migration/reset thủ công (`scripts/reset_demo.py`).

## Cấu trúc dự án (Kiến trúc bốn tầng)

```text
cyberhub-manager/
├── docs/
│   ├── architecture/      # OVERVIEW, BUSINESS_FLOWS, DATA_MODEL, 3NF proofs & plan
│   ├── diagrams/          # current_erd.md, system_uml.md, data_dictionary.md
│   ├── features/          # POS_INVENTORY_LIFECYCLE, OPERATIONS, COMMERCIAL_PARTNERS, FORECASTING
│   ├── guides/            # QUICKSTART, DEVELOPMENT, WEB_DEPLOYMENT, GEMINI_API_RUNBOOK
│   └── knowledge-base/    # Kho tri thức phân quyền cho trợ lý RAG
├── scripts/               # Migration, seed, reset, perf_check, data dictionary, forecasting, RAG
├── sql/                   # Migrations 001–032 (MySQL 8.4 InnoDB, utf8mb4_0900_ai_ci)
├── src/cyberhub_manager/
│   ├── presentation/      # Flask web routes/static/templates & CustomTkinter desktop UI
│   ├── application/       # Services, forecasting, AI RAG orchestration, in-memory mocks
│   ├── infrastructure/    # MySQL repositories, transaction manager, Gemini/SQLite/bcrypt adapters
│   └── domain/            # Entities, enums, DTOs, policies (RBAC & money rules), exceptions
└── tests/
    ├── unit/
    └── integration/
```

Quy tắc phụ thuộc bắt buộc (được kiểm tra tự động bằng AST trong `tests/unit/test_layered_architecture.py`):
- **Presentation** gọi **Application** và dùng DTO/enum của **Domain**; không mở transaction hoặc chạy SQL.
- **Application** sở hữu use case, phân quyền và biên giao dịch (`with transaction() as conn:`); không import Flask/Tk hay chạy SQL trực tiếp.
- **Infrastructure** chỉ truy cập dữ liệu/adapter kỹ thuật, không tự `commit`/`rollback`.
- **Domain** thuần Python, không phụ thuộc 3 tầng còn lại hay thư viện lưu trữ/framework.

## Trợ lý Gemini API & Dự báo offline

- **Trợ lý RAG & Phân tích (Gemini API):** Thêm `GEMINI_API_KEY=...` vào `.env` rồi chạy `python -m scripts.run_rag_gemini --port 8059`. Xem chi tiết tại [hướng dẫn trợ lý Gemini](docs/guides/GEMINI_API_RUNBOOK.md).
- **Dự báo doanh thu offline:** Chạy `python -m scripts.run_forecasting --source demo --history-days 180` (hoặc `--source mysql`). Xem chi tiết tại [tài liệu dự báo](docs/features/FORECASTING.md).

## Tài liệu tham khảo chính

1. [Mục lục tài liệu hiện hành](docs/README.md)
2. [Chạy nhanh](docs/guides/QUICKSTART.md)
3. [Kiến trúc bốn tầng](docs/architecture/OVERVIEW.md) & [Luồng nghiệp vụ](docs/architecture/BUSINESS_FLOWS.md)
4. [Mô hình dữ liệu](docs/architecture/DATA_MODEL.md), [ERD hiện hành](docs/diagrams/current_erd.md) & [Data Dictionary](docs/diagrams/data_dictionary.md)
5. [Chứng minh chuẩn hóa 3NF (75/75 bảng)](docs/architecture/DATABASE_3NF_PROOFS.md)
6. [Hướng dẫn phát triển & kiểm thử](docs/guides/DEVELOPMENT.md)
