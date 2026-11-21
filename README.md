# CyberHub Manager — Hệ thống quản lý quán Net

CyberHub Manager hỗ trợ vận hành quán net qua desktop CustomTkinter và web Flask,
dùng chung service nghiệp vụ Python/MySQL. Hệ thống có cổng khách hàng, quản lý
máy/phiên, thanh toán, POS/kho, ca/két, bảo trì, mua hàng, game/quảng cáo,
trợ lý Gemini và dự báo offline.

**Bắt đầu tại [tài liệu hiện hành](docs/README.md):** [chạy nhanh](docs/guides/QUICKSTART.md),
[kiến trúc](docs/architecture/OVERVIEW.md), [luồng nghiệp vụ](docs/architecture/BUSINESS_FLOWS.md)
và [mô hình dữ liệu](docs/architecture/DATA_MODEL.md). Các báo cáo và tài liệu từng đợt
được giữ trong [history](history/README.md).

RBAC có vai trò `DIRECTOR` và chế độ chuyển đổi an toàn, không tự đổi quyền tài khoản đang hoạt động.
Đọc [thiết kế RBAC](docs/RBAC_DESIGN.md) và [ma trận quyền](docs/RBAC_PERMISSION_MATRIX.md)
trước khi bật `CYBERHUB_RBAC_POLICY=separated`.

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
Xem [WEB_DEPLOYMENT.md](docs/guides/WEB_DEPLOYMENT.md) để dùng MySQL thật, triển khai Render
qua `render.yaml` hoặc Railway qua `railway.json` / `Dockerfile.web`.

### Xem Login và full UI không cần MySQL

```powershell
python -m cyberhub_manager.app --mock
```

Manager: `quanly01 / demo123`; Staff: `nhanvien01 / demo123`.
Chạy `python -m cyberhub_manager.app` để dùng cấu hình MySQL thật bên dưới.
Xem [hướng dẫn Login desktop](history/docs/guides/LOGIN_DESKTOP.md) để thử VI/EN, validation và các trạng thái UI.
Xem [hướng dẫn giao diện và biểu đồ](history/docs/reference/WORKSPACE_UI.md) để kiểm tra các màn nghiệp vụ,
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

## Chuẩn bị database ứng dụng (lần đầu)

Database `cyberhub_manager` trong container mới chưa có bảng. Tạo bảng và dữ liệu demo
một lần trước khi chạy ứng dụng:

```powershell
python scripts/init_db.py
python -c "from scripts.seed_db import run_seed; run_seed(expected_database='cyberhub_manager')"
```

- `init_db.py` áp dụng các file trong `sql/` theo thứ tự; chạy lại sẽ bỏ qua migration đã áp dụng.
- Seed hỏi **mật khẩu demo** hai lần (không phải mật khẩu MySQL). Mật khẩu này dùng cho
  mọi tài khoản demo bên dưới. Seed chạy lại không tạo bản ghi trùng.

| Dữ liệu demo | Giá trị |
|---|---|
| Quản lý | `demo.manager` |
| Nhân viên | `demo.staff01`, `demo.staff02` |
| Khách hàng | `DEMO_CUS_01` đến `DEMO_CUS_05`, số dư 0đ |
| Máy | `DEMO_PC_01` đến `DEMO_PC_20`, 10.000đ/giờ |

Nếu bỏ qua bước này, màn đăng nhập sẽ báo *Service is temporarily unavailable* vì chưa có bảng.

## Chạy ứng dụng

Đảm bảo virtual environment đang hoạt động, MySQL đang chạy và database đã được chuẩn bị:

```powershell
cyberhub-manager
```

Ứng dụng sẽ mở cửa sổ desktop có tiêu đề `CyberHub Manager`. Đăng nhập bằng `demo.manager`
và mật khẩu demo đã nhập khi seed.

| Lệnh | Mục đích |
|---|---|
| `cyberhub-manager` | Chạy với MySQL theo `.env` |
| `cyberhub-manager --mock` | Demo giao diện không cần MySQL/`.env` (`quanly01` hoặc `nhanvien01`, mật khẩu `demo123`) |
| `cyberhub-manager --lang en` | Mở giao diện tiếng Anh |

Thiếu biến cấu hình bắt buộc thì lệnh dừng trước khi mở cửa sổ (exit code 2),
hướng dẫn cấu hình `.env` hoặc dùng `--mock`.

### Menu sách lật trên web

Chạy web ở chế độ demo rồi mở `http://127.0.0.1:8000/customer`, đăng nhập tài khoản khách demo và chọn **Menu đồ ăn**:

```powershell
$env:CYBERHUB_WEB_MODE="demo"
python -m cyberhub_manager.web --port 8000
```

