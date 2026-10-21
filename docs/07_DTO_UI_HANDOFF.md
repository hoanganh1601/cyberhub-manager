# Bản thống nhất DTO, service và UI — v1

Bản giao việc cho Hoàng Anh, Linh và Ngát sau HA-02. Tài liệu này bổ sung chi tiết còn thiếu trong `02_CODEBASE_SKELETON.md`; không phải code đã triển khai. Trưởng nhóm chuyển cùng tài liệu này cho cả hai thành viên. Phần thay đổi so với skeleton được ghi tại mục 12.

Nguồn: `01_REQUIREMENTS.md`, `02_CODEBASE_SKELETON.md`, `03_UI_THEME.md`, `04_LINEAR_BACKLOG.md`, `diagrams/logical_erd.md` và schema HA-02.

## 1. Phạm vi và người sở hữu

| Thành viên | Phần thực hiện ngay | Bàn giao |
|---|---|---|
| Linh | LI-01 rồi LI-02 | Domain, DTO, exception, service interface, mock và Class Diagram |
| Ngát | NG-01 | Theme, component catalog, UI state, gallery và wireflow |
| Hoàng Anh | HA-04 và HA-03 | Connection/transaction, migration/seed; dùng DTO/interface chung khi triển khai repository và Login sau này |

Ngát có thể làm token, layout và component với đầu vào giả được tiêm từ ngoài ngay. Linh bàn giao sớm DTO tối thiểu cho `EmployeeSession`, `CustomerSummary`, `MachineSummary` để nối mock; không chờ hoàn thành mọi service thật.

HA-11/Login UI thuộc Hoàng Anh. Ngát cung cấp password field/button/loading/error states, không nhận thêm màn Login vào NG-01. NG-02 và NG-03 là công việc tiếp theo, chưa nằm trong điều kiện hoàn thành NG-01.

Helper mật khẩu do Hoàng Anh triển khai dùng chung tại `src/cyberhub_manager/security.py`: `hash_password(raw_password: str) -> str`, `verify_password(raw_password: str, password_hash: str) -> bool`, dùng bcrypt đã khai báo trong dependencies. HA-03 và auth service thật gọi cùng helper này; Linh/Ngát không tạo helper khác. Mock chỉ dùng credential demo giả theo README, không yêu cầu helper production hoặc mật khẩu MySQL.

## 2. Quy ước dữ liệu

- ID: `int`; tiền: `int`, đơn vị VND. Không truyền tiền đã format, `float` hoặc `Decimal` sang UI trong P0.
- `balance`, `projected_balance` và số tiền giao dịch có thể âm. Phí, doanh thu, tiền bù là số không âm.
- SĐT: `str`, giữ số 0 đầu. Username được trim; password không bị tự động trim.
- Mốc thời gian qua service/DTO: `datetime` có timezone UTC. MySQL lưu `DATETIME` UTC không kèm timezone; lớp chuyển đổi gắn/bỏ timezone đúng tại biên DB.
- Bộ lọc ngày và dòng doanh thu: `date` theo ngày địa phương `Asia/Ho_Chi_Minh`. Service chuyển sang khoảng UTC nửa mở để truy vấn; UI không tự đổi điều kiện SQL.
- UI format tiền `25.000 VND`, thời gian `HH:mm dd/MM/yyyy`, thời lượng `1 giờ 12 phút`.
- Cột trạng thái dùng enum, không dùng nhãn tiếng Việt làm giá trị nghiệp vụ.
- DTO là dataclass chỉ đọc (`frozen=True`); service trả DTO/entity đã quy định, không trả cursor, tuple không tên hoặc dictionary thay DTO.
- Danh sách rỗng: `[]`. Đối tượng không tồn tại: `NotFoundError`. Giá trị chưa có: `None`, không dùng `0` hoặc chuỗi rỗng thay ID/thời gian.
- Không có `password` hoặc `password_hash` trong DTO trả về UI. Các trường generated `active_machine_id`/`active_customer_id` không xuất hiện trong DTO.
- Không thêm bảng/cột SQL để phục vụ mock. P0 không thêm promotion engine, chart, cổng thanh toán, in hóa đơn hay trường ghi chú giao dịch chưa có trong schema.

