# Data dictionary — CyberHub Manager

<!-- File sinh tự động bởi scripts/gen_data_dictionary.py từ schema MySQL. Không sửa tay;
     sửa DESCRIPTIONS trong script rồi chạy lại. -->

Nguồn: các migration `sql/001_*.sql` đến `sql/011_*.sql` (MySQL 8.4, InnoDB, utf8mb4). Quy ước:
tiền là `BIGINT` đơn vị VND, thời gian là `DATETIME` lưu UTC. Lịch sử nghiệp vụ dùng `RESTRICT`; chỉ ánh xạ phân phòng (`machine_room_types`), khóa phiên đang hoạt động (`active_usage_sessions`) và trạng thái đã đọc thông báo (`customer_notification_reads`) dùng `CASCADE` khi bản ghi cha được phép xóa.

## 1. Danh sách bảng

| Bảng | Mục đích | Số cột |
|---|---|---:|
| [`stores`](#stores) | Cửa hàng net. Nhân viên, máy và hóa đơn đều thuộc một cửa hàng. | 7 |
| [`employees`](#employees) | Tài khoản nhân viên dùng để xác thực và phân quyền. | 11 |
| [`employee_profiles`](#employee_profiles) | Hồ sơ nhân sự và cơ sở công tác chính, tách khỏi thông tin xác thực. | 7 |
| [`employee_store_assignments`](#employee_store_assignments) | Phân công bổ sung cho MANAGER được vận hành tại nhiều cơ sở; không thay đổi cơ sở chính trong hồ sơ. | 4 |
| [`customers`](#customers) | Thông tin cá nhân của khách chơi. | 8 |
| [`accounts`](#accounts) | Tài khoản đăng nhập và ví tiền của khách; mỗi khách có tối đa một tài khoản. | 12 |
| [`machines`](#machines) | Máy trạm của cửa hàng và trạng thái hiện tại. | 9 |
| [`usage_sessions`](#usage_sessions) | Một lần khách sử dụng máy, từ lúc mở đến lúc checkout. | 11 |
| [`account_transactions`](#account_transactions) | Sổ cái biến động số dư: mọi lần cộng/trừ `accounts.balance` đều có đúng một dòng; không sửa, không xóa. | 10 |
| [`session_transactions`](#session_transactions) | Bảng liên kết chuẩn hóa 3NF: liên kết bút toán sổ cái với phiên sử dụng máy trạm liên quan. | 2 |
| [`invoices`](#invoices) | Hóa đơn checkout; session_id UNIQUE bảo đảm tối đa một hóa đơn cho mỗi phiên. | 11 |
| [`promotions`](#promotions) | Chính sách thưởng theo mốc nạp, phạm vi và thời gian. | 10 |
| [`management_audit`](#management_audit) | Lịch sử thay đổi quản trị, không lưu mật khẩu. | 6 |
| [`active_usage_sessions`](#active_usage_sessions) | Bảng chiếm dụng các phiên đang hoạt động; UNIQUE trên máy và khách ngăn mở phiên trùng. | 3 |
| [`customer_notification_reads`](#customer_notification_reads) | Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền. | 2 |
| [`customer_notification_events`](#customer_notification_events) | Sổ sự kiện thông báo bền vững cho khách theo vòng đời đơn; khóa sự kiện chống phát trùng. | 4 |
| [`machine_room_types`](#machine_room_types) | Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường. | 2 |
| [`menu_categories`](#menu_categories) | Nhóm món theo cơ sở, xếp vào trang Đồ ăn (FOOD) hoặc Đồ uống (DRINK). | 7 |
| [`menu_items`](#menu_items) | Món ăn/đồ uống của cơ sở; không xóa cứng, chỉ ẩn để giữ lịch sử gọi món. | 10 |
| [`menu_orders`](#menu_orders) | Đơn POS đồ ăn/thức uống của khách đang chơi; thanh toán tại quầy, không trừ ví giờ chơi. | 14 |
| [`menu_order_items`](#menu_order_items) | Từng món trong yêu cầu gọi món, với tên và giá chụp lúc đặt. | 5 |
| [`pos_order_reversals`](#pos_order_reversals) | Yêu cầu hoàn/hủy toàn bộ đơn POS có maker-checker và quyết định hoàn kho hoặc ghi hao hụt. | 12 |
| [`menu_promotions`](#menu_promotions) | Chính sách khuyến mãi POS theo cơ sở; mỗi đơn chỉ chọn một ưu đãi xác định. | 9 |
| [`menu_promotion_versions`](#menu_promotion_versions) | Phiên bản chính sách khuyến mãi POS được giữ để bảo toàn điều kiện áp dụng cho đơn cũ. | 10 |
| [`menu_order_pricing`](#menu_order_pricing) | Snapshot kết quả tính giá POS bất biến tại thời điểm đặt/thanh toán. | 3 |

## 2. Quan hệ và cardinality

Đọc từ khóa ngoại: phía cha là `1` khi mọi cột FK `NOT NULL`, `0..1` khi có cột cho phép NULL;
phía con là `0..1` khi bộ cột FK có UNIQUE, ngược lại `0..n`.

| Cha | | Con | Khóa ngoại | Ý nghĩa |
|---|:---:|---|---|---|
| `stores` | 1 — 0..n | `employee_profiles` | `employee_profiles.home_store_id` → `stores.id` | Cơ sở công tác chính. |
| `stores` | 1 — 0..n | `employee_store_assignments` | `employee_store_assignments.store_id` → `stores.id` | Cơ sở được phép vận hành; phần thứ hai của khóa chính. |
| `stores` | 1 — 0..n | `machines` | `machines.store_id` → `stores.id` | Cửa hàng sở hữu máy. |
| `stores` | 1 — 0..n | `account_transactions` | `account_transactions.store_id` → `stores.id` | Cơ sở ghi nhận giao dịch tại thời điểm phát sinh. |
| `stores` | 1 — 0..n | `invoices` | `invoices.store_id` → `stores.id` | Cơ sở của phiên tại thời điểm checkout. |
| `stores` | 0..1 — 0..n | `promotions` | `promotions.store_id` → `stores.id` | Cơ sở áp dụng; NULL = toàn hệ thống. |
| `stores` | 1 — 0..n | `management_audit` | `management_audit.store_id` → `stores.id` | Cơ sở đang vận hành. |
| `stores` | 1 — 0..n | `menu_categories` | `menu_categories.store_id` → `stores.id` | Cơ sở sở hữu nhóm món. |
| `stores` | 1 — 0..n | `menu_promotions` | `menu_promotions.store_id` → `stores.id` | Cơ sở áp dụng. |
| `employees` | 1 — 0..n | `employee_store_assignments` | `employee_store_assignments.employee_id` → `employees.id` | Nhân viên được phân công; phần thứ nhất của khóa chính. |
| `employees` | 1 — 0..n | `employee_store_assignments` | `employee_store_assignments.granted_by` → `employees.id` | ADMIN đã cấp quyền phân công. |
| `employees` | 0..1 — 0..n | `usage_sessions` | `usage_sessions.closed_by` → `employees.id` | Nhân viên checkout; NULL khi phiên còn hoạt động. |
| `employees` | 1 — 0..n | `usage_sessions` | `usage_sessions.opened_by` → `employees.id` | Nhân viên mở phiên. |
| `employees` | 1 — 0..n | `account_transactions` | `account_transactions.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `invoices` | `invoices.employee_id` → `employees.id` | Nhân viên checkout. |
| `employees` | 1 — 0..n | `management_audit` | `management_audit.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 0..1 — 0..n | `menu_orders` | `menu_orders.handled_by` → `employees.id` | Nhân viên tiếp nhận/phục vụ/hủy; NULL khi còn NEW. |
| `employees` | 0..1 — 0..n | `menu_orders` | `menu_orders.paid_by` → `employees.id` | Nhân viên xác nhận thanh toán. |
| `employees` | 0..1 — 0..n | `pos_order_reversals` | `pos_order_reversals.decided_by` → `employees.id` | Quản lý quyết định; NULL khi đang chờ. |
| `employees` | 1 — 0..n | `pos_order_reversals` | `pos_order_reversals.requested_by` → `employees.id` | Nhân viên đề nghị. |
| `employee_profiles` | 1 — 0..1 | `employees` | `employees.profile_id` → `employee_profiles.id` | Hồ sơ nhân sự; UNIQUE để mỗi hồ sơ có tối đa một tài khoản. |
| `customers` | 1 — 0..1 | `accounts` | `accounts.customer_id` → `customers.id` | Khách sở hữu; UNIQUE. |
| `customers` | 1 — 0..n | `usage_sessions` | `usage_sessions.customer_id` → `customers.id` | Khách sử dụng máy. |
| `customers` | 1 — 0..n | `invoices` | `invoices.customer_id` → `customers.id` | Khách tại thời điểm lập hóa đơn. |
| `customers` | 1 — 0..1 | `active_usage_sessions` | `active_usage_sessions.customer_id` → `customers.id` | Khách đang dùng máy; UNIQUE để mỗi khách chỉ có một phiên hoạt động. |
| `accounts` | 1 — 0..n | `account_transactions` | `account_transactions.account_id` → `accounts.id` | Tài khoản bị thay đổi số dư. |
| `machines` | 1 — 0..n | `usage_sessions` | `usage_sessions.machine_id` → `machines.id` | Máy được sử dụng. |
| `machines` | 1 — 0..1 | `active_usage_sessions` | `active_usage_sessions.machine_id` → `machines.id` | Máy đang được dùng; UNIQUE để mỗi máy chỉ có một phiên hoạt động. |
| `machines` | 1 — 0..1 | `machine_room_types` | `machine_room_types.machine_id` → `machines.id` | Máy được phân loại; khóa chính và khóa ngoại; CASCADE chỉ xóa ánh xạ khi máy được phép xóa. |
| `usage_sessions` | 1 — 0..n | `session_transactions` | `session_transactions.session_id` → `usage_sessions.id` | Phiên máy trạm liên quan đến giao dịch thanh toán hoặc bù tiền. |
| `usage_sessions` | 1 — 0..1 | `invoices` | `invoices.session_id` → `usage_sessions.id` | Phiên được lập hóa đơn; UNIQUE. |
| `usage_sessions` | 1 — 0..1 | `active_usage_sessions` | `active_usage_sessions.session_id` → `usage_sessions.id` | Phiên đang hoạt động; khóa chính và khóa ngoại tới `usage_sessions.id`. |
| `usage_sessions` | 1 — 0..n | `menu_orders` | `menu_orders.session_id` → `usage_sessions.id` | Phiên ACTIVE lúc đặt. |
| `account_transactions` | 1 — 0..1 | `session_transactions` | `session_transactions.transaction_id` → `account_transactions.id` | Mã giao dịch sổ cái (khóa chính kiêm khóa ngoại). |
| `promotions` | 0..1 — 0..n | `account_transactions` | `account_transactions.promotion_id` → `promotions.id` | Chính sách thưởng đã áp dụng, NULL với giao dịch thường. |
| `customer_notification_events` | 1 — 0..1 | `customer_notification_reads` | `customer_notification_reads.event_id` → `customer_notification_events.id` | ID sự kiện thông báo tương ứng; PK kiêm FK tham chiếu customer_notification_events(id). |
| `menu_categories` | 1 — 0..n | `menu_items` | `menu_items.category_id` → `menu_categories.id` | Nhóm món; service bảo đảm cùng cơ sở với món. |
| `menu_items` | 1 — 0..n | `menu_order_items` | `menu_order_items.item_id` → `menu_items.id` | Món được gọi. |
| `menu_items` | 0..1 — 0..n | `menu_promotions` | `menu_promotions.item_id` → `menu_items.id` | Món áp dụng; NULL khi ưu đãi không gắn một món. |
| `menu_items` | 0..1 — 0..n | `menu_promotion_versions` | `menu_promotion_versions.item_id` → `menu_items.id` | Món áp dụng nếu có. |
| `menu_orders` | 1 — 0..n | `customer_notification_events` | `customer_notification_events.order_id` → `menu_orders.id` | Đơn hàng phát sinh sự kiện thông báo; FK tham chiếu menu_orders(id). |
| `menu_orders` | 1 — 0..n | `menu_order_items` | `menu_order_items.order_id` → `menu_orders.id` | Yêu cầu gọi món. |
| `menu_orders` | 1 — 0..1 | `pos_order_reversals` | `pos_order_reversals.order_id` → `menu_orders.id` | Đơn POS; UNIQUE nên mỗi đơn có tối đa một yêu cầu hoàn/hủy. |
| `menu_orders` | 1 — 0..1 | `menu_order_pricing` | `menu_order_pricing.order_id` → `menu_orders.id` | Đơn POS; khóa chính/FK. |
| `menu_promotions` | 1 — 0..n | `menu_promotion_versions` | `menu_promotion_versions.promotion_id` → `menu_promotions.id` | Chính sách POS gốc. |
| `menu_promotion_versions` | 0..1 — 0..n | `menu_order_pricing` | `menu_order_pricing.promotion_version_id` → `menu_promotion_versions.id` | Phiên bản chính sách khuyến mãi được áp dụng; NULL nếu không dùng ưu đãi. |

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

Tài khoản nhân viên dùng để xác thực và phân quyền.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `profile_id` | `bigint unsigned` | Không | — | UK, FK → `employee_profiles.id` | Hồ sơ nhân sự; UNIQUE để mỗi hồ sơ có tối đa một tài khoản. |
| `username` | `varchar(30)` | Không | — | UK | Tên đăng nhập duy nhất. |
| `password_hash` | `varchar(255)` | Không | — | — | Mật khẩu đã băm bcrypt; không lưu mật khẩu thô. |
| `role` | `varchar(20)` | Không | — | — | Vai trò được phép trong hệ thống. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | Trạng thái tài khoản. |
| `auth_version` | `int unsigned` | Không | `0` | — | Phiên bản xác thực để thu hồi phiên đăng nhập cũ. |
| `must_change_password` | `tinyint(1)` | Không | `0` | — | Yêu cầu đổi mật khẩu trước khi thao tác. |
| `password_changed_at` | `datetime` | Có | — | — | Thời điểm đổi mật khẩu gần nhất; có thể NULL. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_employees_profile` (`profile_id`)
- UNIQUE `uq_employees_username` (`username`)
- FOREIGN KEY `fk_employees_profile` (`profile_id`) → `employee_profiles` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_employees_password_hash_not_blank`: `(char_length(trim(password_hash)) > 0)`
- CHECK `chk_employees_role`: `(role in ('ADMIN','DIRECTOR','MANAGER','STAFF','KITCHEN'))`
- CHECK `chk_employees_status`: `(status in ('ACTIVE','INACTIVE','LOCKED'))`
- CHECK `chk_employees_username_length`: `(char_length(username) between 4 and 30)`

### employee_profiles

Hồ sơ nhân sự và cơ sở công tác chính, tách khỏi thông tin xác thực.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã hồ sơ duy nhất. |
| `home_store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở công tác chính. |
| `full_name` | `varchar(100)` | Không | — | — | Họ tên nhân sự. |
| `employment_status` | `varchar(10)` | Không | `ACTIVE` | — | Trạng thái làm việc. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_employee_profiles_code` (`code`)
- FOREIGN KEY `fk_employee_profiles_store` (`home_store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_employee_profiles_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_employee_profiles_name_not_blank`: `(char_length(trim(full_name)) > 0)`
- CHECK `chk_employee_profiles_status`: `(employment_status in ('ACTIVE','INACTIVE'))`

### employee_store_assignments

Phân công bổ sung cho MANAGER được vận hành tại nhiều cơ sở; không thay đổi cơ sở chính trong hồ sơ.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `employee_id` | `bigint unsigned` | Không | — | PK, FK → `employees.id` | Nhân viên được phân công; phần thứ nhất của khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | PK, FK → `stores.id` | Cơ sở được phép vận hành; phần thứ hai của khóa chính. |
| `granted_by` | `bigint unsigned` | Không | — | FK → `employees.id` | ADMIN đã cấp quyền phân công. |
| `granted_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm cấp (UTC). |

Ràng buộc:

- PRIMARY KEY (`employee_id,store_id`)
- FOREIGN KEY `fk_employee_assignments_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_employee_assignments_granter` (`granted_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_employee_assignments_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_employee_assignments_no_self_grant`: `(granted_by <> employee_id)`

### customers

Thông tin cá nhân của khách chơi.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã khách hàng, duy nhất (`CUS-` + hex). |
| `full_name` | `varchar(100)` | Không | — | — | Họ tên, 2–100 ký tự. |
| `phone` | `char(10)` | Không | — | UK | Số điện thoại 10 số bắt đầu bằng 0, duy nhất. |
| `email` | `varchar(254)` | Có | — | UK | Email đăng ký/kích hoạt tài khoản; NULL với tài khoản cũ chưa xác minh, UNIQUE nếu có. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `INACTIVE`. Khách INACTIVE không được mở phiên mới. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customers_code` (`code`)
- UNIQUE `uq_customers_email` (`email`)
- UNIQUE `uq_customers_phone` (`phone`)
- CHECK `chk_customers_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_customers_full_name_length`: `(char_length(trim(full_name)) between 2 and 100)`
- CHECK `chk_customers_phone_format`: `regexp_like(phone,'^0[0-9]{9}$','c')`
- CHECK `chk_customers_status`: `(status in ('ACTIVE','INACTIVE'))`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_customers_full_name` (`full_name`)

### accounts

Tài khoản đăng nhập và ví tiền của khách; mỗi khách có tối đa một tài khoản.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã tài khoản duy nhất. |
| `customer_id` | `bigint unsigned` | Không | — | UK, FK → `customers.id` | Khách sở hữu; UNIQUE. |
| `username` | `varchar(30)` | Không | — | UK | Tên đăng nhập duy nhất. |
| `password_hash` | `varchar(255)` | Có | — | — | Mật khẩu đã băm bcrypt; NULL nếu chưa bật đăng nhập web. |
| `balance` | `bigint` | Không | `0` | — | Số dư ví hiện tại (VND), luôn không âm (balance >= 0) theo ràng buộc CHECK; cập nhật nguyên tử cùng `account_transactions` trong transaction. |
| `bonus_balance` | `bigint` | Không | `0` | — | Phần số dư khuyến mãi còn lại (VND). |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | Trạng thái tài khoản. |
| `auth_version` | `bigint unsigned` | Không | `0` | — | Phiên bản xác thực. |
| `web_login_enabled` | `tinyint(1)` | Không | `1` | — | Cho phép hoặc khóa đăng nhập web. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_accounts_code` (`code`)
- UNIQUE `uq_accounts_customer` (`customer_id`)
- UNIQUE `uq_accounts_username` (`username`)
- FOREIGN KEY `fk_accounts_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_accounts_balance_and_bonus`: `((balance >= 0) and (bonus_balance >= 0) and (bonus_balance <= balance))`
- CHECK `chk_accounts_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_accounts_password_hash_not_blank`: `((password_hash is null) or (char_length(trim(password_hash)) > 0))`
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

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_machines_store_active_status` (`store_id, is_active, status`)

### usage_sessions

Một lần khách sử dụng máy, từ lúc mở đến lúc checkout.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã phiên duy nhất. |
| `customer_id` | `bigint unsigned` | Không | — | FK → `customers.id` | Khách sử dụng máy. |
| `machine_id` | `bigint unsigned` | Không | — | FK → `machines.id` | Máy được sử dụng. |
| `opened_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên mở phiên. |
| `closed_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên checkout; NULL khi phiên còn hoạt động. |
| `started_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm bắt đầu (UTC). |
| `ended_at` | `datetime` | Có | — | — | Thời điểm kết thúc; NULL khi phiên còn hoạt động. |
| `hourly_rate` | `bigint` | Không | — | — | Đơn giá chụp từ máy khi bắt đầu phiên. |
| `cost` | `bigint` | Có | — | — | Phí checkout; NULL khi phiên còn hoạt động. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | Trạng thái phiên. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_usage_sessions_code` (`code`)
- FOREIGN KEY `fk_usage_sessions_closed_by` (`closed_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_usage_sessions_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_usage_sessions_machine` (`machine_id`) → `machines` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_usage_sessions_opened_by` (`opened_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_usage_sessions_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_usage_sessions_cost`: `((cost is null) or (cost >= 0))`
- CHECK `chk_usage_sessions_hourly_rate`: `(hourly_rate > 0)`
- CHECK `chk_usage_sessions_state`: `(((status = 'ACTIVE') and (closed_by is null) and (ended_at is null) and (cost is null)) or ((status = 'COMPLETED') and (closed_by is not null) and (ended_at is not null) and (cost is not null)) or ((status = 'CANCELLED') and (ended_at is not null)))`
- CHECK `chk_usage_sessions_status`: `(status in ('ACTIVE','COMPLETED','CANCELLED'))`
- CHECK `chk_usage_sessions_time_order`: `((ended_at is null) or (ended_at >= started_at))`

Index bổ sung (`007_indexes.sql`):

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
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở ghi nhận giao dịch tại thời điểm phát sinh. |
| `promotion_id` | `bigint unsigned` | Có | — | FK → `promotions.id` | Chính sách thưởng đã áp dụng, NULL với giao dịch thường. |
| `type` | `varchar(20)` | Không | — | — | `TOP_UP` / `PROMOTION` / `USAGE_PAYMENT` / `DEBT_SETTLEMENT`. |
| `amount` | `bigint` | Không | — | — | Số tiền có dấu (VND): dương khi cộng, âm khi `USAGE_PAYMENT`. |
| `method` | `varchar(20)` | Không | — | — | `CASH` / `TRANSFER` / `ACCOUNT_BALANCE` / `PROMOTION`, phải hợp với `type`. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm ghi (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_account_transactions_code` (`code`)
- FOREIGN KEY `fk_account_transactions_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_account_transactions_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_transactions_promotion` (`promotion_id`) → `promotions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_transactions_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_account_transactions_amount`: `(((type in ('TOP_UP','PROMOTION','DEBT_SETTLEMENT')) and (amount > 0)) or ((type = 'USAGE_PAYMENT') and (amount < 0)))`
- CHECK `chk_account_transactions_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_account_transactions_method`: `(method in ('CASH','TRANSFER','ACCOUNT_BALANCE','PROMOTION'))`
- CHECK `chk_account_transactions_type`: `(type in ('TOP_UP','PROMOTION','USAGE_PAYMENT','DEBT_SETTLEMENT'))`
- CHECK `chk_account_transactions_type_method`: `(((type in ('TOP_UP','DEBT_SETTLEMENT')) and (method in ('CASH','TRANSFER'))) or ((type = 'USAGE_PAYMENT') and (method = 'ACCOUNT_BALANCE')) or ((type = 'PROMOTION') and (method = 'PROMOTION')))`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_account_transactions_account_created_at` (`account_id, created_at`)

### session_transactions

Bảng liên kết chuẩn hóa 3NF: liên kết bút toán sổ cái với phiên sử dụng máy trạm liên quan.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `transaction_id` | `bigint unsigned` | Không | — | PK, FK → `account_transactions.id` | Mã giao dịch sổ cái (khóa chính kiêm khóa ngoại). |
| `session_id` | `bigint unsigned` | Không | — | FK → `usage_sessions.id` | Phiên máy trạm liên quan đến giao dịch thanh toán hoặc bù tiền. |

Ràng buộc:

- PRIMARY KEY (`transaction_id`)
- FOREIGN KEY `fk_session_transactions_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_session_transactions_tx` (`transaction_id`) → `account_transactions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT

### invoices

Hóa đơn checkout; session_id UNIQUE bảo đảm tối đa một hóa đơn cho mỗi phiên.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã hóa đơn duy nhất. |
| `session_id` | `bigint unsigned` | Không | — | UK, FK → `usage_sessions.id` | Phiên được lập hóa đơn; UNIQUE. |
| `customer_id` | `bigint unsigned` | Không | — | FK → `customers.id` | Khách tại thời điểm lập hóa đơn. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên checkout. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở của phiên tại thời điểm checkout. |
| `usage_cost` | `bigint` | Không | — | — | Phí sử dụng máy (VND). |
| `settlement_amount` | `bigint` | Không | `0` | — | Khoản khách trả bù tại checkout (VND). |
| `bonus_used` | `bigint` | Không | `0` | — | Phần phí trừ từ số dư khuyến mãi (VND). |
| `status` | `varchar(20)` | Không | `PAID` | — | Trạng thái hóa đơn. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm lập hóa đơn (UTC). |

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
- CHECK `chk_invoices_money`: `((usage_cost >= 0) and (settlement_amount >= 0))`
- CHECK `chk_invoices_settlement`: `(settlement_amount <= usage_cost)`
- CHECK `chk_invoices_status`: `(status in ('PAID','VOID'))`

Index bổ sung (`007_indexes.sql`):

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
- UNIQUE `uq_promotions_code` (`code`)
- FOREIGN KEY `fk_promotions_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_promotions_amount`: `((minimum_amount > 0) and (minimum_amount <= 100000000))`
- CHECK `chk_promotions_percent`: `(bonus_percent between 0 and 100)`
- CHECK `chk_promotions_period`: `(ends_at > starts_at)`

Index bổ sung (`007_indexes.sql`):

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
- FOREIGN KEY `fk_management_audit_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_management_audit_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_management_audit_action_not_blank`: `(char_length(trim(action)) > 0)`

### active_usage_sessions

Bảng chiếm dụng các phiên đang hoạt động; UNIQUE trên máy và khách ngăn mở phiên trùng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `session_id` | `bigint unsigned` | Không | — | PK, FK → `usage_sessions.id` | Phiên đang hoạt động; khóa chính và khóa ngoại tới `usage_sessions.id`. |
| `machine_id` | `bigint unsigned` | Không | — | UK, FK → `machines.id` | Máy đang được dùng; UNIQUE để mỗi máy chỉ có một phiên hoạt động. |
| `customer_id` | `bigint unsigned` | Không | — | UK, FK → `customers.id` | Khách đang dùng máy; UNIQUE để mỗi khách chỉ có một phiên hoạt động. |

Ràng buộc:

- PRIMARY KEY (`session_id`)
- UNIQUE `uq_active_usage_customer` (`customer_id`)
- UNIQUE `uq_active_usage_machine` (`machine_id`)
- FOREIGN KEY `fk_active_usage_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_active_usage_machine` (`machine_id`) → `machines` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_active_usage_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE CASCADE

### customer_notification_reads

Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `event_id` | `bigint unsigned` | Không | — | PK, FK → `customer_notification_events.id` | ID sự kiện thông báo tương ứng; PK kiêm FK tham chiếu customer_notification_events(id). |
| `read_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đánh dấu đã đọc (UTC). |

Ràng buộc:

- PRIMARY KEY (`event_id`)
- FOREIGN KEY `fk_customer_notification_reads_event` (`event_id`) → `customer_notification_events` (`id`) ON UPDATE RESTRICT ON DELETE CASCADE

### customer_notification_events

Sổ sự kiện thông báo bền vững cho khách theo vòng đời đơn; khóa sự kiện chống phát trùng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `order_id` | `bigint unsigned` | Không | — | FK → `menu_orders.id` | Đơn hàng phát sinh sự kiện thông báo; FK tham chiếu menu_orders(id). |
| `order_status` | `varchar(12)` | Không | — | — | Trạng thái đơn hàng tại thời điểm phát sinh sự kiện. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo sự kiện (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customer_notification_order_status` (`order_id,order_status`)
- FOREIGN KEY `fk_customer_notification_order` (`order_id`) → `menu_orders` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_customer_notification_order_status`: `(order_status in ('NEW','PREPARING','SERVED','PAID','CANCELLED','REFUNDED'))`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_customer_notification_order_created` (`order_id, created_at, id`)

### machine_room_types

Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `machine_id` | `bigint unsigned` | Không | — | PK, FK → `machines.id` | Máy được phân loại; khóa chính và khóa ngoại; CASCADE chỉ xóa ánh xạ khi máy được phép xóa. |
| `room_type` | `varchar(10)` | Không | — | — | STANDARD = phòng thường, VIP = phòng VIP; không suy đoán từ giá giờ hoặc tên máy. |

Ràng buộc:

- PRIMARY KEY (`machine_id`)
- FOREIGN KEY `fk_machine_room_machine` (`machine_id`) → `machines` (`id`) ON UPDATE RESTRICT ON DELETE CASCADE
- CHECK `chk_machine_room_type`: `(room_type in ('STANDARD','VIP','COUPLE','SUPER_VIP'))`

### menu_categories

Nhóm món theo cơ sở, xếp vào trang Đồ ăn (FOOD) hoặc Đồ uống (DRINK).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở sở hữu nhóm món. |
| `page` | `varchar(10)` | Không | — | — | `FOOD` (trang 1) / `DRINK` (trang 2) của menu sách lật. |
| `name` | `varchar(60)` | Không | — | — | Tên nhóm, duy nhất trong một cơ sở. |
| `sort_order` | `int` | Không | `0` | — | Thứ tự hiển thị 0–9999, nhỏ đứng trước. |
| `is_active` | `tinyint(1)` | Không | `1` | — | FALSE thì toàn bộ món trong nhóm bị ẩn với khách. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_categories_store_name` (`store_id,name`)
- FOREIGN KEY `fk_menu_categories_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_categories_name`: `(char_length(trim(name)) > 0)`
- CHECK `chk_menu_categories_page`: `(page in ('FOOD','DRINK'))`
- CHECK `chk_menu_categories_sort`: `(sort_order between 0 and 9999)`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_menu_categories_store_page` (`store_id, page, sort_order`)

### menu_items

Món ăn/đồ uống của cơ sở; không xóa cứng, chỉ ẩn để giữ lịch sử gọi món.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `category_id` | `bigint unsigned` | Không | — | FK → `menu_categories.id` | Nhóm món; service bảo đảm cùng cơ sở với món. |
| `name` | `varchar(80)` | Không | — | — | Tên món, duy nhất trong một cơ sở. |
| `description` | `varchar(200)` | Không | `` | — | Mô tả ngắn hiển thị cho khách. |
| `price` | `bigint` | Không | — | — | Giá bán (VND, 1.000–10.000.000); backend đọc lại khi khách đặt. |
| `sort_order` | `int` | Không | `0` | — | Thứ tự trong nhóm. |
| `is_visible` | `tinyint(1)` | Không | `1` | — | FALSE = ẩn khỏi menu khách. |
| `is_available` | `tinyint(1)` | Không | `1` | — | FALSE = hết món; khách không chọn/đặt được. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_items_category_name` (`category_id,name`)
- FOREIGN KEY `fk_menu_items_category` (`category_id`) → `menu_categories` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_items_name`: `(char_length(trim(name)) > 0)`
- CHECK `chk_menu_items_price`: `(price between 1000 and 10000000)`
- CHECK `chk_menu_items_sort`: `(sort_order between 0 and 9999)`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_menu_items_category_sort` (`category_id, sort_order`)

### menu_orders

Đơn POS đồ ăn/thức uống của khách đang chơi; thanh toán tại quầy, không trừ ví giờ chơi.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã yêu cầu, duy nhất (`ORD-` + hex). |
| `session_id` | `bigint unsigned` | Không | — | FK → `usage_sessions.id` | Phiên ACTIVE lúc đặt. |
| `note` | `varchar(200)` | Không | `` | — | Ghi chú của khách (≤ 200 ký tự). |
| `total_amount` | `bigint` | Không | — | — | Tổng tiền theo giá chụp lúc đặt (VND). |
| `status` | `varchar(12)` | Không | `NEW` | — | `NEW` / `PREPARING` / `SERVED` / `PAID` / `CANCELLED`. |
| `handled_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên tiếp nhận/phục vụ/hủy; NULL khi còn NEW. |
| `payment_method` | `varchar(10)` | Có | — | — | `CASH` / `TRANSFER` khi đã thanh toán; NULL trước đó. |
| `paid_at` | `datetime` | Có | — | — | Thời điểm thanh toán tại quầy (UTC). |
| `paid_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên xác nhận thanh toán. |
| `reservation_expires_at` | `datetime` | Có | — | — | Hạn giữ tồn cho đơn mới (UTC); tác vụ timeout dùng để giải phóng idempotent. |
| `cancel_reason` | `varchar(255)` | Có | — | — | Lý do hủy đơn; giữ được cả với đơn cũ chưa có ảnh chụp công thức. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đặt (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật trạng thái (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_orders_code` (`code`)
- FOREIGN KEY `fk_menu_orders_handled_by` (`handled_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_orders_paid_by` (`paid_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_orders_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_orders_handled`: `(((status = 'NEW') and (handled_by is null)) or ((status = 'CANCELLED') and (handled_by is null) and (cancel_reason = 'AUTO_EXPIRED')) or ((status <> 'NEW') and (handled_by is not null)))`
- CHECK `chk_menu_orders_payment`: `(((status in ('PAID','REFUNDED')) and (payment_method is not null) and (payment_method in ('CASH','TRANSFER')) and (paid_at is not null) and (paid_by is not null)) or ((status not in ('PAID','REFUNDED')) and (payment_method is null) and (paid_at is null) and (paid_by is null)))`
- CHECK `chk_menu_orders_status`: `(status in ('NEW','PREPARING','SERVED','PAID','CANCELLED','REFUNDED'))`
- CHECK `chk_menu_orders_total`: `(total_amount > 0)`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_menu_orders_hold_expiry` (`status, reservation_expires_at, id`)
- INDEX `idx_menu_orders_session_status` (`session_id, status, created_at`)
- INDEX `idx_menu_orders_status_paid` (`status, paid_at`)

### menu_order_items

Từng món trong yêu cầu gọi món, với tên và giá chụp lúc đặt.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `order_id` | `bigint unsigned` | Không | — | PK, FK → `menu_orders.id` | Yêu cầu gọi món. |
| `item_id` | `bigint unsigned` | Không | — | PK, FK → `menu_items.id` | Món được gọi. |
| `item_name` | `varchar(80)` | Không | — | — | Tên món tại thời điểm đặt. |
| `unit_price` | `bigint` | Không | — | — | Đơn giá tại thời điểm đặt (VND). |
| `quantity` | `int` | Không | — | — | Số lượng 1–20. |

Ràng buộc:

- PRIMARY KEY (`order_id,item_id`)
- FOREIGN KEY `fk_menu_order_items_item` (`item_id`) → `menu_items` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_order_items_order` (`order_id`) → `menu_orders` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_order_items_price`: `(unit_price between 1000 and 10000000)`
- CHECK `chk_menu_order_items_quantity`: `(quantity between 1 and 20)`

### pos_order_reversals

Yêu cầu hoàn/hủy toàn bộ đơn POS có maker-checker và quyết định hoàn kho hoặc ghi hao hụt.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `order_id` | `bigint unsigned` | Không | — | UK, FK → `menu_orders.id` | Đơn POS; UNIQUE nên mỗi đơn có tối đa một yêu cầu hoàn/hủy. |
| `requested_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên đề nghị. |
| `reason` | `varchar(255)` | Không | — | — | Lý do bắt buộc. |
| `disposition` | `varchar(8)` | Không | — | — | `RESTOCK` hoặc `WASTE`. |
| `status` | `varchar(10)` | Không | `PENDING` | — | `PENDING` / `APPROVED` / `REJECTED`. |
| `decided_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Quản lý quyết định; NULL khi đang chờ. |
| `decided_at` | `datetime` | Có | — | — | Thời điểm quyết định (UTC). |
| `refund_amount` | `bigint unsigned` | Không | `0` | — | Số tiền hoàn VND. |
| `refund_method` | `varchar(10)` | Có | — | — | `CASH` / `TRANSFER`. |
| `refund_reference` | `varchar(100)` | Có | — | — | Tham chiếu giao dịch hoàn. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_pos_reversal_order` (`order_id`)
- FOREIGN KEY `fk_pos_reversal_approver` (`decided_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_pos_reversal_order` (`order_id`) → `menu_orders` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_pos_reversal_requester` (`requested_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_pos_reversal_decision_and_sod`: `(((status = 'PENDING') and (decided_by is null) and (decided_at is null) and (refund_amount = 0) and (refund_method is null)) or ((status = 'REJECTED') and (decided_by is not null) and (decided_at is not null) and (decided_by <> requested_by) and (refund_amount = 0) and (refund_method is null)) or ((status = 'APPROVED') and (decided_by is not null) and (decided_at is not null) and (decided_by <> requested_by) and (((refund_amount = 0) and (refund_method is null)) or ((refund_amount > 0) and (refund_method is not null) and (refund_method in ('CASH','TRANSFER'))))))`
- CHECK `chk_pos_reversal_disposition`: `(disposition in ('RESTOCK','WASTE'))`
- CHECK `chk_pos_reversal_method`: `((refund_method is null) or (refund_method in ('CASH','TRANSFER')))`
- CHECK `chk_pos_reversal_reason_not_blank`: `(char_length(trim(reason)) > 0)`
- CHECK `chk_pos_reversal_status`: `(status in ('PENDING','APPROVED','REJECTED'))`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_pos_reversal_status_id` (`status, id`)

### menu_promotions

Chính sách khuyến mãi POS theo cơ sở; mỗi đơn chỉ chọn một ưu đãi xác định.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở áp dụng. |
| `code` | `varchar(30)` | Không | — | — | Mã duy nhất trong cơ sở. |
| `kind` | `varchar(16)` | Không | — | — | `BOGO` / `PLAY_DRINK` / `TIER_PERCENT`. |
| `item_id` | `bigint unsigned` | Có | — | FK → `menu_items.id` | Món áp dụng; NULL khi ưu đãi không gắn một món. |
| `value` | `int unsigned` | Không | — | — | Giá trị cấu hình theo loại ưu đãi. |
| `starts_at` | `datetime` | Không | — | — | Bắt đầu hiệu lực (UTC). |
| `ends_at` | `datetime` | Không | — | — | Kết thúc hiệu lực (UTC). |
| `is_active` | `tinyint(1)` | Không | `0` | — | Bật/tắt chính sách. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_promo_store_code` (`store_id,code`)
- FOREIGN KEY `fk_menu_promo_item` (`item_id`) → `menu_items` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_promo_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_promo_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_menu_promo_kind`: `(kind in ('BOGO','PLAY_DRINK'))`
- CHECK `chk_menu_promo_period`: `(starts_at < ends_at)`

Index bổ sung (`007_indexes.sql`):

- INDEX `idx_menu_promo_active` (`store_id, is_active, starts_at, ends_at`)

### menu_promotion_versions

Phiên bản chính sách khuyến mãi POS được giữ để bảo toàn điều kiện áp dụng cho đơn cũ.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `promotion_id` | `bigint unsigned` | Không | — | FK → `menu_promotions.id` | Chính sách POS gốc. |
| `version` | `int unsigned` | Không | — | — | Số phiên bản duy nhất trong một chính sách. |
| `code` | `varchar(30)` | Không | — | — | Mã khuyến mãi ở phiên bản này. |
| `kind` | `varchar(16)` | Không | — | — | Loại ưu đãi tại thời điểm tạo phiên bản. |
| `item_id` | `bigint unsigned` | Có | — | FK → `menu_items.id` | Món áp dụng nếu có. |
| `value` | `int unsigned` | Không | — | — | Giá trị ưu đãi tại thời điểm tạo phiên bản. |
| `starts_at` | `datetime` | Không | — | — | Bắt đầu hiệu lực (UTC). |
| `ends_at` | `datetime` | Không | — | — | Kết thúc hiệu lực (UTC). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo phiên bản (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_promo_ver` (`promotion_id,version`)
- FOREIGN KEY `fk_menu_promo_ver_item` (`item_id`) → `menu_items` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_promo_ver_promo` (`promotion_id`) → `menu_promotions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_promo_ver_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_menu_promo_ver_kind`: `(kind in ('BOGO','PLAY_DRINK'))`
- CHECK `chk_menu_promo_ver_period`: `(starts_at < ends_at)`
- CHECK `chk_menu_promo_ver_version`: `(version >= 1)`

### menu_order_pricing

Snapshot kết quả tính giá POS bất biến tại thời điểm đặt/thanh toán.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `order_id` | `bigint unsigned` | Không | — | PK, FK → `menu_orders.id` | Đơn POS; khóa chính/FK. |
| `promotion_version_id` | `bigint unsigned` | Có | — | FK → `menu_promotion_versions.id` | Phiên bản chính sách khuyến mãi được áp dụng; NULL nếu không dùng ưu đãi. |
| `discount_amount` | `bigint unsigned` | Không | `0` | — | Tổng số tiền giảm giá được áp dụng (VND). |

Ràng buộc:

- PRIMARY KEY (`order_id`)
- FOREIGN KEY `fk_menu_pricing_order` (`order_id`) → `menu_orders` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_pricing_promo_version` (`promotion_version_id`) → `menu_promotion_versions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_order_pricing_discount`: `((discount_amount >= 0) and ((promotion_version_id is not null) or (discount_amount = 0)))`