Desktop hiển thị hai trang cạnh nhau; điện thoại hiển thị một trang. Dùng nút **Trang trước/Trang sau**, phím mũi tên hoặc vuốt để lật. Menu, giá, trạng thái còn món và ảnh do quản lý tải lên vẫn lấy từ dữ liệu của từng cơ sở; giỏ món được giữ khi chuyển trang. Hiệu ứng dùng CSS/JavaScript của dự án, không cần nhúng dịch vụ Heyzine.

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

Đo thời gian thao tác và `EXPLAIN` các câu SELECT trên dữ liệu lớn (HA-09). Script chỉ chạy
trên `cyberhub_manager_test`, in namespace duy nhất dạng `PF...`, tạo dữ liệu riêng rồi tự xóa.
Nếu `.env` đang trỏ database ứng dụng, đặt `MYSQL_DATABASE=cyberhub_manager_test` trong
terminal riêng trước khi chạy; script sẽ từ chối database khác:

```powershell
$env:MYSQL_DATABASE = "cyberhub_manager_test"
python scripts/perf_check.py              # 5.000 khách, 60.000 phiên/hóa đơn
python scripts/perf_check.py --scale 0.2  # nhanh hơn
```

Kết quả review database: [history/docs/testing/HA09_DB_REVIEW.md](history/docs/testing/HA09_DB_REVIEW.md).
Tình trạng toàn bộ task HA/LI/NG và kết quả bản tích hợp:
[HA_LI_NG_RELEASE_AUDIT.md](history/docs/testing/HA_LI_NG_RELEASE_AUDIT.md).

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
[history/docs/testing/LI09_TEST_REPORT.md](history/docs/testing/LI09_TEST_REPORT.md).

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

Dự án sử dụng Layered Architecture. Desktop và Flask web là hai adapter dùng
chung service layer:

```text
CustomTkinter UI ─┐
Flask Web ────────┼─> Service → Repository → Database
                  └─> AI/RAG (read-only theo quyền truy cập)
```

Quy tắc bắt buộc:

- UI/web không mở transaction hoặc gọi repository trực tiếp.
- Service sở hữu use case, authorization và transaction boundary.
- Repository chỉ nhận connection từ caller, chạy SQL và map dữ liệu.
- `database.transaction.transaction()` là cơ chế commit/rollback chuẩn.
- Cấu hình web nằm tại `presentation/web/config.py`; cấu trúc bốn tầng xem [kiến trúc hiện hành](docs/architecture/OVERVIEW.md). `.env` thật và `runtime/` không commit.

## Tài liệu dự án

1. [Mục lục hiện hành](docs/README.md)
2. [Quickstart](docs/guides/QUICKSTART.md)
3. [Kiến trúc và luồng nghiệp vụ](docs/architecture/OVERVIEW.md)
4. [Mô hình dữ liệu](docs/architecture/DATA_MODEL.md)
5. [Hướng dẫn mở rộng](docs/guides/DEVELOPMENT.md)
6. [Tư liệu lịch sử và bằng chứng nghiệm thu](history/README.md)

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

## Trợ lý Gemini API cho máy cấu hình thấp

Tạo API key tại [Google AI Studio](https://aistudio.google.com/api-keys), thêm
`GEMINI_API_KEY=key_cua_ban` vào `.env`, rồi chạy:

```powershell
python -m scripts.run_rag_gemini --port 8059
```

Không cần GPU hoặc tải model. Mặc định dùng Gemini Flash-Lite và Gemini embedding;
free tier có giới hạn và gửi dữ liệu tới Google. Xem [hướng dẫn Gemini API](docs/guides/GEMINI_API_RUNBOOK.md)
để cấu hình model, quyền dữ liệu và xử lý lỗi key/quota.

5A giải thích tài liệu đúng quyền; 5B phân tích
snapshot doanh thu/máy đã lọc cho MANAGER/ADMIN; 5C gợi ý menu, ưu đãi, voucher và
game cho chính khách hàng đang đăng nhập. Xem [thiết kế và cách kiểm tra 5B–5C](history/docs/features/AI_PHASES_5B_5C.md).
AI không được thao tác nạp tiền, checkout, đặt món hay dùng voucher. Mặc định app
thường chỉ bật trợ lý khi cấu hình API key, cờ bật và audit path; helper Gemini tự đặt cờ/audit path.
Lệnh cũ `python -m scripts.run_rag_local` cũng chuyển tiếp sang Gemini API.
Xem [các lựa chọn API miễn phí](history/docs/guides/FREE_API_OPTIONS.md) khi cần dự phòng hạn mức.