## 3. Enum thống nhất

Linh triển khai tại `domain/enums.py`, theo miền giá trị trong Logical ERD:

| Enum | Giá trị |
|---|---|
| `Role` | `ADMIN`, `MANAGER`, `STAFF` |
| `StoreStatus` | `ACTIVE`, `INACTIVE` |
| `EmployeeStatus` | `ACTIVE`, `INACTIVE`, `LOCKED` |
| `CustomerStatus` | `ACTIVE`, `INACTIVE` |
| `AccountStatus` | `ACTIVE`, `LOCKED` |
| `MachineStatus` | `AVAILABLE`, `IN_USE`, `MAINTENANCE` |
| `SessionStatus` | `ACTIVE`, `COMPLETED`, `CANCELLED` |
| `TransactionType` | `TOP_UP`, `PROMOTION`, `USAGE_PAYMENT`, `DEBT_SETTLEMENT` |
| `PaymentMethod` | `CASH`, `TRANSFER`, `ACCOUNT_BALANCE`, `PROMOTION` |
| `InvoiceStatus` | `PAID`, `VOID` |
| `MachineArchiveAction` | `DELETED`, `ARCHIVED` |

Giữ giá trị enum trùng SQL; `PROMOTION` được khai báo để khớp schema nhưng chưa có nghiệp vụ P1. Form nạp/bù tiền chỉ cho chọn `CASH` hoặc `TRANSFER`. Hai trường `customer_status` và `account_status` luôn tách biệt.

## 4. Domain và DTO

Linh giữ entity ở `domain/models.py`, tạo DTO ở `domain/dtos.py`. Không import UI hoặc MySQL connector vào hai module này.

### 4.1. Entity dùng ở kết quả service

| Entity | Trường công khai |
|---|---|
| `Account` | `id: int`, `code: str`, `customer_id: int`, `username: str`, `balance: int`, `status: AccountStatus` |
| `Customer` | `id: int`, `code: str`, `full_name: str`, `phone: str`, `status: CustomerStatus`, `account: Account` |
| `Machine` | `id: int`, `code: str`, `store_id: int`, `name: str`, `status: MachineStatus`, `hourly_rate: int`, `is_active: bool`, `updated_at: datetime` |

Các entity còn lại (`Employee`, `UsageSession`, `AccountTransaction`, `Invoice`) theo skeleton và schema; trường trạng thái có enum tương ứng, nullable có `| None`. Thông tin hash phục vụ xác thực chỉ nằm trong record nội bộ repository, không thêm vào các entity công khai ở trên.

### 4.2. DTO hiển thị

Các tên trường và kiểu dưới đây là giao kèo chung; hai thành viên không tự đổi tên riêng.

