# Data dictionary — CyberHub Manager

<!-- File sinh tự động bởi scripts/gen_data_dictionary.py từ schema MySQL. Không sửa tay;
     sửa DESCRIPTIONS trong script rồi chạy lại. -->

Nguồn: `sql/001_initial_schema.sql` + `sql/002_indexes.sql` + `sql/003_p1_management_wallet.sql` + `sql/004_customer_notifications.sql` + `sql/005_customer_phase2.sql` + `sql/006_customer_membership_avatar.sql` (MySQL 8.4, InnoDB, utf8mb4). Quy ước:
tiền là `BIGINT` đơn vị VND, thời gian là `DATETIME` lưu UTC. Lịch sử nghiệp vụ dùng `RESTRICT`; chỉ ánh xạ phân phòng và ảnh đại diện dùng `CASCADE` khi entity cha được phép xóa.

## 1. Danh sách bảng

| Bảng | Mục đích | Số cột |
|---|---|---:|
| [`stores`](#stores) | Cửa hàng net. Nhân viên, máy và hóa đơn đều thuộc một cửa hàng. | 7 |
| [`employees`](#employees) | Nhân viên đăng nhập ứng dụng; vai trò quyết định quyền thao tác. | 10 |
| [`customers`](#customers) | Thông tin cá nhân của khách chơi. | 7 |
| [`accounts`](#accounts) | Tài khoản đăng nhập máy trạm và ví tiền của khách; mỗi khách đúng một tài khoản. | 12 |
| [`machines`](#machines) | Máy trạm của cửa hàng và trạng thái hiện tại. | 9 |
| [`usage_sessions`](#usage_sessions) | Một lần khách dùng một máy, từ lúc mở đến lúc checkout. | 13 |
| [`account_transactions`](#account_transactions) | Sổ cái biến động số dư: mọi lần cộng/trừ `accounts.balance` đều có đúng một dòng; không sửa, không xóa. | 11 |
| [`invoices`](#invoices) | Hóa đơn tạo khi checkout thành công; lưu lại khách, nhân viên, cửa hàng để giữ đúng lịch sử. | 16 |
| [`promotions`](#promotions) | Chính sách thưởng theo mốc nạp, phạm vi và thời gian. | 13 |
| [`management_audit`](#management_audit) | Lịch sử thay đổi quản trị, không lưu mật khẩu. | 6 |
| [`customer_notification_reads`](#customer_notification_reads) | Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền. | 3 |
| [`machine_room_types`](#machine_room_types) | Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường. | 2 |
| [`loyalty_settings`](#loyalty_settings) | Cấu hình toàn hệ thống, một dòng id=1; chỉ Admin được sửa, có version chống ghi đè. | 8 |
| [`customer_avatars`](#customer_avatars) | Ảnh đại diện riêng theo tài khoản; WebP 512×512 đã chuẩn hóa, không giữ tên file hay metadata gốc. | 4 |
| [`menu_categories`](#menu_categories) | Nhóm món theo cơ sở, xếp vào trang Đồ ăn (FOOD) hoặc Đồ uống (DRINK). | 7 |
| [`menu_items`](#menu_items) | Món ăn/đồ uống của cơ sở; không xóa cứng, chỉ ẩn để giữ lịch sử gọi món. | 11 |
| [`menu_item_images`](#menu_item_images) | Ảnh món đã chuẩn hóa (WebP 512×512, không metadata). | 4 |
| [`menu_item_changes`](#menu_item_changes) | Lịch sử thay đổi giá, tên, nhóm, ảnh và trạng thái bán; chỉ thêm, không sửa. | 7 |
| [`menu_orders`](#menu_orders) | Yêu cầu gọi món của khách đang chơi; chưa trừ ví, thu tiền tại quầy. | 12 |
| [`menu_order_items`](#menu_order_items) | Từng món trong yêu cầu gọi món, với tên và giá chụp lúc đặt. | 5 |
| [`reward_catalog`](#reward_catalog) | Danh mục phần thưởng; không có loại nào quy đổi tiền mặt. | 11 |
| [`customer_vouchers`](#customer_vouchers) | Voucher của khách; điều kiện được chụp lúc phát, dùng một lần. | 19 |
| [`voucher_events`](#voucher_events) | Nhật ký phát hành, sử dụng, khóa và cả lần bị từ chối; chỉ thêm. | 7 |
| [`loyalty_point_grants`](#loyalty_point_grants) | Điểm thành viên tặng qua voucher; cộng vào điểm, không đổi hạng. | 6 |

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
| `stores` | 1 — 0..n | `menu_categories` | `menu_categories.store_id` → `stores.id` | Cơ sở sở hữu nhóm món. |
| `stores` | 1 — 0..n | `menu_items` | `menu_items.store_id` → `stores.id` | Cơ sở bán món; menu khác nhau giữa các cơ sở. |
| `stores` | 1 — 0..n | `menu_orders` | `menu_orders.store_id` → `stores.id` | Cơ sở của máy đang dùng. |
| `stores` | 0..1 — 0..n | `reward_catalog` | `reward_catalog.store_id` → `stores.id` | Cơ sở áp dụng; NULL = mọi cơ sở (chỉ ADMIN tạo). |
| `stores` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.store_id` → `stores.id` | Cơ sở áp dụng (chụp từ danh mục); NULL = mọi cơ sở. |
| `stores` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.used_store_id` → `stores.id` | Cơ sở nơi dùng. |
| `stores` | 0..1 — 0..n | `voucher_events` | `voucher_events.store_id` → `stores.id` | Cơ sở phát sinh. |
| `employees` | 0..1 — 0..n | `usage_sessions` | `usage_sessions.closed_by` → `employees.id` | Nhân viên checkout; NULL khi phiên đang chạy. |
| `employees` | 1 — 0..n | `usage_sessions` | `usage_sessions.opened_by` → `employees.id` | Nhân viên mở phiên. |
| `employees` | 1 — 0..n | `account_transactions` | `account_transactions.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `invoices` | `invoices.employee_id` → `employees.id` | Nhân viên checkout. |
| `employees` | 1 — 0..n | `management_audit` | `management_audit.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `menu_item_changes` | `menu_item_changes.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 0..1 — 0..n | `menu_orders` | `menu_orders.handled_by` → `employees.id` | Nhân viên phục vụ/hủy; NULL khi còn NEW. |
| `employees` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.issued_by` → `employees.id` | Nhân viên phát (NULL khi do hệ thống). |
| `employees` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.used_by` → `employees.id` | Nhân viên xác nhận. |
| `employees` | 0..1 — 0..n | `voucher_events` | `voucher_events.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `loyalty_point_grants` | `loyalty_point_grants.employee_id` → `employees.id` | Nhân viên xác nhận. |
| `customers` | 1 — 0..1 | `accounts` | `accounts.customer_id` → `customers.id` | Khách sở hữu tài khoản; UNIQUE nên mỗi khách tối đa một tài khoản. |
| `customers` | 1 — 0..n | `usage_sessions` | `usage_sessions.customer_id` → `customers.id` | Khách dùng máy. |
| `customers` | 1 — 0..n | `invoices` | `invoices.customer_id` → `customers.id` | Khách (lưu thẳng để báo cáo không phải đi qua phiên). |
| `customers` | 0..1 — 0..n | `promotions` | `promotions.target_customer_id` → `customers.id` | Khách nhận riêng; NULL áp dụng cho mọi khách đủ các điều kiện còn lại. |
| `customers` | 1 — 0..n | `loyalty_point_grants` | `loyalty_point_grants.customer_id` → `customers.id` | Khách nhận điểm. |
| `accounts` | 1 — 0..n | `account_transactions` | `account_transactions.account_id` → `accounts.id` | Tài khoản bị thay đổi số dư. |
| `accounts` | 1 — 0..n | `customer_notification_reads` | `customer_notification_reads.account_id` → `accounts.id` | Tài khoản sở hữu trạng thái đọc; phần thứ nhất của khóa chính. |
| `accounts` | 1 — 0..1 | `customer_avatars` | `customer_avatars.account_id` → `accounts.id` | Tài khoản sở hữu ảnh; PK/FK, CASCADE chỉ dọn ảnh khi tài khoản được phép xóa. |
| `accounts` | 1 — 0..n | `menu_orders` | `menu_orders.account_id` → `accounts.id` | Tài khoản khách đặt món. |
| `accounts` | 1 — 0..n | `customer_vouchers` | `customer_vouchers.account_id` → `accounts.id` | Tài khoản sở hữu voucher. |
| `machines` | 1 — 0..n | `usage_sessions` | `usage_sessions.machine_id` → `machines.id` | Máy được dùng. |
| `machines` | 1 — 0..1 | `machine_room_types` | `machine_room_types.machine_id` → `machines.id` | Máy được phân loại; khóa chính và khóa ngoại; CASCADE chỉ xóa ánh xạ khi máy được phép xóa. |
| `machines` | 1 — 0..n | `menu_orders` | `menu_orders.machine_id` → `machines.id` | Máy giao món tới. |
| `usage_sessions` | 0..1 — 0..n | `account_transactions` | `account_transactions.session_id` → `usage_sessions.id` | Phiên liên quan (trừ phí, bù tiền lúc checkout); NULL với nạp tiền độc lập. |
| `usage_sessions` | 1 — 0..1 | `invoices` | `invoices.session_id` → `usage_sessions.id` | Phiên được thanh toán; UNIQUE ⇒ mỗi phiên tối đa một hóa đơn. |
| `usage_sessions` | 1 — 0..n | `menu_orders` | `menu_orders.session_id` → `usage_sessions.id` | Phiên ACTIVE lúc đặt. |
| `promotions` | 0..1 — 0..n | `account_transactions` | `account_transactions.promotion_id` → `promotions.id` | Chính sách thưởng đã áp dụng, NULL với giao dịch thường. |
| `menu_categories` | 1 — 0..n | `menu_items` | `menu_items.category_id` → `menu_categories.id` | Nhóm món; service bảo đảm cùng cơ sở với món. |
| `menu_items` | 1 — 0..1 | `menu_item_images` | `menu_item_images.item_id` → `menu_items.id` | Món sở hữu ảnh; PK/FK. |
| `menu_items` | 1 — 0..n | `menu_item_changes` | `menu_item_changes.item_id` → `menu_items.id` | Món bị thay đổi. |
| `menu_items` | 1 — 0..n | `menu_order_items` | `menu_order_items.item_id` → `menu_items.id` | Món được gọi. |
| `menu_orders` | 1 — 0..n | `menu_order_items` | `menu_order_items.order_id` → `menu_orders.id` | Yêu cầu gọi món. |
| `menu_orders` | 0..1 — 0..1 | `customer_vouchers` | `customer_vouchers.used_order_id` → `menu_orders.id` | Yêu cầu gọi món được áp (voucher đồ ăn); UNIQUE. |
| `reward_catalog` | 1 — 0..n | `customer_vouchers` | `customer_vouchers.catalog_id` → `reward_catalog.id` | Phần thưởng gốc. |
| `customer_vouchers` | 0..1 — 0..n | `voucher_events` | `voucher_events.voucher_id` → `customer_vouchers.id` | Voucher liên quan; NULL khi mã nhập không tồn tại. |
| `customer_vouchers` | 1 — 0..1 | `loyalty_point_grants` | `loyalty_point_grants.voucher_id` → `customer_vouchers.id` | Voucher MEMBER_POINTS; UNIQUE. |

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
| `auth_version` | `bigint unsigned` | Không | `0` | — | Phiên bản xác thực khách hàng; tăng khi đổi mật khẩu để thu hồi các phiên cũ. |

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
| `loyalty_eligible_amount` | `bigint` | Không | `0` | — | Phí trả bằng tiền chính/tiền bù (không gồm bonus_used), chụp khi lập hóa đơn; chỉ cộng PAID vào xét hạng. |
| `loyalty_points` | `bigint` | Không | `0` | — | Điểm chụp lúc lập hóa đơn; chỉ cộng PAID, VOID có hiệu lực 0 điểm. Không đổi ra tiền. |
| `loyalty_unit` | `bigint` | Không | `10000` | — | Số VND hợp lệ cho một điểm tại thời điểm hóa đơn, không đổi khi cập nhật cấu hình. |
| `loyalty_rule_version` | `int unsigned` | Không | `1` | — | Phiên bản cấu hình tại lúc lập hóa đơn. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_invoices_code` (`code`)
- UNIQUE `uq_invoices_session` (`session_id`)
- FOREIGN KEY `fk_invoices_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_invoice_loyalty`: `((loyalty_eligible_amount >= 0) and (loyalty_points >= 0) and (loyalty_unit > 0))`
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
| `minimum_tier` | `varchar(10)` | Không | `BRONZE` | — | Hạng tối thiểu (BRONZE/SILVER/GOLD/PLATINUM); mặc định BRONZE. |
| `minimum_points` | `bigint` | Không | `0` | — | Điểm được tính tối thiểu để đủ đối tượng ưu đãi; không tiêu điểm. |
| `target_customer_id` | `bigint unsigned` | Có | — | FK → `customers.id` | Khách nhận riêng; NULL áp dụng cho mọi khách đủ các điều kiện còn lại. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `code` (`code`)
- FOREIGN KEY `fk_promotion_target_customer` (`target_customer_id`) → `customers` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
- FOREIGN KEY `fk_promotions_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
- CHECK `chk_promotion_points`: `((minimum_points >= 0) and (minimum_points <= 1000000000))`
- CHECK `chk_promotion_tier`: `(minimum_tier in ('BRONZE','SILVER','GOLD','PLATINUM'))`
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

### machine_room_types

Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `machine_id` | `bigint unsigned` | Không | — | PK, FK → `machines.id` | Máy được phân loại; khóa chính và khóa ngoại; CASCADE chỉ xóa ánh xạ khi máy được phép xóa. |
| `room_type` | `varchar(10)` | Không | — | — | STANDARD = phòng thường, VIP = phòng VIP; không suy đoán từ giá giờ hoặc tên máy. |

Ràng buộc:

- PRIMARY KEY (`machine_id`)
- FOREIGN KEY `fk_machine_room_machine` (`machine_id`) → `machines` (`id`) ON UPDATE RESTRICT ON DELETE CASCADE
- CHECK `chk_machine_room_type`: `(room_type in ('STANDARD','VIP'))`

### loyalty_settings

Cấu hình toàn hệ thống, một dòng id=1; chỉ Admin được sửa, có version chống ghi đè.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `tinyint unsigned` | Không | — | PK | Singleton id=1. |
| `enabled` | `tinyint(1)` | Không | `1` | — | Bật/tắt tích điểm cho hóa đơn mới, không xóa điểm cũ hoặc ngừng xét chi tiêu hạng. |
| `unit_amount` | `bigint` | Không | `10000` | — | VND hợp lệ / 1 điểm, làm tròn xuống theo từng hóa đơn. |
| `silver_spend` | `bigint` | Không | `1000000` | — | Mốc chi tiêu hợp lệ hạng Bạc. |
| `gold_spend` | `bigint` | Không | `3000000` | — | Mốc chi tiêu hợp lệ hạng Vàng. |
| `platinum_spend` | `bigint` | Không | `5000000` | — | Mốc chi tiêu hợp lệ hạng Kim cương (mã PLATINUM). |
| `version` | `int unsigned` | Không | `1` | — | Tăng sau mỗi lần cập nhật, được chụp vào hóa đơn mới. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật UTC. |

Ràng buộc:

- PRIMARY KEY (`id`)
- CHECK `chk_loyalty_singleton`: `(id = 1)`
- CHECK `chk_loyalty_tiers`: `((silver_spend > 0) and (gold_spend > silver_spend) and (platinum_spend > gold_spend))`
- CHECK `chk_loyalty_unit`: `((unit_amount > 0) and (unit_amount <= 100000000))`

### customer_avatars

Ảnh đại diện riêng theo tài khoản; WebP 512×512 đã chuẩn hóa, không giữ tên file hay metadata gốc.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `account_id` | `bigint unsigned` | Không | — | PK, FK → `accounts.id` | Tài khoản sở hữu ảnh; PK/FK, CASCADE chỉ dọn ảnh khi tài khoản được phép xóa. |
| `image_data` | `mediumblob` | Không | — | — | Nội dung WebP tối đa 300.000 byte sau chuẩn hóa. |
| `digest` | `char(64)` | Không | — | — | SHA-256 của nội dung ảnh chuẩn hóa. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật UTC. |

Ràng buộc:

- PRIMARY KEY (`account_id`)
- FOREIGN KEY `fk_customer_avatar_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE

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

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_menu_categories_store_page` (`store_id, page, sort_order`)

### menu_items

Món ăn/đồ uống của cơ sở; không xóa cứng, chỉ ẩn để giữ lịch sử gọi món.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở bán món; menu khác nhau giữa các cơ sở. |
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
- UNIQUE `uq_menu_items_store_name` (`store_id,name`)
- FOREIGN KEY `fk_menu_items_category` (`category_id`) → `menu_categories` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_items_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_items_name`: `(char_length(trim(name)) > 0)`
- CHECK `chk_menu_items_price`: `(price between 1000 and 10000000)`
- CHECK `chk_menu_items_sort`: `(sort_order between 0 and 9999)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_menu_items_store_category` (`store_id, category_id, sort_order`)

### menu_item_images

Ảnh món đã chuẩn hóa (WebP 512×512, không metadata).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `item_id` | `bigint unsigned` | Không | — | PK, FK → `menu_items.id` | Món sở hữu ảnh; PK/FK. |
| `image_data` | `mediumblob` | Không | — | — | Nội dung WebP sau chuẩn hóa. |
| `digest` | `char(64)` | Không | — | — | SHA-256 nội dung ảnh; 12 ký tự đầu dùng làm phiên bản cache. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật (UTC). |

Ràng buộc:

- PRIMARY KEY (`item_id`)
- FOREIGN KEY `fk_menu_item_images_item` (`item_id`) → `menu_items` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT

### menu_item_changes

Lịch sử thay đổi giá, tên, nhóm, ảnh và trạng thái bán; chỉ thêm, không sửa.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `item_id` | `bigint unsigned` | Không | — | FK → `menu_items.id` | Món bị thay đổi. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên thực hiện. |
| `field` | `varchar(20)` | Không | — | — | `CREATE` / `NAME` / `CATEGORY` / `PRICE` / `AVAILABLE` / `VISIBLE` / `IMAGE`. |
| `old_value` | `varchar(200)` | Có | — | — | Giá trị cũ (dạng chữ), NULL khi tạo mới. |
| `new_value` | `varchar(200)` | Có | — | — | Giá trị mới (dạng chữ). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm thay đổi (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_menu_item_changes_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_item_changes_item` (`item_id`) → `menu_items` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_item_changes_field`: `(field in ('CREATE','NAME','CATEGORY','PRICE','AVAILABLE','VISIBLE','IMAGE'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_menu_item_changes_item` (`item_id, created_at`)

### menu_orders

Yêu cầu gọi món của khách đang chơi; chưa trừ ví, thu tiền tại quầy.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã yêu cầu, duy nhất (`ORD-` + hex). |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở của máy đang dùng. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản khách đặt món. |
| `session_id` | `bigint unsigned` | Không | — | FK → `usage_sessions.id` | Phiên ACTIVE lúc đặt. |
| `machine_id` | `bigint unsigned` | Không | — | FK → `machines.id` | Máy giao món tới. |
| `note` | `varchar(200)` | Không | `` | — | Ghi chú của khách (≤ 200 ký tự). |
| `total_amount` | `bigint` | Không | — | — | Tổng tiền theo giá chụp lúc đặt (VND). |
| `status` | `varchar(12)` | Không | `NEW` | — | `NEW` / `SERVED` / `CANCELLED`. |
| `handled_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên phục vụ/hủy; NULL khi còn NEW. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đặt (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật trạng thái (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_orders_code` (`code`)
- FOREIGN KEY `fk_menu_orders_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_orders_handled_by` (`handled_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_orders_machine` (`machine_id`) → `machines` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_orders_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_orders_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_orders_handled`: `(((status = 'NEW') and (handled_by is null)) or ((status <> 'NEW') and (handled_by is not null)))`
- CHECK `chk_menu_orders_status`: `(status in ('NEW','SERVED','CANCELLED'))`
- CHECK `chk_menu_orders_total`: `(total_amount > 0)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_menu_orders_account` (`account_id, created_at`)
- INDEX `idx_menu_orders_store_status` (`store_id, status, created_at`)

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

### reward_catalog

Danh mục phần thưởng; không có loại nào quy đổi tiền mặt.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã phần thưởng, duy nhất. |
| `name` | `varchar(80)` | Không | — | — | Tên hiển thị. |
| `store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cơ sở áp dụng; NULL = mọi cơ sở (chỉ ADMIN tạo). |
| `reward_type` | `varchar(20)` | Không | — | — | `FOOD_DISCOUNT` / `FREE_DRINK` / `PLAYTIME_CREDIT` (số dư khuyến mãi) / `MEMBER_POINTS`. |
| `value` | `bigint` | Không | — | — | VND giảm/tặng/cộng giờ, hoặc số điểm với MEMBER_POINTS. |
| `min_order_amount` | `bigint` | Không | `0` | — | Đơn gọi món tối thiểu (chỉ voucher đồ ăn/đồ uống). |
| `valid_days` | `int` | Không | — | — | Số ngày hiệu lực kể từ lúc phát. |
| `coin_cost` | `bigint` | Có | — | — | Giá đổi bằng xu game (Đợt 3); NULL = không bán. |
| `is_active` | `tinyint(1)` | Không | `1` | — | FALSE = tạm ngưng phát. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_reward_catalog_code` (`code`)
- FOREIGN KEY `fk_reward_catalog_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_reward_catalog_coin`: `((coin_cost is null) or (coin_cost between 1 and 1000000))`
- CHECK `chk_reward_catalog_days`: `(valid_days between 1 and 365)`
- CHECK `chk_reward_catalog_min_order`: `(min_order_amount between 0 and 10000000)`
- CHECK `chk_reward_catalog_name`: `(char_length(trim(name)) > 0)`
- CHECK `chk_reward_catalog_type`: `(reward_type in ('FOOD_DISCOUNT','FREE_DRINK','PLAYTIME_CREDIT','MEMBER_POINTS'))`
- CHECK `chk_reward_catalog_value`: `(value between 1 and 1000000)`

### customer_vouchers

Voucher của khách; điều kiện được chụp lúc phát, dùng một lần.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã ngẫu nhiên (secrets) khách đưa cho nhân viên, duy nhất. |
| `catalog_id` | `bigint unsigned` | Không | — | FK → `reward_catalog.id` | Phần thưởng gốc. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản sở hữu voucher. |
| `store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cơ sở áp dụng (chụp từ danh mục); NULL = mọi cơ sở. |
| `reward_type` | `varchar(20)` | Không | — | — | Loại phần thưởng (chụp). |
| `value` | `bigint` | Không | — | — | Giá trị (chụp). |
| `min_order_amount` | `bigint` | Không | `0` | — | Đơn tối thiểu (chụp). |
| `status` | `varchar(10)` | Không | `ISSUED` | — | `ISSUED` / `USED` / `REVOKED`; hết hạn suy ra từ `expires_at`. |
| `source` | `varchar(10)` | Không | — | — | `MANUAL` / `GAME` / `AD`. |
| `source_ref` | `varchar(64)` | Có | — | — | Mã nguồn; UNIQUE cùng `source` chống phát trùng. |
| `issued_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên phát (NULL khi do hệ thống). |
| `issued_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm phát (UTC). |
| `expires_at` | `datetime` | Không | — | — | Hết hạn (UTC). |
| `used_at` | `datetime` | Có | — | — | Thời điểm dùng (UTC). |
| `used_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên xác nhận. |
| `used_store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cơ sở nơi dùng. |
| `used_order_id` | `bigint unsigned` | Có | — | UK, FK → `menu_orders.id` | Yêu cầu gọi món được áp (voucher đồ ăn); UNIQUE. |
| `revoked_reason` | `varchar(200)` | Có | — | — | Lý do khóa. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customer_vouchers_code` (`code`)
- UNIQUE `uq_customer_vouchers_order` (`used_order_id`)
- UNIQUE `uq_customer_vouchers_source` (`source,source_ref`)
- FOREIGN KEY `fk_customer_vouchers_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_customer_vouchers_catalog` (`catalog_id`) → `reward_catalog` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_customer_vouchers_issued_by` (`issued_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_customer_vouchers_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_customer_vouchers_used_by` (`used_by`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_customer_vouchers_used_order` (`used_order_id`) → `menu_orders` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_customer_vouchers_used_store` (`used_store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_customer_vouchers_period`: `(expires_at > issued_at)`
- CHECK `chk_customer_vouchers_source`: `(source in ('MANUAL','GAME','AD'))`
- CHECK `chk_customer_vouchers_status`: `(status in ('ISSUED','USED','REVOKED'))`
- CHECK `chk_customer_vouchers_type`: `(reward_type in ('FOOD_DISCOUNT','FREE_DRINK','PLAYTIME_CREDIT','MEMBER_POINTS'))`
- CHECK `chk_customer_vouchers_used`: `(((status = 'USED') and (used_at is not null) and (used_by is not null) and (used_store_id is not null)) or ((status <> 'USED') and (used_at is null) and (used_by is null) and (used_order_id is null)))`
- CHECK `chk_customer_vouchers_value`: `(value between 1 and 1000000)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_customer_vouchers_account` (`account_id, status, expires_at`)

### voucher_events

Nhật ký phát hành, sử dụng, khóa và cả lần bị từ chối; chỉ thêm.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `voucher_id` | `bigint unsigned` | Có | — | FK → `customer_vouchers.id` | Voucher liên quan; NULL khi mã nhập không tồn tại. |
| `action` | `varchar(10)` | Không | — | — | `ISSUE` / `REDEEM` / `REVOKE` / `REJECT`. |
| `employee_id` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên thực hiện. |
| `store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cơ sở phát sinh. |
| `reason` | `varchar(200)` | Không | `` | — | Lý do/chi tiết (vd. EXPIRED, USED, WRONG_OWNER). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_voucher_events_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_voucher_events_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_voucher_events_voucher` (`voucher_id`) → `customer_vouchers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_voucher_events_action`: `(action in ('ISSUE','REDEEM','REVOKE','REJECT'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_voucher_events_store` (`store_id, created_at`)
- INDEX `idx_voucher_events_voucher` (`voucher_id, created_at`)

### loyalty_point_grants

Điểm thành viên tặng qua voucher; cộng vào điểm, không đổi hạng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `customer_id` | `bigint unsigned` | Không | — | FK → `customers.id` | Khách nhận điểm. |
| `voucher_id` | `bigint unsigned` | Không | — | UK, FK → `customer_vouchers.id` | Voucher MEMBER_POINTS; UNIQUE. |
| `points` | `bigint` | Không | — | — | Số điểm tặng. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên xác nhận. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_loyalty_point_grants_voucher` (`voucher_id`)
- FOREIGN KEY `fk_loyalty_point_grants_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_loyalty_point_grants_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_loyalty_point_grants_voucher` (`voucher_id`) → `customer_vouchers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_loyalty_point_grants_points`: `(points between 1 and 1000000)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_loyalty_point_grants_customer` (`customer_id`)
