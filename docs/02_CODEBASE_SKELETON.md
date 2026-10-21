# 2. Khung code và hợp đồng module

Tài liệu này quy định cấu trúc mà nhóm sẽ tạo. Hiện chưa có implementation để tránh làm thay phần của các thành viên.

Repository đã có sẵn các file placeholder chứa owner/task nhưng chưa có logic. Git theo dõi được toàn bộ cây thư mục; thành viên thay nội dung placeholder khi bắt đầu Linear issue tương ứng. Các thư mục Python có thêm `__init__.py` dù cây bên dưới lược bớt để dễ đọc.

## 2.1. Cấu trúc thư mục chuẩn

```text
cyberhub-manager/                   # repository/thư mục project
├── README.md
├── requirements.txt              # customtkinter, pillow, mysql-connector-python, pytest...
├── pyproject.toml                # cấu hình project/test/format
├── .env.example                  # MYSQL_HOST/PORT/DATABASE/USER/PASSWORD, LOG_LEVEL
├── docker-compose.yml            # pin image mysql:8.4 cho môi trường local
├── docs/
│   ├── 01_REQUIREMENTS.md
│   ├── 02_CODEBASE_SKELETON.md
│   ├── 03_UI_THEME.md
│   ├── 04_LINEAR_BACKLOG.md
│   ├── 05_GITHUB_WORKFLOW.md
│   ├── 06_KICKOFF_CHECKLIST.md
│   ├── linear_import.csv
│   └── diagrams/
│       ├── erd.md                # Mermaid/ảnh ERD và cardinality
│       ├── class_diagram.md      # Domain/service class diagram
│       └── activity_diagrams.md  # Nạp tiền, mở phiên, checkout
├── scripts/
│   ├── init_db.py                # chạy migration
│   └── seed_db.py                # tạo dữ liệu demo
├── sql/
│   ├── 001_initial_schema.sql
│   ├── 002_indexes.sql
│   └── seed.sql                  # chỉ dữ liệu không cần hash password
├── src/
│   └── cyberhub_manager/
│       ├── app.py                # composition root, chạy ứng dụng
│       ├── config.py             # đọc cấu hình
│       ├── domain/
│       │   ├── models.py         # dataclass/entity
│       │   ├── enums.py          # status/role/type
│       │   └── exceptions.py     # lỗi nghiệp vụ
│       ├── database/
│       │   ├── connection.py     # MySQL connection pool/factory
│       │   └── transaction.py    # begin/commit/rollback
│       ├── repositories/
│       │   ├── auth_repository.py
│       │   ├── customer_repository.py
│       │   ├── account_repository.py
│       │   ├── machine_repository.py
│       │   ├── session_repository.py
│       │   └── invoice_repository.py
│       ├── services/
│       │   ├── auth_service.py
│       │   ├── customer_service.py
│       │   ├── wallet_service.py
│       │   ├── machine_service.py
│       │   ├── session_service.py
│       │   └── report_service.py
│       └── ui/
│           ├── theme.py          # token màu/font/spacing duy nhất
│           ├── app_shell.py      # sidebar/header/content
│           ├── login_view.py     # Hoàng Anh implement, Ngát review UI
│           ├── dashboard_view.py
│           ├── customers_view.py
│           ├── machine_management_view.py
│           ├── invoices_view.py
│           ├── reports_view.py
│           ├── dialogs/
│           │   ├── customer_dialog.py
│           │   ├── machine_dialog.py
│           │   ├── topup_dialog.py
│           │   ├── open_session_dialog.py
│           │   └── checkout_dialog.py
│           └── components/
│               ├── machine_card.py
│               ├── data_table.py
│               ├── form_field.py
│               └── toast.py
└── tests/
    ├── conftest.py               # DB tạm và fixtures
    ├── unit/
    │   ├── test_wallet_service.py
    │   └── test_session_service.py
    ├── integration/
    │   ├── test_customer_flow.py
    │   ├── test_machine_management_flow.py
    │   └── test_checkout_flow.py
    └── manual/
        └── CHECKLIST.md
```

## 2.2. Trách nhiệm từng layer