| DTO | Trường |
|---|---|
| `EmployeeSession` | `employee_id: int`, `employee_code: str`, `full_name: str`, `username: str`, `store_id: int`, `store_code: str`, `store_name: str`, `role: Role` |
| `CustomerSummary` | `customer_id: int`, `customer_code: str`, `full_name: str`, `phone: str`, `account_id: int`, `username: str`, `balance: int`, `customer_status: CustomerStatus`, `account_status: AccountStatus` |
| `SessionSummary` | `session_id: int`, `session_code: str`, `customer_id: int`, `customer_code: str`, `customer_name: str`, `machine_id: int`, `machine_code: str`, `machine_name: str`, `started_at: datetime`, `hourly_rate: int`, `status: SessionStatus` |
| `ActiveSessionSummary` | `session: SessionSummary`, `account_balance: int`, `elapsed_seconds: int`, `estimated_cost: int`, `projected_balance: int`, `as_of: datetime` |
| `MachineSummary` | `machine_id: int`, `machine_code: str`, `store_id: int`, `name: str`, `status: MachineStatus`, `hourly_rate: int`, `is_active: bool`, `updated_at: datetime`, `active_session: ActiveSessionSummary \| None` |
| `TransactionSummary` | `transaction_id: int`, `transaction_code: str`, `account_id: int`, `session_id: int \| None`, `type: TransactionType`, `amount: int`, `method: PaymentMethod`, `employee_id: int`, `employee_name: str`, `created_at: datetime` |
| `TopUpResult` | `customer_id: int`, `account_id: int`, `balance_before: int`, `balance_after: int`, `transaction: TransactionSummary` |
| `OpenSessionPreview` | `customer_id: int`, `machine_id: int`, `balance: int`, `hourly_rate: int`, `minimum_balance: int`, `estimated_minutes: int`, `can_open: bool`, `blocked_reason: str \| None`, `as_of: datetime` |
| `CheckoutPreview` | `session: SessionSummary`, `calculated_at: datetime`, `elapsed_seconds: int`, `billed_minutes: int`, `usage_cost: int`, `balance_before: int`, `projected_balance: int`, `settlement_required: int` |
| `InvoiceSummary` | `invoice_id: int`, `invoice_code: str`, `session_id: int`, `customer_id: int`, `customer_name: str`, `employee_id: int`, `employee_name: str`, `store_id: int`, `store_name: str`, `usage_cost: int`, `settlement_amount: int`, `total_amount: int`, `status: InvoiceStatus`, `created_at: datetime` |
| `InvoiceDetail` | `invoice: InvoiceSummary`, `session: SessionSummary`, `ended_at: datetime`, `billed_minutes: int` |
| `CheckoutResult` | `invoice: InvoiceDetail`, `balance_after: int` |
| `DailyRevenue` | `date: date`, `invoice_count: int`, `revenue: int` |
| `MachineArchiveResult` | `machine_id: int`, `action: MachineArchiveAction` |
| `InvoiceFilters` | `date_from: date \| None = None`, `date_to: date \| None = None`, `keyword: str = ""`, `customer_id: int \| None = None`, `status: InvoiceStatus \| None = None` |

Quy tắc nhất quán:

- `MachineSummary.status == IN_USE` thì có `active_session`; hai trạng thái còn lại trả `None`. Nếu DB thật không nhất quán, service báo lỗi, không dựng khách/phiên giả.
- Giá máy hiện tại nằm ở `MachineSummary.hourly_rate`; giá snapshot phiên nằm ở `active_session.session.hourly_rate`.
- `estimated_cost`, `projected_balance`, `billed_minutes`, `minimum_balance`, `estimated_minutes`, `settlement_required` do service tính. UI chỉ hiển thị và so sánh điều kiện enable từ dữ liệu trả về.
- Dashboard cập nhật 15 giây theo snapshot mới từ service. P0 không tự chạy công thức phí ở UI giữa hai snapshot.
- `preview_open` trả `can_open=False` khi chỉ thiếu số dư; kèm `blocked_reason` để UI hiện CTA nạp tiền. Sai đối tượng, bị khóa, máy bận hoặc xung đột khác dùng exception. Khi confirm, `open_session` kiểm tra lại và có thể raise `InsufficientBalanceError`.
- Checkout preview chỉ là ước tính. `complete_checkout` tính lại trong transaction; nếu tiền bù không còn đủ thì raise `SettlementRequiredError`, chưa thay đổi DB và UI tải preview mới.
- `settlement_amount` là phần tiền bù, không cộng thêm lần nữa vào `total_amount`; P0 giữ `total_amount = usage_cost`.
- `InvoiceDetail` có thể lấy tên và thông tin phiên qua JOIN; không suy diễn rằng schema đang snapshot tên khách/nhân viên.

## 5. Service interface dùng chung cho mock và thật

Linh tạo các `Protocol` tại `services/contracts.py`. Tham số trong ngoặc là thứ tự/keyword thống nhất; kiểu `actor` là `EmployeeSession`, `current_time` là datetime UTC, `filters` là `InvoiceFilters`. ID/amount/rate là `int`; tên/code/password/keyword là `str`; `enabled` là `bool`. Giá trị `status` dùng enum của entity tương ứng.

