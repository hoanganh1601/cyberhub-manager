# CyberHub Manager — Hệ thống quản lý quán Net

CyberHub Manager hỗ trợ nhân viên và quản lý vận hành quán net qua ứng dụng desktop
và giao diện web dùng chung các service nghiệp vụ Python/MySQL.

## Công nghệ

- Python 3.11 trở lên
- CustomTkinter
- MySQL 8.4 LTS
- mysql-connector-python
- pytest
- Docker Desktop và Docker Compose

## Yêu cầu môi trường

Cài đặt trước:

- Git
- Python 3.11 trở lên
- Docker Desktop

Kiểm tra:

```powershell
git --version
python --version
docker --version
docker compose version
```

## Cài đặt trên Windows

### 1. Clone repository

```powershell
git clone <repository-url>
cd cyberhub-manager
```

### 2. Tạo virtual environment

```powershell
py -m venv .venv
```

Nếu PowerShell chặn script, cho phép trong terminal hiện tại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Kích hoạt môi trường:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Cài dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Kiểm tra dependencies:

```powershell
python -m pip check
```

## Cấu hình môi trường

### Chạy bản web (không cần màn hình desktop hoặc MySQL để demo)

```bash
python -m pip install -e '.[web]'
python -m cyberhub_manager.web --host 0.0.0.0 --port 8000
```

Mở `http://localhost:8000`, đăng nhập `quanly01 / demo123` hoặc `nhanvien01 / demo123`.
Demo có dữ liệu riêng cho mỗi phiên đăng nhập và mất khi server khởi động lại.
Xem [WEB_DEPLOYMENT.md](docs/WEB_DEPLOYMENT.md) để dùng MySQL thật, triển khai Render
qua `render.yaml` hoặc Railway qua `railway.json` / `Dockerfile.web`.

### Xem Login và full UI không cần MySQL

```powershell
python -m cyberhub_manager.app --mock
```

Manager: `quanly01 / demo123`; Staff: `nhanvien01 / demo123`.
Chạy `python -m cyberhub_manager.app` để dùng cấu hình MySQL thật bên dưới.
Xem [hướng dẫn Login desktop](docs/LOGIN_DESKTOP.md) để thử VI/EN, validation và các trạng thái UI.
Xem [hướng dẫn giao diện và biểu đồ](docs/WORKSPACE_UI.md) để kiểm tra các màn nghiệp vụ,
chế độ EN và hộp thoại. Thêm `--lang en` vào lệnh trên để bắt đầu bằng tiếng Anh.

Tạo `.env` từ file mẫu:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và cập nhật các giá trị local nếu cần.

Không commit file `.env` vì file này có thể chứa mật khẩu.

Nếu cổng MySQL `3306` đã được chương trình khác sử dụng, đổi trong `.env`:

```dotenv
MYSQL_PORT=3307
```

Không cần đổi `.env.example`; cổng mặc định của repository vẫn là `3306`.

## Khởi động MySQL

Đảm bảo Docker Desktop đang chạy, sau đó thực hiện:

```powershell
docker compose up -d mysql
```

Kiểm tra trạng thái:

```powershell
docker compose ps
```

MySQL sẵn sàng khi trạng thái hiển thị:

```text
healthy
```

Dừng container mà vẫn giữ dữ liệu:

```powershell
docker compose down
```

## Chạy ứng dụng

Đảm bảo virtual environment đang hoạt động và MySQL đang chạy:

```powershell
cyberhub-manager
```

Ứng dụng sẽ mở cửa sổ desktop có tiêu đề `CyberHub Manager`.

## Chuẩn bị và chạy kiểm thử

Docker/MySQL là bước **chuẩn bị môi trường**, không phải chạy lại trước mọi lần
pytest. Sau khi môi trường đã sẵn sàng, toàn bộ automated test chạy bằng đúng một
lệnh: `python -m pytest -q`.