| Layer | Được làm | Không được làm |
|---|---|---|
| `ui` | Render, lấy input, validation hình thức, gọi service, hiển thị kết quả/lỗi | SQL trực tiếp; tự cộng/trừ tiền; tự quyết định business rule |
| `services` | Điều phối use case, validation nghiệp vụ, transaction boundary, tính phí | Tạo widget; phụ thuộc UI |
| `repositories` | Chứa SQL và map row dữ liệu | Chứa quy tắc tính phí hoặc hiển thị message |
| `database` | Kết nối, transaction, migration | Biết màn hình hoặc use case |
| `domain` | Model, enum, exception dùng chung | Import UI/database concrete |

Chiều import bắt buộc: `ui -> services -> repositories -> database`; `domain` có thể được dùng bởi mọi layer nhưng không import ngược lại.

## 2.3. Model và enum thống nhất

### Model tối thiểu

- `Employee`: id, code, full_name, store_id, username, role, status.
- `Customer`: id, code, full_name, phone, status, account.
- `Account`: id, code, customer_id, username, balance, status; số dư chỉ đổi qua service.
- `Machine`: id, code, store_id, name, status, hourly_rate.
- `UsageSession`: id, code, customer_id, machine_id, opened_by, closed_by, started_at, ended_at, hourly_rate, cost, status.
- `AccountTransaction`: id, code, account_id, employee_id, session_id, type, amount, method, created_at.
- `Invoice`: id, code, session_id, customer_id, employee_id, store_id, usage_cost, settlement_amount, total_amount, status, created_at.

### Enum

| Enum | Giá trị |
|---|---|
| `Role` | `ADMIN`, `MANAGER`, `STAFF` |
| `CommonStatus` | `ACTIVE`, `INACTIVE`, `LOCKED` theo entity |
| `MachineStatus` | `AVAILABLE`, `IN_USE`, `MAINTENANCE` |
| `SessionStatus` | `ACTIVE`, `COMPLETED`, `CANCELLED` |
| `TransactionType` | `TOP_UP`, `PROMOTION`, `USAGE_PAYMENT`, `DEBT_SETTLEMENT` |
| `PaymentMethod` | `CASH`, `TRANSFER`, `ACCOUNT_BALANCE`, `PROMOTION` |
| `InvoiceStatus` | `PAID`, `VOID` |

Không dùng chuỗi tự gõ rải rác ngoài enum.

## 2.4. Public contract giữa UI và service

Tên dưới đây phải chốt trước khi Linh và Ngát làm song song. Có thể đổi tên một lần trong buổi kickoff; sau đó đổi phải báo cả nhóm.

| Service | Operation | Input | Output chính | Lỗi nghiệp vụ |
|---|---|---|---|---|
| `AuthService` | `login` | username, password | `EmployeeSession` | `AuthenticationError` |
| `CustomerService` | `create_customer` | full_name, phone, username, password | `Customer` | `ValidationError`, `ConflictError` |
| `CustomerService` | `search_customers` | keyword | list `CustomerSummary` | — |
| `CustomerService` | `update_customer` | customer_id, full_name, phone | `Customer` | `NotFoundError`, `ConflictError` |
| `CustomerService` | `set_customer_status` | customer_id, status, actor | `Customer` | `NotFoundError`, `PermissionDenied`, `ConflictError` |
| `WalletService` | `top_up` | customer_id, amount, method, employee_id | `TopUpResult` | `ValidationError`, `NotFoundError` |
| `WalletService` | `get_history` | customer_id | list `TransactionSummary` | — |
| `MachineService` | `list_machines` | store_id | list `MachineSummary` gồm dữ liệu phiên live | — |
| `MachineService` | `create_machine` | code, store_id, name, hourly_rate, actor | `Machine` | `ValidationError`, `PermissionDenied`, `ConflictError` |
| `MachineService` | `update_machine` | machine_id, name, hourly_rate, actor | `Machine` | `NotFoundError`, `PermissionDenied`, `ConflictError` |
| `MachineService` | `set_maintenance` | machine_id, enabled, actor | `Machine` | `PermissionDenied`, `ConflictError` |
| `MachineService` | `archive_machine` | machine_id, actor | `Machine` hoặc kết quả xóa | `NotFoundError`, `PermissionDenied`, `ConflictError` |
| `SessionService` | `preview_open` | customer_id, machine_id, actor | minimum balance, estimated minutes | `ConflictError`, `InsufficientBalance` |
| `SessionService` | `open_session` | customer_id, machine_id, actor | `SessionSummary` | như trên |
| `SessionService` | `preview_checkout` | machine_id, current_time | minutes, cost, projected balance, settlement required | `NotFoundError` |
| `SessionService` | `complete_checkout` | machine_id, actor, settlement amount/method | `CheckoutResult` + invoice | `SettlementRequired`, `ConflictError` |
| `ReportService` | `list_invoices` | store_id, filters | list `InvoiceSummary` | — |
| `ReportService` | `daily_revenue` | store_id, date range | list `DailyRevenue` | `ValidationError` |

