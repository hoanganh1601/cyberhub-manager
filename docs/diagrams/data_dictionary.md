# Data dictionary — CyberHub Manager

<!-- File sinh tự động bởi scripts/gen_data_dictionary.py từ schema MySQL. Không sửa tay;
     sửa DESCRIPTIONS trong script rồi chạy lại. -->

Nguồn: `sql/001_initial_schema.sql` + `sql/002_indexes.sql` + `sql/003_p1_management_wallet.sql` + `sql/004_customer_notifications.sql` (MySQL 8.4, InnoDB, utf8mb4). Quy ước:
tiền là `BIGINT` đơn vị VND, thời gian là `DATETIME` lưu UTC, mọi khóa ngoại `RESTRICT` (không xóa dây chuyền).

## 1. Danh sách bảng

| Bảng | Mục đích | Số cột |
|---|---|---:|
| [`stores`](#stores) | Cửa hàng net. Nhân viên, máy và hóa đơn đều thuộc một cửa hàng. | 7 |
| [`employees`](#employees) | Nhân viên đăng nhập ứng dụng; vai trò quyết định quyền thao tác. | 10 |
| [`customers`](#customers) | Thông tin cá nhân của khách chơi. | 7 |
| [`accounts`](#accounts) | Tài khoản đăng nhập máy trạm và ví tiền của khách; mỗi khách đúng một tài khoản. | 11 |
| [`machines`](#machines) | Máy trạm của cửa hàng và trạng thái hiện tại. | 9 |
| [`usage_sessions`](#usage_sessions) | Một lần khách dùng một máy, từ lúc mở đến lúc checkout. | 13 |
| [`account_transactions`](#account_transactions) | Sổ cái biến động số dư: mọi lần cộng/trừ `accounts.balance` đều có đúng một dòng; không sửa, không xóa. | 11 |
| [`invoices`](#invoices) | Hóa đơn tạo khi checkout thành công; lưu lại khách, nhân viên, cửa hàng để giữ đúng lịch sử. | 12 |
| [`promotions`](#promotions) | Chính sách thưởng theo mốc nạp, phạm vi và thời gian. | 10 |
| [`management_audit`](#management_audit) | Lịch sử thay đổi quản trị, không lưu mật khẩu. | 6 |
| [`customer_notification_reads`](#customer_notification_reads) | Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền. | 3 |

## 2. Quan hệ và cardinality

Đọc từ khóa ngoại: phía cha là `1` khi cột FK `NOT NULL`, `0..1` khi cho phép NULL;
phía con là `0..1` khi cột FK có UNIQUE, ngược lại `0..n`.

| Cha | | Con | Khóa ngoại | Ý nghĩa |
|---|:---:|---|---|---|
| `stores` | 1 — 0..n | `employees` | `employees.store_id` → `stores.id` | Cửa hàng nhân viên làm việc. |
| `stores` | 1 — 0..n | `machines` | `machines.store_id` → `stores.id` | Cửa hàng sở hữu máy. |
| `stores` | 0..1 — 0..n | `account_transactions` | `account_transactions.store_id` → `stores.id` | Cơ sở ghi nhận giao dịch tại thời điểm phát sinh. |
| `stores` | 1 — 0..n | `invoices` | `invoices.store_id` → `stores.id` | Cửa hàng; dùng cho báo cáo doanh thu. |
| `stores` | 0..1 — 0..n | `promotions` | `promotions.store_id` → `stores.id` | Cơ sở áp dụng; NULL = toàn hệ thống. |
| `stores` | 1 — 0..n | `management_audit` | `management_audit.store_id` → `stores.id` | Cơ sở đang vận hành. |
| `employees` | 0..1 — 0..n | `usage_sessions` | `usage_sessions.closed_by` → `employees.id` | Nhân viên checkout; NULL khi phiên đang chạy. |
| `employees` | 1 — 0..n | `usage_sessions` | `usage_sessions.opened_by` → `employees.id` | Nhân viên mở phiên. |
| `employees` | 1 — 0..n | `account_transactions` | `account_transactions.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `invoices` | `invoices.employee_id` → `employees.id` | Nhân viên checkout. |
| `employees` | 1 — 0..n | `management_audit` | `management_audit.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `customers` | 1 — 0..1 | `accounts` | `accounts.customer_id` → `customers.id` | Khách sở hữu tài khoản; UNIQUE nên mỗi khách tối đa một tài khoản. |
| `customers` | 1 — 0..n | `usage_sessions` | `usage_sessions.customer_id` → `customers.id` | Khách dùng máy. |
| `customers` | 1 — 0..n | `invoices` | `invoices.customer_id` → `customers.id` | Khách (lưu thẳng để báo cáo không phải đi qua phiên). |
| `accounts` | 1 — 0..n | `account_transactions` | `account_transactions.account_id` → `accounts.id` | Tài khoản bị thay đổi số dư. |
| `accounts` | 1 — 0..n | `customer_notification_reads` | `customer_notification_reads.account_id` → `accounts.id` | Tài khoản sở hữu trạng thái đọc; phần thứ nhất của khóa chính. |
| `machines` | 1 — 0..n | `usage_sessions` | `usage_sessions.machine_id` → `machines.id` | Máy được dùng. |
| `usage_sessions` | 0..1 — 0..n | `account_transactions` | `account_transactions.session_id` → `usage_sessions.id` | Phiên liên quan (trừ phí, bù tiền lúc checkout); NULL với nạp tiền độc lập. |
| `usage_sessions` | 1 — 0..1 | `invoices` | `invoices.session_id` → `usage_sessions.id` | Phiên được thanh toán; UNIQUE ⇒ mỗi phiên tối đa một hóa đơn. |
| `promotions` | 0..1 — 0..n | `account_transactions` | `account_transactions.promotion_id` → `promotions.id` | Chính sách thưởng đã áp dụng, NULL với giao dịch thường. |

## 3. Chi tiết từng bảng

### stores

Cửa hàng net. Nhân viên, máy và hóa đơn đều thuộc một cửa hàng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã cửa hàng, duy nhất. |
| `name` | `varchar(100)` | Không | — | — | Tên cửa hàng. |
| `address` | `varchar(255)` | Không | — | — | Địa chỉ. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `INACTIVE`. Cửa hàng ngừng hoạt động thì nhân viên không đăng nhập được. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_stores_code` (`code`)
- CHECK `chk_stores_address_not_blank`: `(char_length(trim(address)) > 0)`
- CHECK `chk_stores_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_stores_name_not_blank`: `(char_length(trim(name)) > 0)`
- CHECK `chk_stores_status`: `(status in ('ACTIVE','INACTIVE'))`

### employees

Nhân viên đăng nhập ứng dụng; vai trò quyết định quyền thao tác.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã nhân viên, duy nhất. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cửa hàng nhân viên làm việc. |
| `full_name` | `varchar(100)` | Không | — | — | Họ tên. |
| `username` | `varchar(30)` | Không | — | UK | Tên đăng nhập, duy nhất, 4–30 ký tự. |
| `password_hash` | `varchar(255)` | Không | — | — | Mật khẩu đã băm bcrypt; không bao giờ trả ra UI/DTO. |
| `role` | `varchar(20)` | Không | — | — | `ADMIN` / `MANAGER` / `STAFF`. Chỉ MANAGER, ADMIN được quản lý máy và đổi trạng thái khách. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `INACTIVE` / `LOCKED`. Chỉ ACTIVE đăng nhập được. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_employees_code` (`code`)
- UNIQUE `uq_employees_username` (`username`)
- FOREIGN KEY `fk_employees_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_employees_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_employees_full_name_not_blank`: `(char_length(trim(full_name)) > 0)`
- CHECK `chk_employees_password_hash_not_blank`: `(char_length(trim(password_hash)) > 0)`
- CHECK `chk_employees_role`: `(role in ('ADMIN','MANAGER','STAFF'))`
- CHECK `chk_employees_status`: `(status in ('ACTIVE','INACTIVE','LOCKED'))`
- CHECK `chk_employees_username_length`: `(char_length(username) between 4 and 30)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_employees_store_status` (`store_id, status`)

### customers

Thông tin cá nhân của khách chơi.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã khách hàng, duy nhất (`CUS-` + hex). |
| `full_name` | `varchar(100)` | Không | — | — | Họ tên, 2–100 ký tự. |
| `phone` | `char(10)` | Không | — | UK | Số điện thoại 10 số bắt đầu bằng 0, duy nhất. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `INACTIVE`. Khách INACTIVE không được mở phiên mới. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customers_code` (`code`)
- UNIQUE `uq_customers_phone` (`phone`)
- CHECK `chk_customers_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_customers_full_name_length`: `(char_length(trim(full_name)) between 2 and 100)`
- CHECK `chk_customers_phone_format`: `regexp_like(phone,'^0[0-9]{9}$','c')`
- CHECK `chk_customers_status`: `(status in ('ACTIVE','INACTIVE'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_customers_full_name` (`full_name`)

### accounts

Tài khoản đăng nhập máy trạm và ví tiền của khách; mỗi khách đúng một tài khoản.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã tài khoản, duy nhất (`ACC-` + hex). |
| `customer_id` | `bigint unsigned` | Không | — | UK, FK → `customers.id` | Khách sở hữu tài khoản; UNIQUE nên mỗi khách tối đa một tài khoản. |
| `username` | `varchar(30)` | Không | — | UK | Tên đăng nhập máy trạm, duy nhất, chữ/số/`_`/`.`, 4–30 ký tự. |
| `password_hash` | `varchar(255)` | Không | — | — | Mật khẩu đã băm bcrypt. |
| `balance` | `bigint` | Không | `0` | — | Số dư sổ cái (VND), có dấu để hỗ trợ dữ liệu nợ. Cảnh báo âm trong phiên dùng số dư dự kiến; checkout P0 phải bù đủ để số dư cuối không âm. Mọi thay đổi phải kèm `account_transactions`. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `LOCKED`. LOCKED không mở phiên được nhưng vẫn nạp tiền để trả nợ. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |
| `bonus_balance` | `bigint` | Không | `0` | — | Số dư khuyến mãi (VND), dùng trước, không quy đổi tiền mặt. |
| `cash_balance` | `bigint` | Có | — | — | Cột sinh tự động: tổng balance trừ bonus_balance; số dư chính. Biểu thức: `(balance - bonus_balance)` (STORED). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_accounts_code` (`code`)
- UNIQUE `uq_accounts_customer` (`customer_id`)
- UNIQUE `uq_accounts_username` (`username`)
- FOREIGN KEY `fk_accounts_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_accounts_bonus_nonnegative`: `(bonus_balance >= 0)`
- CHECK `chk_accounts_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_accounts_password_hash_not_blank`: `(char_length(trim(password_hash)) > 0)`
- CHECK `chk_accounts_status`: `(status in ('ACTIVE','LOCKED'))`
- CHECK `chk_accounts_username_format`: `regexp_like(username,'^[A-Za-z0-9_.]{4,30}$','c')`

### machines

Máy trạm của cửa hàng và trạng thái hiện tại.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã máy, duy nhất (vd. `PC01`). |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cửa hàng sở hữu máy. |
| `name` | `varchar(100)` | Không | — | — | Tên hiển thị. |
| `status` | `varchar(20)` | Không | `AVAILABLE` | — | `AVAILABLE` / `IN_USE` / `MAINTENANCE`. Chỉ AVAILABLE mới mở phiên được. |
| `hourly_rate` | `bigint` | Không | — | — | Đơn giá mỗi giờ (VND, > 0). Phiên chụp lại giá này lúc mở. |
| `is_active` | `tinyint(1)` | Không | `1` | — | FALSE = đã ngừng sử dụng (archive) vì có lịch sử, không xóa cứng. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC); dùng để hiển thị thời gian trống của máy. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_machines_code` (`code`)
- FOREIGN KEY `fk_machines_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_machines_archived_not_in_use`: `((is_active = true) or (status <> 'IN_USE'))`
- CHECK `chk_machines_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_machines_hourly_rate`: `(hourly_rate > 0)`
- CHECK `chk_machines_is_active`: `(is_active in (false,true))`
- CHECK `chk_machines_name_not_blank`: `(char_length(trim(name)) > 0)`
- CHECK `chk_machines_status`: `(status in ('AVAILABLE','IN_USE','MAINTENANCE'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_machines_store_active_status` (`store_id, is_active, status`)

### usage_sessions

Một lần khách dùng một máy, từ lúc mở đến lúc checkout.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã phiên, duy nhất (`SS-` + hex). |
| `customer_id` | `bigint unsigned` | Không | — | FK → `customers.id` | Khách dùng máy. |
| `machine_id` | `bigint unsigned` | Không | — | FK → `machines.id` | Máy được dùng. |
| `opened_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên mở phiên. |
| `closed_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên checkout; NULL khi phiên đang chạy. |
| `started_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm bắt đầu (UTC). |
| `ended_at` | `datetime` | Có | — | — | Thời điểm kết thúc (UTC); NULL khi phiên ACTIVE. |
| `hourly_rate` | `bigint` | Không | — | — | Đơn giá chụp từ máy lúc mở phiên; đổi giá máy sau đó không ảnh hưởng phiên. |
| `cost` | `bigint` | Có | — | — | Tiền phí tính lúc checkout (VND); NULL khi phiên ACTIVE. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `COMPLETED` / `CANCELLED`. |
| `active_machine_id` | `bigint unsigned` | Có | — | UK | Cột sinh tự động: `machine_id` khi ACTIVE, ngược lại NULL. UNIQUE ⇒ mỗi máy tối đa một phiên ACTIVE. Biểu thức: `(case when (status = 'ACTIVE') then machine_id else NULL end)` (STORED). |
| `active_customer_id` | `bigint unsigned` | Có | — | UK | Cột sinh tự động: `customer_id` khi ACTIVE, ngược lại NULL. UNIQUE ⇒ mỗi khách tối đa một phiên ACTIVE. Biểu thức: `(case when (status = 'ACTIVE') then customer_id else NULL end)` (STORED). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_usage_sessions_active_customer` (`active_customer_id`)
- UNIQUE `uq_usage_sessions_active_machine` (`active_machine_id`)
- UNIQUE `uq_usage_sessions_code` (`code`)
- FOREIGN KEY `fk_usage_sessions_closed_by` (`closed_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_usage_sessions_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_usage_sessions_machine` (`machine_id`) → `machines` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_usage_sessions_opened_by` (`opened_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_usage_sessions_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_usage_sessions_cost`: `((cost is null) or (cost >= 0))`
- CHECK `chk_usage_sessions_hourly_rate`: `(hourly_rate > 0)`
- CHECK `chk_usage_sessions_state`: `(((status = 'ACTIVE') and (ended_at is null) and (cost is null)) or ((status = 'COMPLETED') and (ended_at is not null) and (cost is not null)) or ((status = 'CANCELLED') and (ended_at is not null)))`
- CHECK `chk_usage_sessions_status`: `(status in ('ACTIVE','COMPLETED','CANCELLED'))`
- CHECK `chk_usage_sessions_time_order`: `((ended_at is null) or (ended_at >= started_at))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_usage_sessions_customer_started_at` (`customer_id, started_at`)
- INDEX `idx_usage_sessions_machine_started_at` (`machine_id, started_at`)
- INDEX `idx_usage_sessions_status_started_at` (`status, started_at`)

### account_transactions

Sổ cái biến động số dư: mọi lần cộng/trừ `accounts.balance` đều có đúng một dòng; không sửa, không xóa.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã giao dịch, duy nhất (`TX-` + hex). |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản bị thay đổi số dư. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên thực hiện. |
| `session_id` | `bigint unsigned` | Có | — | FK → `usage_sessions.id` | Phiên liên quan (trừ phí, bù tiền lúc checkout); NULL với nạp tiền độc lập. |
| `type` | `varchar(20)` | Không | — | — | `TOP_UP` / `PROMOTION` / `USAGE_PAYMENT` / `DEBT_SETTLEMENT`. |
| `amount` | `bigint` | Không | — | — | Số tiền có dấu (VND): dương khi cộng, âm khi `USAGE_PAYMENT`. |
| `method` | `varchar(20)` | Không | — | — | `CASH` / `TRANSFER` / `ACCOUNT_BALANCE` / `PROMOTION`, phải hợp với `type`. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm ghi (UTC). |
| `store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cơ sở ghi nhận giao dịch tại thời điểm phát sinh. |
| `promotion_id` | `bigint unsigned` | Có | — | FK → `promotions.id` | Chính sách thưởng đã áp dụng, NULL với giao dịch thường. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_account_transactions_code` (`code`)
- FOREIGN KEY `fk_account_transactions_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_account_transactions_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_account_transactions_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_transactions_promotion` (`promotion_id`) → `promotions` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
- FOREIGN KEY `fk_transactions_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
- CHECK `chk_account_transactions_amount`: `(((type in ('TOP_UP','PROMOTION','DEBT_SETTLEMENT')) and (amount > 0)) or ((type = 'USAGE_PAYMENT') and (amount < 0)))`
- CHECK `chk_account_transactions_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_account_transactions_method`: `(method in ('CASH','TRANSFER','ACCOUNT_BALANCE','PROMOTION'))`
- CHECK `chk_account_transactions_type`: `(type in ('TOP_UP','PROMOTION','USAGE_PAYMENT','DEBT_SETTLEMENT'))`
- CHECK `chk_account_transactions_type_method`: `(((type in ('TOP_UP','DEBT_SETTLEMENT')) and (method in ('CASH','TRANSFER'))) or ((type = 'USAGE_PAYMENT') and (method = 'ACCOUNT_BALANCE')) or ((type = 'PROMOTION') and (method = 'PROMOTION')))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_account_transactions_account_created_at` (`account_id, created_at`)

### invoices

Hóa đơn tạo khi checkout thành công; lưu lại khách, nhân viên, cửa hàng để giữ đúng lịch sử.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã hóa đơn, duy nhất (`INV-` + hex). |
| `session_id` | `bigint unsigned` | Không | — | UK, FK → `usage_sessions.id` | Phiên được thanh toán; UNIQUE ⇒ mỗi phiên tối đa một hóa đơn. |
| `customer_id` | `bigint unsigned` | Không | — | FK → `customers.id` | Khách (lưu thẳng để báo cáo không phải đi qua phiên). |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên checkout. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cửa hàng; dùng cho báo cáo doanh thu. |
| `usage_cost` | `bigint` | Không | — | — | Phí sử dụng (VND). Doanh thu ngày = tổng `usage_cost` của hóa đơn PAID. |
| `settlement_amount` | `bigint` | Không | `0` | — | Phần tiền bù thực ghi nhận, bằng đúng `settlement_required` khi checkout; không phải tiền khách đưa, không cộng lần nữa vào doanh thu. Schema giới hạn ≤ `usage_cost`; nợ cũ âm phải nạp bù qua ví trước checkout. |
| `total_amount` | `bigint` | Không | — | — | Tổng hóa đơn; P0 luôn bằng `usage_cost` (tiền bù không cộng lần hai). |
| `status` | `varchar(20)` | Không | `PAID` | — | `PAID` / `VOID`. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm checkout (UTC); báo cáo quy đổi sang giờ Việt Nam (UTC+7). |
| `bonus_used` | `bigint` | Không | `0` | — | Phần phí sử dụng trừ từ khuyến mãi, chụp tại checkout. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_invoices_code` (`code`)
- UNIQUE `uq_invoices_session` (`session_id`)
- FOREIGN KEY `fk_invoices_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_invoices_bonus_used`: `((bonus_used >= 0) and (bonus_used <= usage_cost))`
- CHECK `chk_invoices_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_invoices_money`: `((usage_cost >= 0) and (settlement_amount >= 0) and (total_amount >= 0))`
- CHECK `chk_invoices_settlement`: `(settlement_amount <= usage_cost)`
- CHECK `chk_invoices_status`: `(status in ('PAID','VOID'))`
- CHECK `chk_invoices_total`: `(total_amount = usage_cost)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_invoices_customer_created_at` (`customer_id, created_at`)
- INDEX `idx_invoices_store_status_created_at` (`store_id, status, created_at`)

### promotions

Chính sách thưởng theo mốc nạp, phạm vi và thời gian.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã chính sách duy nhất. |
| `name` | `varchar(100)` | Không | — | — | Tên chính sách. |
| `store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cơ sở áp dụng; NULL = toàn hệ thống. |
| `minimum_amount` | `bigint` | Không | — | — | Mốc tiền nạp tối thiểu (VND). |
| `bonus_percent` | `int` | Không | — | — | Phần trăm thưởng, số nguyên 0–100. |
| `starts_at` | `datetime` | Không | — | — | Bắt đầu hiệu lực (UTC, bao gồm). |
| `ends_at` | `datetime` | Không | — | — | Kết thúc hiệu lực (UTC, không bao gồm). |
| `is_active` | `tinyint(1)` | Không | `1` | — | Bật/tắt chính sách. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `code` (`code`)
- FOREIGN KEY `fk_promotions_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
- CHECK `chk_promotions_amount`: `((minimum_amount > 0) and (minimum_amount <= 100000000))`
- CHECK `chk_promotions_percent`: `(bonus_percent between 0 and 100)`
- CHECK `chk_promotions_period`: `(ends_at > starts_at)`

Index bổ sung (`002_indexes.sql`):

- INDEX `ix_promotions_eligible` (`store_id, is_active, minimum_amount`)

### management_audit

Lịch sử thay đổi quản trị, không lưu mật khẩu.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên thực hiện. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở đang vận hành. |
| `action` | `varchar(40)` | Không | — | — | Loại thay đổi quản trị. |
| `entity_id` | `bigint unsigned` | Không | — | — | ID đối tượng được thay đổi. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm thay đổi (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_management_audit_employee` (`employee_id`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
- FOREIGN KEY `fk_management_audit_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT

### customer_notification_reads

Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `account_id` | `bigint unsigned` | Không | — | PK, FK → `accounts.id` | Tài khoản sở hữu trạng thái đọc; phần thứ nhất của khóa chính. |
| `notification_key` | `varchar(100)` | Không | — | PK | Khóa sự kiện ổn định, phân biệt hoa/thường; phần thứ hai của khóa chính. |
| `read_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đánh dấu đã đọc (UTC). |

Ràng buộc:

- PRIMARY KEY (`account_id,notification_key`)
- FOREIGN KEY `fk_customer_notification_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