| Loại test | Thư mục | Cần MySQL |
|---|---|---|
| Unit test | `tests/unit/` | Không |
| Integration test | `tests/integration/` | Có, database `cyberhub_manager_test` |
| Manual acceptance | `tests/manual/CHECKLIST.md` | Có, chạy ứng dụng thật |

### 1. Cài dependencies

```powershell
python -m pip install -e ".[dev]"
```

### 2. Chuẩn bị MySQL test (lần đầu hoặc khi schema thay đổi)

```powershell
docker compose up -d mysql
docker compose ps
python scripts/prepare_test_db.py
```

MySQL chỉ được coi là sẵn sàng khi container ở trạng thái `healthy`.

`scripts/prepare_test_db.py` đọc thông tin kết nối từ `.env`, tạo
`cyberhub_manager_test` nếu chưa có và áp dụng migration theo thứ tự. Script chạy
lại nhiều lần được, không seed dữ liệu demo và từ chối mọi database khác.

Nếu tài khoản ứng dụng không có quyền tạo database, script in sẵn các lệnh `CREATE
DATABASE` và `GRANT` cần chạy bằng tài khoản root.

### 3. Chạy test

Toàn bộ automated test:

```powershell
python -m pytest -q
```

Một file test:

```powershell
python -m pytest tests/integration/test_customer_flow.py -q
```

Một test riêng lẻ:

```powershell
python -m pytest tests/integration/test_customer_flow.py::test_login_returns_session_for_active_employee -q
```

Chỉ chạy unit test (không cần MySQL):

```powershell
python -m pytest tests/unit -q
```

Kèm báo cáo coverage (chỉ báo hỗ trợ, không thay thế việc kiểm tra đúng nghiệp vụ):

```powershell
python -m pytest --cov=cyberhub_manager --cov-report=term-missing
```

### Quy tắc database test

- `cyberhub_manager`: database development/ứng dụng, **cấm** dùng cho test.
- `cyberhub_manager_test`: database duy nhất của automated test.
- `cyberhub_manager_migration_test`: chỉ dành cho kiểm tra thủ công migration/reset
  của HA-03 (xem mục Migration và dữ liệu demo).

`tests/conftest.py` luôn ép `MYSQL_DATABASE=cyberhub_manager_test`, không cần sửa
`.env`, và từ chối chạy trên database khác với thông báo
`Refusing to run integration tests outside cyberhub_manager_test`.

Test không phụ thuộc dữ liệu demo: mỗi test tự tạo dữ liệu với mã duy nhất rồi tự
rollback hoặc xóa đúng các dòng đã tạo. Fixture dùng chung nằm trong
`tests/conftest.py`: `db_conn` (connection trong transaction, luôn rollback) và
`test_scenario` (tạo store, nhân viên, khách, account, máy cho một test).

### Xử lý lỗi thường gặp

| Thông báo | Nguyên nhân | Cách xử lý |
|---|---|---|
| `MySQL test database is unavailable.` | MySQL chưa chạy, sai host/port, hoặc chưa có `cyberhub_manager_test` | Bật Docker Desktop, `docker compose up -d mysql`, đợi `healthy`, rồi `python scripts/prepare_test_db.py` |
| `cyberhub_manager_test has no schema yet` | Chưa áp dụng migration | `python scripts/prepare_test_db.py` |
| Lỗi cột hoặc bảng không tồn tại sau khi pull code | Có migration mới | `python scripts/prepare_test_db.py` |
| `Refusing to run integration tests outside cyberhub_manager_test` | Test tự đổi `MYSQL_DATABASE` | Bỏ đoạn đổi database trong test; `conftest.py` đã cấu hình sẵn |

Unit test vẫn chạy được khi MySQL tắt; khi đó chỉ các integration test báo lỗi với
hướng dẫn trên.

Kết quả kiểm thử của từng phiên bản ghi tại
[docs/testing/LI09_TEST_REPORT.md](docs/testing/LI09_TEST_REPORT.md).