| Service | Hàm | Kết quả |
|---|---|---|
| Auth | `login(username, password)` | `EmployeeSession` |
| Customer | `create_customer(full_name, phone, username, password)` | `Customer` |
| Customer | `get_customer(customer_id)` | `Customer` |
| Customer | `search_customers(keyword)` | `list[CustomerSummary]` |
| Customer | `update_customer(customer_id, full_name, phone)` | `Customer` |
| Customer | `set_customer_status(customer_id, status, actor)` | `Customer` |
| Wallet | `top_up(customer_id, amount, method, employee_id)` | `TopUpResult` |
| Wallet | `get_history(customer_id)` | `list[TransactionSummary]` |
| Machine | `list_machines(store_id)` | `list[MachineSummary]` |
| Machine | `create_machine(code, store_id, name, hourly_rate, actor)` | `Machine` |
| Machine | `update_machine(machine_id, name, hourly_rate, actor)` | `Machine` |
| Machine | `set_maintenance(machine_id, enabled, actor)` | `Machine` |
| Machine | `archive_machine(machine_id, actor)` | `MachineArchiveResult` |
| Session | `preview_open(customer_id, machine_id, actor)` | `OpenSessionPreview` |
| Session | `open_session(customer_id, machine_id, actor)` | `SessionSummary` |
| Session | `preview_checkout(machine_id, current_time)` | `CheckoutPreview` |
| Session | `complete_checkout(machine_id, actor, settlement_amount, method)` | `CheckoutResult` |
| Report | `list_invoices(store_id, filters)` | `list[InvoiceSummary]` |
| Report | `get_invoice(invoice_id)` | `InvoiceDetail` |
| Report | `daily_revenue(store_id, date_from, date_to)` | `list[DailyRevenue]` |

Chốt thêm để không phải tự đoán:

- Tên Protocol: `AuthServiceProtocol`, `CustomerServiceProtocol`, `WalletServiceProtocol`, `MachineServiceProtocol`, `SessionServiceProtocol`, `ReportServiceProtocol`.
- `ServiceBundle` tại cùng module chứa sáu trường `auth`, `customers`, `wallet`, `machines`, `sessions`, `reports`, lần lượt mang các Protocol trên. Các view nhận dependency từ ngoài, không tự khởi tạo service/repository.
- `method` của top-up là `PaymentMethod.CASH` hoặc `TRANSFER`. Checkout không cần bù: `settlement_amount=0`, `method=None`; nếu cần bù thì method bắt buộc là CASH/TRANSFER. Kiểu tham số checkout là `PaymentMethod | None`.
- `set_customer_status` nhận `CustomerStatus`: INACTIVE đồng thời khóa account; ACTIVE đồng thời mở account. Service làm cùng transaction; không tự kết thúc phiên đang chạy. Không có nút sửa trực tiếp số dư.
- `archive_machine`: máy chưa có lịch sử trả `DELETED`; máy có lịch sử đặt `is_active=False`, trả `ARCHIVED`; không tạo MachineStatus mới. Máy IN_USE bị từ chối. Danh sách máy vận hành chỉ trả `is_active=True`.
- `date_from`/`date_to` là ngày đầu/ngày cuối được chọn, bao gồm cả hai ngày. Thiếu một đầu mốc trong `InvoiceFilters` nghĩa là không giới hạn phía đó; nếu có cả hai thì từ ngày <= đến ngày. Revenue yêu cầu đủ hai mốc và chỉ cộng invoice PAID. Dòng DailyRevenue chỉ có những ngày có invoice PAID; UI tổng hợp count/tổng từ các dòng, danh sách rỗng hiển thị 0.
- Các ID nhân viên/cửa hàng và actor trên UI lấy từ EmployeeSession, không nhập tay. Service thật được khởi tạo/gắn với ngữ cảnh phiên đã đăng nhập và kiểm tra scope/role; không tin employee_id/store_id/actor tùy ý từ caller. Mock cũng phải có trường hợp từ chối quyền.
- Service và mock dùng cùng chữ ký, DTO, exception. Protocol chỉ là giao kèo; chưa triển khai SQL/business service thật trong LI-02.

## 6. Exception và cách UI hiển thị

Linh tạo `ApplicationError` gốc với `code: str`, `message: str`, `field_errors: dict[str, str]` và `details: dict[str, object]`; hai dictionary mặc định rỗng. `details` chỉ chứa dữ liệu nghiệp vụ được cho phép, không chứa câu SQL, credential hay traceback.

