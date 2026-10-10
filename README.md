# CyberHub Manager — Hệ thống quản lý quán Net

CyberHub Manager là ứng dụng desktop hỗ trợ nhân viên và quản lý vận hành quán net tập trung.

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

## Chạy kiểm thử

Chạy toàn bộ test:

```powershell
python -m pytest
```

Chạy test kèm báo cáo coverage:

```powershell
python -m pytest --cov=cyberhub_manager --cov-report=term-missing
```

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