## Cấu trúc chính

```text
cyberhub-manager/
├── docs/
├── scripts/
├── sql/
├── src/
│   └── cyberhub_manager/
├── tests/
│   ├── integration/
│   ├── manual/
│   └── unit/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── requirements.txt
```

## Kiến trúc

Dự án sử dụng Layered Architecture:

```text
UI → Service → Repository → Database
```

## Tài liệu dự án

1. [Yêu cầu sản phẩm](docs/01_REQUIREMENTS.md)
2. [Khung code và hợp đồng module](docs/02_CODEBASE_SKELETON.md)
3. [Theme và quy chuẩn frontend](docs/03_UI_THEME.md)
4. [Phân công và backlog Linear](docs/04_LINEAR_BACKLOG.md)
5. [GitHub workflow](docs/05_GITHUB_WORKFLOW.md)
6. [Checklist kickoff](docs/06_KICKOFF_CHECKLIST.md)
7. [CSV nhập task vào Linear](docs/linear_import.csv)

Mọi thay đổi tên bảng, field, service contract hoặc theme phải được cập nhật trong tài liệu liên quan trước khi merge.

## Connection và transaction — HA-04
Cấu hình kết nối được đọc từ `.env`.

Service mở transaction bằng `with transaction() as conn` và truyền
cùng `conn` cho các repository tham gia một nghiệp vụ.

Repository không tự commit, rollback hoặc đóng connection.
Transaction manager chịu trách nhiệm commit khi thành công,
rollback khi có lỗi và trả connection về pool khi kết thúc.

### Kiểm thử transaction

Chuẩn bị database theo mục Chuẩn bị và chạy kiểm thử, rồi chạy:

```powershell
python -m pytest tests/integration/test_transaction_manager.py -q
```

Ba kiểm thử xác nhận:
- Thành công thì commit toàn bộ thay đổi.
- Có exception thì rollback toàn bộ thay đổi.
- Connection được trả về pool sau cả hai trường hợp.

## Migration và dữ liệu demo (PowerShell)

Mục này chỉ dùng để kiểm tra migration/reset của HA-03; automated test không dùng database này (xem mục Chuẩn bị và chạy kiểm thử).

Cần chạy MySQL bằng Docker, cấu hình kết nối trong `.env`, và tạo sẵn database `cyberhub_manager_migration_test` với quyền cho `cyberhub_app`. Đây là database trong MySQL, không phải thư mục của dự án.

Chạy migration:

```powershell
python -c "import os; os.environ['MYSQL_DATABASE'] = 'cyberhub_manager_migration_test'; from scripts.init_db import run_migrations; run_migrations()"
```

Thêm dữ liệu demo (chương trình sẽ yêu cầu nhập mật khẩu demo):

```powershell
python -c "import os; os.environ['MYSQL_DATABASE'] = 'cyberhub_manager_migration_test'; from scripts.seed_db import run_seed; run_seed(expected_database='cyberhub_manager_migration_test')"
```

Có thể chạy lại migration và seed: migration đã áp dụng sẽ được bỏ qua; seed không tạo bản ghi trùng.

Chỉ khi muốn **xóa dữ liệu nghiệp vụ** trong database thử nghiệm, chạy:

```powershell
python -c "import os; os.environ['MYSQL_DATABASE'] = 'cyberhub_manager_migration_test'; from scripts.reset_demo import run_reset; run_reset(expected_database='cyberhub_manager_migration_test')"
```

Để xác nhận, nhập chính xác `RESET cyberhub_manager_migration_test`. Reset giữ nguyên cấu trúc bảng và lịch sử migration, nhưng xóa dữ liệu nghiệp vụ trong database này. Có thể chạy seed lại để lấy lại dữ liệu demo ban đầu; dữ liệu phát sinh sau đó không được khôi phục bằng seed. **Không chạy reset trên database chứa dữ liệu cần giữ.**