| Exception | Code | Ngát xử lý |
|---|---|---|
| `ValidationError` | `VALIDATION_ERROR` | Gắn `field_errors` vào đúng field; giữ giá trị nhập |
| `AuthenticationError` | `AUTH_INVALID_CREDENTIALS` | Thông báo chung; giữ username, xóa password |
| `NotFoundError` | `NOT_FOUND` | Thông báo đối tượng không còn tồn tại, refresh danh sách |
| `ConflictError` | `CONFLICT` | Dialog cảnh báo, giữ form, cho refresh/thử lại |
| `PermissionDeniedError` | `PERMISSION_DENIED` | Báo không có quyền, không thực hiện thay đổi |
| `InsufficientBalanceError` | `INSUFFICIENT_BALANCE` | Giữ dialog mở phiên, tải preview mới, hiện CTA nạp tiền |
| `SettlementRequiredError` | `SETTLEMENT_REQUIRED` | Giữ checkout, tải preview mới, focus field tiền bù |
| `ServiceUnavailableError` | `SERVICE_UNAVAILABLE` | Thông báo không tải được dữ liệu, có nút Thử lại |

Tên field lỗi: `full_name`, `phone`, `username`, `password`, `amount`, `method`, `code`, `name`, `hourly_rate`, `customer_id`, `machine_id`, `settlement_amount`, `date_from`, `date_to`. Ví dụ lỗi trùng SĐT: `ConflictError`, code CONFLICT, `field_errors={"phone": "Số điện thoại đã được sử dụng"}`; UI vừa đánh dấu field vừa hiển thị thông báo phù hợp.

Lỗi xác thực luôn dùng nội dung "Tên đăng nhập hoặc mật khẩu không đúng". Ngoại lệ kỹ thuật ngoài dự kiến được log và hiển thị thông báo chung; không dùng repr(exception) làm text trên UI.

## 7. UI state và component API

Ngát tạo `ui/state.py` chứa `ViewState`: `LOADING`, `READY`, `EMPTY`, `ERROR`. Trạng thái submit là cờ `is_submitting: bool` riêng của form, không phải trạng thái máy/tài khoản.

| Trạng thái | Hiển thị | Hành vi |
|---|---|---|
| LOADING | "Đang tải dữ liệu…" | Disable action phụ thuộc dữ liệu |
| READY | Dữ liệu thật hoặc mock hợp lệ | Enable action theo dữ liệu và quyền |
| EMPTY | "Chưa có dữ liệu phù hợp" | Cho thay bộ lọc hoặc tạo mới nếu có quyền |
| ERROR | Thông báo thân thiện + "Thử lại" | Retry cùng service operation |
| is_submitting=True | "Đang xử lý…" | Disable submit, chặn double click; giữ dữ liệu form |

Sau cả thành công và thất bại phải thoát trạng thái submitting. Đóng view hủy lịch refresh của view; tránh đăng ký hai vòng refresh. Refresh nền thất bại có thể giữ snapshot trước và đánh dấu đã cũ, không giả vờ snapshot đó vừa được cập nhật.

API ngoài tối thiểu của component để người khác dùng ổn định (constructor của CustomTkinter do Ngát tự tổ chức):

| Component/module | API chốt |
|---|---|
| `ui/components/form_field.py` | `FormField.get_value() -> str`, `set_value(value: str)`, `set_error(message: str \| None)`, `set_enabled(enabled: bool)`; password field có hiện/ẩn |
| `ui/components/data_table.py` | `DataTable.set_columns(columns)`, `set_rows(rows)`, `set_state(state, message=None)`, `set_on_select(callback)` |
| Dữ liệu bảng trong `data_table.py` | `TableColumn(key: str, label: str, align: str)` với align left/right/center; `TableRow(key: int \| str, cells: dict[str, str])`; callback nhận row key, không nhận vị trí dòng |
| `ui/components/machine_card.py` | `MachineCard.render(machine: MachineSummary, actor: EmployeeSession)`, `set_busy(busy: bool)`, `set_on_open(callback)`, `set_on_checkout(callback)`, `set_on_maintenance(callback)`; callback nhận machine_id |
| `ui/components/toast.py` | `ToastManager.show(message: str, kind: str = "info")`; kind info/success/warning/error |
| `ui/components/action_button.py` mới | `ActionButton.set_busy(busy: bool)`, `set_enabled(enabled: bool)`; busy giữ nhãn gốc để phục hồi |
| `ui/components/status_badge.py` mới | `StatusBadge.set_status(status)` nhận enum nghiệp vụ, tự chọn nhãn/icon/token |
| `ui/components/confirm_dialog.py` mới | `ConfirmDialog.ask(parent, title: str, message: str) -> bool`; gọi từ UI thread, không thực hiện nghiệp vụ |