Quy ước output: service trả dataclass/DTO, không trả raw MySQL cursor row/dictionary, tuple không tên hoặc widget.

Quy ước quyền và xóa máy:

- `set_customer_status`, `create_machine`, `update_machine`, `set_maintenance`, `archive_machine` chỉ chấp nhận actor `MANAGER` hoặc `ADMIN` đúng cửa hàng.
- `archive_machine` xóa cứng nếu máy chưa có lịch sử; nếu đã có phiên thì chuyển sang trạng thái archive/inactive theo schema đã chốt.
- UI không tự suy luận quyền; service luôn kiểm tra lại để tránh bypass.

## 2.5. Exception contract

| Exception | UI xử lý |
|---|---|
| `ValidationError` | Hiện lỗi ngay dưới field hoặc dialog warning |
| `AuthenticationError` | Giữ màn login, xóa password, hiện message chung |
| `NotFoundError` | Toast/dialog và refresh dữ liệu |
| `ConflictError` | Dialog cảnh báo; enable lại nút thao tác |
| `PermissionDeniedError` | Dialog lỗi quyền; ghi log |
| `InsufficientBalanceError` | Hiện số dư tối thiểu, nút chuyển sang nạp tiền |
| `SettlementRequiredError` | Giữ checkout dialog, focus ô tiền bù |
| Lỗi hệ thống khác | Message “Có lỗi hệ thống”; log stack trace; không show SQL/traceback cho user |

## 2.6. Transaction boundary

Chỉ service mở transaction. Repository nhận connection của transaction hiện tại và **không tự commit**.

Với dữ liệu có cạnh tranh, service phải đọc bản ghi bằng `SELECT ... FOR UPDATE` sau khi bắt đầu transaction. Connection phải giữ nguyên từ lúc khóa đến lúc commit/rollback; không mở connection mới giữa use case.

- Tạo khách: insert customer + insert account.
- Nạp tiền: update balance + insert transaction (+ promotion transaction).
- Mở phiên: insert session + update machine.
- Checkout: update balance + insert transaction(s) + complete session + update machine + insert invoice.

Mỗi nhóm lệnh trên phải commit toàn bộ hoặc rollback toàn bộ.

## 2.7. Quy ước code và Git

- Python: PEP 8, type hints cho public function, docstring cho business rule khó.
- Tên Python/SQL: tiếng Anh `snake_case`; text UI và tài liệu: tiếng Việt có dấu.
- Không commit `.env`, MySQL credential, database dump chứa dữ liệu thật, file log hoặc thư mục virtual environment.
- Branch: `main` luôn chạy được; `develop` để tích hợp; task dùng `feature/HA-01-schema`, `feature/LI-03-wallet`, `feature/NG-03-dashboard`.
- PR cần: link Linear issue, ảnh/video chức năng nếu có UI, test result và migration note nếu đổi DB.
- Một PR ưu tiên dưới 500 dòng thay đổi; schema hoặc contract đổi cần Hoàng Anh review, theme/UI đổi cần Ngát review, business rule đổi cần Linh review.

## 2.8. Definition of Ready / Done

Issue chỉ bắt đầu khi có input/output, acceptance criteria, dependency và mock/service contract. Issue hoàn thành khi code chạy, có validation/error states, test phù hợp, không phá test cũ, cập nhật tài liệu và được ít nhất một thành viên khác review.

## 2.9. Ngoại lệ ownership cho Login UI

- Hoàng Anh sở hữu `login_view.py` và tích hợp `AuthService` vì đây là vertical slice nối trực tiếp auth repository/backend.
- Ngát cung cấp token/component từ NG-01 và review layout, spacing, wording, keyboard/focus state.
- Linh review validation, `AuthenticationError` và hành vi login/logout.
- Hoàng Anh không tự tạo màu/font riêng; Login phải dùng component/theme chung của Ngát.