`TableRow` và `TableColumn` là cấu trúc trình bày nội bộ UI, được adapter của view tạo từ DTO; đây không phải dictionary thô do service trả về. Mọi hàm callback nhận ID ổn định, không phụ thuộc thứ tự sắp xếp bảng. Có thể thêm phương thức phụ, không đổi API trên mà không cập nhật giao kèo.

## 8. Nhãn, quyền và format

Theme dùng nguyên token/kích thước/font trong `03_UI_THEME.md`; không chọn bảng màu mới. Ngát tạo thêm `ui/formatters.py` với `format_money(amount: int)`, `format_datetime(value: datetime)`, `format_duration(seconds: int)` để các view tái sử dụng. Trạng thái luôn có chữ + icon, không chỉ có màu.

| Trạng thái | Nhãn | Token | Action |
|---|---|---|---|
| Máy AVAILABLE | Trống | SUCCESS | Mở phiên |
| Máy IN_USE | Đang dùng | DANGER | Checkout |
| Máy MAINTENANCE | Bảo trì | WARNING | STAFF xem; MANAGER/ADMIN có Bật lại |
| Customer ACTIVE/INACTIVE | Hoạt động / Ngừng hoạt động | SUCCESS / DISABLED | Đổi trạng thái chỉ MANAGER/ADMIN |
| Account ACTIVE/LOCKED | Hoạt động / Đã khóa | SUCCESS / DANGER | Hiện riêng với trạng thái customer |
| Máy is_active=False | Ngừng sử dụng | DISABLED | Không xuất hiện trong dashboard vận hành |

Menu quản lý máy và action quản trị máy/khóa khách chỉ cho MANAGER/ADMIN. Nạp tiền, mở phiên, checkout cho nhân viên đăng nhập đúng cửa hàng. Service kiểm tra quyền lại dù UI đã ẩn nút.

Chốt quyền xem invoice/revenue P0 theo backlog LI-08 và menu trong tài liệu theme: STAFF, MANAGER và ADMIN đều xem dữ liệu của cửa hàng hiện tại; quản lý nhiều cửa hàng là P1. STAFF không chọn store khác. Đây là điểm làm rõ so với bảng vai trò khái quát trong requirements (đang ghi STAFF chỉ xem hóa đơn vừa tạo); Hoàng Anh cập nhật bảng vai trò đó cho khớp khi nhận bàn giao, không để mỗi thành viên tự chọn một cách hiểu.

Machine card dùng `active_session.projected_balance` để cảnh báo âm, không dùng nhầm account_balance. Text cảnh báo dạng "Âm 10.000 VND". Mở phiên và checkout dựa trên preview từ service; UI không tự tính phí, số phút làm tròn hoặc số dư tối thiểu.

Không chạy service/DB call có thể chặn lâu trên Tk main thread. UI cập nhật widget ở main thread; nếu dùng worker thì kết quả được chuyển về bằng `after`. Không để worker trực tiếp thay widget. Gallery loading có thể dùng `after` giả lập độ trễ, không cần gọi DB.

## 9. Mock dùng chung

Linh tạo package `services/mocks/`. Đầu vào thống nhất:

- `build_mock_services(scenario: MockScenario = MockScenario.SUCCESS) -> ServiceBundle`.
- `MockScenario` đặt trong `services/mocks/scenarios.py`: `SUCCESS`, `EMPTY`, `VALIDATION_ERROR`, `CONFLICT`, `UNAVAILABLE`.
- Lỗi phải phát sinh ở operation được chọn cho kịch bản (ví dụ validation ở create_customer/top_up, conflict ở open_session), không làm mọi hàm đồng loạt thất bại. Bàn giao bảng operation nào bị tác động trong README của mock.
- Mock role lấy qua login/EmployeeSession; trường hợp STAFF không có quyền quản trị được kiểm tra riêng, không đổi mọi lần gọi thành PermissionDenied.
- Mock không kết nối MySQL, không đọc `.env` và không cần Docker. Dữ liệu demo hoàn toàn giả.
- Mỗi lần gọi factory tạo bộ dữ liệu mới. Sáu service trong cùng bundle chia sẻ dữ liệu; không tạo mỗi service một danh sách riêng.
- Mock chỉ mô phỏng thay đổi cần cho luồng demo; không sao chép toàn bộ công thức phí, locking, SQL transaction của service thật.
- Clock mock cố định và có thể điều khiển để tái hiện preview/checkout. Không gọi `datetime.now()` riêng rẽ ở mỗi mock gây lệch số liệu.

Fixture SUCCESS: 1 cửa hàng, 1 manager, 2 staff, 20 máy, 5 khách. Tất cả thời điểm có timezone UTC. Mốc tham chiếu mặc định `2026-10-18T09:00:00+00:00`, tương ứng 16:00 ở Việt Nam. Có hướng dẫn tài khoản demo giả trong README mock, không tái sử dụng credential MySQL thật.

| Máy | Trạng thái | Nội dung snapshot tại mốc tham chiếu |
|---|---|---|
| PC01 | AVAILABLE | Không có active_session, 10.000 VND/giờ |
| PC02 | IN_USE | KH002, account_balance=5.000; bắt đầu 90 phút trước, rate snapshot=10.000; estimated_cost=15.000; projected_balance=-10.000 |
| PC03 | MAINTENANCE | Không có active_session, 10.000 VND/giờ |
| PC05 | IN_USE | KH005, account_balance=100.000; bắt đầu 30 phút trước, rate snapshot=10.000; estimated_cost=5.000; projected_balance=95.000 |
| PC04, PC06–PC20 | AVAILABLE | Không có active_session, 10.000 VND/giờ |

Tổng snapshot: 20 máy; 17 trống; 2 đang dùng; 1 bảo trì; 1 phiên có projected_balance âm.

| Khách | CustomerStatus | AccountStatus | balance | Phiên |
|---|---|---|---:|---|
| KH001 | ACTIVE | ACTIVE | 50.000 | Không |
| KH002 | ACTIVE | ACTIVE | 5.000 | PC02 |
| KH003 | ACTIVE | LOCKED | 20.000 | Không |
| KH004 | INACTIVE | LOCKED | -5.000 | Không |
| KH005 | ACTIVE | ACTIVE | 100.000 | PC05 |

Tạo một số lịch sử giao dịch và invoice COMPLETED/PAID giả để gallery có thể xem bảng. Invoice phải tham chiếu phiên COMPLETED riêng, không dùng hai phiên ACTIVE trên. EMPTY trả danh sách `[]` cho màn đang demo; không trả None hoặc fake record trống.

## 10. Nghiệm thu chung giữa Linh và Ngát

Ngát thêm `ui/component_gallery.py`, chạy độc lập bằng lệnh dự kiến:

```powershell
python -m cyberhub_manager.ui.component_gallery
```

Đây là đầu ra Ngát phải triển khai, chưa phải lệnh đã hoạt động ở skeleton hiện tại. Gallery nhận bundle do Linh cung cấp; trong lúc chờ mock có thể tiêm DTO mẫu trực tiếp, sau đó thay bằng factory chung. Không sửa entry point production/app.py hoặc Login để chỉ phục vụ catalog.

| Kiểm tra | Kết quả cần thấy |
|---|---|
| Không chạy Docker, không có `.env` | Gallery/mock vẫn mở được |
| Đổi SUCCESS → EMPTY → UNAVAILABLE | Dữ liệu, empty state, error/retry đúng |
| PC01, PC02, PC03 | Đủ ba trạng thái máy; PC02 cảnh báo âm đúng |
| Render datetime UTC 09:00 | Hiện 16:00 giờ Việt Nam, không đổi hai lần |
| SĐT bắt đầu bằng 0; balance âm | Không mất số 0, format tiền và màu đúng |
| Submit gặp validation/conflict | Giữ input, hiện đúng field/dialog, nút được enable lại |
| Double click khi busy | Một callback được nhận |
| Đổi manager → staff | Action quản trị bị ẩn/disable; mock cũng từ chối nếu gọi thẳng |
| Nạp tiền qua mock rồi tải lại dữ liệu | Customer balance và lịch sử cùng được cập nhật trong bundle |
| Chạy ở 1280×720 | Không cắt nút, bảng/dialog dùng được với Tab/Enter |

Linh kiểm tra DTO/interface/mock và các hành vi stateful quan trọng. Ngát kiểm tra gallery/keyboard/UI state, chụp ảnh. Hoàng Anh kiểm tra tương thích schema và thay mock bằng service thật mà không phải đổi field trong view. Không viết test chỉ để kiểm tra dataclass có đúng các field đã khai báo.

## 11. Trình tự bàn giao và tránh sửa đè

1. Cả hai cập nhật develop đã có HA-02, làm nhánh riêng.
2. Ngát bắt đầu theme/layout/component với input được tiêm; Linh bàn giao LI-01 trước, gồm DTO tối thiểu và enum/exception.
3. Linh cập nhật `02_CODEBASE_SKELETON.md` phần interface/DTO theo mục 12 và Class Diagram. Hoàng Anh đối chiếu schema; Ngát đối chiếu field cần render.
4. Linh bàn giao LI-02 (Protocol, bundle, mock, README dùng mock). Ngát nối gallery vào factory chung; không tự khai báo bản sao CustomerSummary/MachineSummary.
5. Cả nhóm chạy bảng nghiệm thu ở mục 10, ghi kết quả ngắn vào task. Sau đó mở công việc NG-02/NG-03 và service thật theo dependency.

Linh sở hữu `domain/`, `services/contracts.py`, `services/mocks/`, tài liệu hợp đồng và Class Diagram. Ngát sở hữu `ui/theme.py`, `ui/state.py`, `ui/formatters.py`, `ui/components/`, `ui/component_gallery.py`, UI wireflow. Hoàng Anh sở hữu SQL, connection, migration/seed, repository và Login. Thay đổi contract qua một đầu mối Linh và trưởng nhóm, không tự sửa DTO riêng ở mỗi nhánh.

## 12. Những điểm cần đồng bộ vào tài liệu cũ

Các điểm sau là quyết định thiết kế được bổ sung trong bản bàn giao này, chưa phải implementation sẵn có:

1. Tách enum status theo entity như Logical ERD thay cho một CommonStatus dùng cho mọi bảng.
2. Thêm `domain/dtos.py`, chốt field/type tại mục 4; bổ sung `is_active` và `updated_at` công khai cho Machine.
3. Bổ sung hàm đọc `get_customer` và `get_invoice` để UI xem chi tiết qua service.
4. Chốt `OpenSessionPreview`, `CheckoutPreview`, `InvoiceDetail`, `CheckoutResult`, `MachineArchiveResult`; bỏ kiểu kết quả archive mơ hồ.
5. Preview mở phiên thiếu tiền trả can_open=False để UI render; thao tác confirm vẫn kiểm tra và raise lỗi nghiệp vụ khi cần.
6. Chốt semantics khóa/mở customer+account và checkout không bù có method=None.
7. Chuẩn hóa hậu tố Error (`PermissionDeniedError`, `InsufficientBalanceError`, `SettlementRequiredError`), thêm ApplicationError/ServiceUnavailableError và field_errors.
8. Bổ sung Protocol, ServiceBundle, mock factory, UI state/component API và gallery để thử độc lập.
9. Chốt helper hash/verify dùng chung do Hoàng Anh sở hữu; chốt quyền xem invoice/revenue theo cửa hàng tại mục 8, đồng bộ bảng vai trò trong requirements.

Không có điểm nào ở trên yêu cầu đổi schema HA-02. Những điểm dependency của backlog (bàn giao insert giao dịch ví sớm trong HA-06; bỏ vòng LI-10 ↔ NG-08) do trưởng nhóm cập nhật riêng trước khi giao các task liên quan, không lẫn vào NG-01/LI-01/LI-02.
