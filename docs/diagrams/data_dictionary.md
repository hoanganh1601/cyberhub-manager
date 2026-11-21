# Data dictionary — CyberHub Manager

<!-- File sinh tự động bởi scripts/gen_data_dictionary.py từ schema MySQL. Không sửa tay;
     sửa DESCRIPTIONS trong script rồi chạy lại. -->

Nguồn: các migration `sql/001_*.sql` đến `sql/030_*.sql` (MySQL 8.4, InnoDB, utf8mb4, chuẩn 3NF nghiêm ngặt). Quy ước:
tiền là `BIGINT` đơn vị VND, thời gian là `DATETIME` lưu UTC. Lịch sử nghiệp vụ dùng `RESTRICT`; chỉ ánh xạ phân phòng và ảnh đại diện dùng `CASCADE` khi entity cha được phép xóa.

## 1. Danh sách bảng

| Bảng | Mục đích | Số cột |
|---|---|---:|
| [`stores`](#stores) | Cửa hàng net. Nhân viên, máy và hóa đơn đều thuộc một cửa hàng. | 7 |
| [`employees`](#employees) | Thông tin xác thực và phân quyền đăng nhập của nhân viên; thông tin nhân sự thuộc `employee_profiles` (chuẩn 3NF NF-03). | 11 |
| [`employee_profiles`](#employee_profiles) | Nguồn sự thật duy nhất về hồ sơ nhân sự (mã, tên, cơ sở chính, trạng thái làm việc); độc lập với thông tin đăng nhập tại `employees` (chuẩn 3NF NF-03). | 7 |
| [`employee_store_assignments`](#employee_store_assignments) | Phân công bổ sung cho MANAGER được vận hành tại nhiều cơ sở; không thay đổi cơ sở chính trong hồ sơ. | 4 |
| [`customers`](#customers) | Thông tin cá nhân của khách chơi. | 8 |
| [`customer_store_links`](#customer_store_links) | Phạm vi khách hàng tại từng cơ sở, suy ra từ giao dịch/phiên hoặc liên kết được xác minh tại quầy. | 4 |
| [`accounts`](#accounts) | Tài khoản đăng nhập máy trạm và ví tiền của khách; mỗi khách đúng một tài khoản. | 13 |
| [`machines`](#machines) | Máy trạm của cửa hàng và trạng thái hiện tại. | 9 |
| [`usage_sessions`](#usage_sessions) | Một lần khách dùng một máy, từ lúc mở đến lúc checkout; ràng buộc chiếm dụng đang hoạt động nằm tại `active_usage_sessions` (chuẩn 3NF). | 11 |
| [`active_usage_sessions`](#active_usage_sessions) | Bảng chiếm dụng 3NF ghi nhận các phiên đang ACTIVE; UNIQUE trên `machine_id` và `customer_id` thay cột sinh để chặn mở trùng. | 3 |
| [`account_transactions`](#account_transactions) | Sổ cái biến động số dư: mọi lần cộng/trừ `accounts.balance` đều có đúng một dòng; không sửa, không xóa. | 11 |
| [`invoices`](#invoices) | Hóa đơn tạo khi checkout thành công; khóa ứng viên `session_id` (UNIQUE), tham chiếu phiên bản chính sách điểm bất biến (`loyalty_policy_versions`). Các giá trị dẫn xuất (`total_amount`, `loyalty_eligible_amount`, `loyalty_points`, `loyalty_unit`) tính qua view `v_invoices`. | 12 |
| [`promotions`](#promotions) | Chính sách thưởng theo mốc nạp, phạm vi và thời gian. | 13 |
| [`management_audit`](#management_audit) | Lịch sử thay đổi quản trị, không lưu mật khẩu. | 6 |
| [`customer_notification_reads`](#customer_notification_reads) | Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền. | 3 |
| [`machine_room_types`](#machine_room_types) | Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường. | 2 |
| [`loyalty_policy_versions`](#loyalty_policy_versions) | Phiên bản bất biến của chính sách tích điểm và xét hạng thành viên; hóa đơn lịch sử tham chiếu đúng version đã áp dụng (NF-01/NF-04). | 7 |
| [`loyalty_settings`](#loyalty_settings) | Con trỏ singleton (id=1) trỏ tới phiên bản chính sách tích điểm đang hiệu lực; chỉ Admin được cập nhật kèm khóa lạc quan theo version. | 3 |
| [`customer_avatars`](#customer_avatars) | Ảnh đại diện riêng theo tài khoản; WebP 512×512 đã chuẩn hóa, không giữ tên file hay metadata gốc. | 4 |
| [`menu_categories`](#menu_categories) | Nhóm món theo cơ sở, xếp vào trang Đồ ăn (FOOD) hoặc Đồ uống (DRINK). | 7 |
| [`menu_items`](#menu_items) | Món ăn/đồ uống của cơ sở; cơ sở suy ra từ `menu_categories.store_id` (NF-02), tên món duy nhất toàn cơ sở qua trigger `trg_menu_items_bi/bu`. | 11 |
| [`menu_item_images`](#menu_item_images) | Ảnh món đã chuẩn hóa (WebP 512×512, không metadata). | 4 |
| [`menu_item_changes`](#menu_item_changes) | Lịch sử thay đổi giá, tên, nhóm, ảnh và trạng thái bán; chỉ thêm, không sửa. | 7 |
| [`menu_orders`](#menu_orders) | Đơn POS đồ ăn/thức uống của khách đang chơi; cơ sở, máy và tài khoản suy ra từ `usage_sessions` (NF-02), đọc đầy đủ qua `v_menu_orders`. | 14 |
| [`menu_order_items`](#menu_order_items) | Từng món trong yêu cầu gọi món, với tên và giá chụp lúc đặt. | 5 |
| [`inventory_ingredients`](#inventory_ingredients) | Nguyên liệu tồn kho theo từng cửa hàng; lượng khả dụng bằng tồn thực tế trừ lượng đã giữ chỗ. | 9 |
| [`menu_item_recipes`](#menu_item_recipes) | Công thức hiện hành của món có theo dõi kho. | 3 |
| [`menu_order_recipe_snapshots`](#menu_order_recipe_snapshots) | Ảnh chụp nhu cầu nguyên liệu của từng dòng đơn, giúp đổi công thức sau này không làm sai giữ/xuất kho cũ. | 4 |
| [`inventory_movements`](#inventory_movements) | Sổ cái kho bất biến: nhập, giữ chỗ, hoàn giữ chỗ, tiêu thụ, hao hụt, trả và điều chỉnh; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02). | 13 |
| [`inventory_counts`](#inventory_counts) | Phiếu kiểm kê đề xuất; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02), người phê duyệt bắt buộc khác `proposed_by` (CHECK SoD). | 13 |
| [`customer_notification_events`](#customer_notification_events) | Sổ sự kiện thông báo bền vững cho khách theo vòng đời đơn; khóa sự kiện chống phát trùng. | 8 |
| [`pos_order_reversals`](#pos_order_reversals) | Yêu cầu hoàn/hủy toàn bộ đơn POS có maker-checker và quyết định hoàn kho hoặc ghi hao hụt; cơ sở suy ra từ `menu_orders` qua `usage_sessions`→`machines` (NF-02). | 12 |
| [`menu_promotions`](#menu_promotions) | Chính sách khuyến mãi POS hiện hành theo cơ sở; mỗi lần lưu tạo một phiên bản bất biến tại `menu_promotion_versions` (NF-04). | 10 |
| [`menu_promotion_versions`](#menu_promotion_versions) | Phiên bản bất biến của chính sách khuyến mãi POS để hóa đơn/đơn hàng lịch sử tham chiếu đúng quy tắc đã áp dụng (NF-04). | 11 |
| [`menu_order_pricing`](#menu_order_pricing) | Kết quả định giá POS dạng cấu trúc chuẩn 3NF (không còn `snapshot_json` hay cột dẫn xuất `final_amount`, đọc qua `v_menu_order_pricing`). | 7 |
| [`reward_catalog`](#reward_catalog) | Danh mục phần thưởng; không có loại nào quy đổi tiền mặt. | 11 |
| [`customer_vouchers`](#customer_vouchers) | Voucher của khách; điều kiện được chụp lúc phát, dùng một lần. | 19 |
| [`voucher_events`](#voucher_events) | Nhật ký phát hành, sử dụng, khóa và cả lần bị từ chối; chỉ thêm. | 7 |
| [`loyalty_point_grants`](#loyalty_point_grants) | Điểm thành viên tặng qua voucher; cộng vào điểm, không đổi hạng. | 6 |
| [`games`](#games) | Cấu hình trò chơi (giai đoạn đầu: vòng quay may mắn), dùng chung mọi cơ sở. | 7 |
| [`game_prizes`](#game_prizes) | Các ô thưởng trên vòng quay và tỉ lệ trúng tương đối. | 6 |
| [`game_wallets`](#game_wallets) | Ví xu game của tài khoản; xu không phải tiền và không phải điểm thành viên. | 8 |
| [`game_sessions`](#game_sessions) | Lịch sử từng lượt quay; kết quả do máy chủ bốc thăm và được chụp lại. | 8 |
| [`game_coin_ledger`](#game_coin_ledger) | Sổ cái xu: mọi thay đổi số dư xu có đúng một dòng; chỉ thêm. | 8 |
| [`ad_settings`](#ad_settings) | Cấu hình chương trình quảng cáo nhận thưởng (một dòng duy nhất). | 7 |
| [`ad_creatives`](#ad_creatives) | Nội dung quảng cáo nội bộ do CyberHub tự soạn. | 8 |
| [`ad_reward_events`](#ad_reward_events) | Mỗi lần bắt đầu xem quảng cáo; token dùng một lần, độc lập với kết quả game. | 15 |
| [`cash_shifts`](#cash_shifts) | Ca làm việc và đối chiếu két tiền của một nhân viên tại một cơ sở; chênh lệch `variance` tính qua `v_cash_shifts`, chiếm dụng ca mở nằm tại `active_employee_shifts`. | 13 |
| [`active_employee_shifts`](#active_employee_shifts) | Bảng chiếm dụng 3NF bảo đảm mỗi nhân viên chỉ có tối đa một ca `OPEN`/`PENDING_REVIEW` cùng lúc (thay cột sinh `active_employee_id`). | 2 |
| [`cash_shift_entries`](#cash_shift_entries) | Sổ bất biến thu, chi, hoàn và điều chỉnh theo ca; cơ sở suy ra từ `cash_shifts.store_id` (NF-02). | 10 |
| [`machine_incidents`](#machine_incidents) | Phiếu sự cố và vòng đời bảo trì máy từ báo lỗi đến nghiệm thu; cơ sở suy ra từ `machines.store_id` (NF-02). | 17 |
| [`machine_incident_parts`](#machine_incident_parts) | Linh kiện sử dụng cho một phiếu sửa máy. | 5 |
| [`machine_incident_events`](#machine_incident_events) | Lịch sử chuyển trạng thái sự cố máy, chỉ thêm. | 7 |
| [`suppliers`](#suppliers) | Nhà cung cấp theo cơ sở và điều khoản thanh toán. | 10 |
| [`purchase_requests`](#purchase_requests) | Đề nghị nhập hàng có người lập và người quyết định (tách nhiệm vụ `decided_by <> requested_by`). | 9 |
| [`purchase_request_lines`](#purchase_request_lines) | Nguyên liệu và số lượng trong đề nghị nhập. | 3 |
| [`purchase_orders`](#purchase_orders) | Đơn mua hàng tạo từ đề nghị đã duyệt và gắn nhà cung cấp; cơ sở suy ra từ `purchase_requests.store_id` (NF-02). | 9 |
| [`purchase_order_lines`](#purchase_order_lines) | Dòng đơn mua và tiến độ nhận theo nguyên liệu. | 6 |
| [`goods_receipts`](#goods_receipts) | Phiếu nhận hàng idempotent, tạo nhập kho và công nợ theo số lượng đạt; cơ sở suy ra từ `purchase_orders`→`purchase_requests` (NF-02). | 8 |
| [`goods_receipt_lines`](#goods_receipt_lines) | Chi tiết hàng đạt, hỏng và thiếu trong một lần nhận. | 6 |
| [`supplier_payables`](#supplier_payables) | Công nợ phát sinh từ phiếu nhận hàng và trạng thái thanh toán; cơ sở và nhà cung cấp suy ra từ `goods_receipts`→`purchase_orders`→`purchase_requests` (NF-02). | 9 |
| [`commercial_partners`](#commercial_partners) | Đối tác cung cấp game hoặc mạng quảng cáo. | 10 |
| [`commercial_contracts`](#commercial_contracts) | Hợp đồng thương mại có maker-checker và mô hình tính doanh thu. | 13 |
| [`commercial_campaigns`](#commercial_campaigns) | Chiến dịch game/quảng cáo thuộc một hợp đồng đã duyệt. | 13 |
| [`commercial_placements`](#commercial_placements) | Vị trí phát game/quảng cáo, có thể giới hạn theo cửa hàng. | 13 |
| [`commercial_play_sessions`](#commercial_play_sessions) | Phiên chơi ngoài có token một lần và hạn sử dụng. | 10 |
| [`commercial_events`](#commercial_events) | Sổ sự kiện impression/start/complete/click, chống ghi trùng; chiến dịch suy ra từ `commercial_placements.campaign_id` (NF-02). | 13 |
| [`commercial_reward_grants`](#commercial_reward_grants) | Outbox phần thưởng; callback không được cộng xu/phát voucher trực tiếp. | 10 |
| [`commercial_settlements`](#commercial_settlements) | Kỳ đối soát doanh thu có maker-checker; `net_amount` tính qua `v_commercial_settlements` (NF-01). | 13 |
| [`commercial_settlement_lines`](#commercial_settlement_lines) | Dòng snapshot đối soát theo vị trí và loại sự kiện; thành tiền `amount` tính qua `v_commercial_settlement_lines` (NF-01). | 5 |
| [`supplier_payable_approvals`](#supplier_payable_approvals) | Bản ghi duyệt công nợ nhà cung cấp; dùng kiểm soát phân tách người duyệt và người chi. | 4 |
| [`customer_email_tokens`](#customer_email_tokens) | Token kích hoạt/đặt lại mật khẩu khách; chỉ lưu hash và nonce dẫn xuất, token thô không được lưu. | 8 |
| [`customer_mail_outbox`](#customer_mail_outbox) | Transactional outbox gửi email khách sau khi transaction đăng ký/reset đã commit. | 7 |
| [`customer_security_audit`](#customer_security_audit) | Audit bất biến cho thao tác kích hoạt, đặt lại mật khẩu và các sự kiện bảo mật khách. | 6 |

## 2. Quan hệ và cardinality

Đọc từ khóa ngoại: phía cha là `1` khi mọi cột FK `NOT NULL`, `0..1` khi có cột cho phép NULL;
phía con là `0..1` khi bộ cột FK có UNIQUE, ngược lại `0..n`.

| Cha | | Con | Khóa ngoại | Ý nghĩa |
|---|:---:|---|---|---|
| `stores` | 1 — 0..n | `employee_profiles` | `employee_profiles.home_store_id` → `stores.id` | Cơ sở công tác chính. |
| `stores` | 1 — 0..n | `employee_store_assignments` | `employee_store_assignments.store_id` → `stores.id` | Cơ sở được phép vận hành; phần thứ hai của khóa chính. |
| `stores` | 1 — 0..n | `customer_store_links` | `customer_store_links.store_id` → `stores.id` | Cơ sở liên quan; phần thứ hai của khóa chính. |
| `stores` | 1 — 0..n | `machines` | `machines.store_id` → `stores.id` | Cửa hàng sở hữu máy. |
| `stores` | 0..1 — 0..n | `account_transactions` | `account_transactions.store_id` → `stores.id` | Cơ sở ghi nhận giao dịch tại thời điểm phát sinh. |
| `stores` | 1 — 0..n | `invoices` | `invoices.store_id` → `stores.id` | Cửa hàng (khớp `machines.store_id` của phiên nhờ trigger `trg_invoices_bi/bu`). |
| `stores` | 0..1 — 0..n | `promotions` | `promotions.store_id` → `stores.id` | Cơ sở áp dụng; NULL = toàn hệ thống. |
| `stores` | 1 — 0..n | `management_audit` | `management_audit.store_id` → `stores.id` | Cơ sở đang vận hành. |
| `stores` | 1 — 0..n | `menu_categories` | `menu_categories.store_id` → `stores.id` | Cơ sở sở hữu nhóm món. |
| `stores` | 1 — 0..n | `inventory_ingredients` | `inventory_ingredients.store_id` → `stores.id` | Cửa hàng sở hữu nguyên liệu; cùng `id` tạo khóa tham chiếu ghép cho sổ kho. |
| `stores` | 1 — 0..n | `customer_notification_events` | `customer_notification_events.store_id` → `stores.id` | Cửa hàng phát sinh thông báo. |
| `stores` | 1 — 0..n | `menu_promotions` | `menu_promotions.store_id` → `stores.id` | Cơ sở áp dụng. |
| `stores` | 0..1 — 0..n | `reward_catalog` | `reward_catalog.store_id` → `stores.id` | Cơ sở áp dụng; NULL = mọi cơ sở (chỉ ADMIN tạo). |
| `stores` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.store_id` → `stores.id` | Cơ sở áp dụng (chụp từ danh mục); NULL = mọi cơ sở. |
| `stores` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.used_store_id` → `stores.id` | Cơ sở nơi dùng. |
| `stores` | 0..1 — 0..n | `voucher_events` | `voucher_events.store_id` → `stores.id` | Cơ sở phát sinh. |
| `stores` | 1 — 0..n | `cash_shifts` | `cash_shifts.store_id` → `stores.id` | Cơ sở mở ca. |
| `stores` | 1 — 0..n | `suppliers` | `suppliers.store_id` → `stores.id` | Cơ sở quản lý nhà cung cấp. |
| `stores` | 1 — 0..n | `purchase_requests` | `purchase_requests.store_id` → `stores.id` | Cơ sở đề nghị. |
| `stores` | 0..1 — 0..n | `commercial_placements` | `commercial_placements.store_id` → `stores.id` | Cửa hàng áp dụng; NULL = toàn hệ thống. |
| `stores` | 0..1 — 0..n | `customer_security_audit` | `customer_security_audit.store_id` → `stores.id` | Cơ sở liên quan nếu có; NULL với luồng web tự phục vụ. |
| `employees` | 1 — 0..n | `employee_store_assignments` | `employee_store_assignments.employee_id` → `employees.id` | Nhân viên được phân công; phần thứ nhất của khóa chính. |
| `employees` | 1 — 0..n | `employee_store_assignments` | `employee_store_assignments.granted_by` → `employees.id` | ADMIN đã cấp quyền phân công. |
| `employees` | 0..1 — 0..n | `usage_sessions` | `usage_sessions.closed_by` → `employees.id` | Nhân viên checkout; NULL khi phiên đang chạy. |
| `employees` | 1 — 0..n | `usage_sessions` | `usage_sessions.opened_by` → `employees.id` | Nhân viên mở phiên. |
| `employees` | 1 — 0..n | `account_transactions` | `account_transactions.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `invoices` | `invoices.employee_id` → `employees.id` | Nhân viên checkout. |
| `employees` | 1 — 0..n | `management_audit` | `management_audit.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `menu_item_changes` | `menu_item_changes.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 0..1 — 0..n | `menu_orders` | `menu_orders.handled_by` → `employees.id` | Nhân viên tiếp nhận/phục vụ/hủy; NULL khi còn NEW. |
| `employees` | 0..1 — 0..n | `menu_orders` | `menu_orders.paid_by` → `employees.id` | Nhân viên xác nhận thanh toán. |
| `employees` | 0..1 — 0..n | `inventory_movements` | `inventory_movements.employee_id` → `employees.id` | Nhân viên thực hiện hoặc phê duyệt; NULL với tác vụ hệ thống. |
| `employees` | 0..1 — 0..n | `inventory_counts` | `inventory_counts.decided_by` → `employees.id` | Nhân viên khác phê duyệt/từ chối; NULL khi đang chờ. |
| `employees` | 1 — 0..n | `inventory_counts` | `inventory_counts.proposed_by` → `employees.id` | Nhân viên đề xuất kiểm kê. |
| `employees` | 0..1 — 0..n | `pos_order_reversals` | `pos_order_reversals.decided_by` → `employees.id` | Quản lý quyết định (khác `requested_by`); NULL khi đang chờ. |
| `employees` | 1 — 0..n | `pos_order_reversals` | `pos_order_reversals.requested_by` → `employees.id` | Nhân viên đề nghị. |
| `employees` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.issued_by` → `employees.id` | Nhân viên phát (NULL khi do hệ thống). |
| `employees` | 0..1 — 0..n | `customer_vouchers` | `customer_vouchers.used_by` → `employees.id` | Nhân viên xác nhận. |
| `employees` | 0..1 — 0..n | `voucher_events` | `voucher_events.employee_id` → `employees.id` | Nhân viên thực hiện. |
| `employees` | 1 — 0..n | `loyalty_point_grants` | `loyalty_point_grants.employee_id` → `employees.id` | Nhân viên xác nhận. |
| `employees` | 1 — 0..n | `cash_shifts` | `cash_shifts.employee_id` → `employees.id` | Nhân viên chịu trách nhiệm ca. |
| `employees` | 0..1 — 0..n | `cash_shifts` | `cash_shifts.reviewed_by` → `employees.id` | Quản lý duyệt chênh lệch (khác `employee_id`). |
| `employees` | 1 — 0..1 | `active_employee_shifts` | `active_employee_shifts.employee_id` → `employees.id` | Nhân viên đang mở ca; UNIQUE ⇒ không thể mở đồng thời hai ca. |
| `employees` | 1 — 0..n | `cash_shift_entries` | `cash_shift_entries.employee_id` → `employees.id` | Nhân viên ghi nhận. |
| `employees` | 0..1 — 0..n | `machine_incidents` | `machine_incidents.assigned_to` → `employees.id` | Người được phân công; có thể NULL trước khi phân công. |
| `employees` | 1 — 0..n | `machine_incidents` | `machine_incidents.reported_by` → `employees.id` | Người báo lỗi. |
| `employees` | 0..1 — 0..n | `machine_incidents` | `machine_incidents.verified_by` → `employees.id` | Người nghiệm thu (khác `assigned_to`). |
| `employees` | 1 — 0..n | `machine_incident_events` | `machine_incident_events.employee_id` → `employees.id` | Người thực hiện. |
| `employees` | 0..1 — 0..n | `purchase_requests` | `purchase_requests.decided_by` → `employees.id` | Người duyệt/từ chối. |
| `employees` | 1 — 0..n | `purchase_requests` | `purchase_requests.requested_by` → `employees.id` | Người lập. |
| `employees` | 1 — 0..n | `purchase_orders` | `purchase_orders.created_by` → `employees.id` | Người tạo đơn. |
| `employees` | 1 — 0..n | `goods_receipts` | `goods_receipts.received_by` → `employees.id` | Người nhận. |
| `employees` | 0..1 — 0..n | `supplier_payables` | `supplier_payables.paid_by` → `employees.id` | Người thanh toán (khác người duyệt nhờ trigger). |
| `employees` | 0..1 — 0..n | `commercial_contracts` | `commercial_contracts.approved_by` → `employees.id` | Người duyệt; phải khác người lập theo service. |
| `employees` | 1 — 0..n | `commercial_contracts` | `commercial_contracts.created_by` → `employees.id` | Nhân viên lập hợp đồng. |
| `employees` | 1 — 0..n | `commercial_campaigns` | `commercial_campaigns.created_by` → `employees.id` | Nhân viên tạo. |
| `employees` | 1 — 0..n | `commercial_settlements` | `commercial_settlements.generated_by` → `employees.id` | Nhân viên tạo kỳ. |
| `employees` | 0..1 — 0..n | `commercial_settlements` | `commercial_settlements.reviewed_by` → `employees.id` | Người duyệt (khác `generated_by` nhờ CHECK SoD). |
| `employees` | 1 — 0..n | `supplier_payable_approvals` | `supplier_payable_approvals.approved_by` → `employees.id` | Nhân viên phê duyệt, phải khác người thanh toán theo service trong chính sách tách quyền. |
| `employees` | 0..1 — 0..n | `customer_security_audit` | `customer_security_audit.employee_id` → `employees.id` | Nhân viên liên quan nếu thao tác tại quầy; NULL với luồng email tự phục vụ. |
| `employee_profiles` | 1 — 0..1 | `employees` | `employees.profile_id` → `employee_profiles.id` | Hồ sơ nhân sự duy nhất (`employee_profiles.id`); UNIQUE nên mỗi hồ sơ gắn tối đa một tài khoản đăng nhập. |
| `customers` | 1 — 0..n | `customer_store_links` | `customer_store_links.customer_id` → `customers.id` | Khách hàng; phần thứ nhất của khóa chính. |
| `customers` | 1 — 0..1 | `accounts` | `accounts.customer_id` → `customers.id` | Khách sở hữu tài khoản; UNIQUE nên mỗi khách tối đa một tài khoản. |
| `customers` | 1 — 0..n | `usage_sessions` | `usage_sessions.customer_id` → `customers.id` | Khách dùng máy. |
| `customers` | 1 — 0..1 | `active_usage_sessions` | `active_usage_sessions.customer_id` → `customers.id` | Khách đang chơi; UNIQUE ⇒ mỗi khách tối đa một phiên ACTIVE. |
| `customers` | 1 — 0..n | `invoices` | `invoices.customer_id` → `customers.id` | Khách (khớp `usage_sessions.customer_id` nhờ trigger `trg_invoices_bi/bu`). |
| `customers` | 0..1 — 0..n | `promotions` | `promotions.target_customer_id` → `customers.id` | Khách nhận riêng; NULL áp dụng cho mọi khách đủ các điều kiện còn lại. |
| `customers` | 1 — 0..n | `loyalty_point_grants` | `loyalty_point_grants.customer_id` → `customers.id` | Khách nhận điểm. |
| `accounts` | 1 — 0..n | `account_transactions` | `account_transactions.account_id` → `accounts.id` | Tài khoản bị thay đổi số dư. |
| `accounts` | 1 — 0..n | `customer_notification_reads` | `customer_notification_reads.account_id` → `accounts.id` | Tài khoản sở hữu trạng thái đọc; phần thứ nhất của khóa chính. |
| `accounts` | 1 — 0..1 | `customer_avatars` | `customer_avatars.account_id` → `accounts.id` | Tài khoản sở hữu ảnh; PK/FK, CASCADE chỉ dọn ảnh khi tài khoản được phép xóa. |
| `accounts` | 0..1 — 0..n | `inventory_movements` | `inventory_movements.account_id` → `accounts.id` | Tài khoản khách liên quan; NULL nếu không gắn khách. |
| `accounts` | 1 — 0..n | `customer_notification_events` | `customer_notification_events.account_id` → `accounts.id` | Tài khoản khách nhận thông báo. |
| `accounts` | 1 — 0..n | `customer_vouchers` | `customer_vouchers.account_id` → `accounts.id` | Tài khoản sở hữu voucher. |
| `accounts` | 1 — 0..1 | `game_wallets` | `game_wallets.account_id` → `accounts.id` | Tài khoản khách; PK/FK. |
| `accounts` | 1 — 0..n | `game_sessions` | `game_sessions.account_id` → `accounts.id` | Tài khoản chơi. |
| `accounts` | 1 — 0..n | `game_coin_ledger` | `game_coin_ledger.account_id` → `accounts.id` | Tài khoản. |
| `accounts` | 1 — 0..n | `ad_reward_events` | `ad_reward_events.account_id` → `accounts.id` | Tài khoản xem. |
| `accounts` | 1 — 0..n | `commercial_play_sessions` | `commercial_play_sessions.account_id` → `accounts.id` | Tài khoản khách chơi. |
| `accounts` | 0..1 — 0..n | `commercial_events` | `commercial_events.account_id` → `accounts.id` | Tài khoản liên quan; có thể NULL. |
| `accounts` | 1 — 0..n | `commercial_reward_grants` | `commercial_reward_grants.account_id` → `accounts.id` | Tài khoản nhận thưởng (khớp sự kiện nhờ trigger `trg_commercial_reward_grants_bi`). |
| `accounts` | 1 — 0..n | `customer_email_tokens` | `customer_email_tokens.account_id` → `accounts.id` | Tài khoản khách nhận token. |
| `accounts` | 1 — 0..n | `customer_security_audit` | `customer_security_audit.account_id` → `accounts.id` | Tài khoản khách chịu tác động. |
| `machines` | 1 — 0..n | `usage_sessions` | `usage_sessions.machine_id` → `machines.id` | Máy được dùng. |
| `machines` | 1 — 0..1 | `active_usage_sessions` | `active_usage_sessions.machine_id` → `machines.id` | Máy đang bị chiếm dụng; UNIQUE ⇒ mỗi máy tối đa một phiên ACTIVE. |
| `machines` | 1 — 0..1 | `machine_room_types` | `machine_room_types.machine_id` → `machines.id` | Máy được phân loại; khóa chính và khóa ngoại; CASCADE chỉ xóa ánh xạ khi máy được phép xóa. |
| `machines` | 1 — 0..n | `machine_incidents` | `machine_incidents.machine_id` → `machines.id` | Máy gặp sự cố. |
| `usage_sessions` | 1 — 0..1 | `active_usage_sessions` | `active_usage_sessions.session_id` → `usage_sessions.id` | Phiên đang ACTIVE; PK/FK tới `usage_sessions.id` (tự đồng bộ qua trigger khi mở/đóng phiên). |
| `usage_sessions` | 0..1 — 0..n | `account_transactions` | `account_transactions.session_id` → `usage_sessions.id` | Phiên liên quan (trừ phí, bù tiền lúc checkout); NULL với nạp tiền độc lập. |
| `usage_sessions` | 1 — 0..1 | `invoices` | `invoices.session_id` → `usage_sessions.id` | Phiên được thanh toán; UNIQUE ⇒ mỗi phiên tối đa một hóa đơn. |
| `usage_sessions` | 1 — 0..n | `menu_orders` | `menu_orders.session_id` → `usage_sessions.id` | Phiên ACTIVE lúc đặt (xác định khách, máy và cơ sở phục vụ). |
| `promotions` | 0..1 — 0..n | `account_transactions` | `account_transactions.promotion_id` → `promotions.id` | Chính sách thưởng đã áp dụng, NULL với giao dịch thường. |
| `loyalty_policy_versions` | 1 — 0..n | `invoices` | `invoices.loyalty_rule_version` → `loyalty_policy_versions.version` | FK tới `loyalty_policy_versions.version` chụp bất biến tại lúc lập hóa đơn. |
| `loyalty_policy_versions` | 1 — 0..n | `loyalty_settings` | `loyalty_settings.current_version` → `loyalty_policy_versions.version` | FK tới `loyalty_policy_versions.version` đang áp dụng. |
| `menu_categories` | 1 — 0..n | `menu_items` | `menu_items.category_id` → `menu_categories.id` | Nhóm món (xác định cơ sở bán món). |
| `menu_items` | 1 — 0..1 | `menu_item_images` | `menu_item_images.item_id` → `menu_items.id` | Món sở hữu ảnh; PK/FK. |
| `menu_items` | 1 — 0..n | `menu_item_changes` | `menu_item_changes.item_id` → `menu_items.id` | Món bị thay đổi. |
| `menu_items` | 1 — 0..n | `menu_order_items` | `menu_order_items.item_id` → `menu_items.id` | Món được gọi. |
| `menu_items` | 1 — 0..n | `menu_item_recipes` | `menu_item_recipes.item_id` → `menu_items.id` | Món dùng nguyên liệu; phần thứ nhất của khóa chính. |
| `menu_items` | 0..1 — 0..n | `menu_promotions` | `menu_promotions.item_id` → `menu_items.id` | Món áp dụng (cùng cơ sở nhờ trigger); NULL khi ưu đãi không gắn một món. |
| `menu_items` | 0..1 — 0..n | `menu_promotion_versions` | `menu_promotion_versions.item_id` → `menu_items.id` | Món áp dụng chụp tại phiên bản; NULL nếu không gắn món. |
| `menu_orders` | 1 — 0..n | `menu_order_items` | `menu_order_items.order_id` → `menu_orders.id` | Yêu cầu gọi món. |
| `menu_orders` | 0..1 — 0..n | `inventory_movements` | `inventory_movements.order_id` → `menu_orders.id` | Đơn POS liên quan; NULL với nhập/kiểm kê độc lập. |
| `menu_orders` | 1 — 0..1 | `pos_order_reversals` | `pos_order_reversals.order_id` → `menu_orders.id` | Đơn POS; UNIQUE nên mỗi đơn có tối đa một yêu cầu hoàn/hủy. |
| `menu_orders` | 1 — 0..1 | `menu_order_pricing` | `menu_order_pricing.order_id` → `menu_orders.id` | Đơn POS; khóa chính/FK. |
| `menu_orders` | 0..1 — 0..1 | `customer_vouchers` | `customer_vouchers.used_order_id` → `menu_orders.id` | Yêu cầu gọi món được áp (voucher đồ ăn); UNIQUE. |
| `menu_order_items` | 1 — 0..n | `menu_order_recipe_snapshots` | `menu_order_recipe_snapshots.order_id,item_id` → `menu_order_items.order_id,item_id` | Đơn chứa dòng món; thuộc khóa chính và FK ghép tới `menu_order_items`.; Món trong đơn; thuộc khóa chính và FK ghép tới `menu_order_items`. |
| `inventory_ingredients` | 1 — 0..n | `menu_item_recipes` | `menu_item_recipes.ingredient_id` → `inventory_ingredients.id` | Nguyên liệu; phần thứ hai của khóa chính. |
| `inventory_ingredients` | 1 — 0..n | `menu_order_recipe_snapshots` | `menu_order_recipe_snapshots.ingredient_id` → `inventory_ingredients.id` | Nguyên liệu đã được chụp cho dòng món. |
| `inventory_ingredients` | 1 — 0..n | `inventory_movements` | `inventory_movements.ingredient_id` → `inventory_ingredients.id` | Nguyên liệu bị thay đổi. |
| `inventory_ingredients` | 1 — 0..n | `inventory_counts` | `inventory_counts.ingredient_id` → `inventory_ingredients.id` | Nguyên liệu được kiểm kê. |
| `inventory_ingredients` | 1 — 0..n | `purchase_request_lines` | `purchase_request_lines.ingredient_id` → `inventory_ingredients.id` | Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính. |
| `inventory_ingredients` | 1 — 0..n | `purchase_order_lines` | `purchase_order_lines.ingredient_id` → `inventory_ingredients.id` | Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính. |
| `inventory_ingredients` | 1 — 0..n | `goods_receipt_lines` | `goods_receipt_lines.ingredient_id` → `inventory_ingredients.id` | Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính. |
| `menu_promotions` | 1 — 0..n | `menu_promotion_versions` | `menu_promotion_versions.promotion_id` → `menu_promotions.id` | Chính sách khuyến mãi cha. |
| `menu_promotion_versions` | 0..1 — 0..n | `menu_order_pricing` | `menu_order_pricing.promotion_version_id` → `menu_promotion_versions.id` | Phiên bản khuyến mãi bất biến đã chọn; NULL nếu không áp dụng. |
| `reward_catalog` | 1 — 0..n | `customer_vouchers` | `customer_vouchers.catalog_id` → `reward_catalog.id` | Phần thưởng gốc. |
| `customer_vouchers` | 0..1 — 0..n | `menu_order_pricing` | `menu_order_pricing.voucher_id` → `customer_vouchers.id` | Voucher đồ ăn/đồ uống đã áp nếu có. |
| `customer_vouchers` | 0..1 — 0..n | `voucher_events` | `voucher_events.voucher_id` → `customer_vouchers.id` | Voucher liên quan; NULL khi mã nhập không tồn tại. |
| `customer_vouchers` | 1 — 0..1 | `loyalty_point_grants` | `loyalty_point_grants.voucher_id` → `customer_vouchers.id` | Voucher MEMBER_POINTS; UNIQUE. |
| `customer_vouchers` | 0..1 — 0..n | `game_coin_ledger` | `game_coin_ledger.voucher_id` → `customer_vouchers.id` | Voucher nhận được khi đổi xu. |
| `games` | 1 — 0..n | `game_prizes` | `game_prizes.game_id` → `games.id` | Game sở hữu ô thưởng. |
| `games` | 1 — 0..n | `game_sessions` | `game_sessions.game_id` → `games.id` | Game. |
| `games` | 0..1 — 0..n | `commercial_placements` | `commercial_placements.legacy_game_id` → `games.id` | Game nội bộ cũ nếu vị trí ánh xạ vào game có sẵn. |
| `ad_creatives` | 0..1 — 0..n | `ad_reward_events` | `ad_reward_events.creative_id` → `ad_creatives.id` | Nội dung đã phát. |
| `ad_creatives` | 0..1 — 0..n | `commercial_placements` | `commercial_placements.legacy_ad_creative_id` → `ad_creatives.id` | Nội dung quảng cáo nội bộ cũ nếu có. |
| `cash_shifts` | 1 — 0..1 | `active_employee_shifts` | `active_employee_shifts.shift_id` → `cash_shifts.id` | Ca đang mở hoặc chờ duyệt; PK/FK tới `cash_shifts.id` (tự đồng bộ qua trigger). |
| `cash_shifts` | 1 — 0..n | `cash_shift_entries` | `cash_shift_entries.shift_id` → `cash_shifts.id` | Ca sở hữu bút toán. |
| `machine_incidents` | 1 — 0..n | `machine_incident_parts` | `machine_incident_parts.incident_id` → `machine_incidents.id` | Phiếu sự cố. |
| `machine_incidents` | 1 — 0..n | `machine_incident_events` | `machine_incident_events.incident_id` → `machine_incidents.id` | Phiếu sự cố. |
| `suppliers` | 1 — 0..n | `purchase_orders` | `purchase_orders.supplier_id` → `suppliers.id` | Nhà cung cấp (cùng cơ sở với đề nghị nhờ trigger). |
| `purchase_requests` | 1 — 0..n | `purchase_request_lines` | `purchase_request_lines.request_id` → `purchase_requests.id` | Đề nghị; phần thứ nhất khóa chính. |
| `purchase_requests` | 1 — 0..1 | `purchase_orders` | `purchase_orders.request_id` → `purchase_requests.id` | Đề nghị nguồn; UNIQUE. |
| `purchase_orders` | 1 — 0..n | `purchase_order_lines` | `purchase_order_lines.order_id` → `purchase_orders.id` | Đơn mua; phần thứ nhất khóa chính. |
| `purchase_orders` | 1 — 0..n | `goods_receipts` | `goods_receipts.order_id` → `purchase_orders.id` | Đơn mua. |
| `goods_receipts` | 1 — 0..n | `goods_receipt_lines` | `goods_receipt_lines.receipt_id` → `goods_receipts.id` | Phiếu nhận; phần thứ nhất khóa chính. |
| `goods_receipts` | 1 — 0..1 | `supplier_payables` | `supplier_payables.receipt_id` → `goods_receipts.id` | Phiếu nhận nguồn; UNIQUE. |
| `supplier_payables` | 1 — 0..1 | `supplier_payable_approvals` | `supplier_payable_approvals.payable_id` → `supplier_payables.id` | Công nợ được duyệt; khóa chính/FK nên mỗi công nợ được duyệt tối đa một lần. |
| `commercial_partners` | 1 — 0..n | `commercial_contracts` | `commercial_contracts.partner_id` → `commercial_partners.id` | Đối tác ký hợp đồng. |
| `commercial_contracts` | 1 — 0..n | `commercial_campaigns` | `commercial_campaigns.contract_id` → `commercial_contracts.id` | Hợp đồng chi phối chiến dịch. |
| `commercial_contracts` | 1 — 0..n | `commercial_settlements` | `commercial_settlements.contract_id` → `commercial_contracts.id` | Hợp đồng được đối soát. |
| `commercial_campaigns` | 1 — 0..n | `commercial_placements` | `commercial_placements.campaign_id` → `commercial_campaigns.id` | Chiến dịch sở hữu vị trí. |
| `commercial_placements` | 1 — 0..n | `commercial_play_sessions` | `commercial_play_sessions.placement_id` → `commercial_placements.id` | Vị trí game được mở. |
| `commercial_placements` | 1 — 0..n | `commercial_events` | `commercial_events.placement_id` → `commercial_placements.id` | Vị trí phát sinh sự kiện. |
| `commercial_placements` | 1 — 0..n | `commercial_settlement_lines` | `commercial_settlement_lines.placement_id` → `commercial_placements.id` | Vị trí được tính tiền. |
| `commercial_play_sessions` | 0..1 — 0..n | `commercial_events` | `commercial_events.play_session_id` → `commercial_play_sessions.id` | Phiên chơi liên quan; có thể NULL. |
| `commercial_events` | 1 — 0..1 | `commercial_reward_grants` | `commercial_reward_grants.event_id` → `commercial_events.id` | COMPLETE event đã xác minh; duy nhất. |
| `commercial_settlements` | 1 — 0..n | `commercial_settlement_lines` | `commercial_settlement_lines.settlement_id` → `commercial_settlements.id` | Kỳ đối soát. |
| `customer_email_tokens` | 1 — 0..1 | `customer_mail_outbox` | `customer_mail_outbox.token_id` → `customer_email_tokens.id` | Token cần gửi; UNIQUE để tránh gửi trùng outbox. |

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

Thông tin xác thực và phân quyền đăng nhập của nhân viên; thông tin nhân sự thuộc `employee_profiles` (chuẩn 3NF NF-03).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính (dùng làm khóa tham chiếu lịch sử cho mọi chứng từ). |
| `profile_id` | `bigint unsigned` | Không | — | UK, FK → `employee_profiles.id` | Hồ sơ nhân sự duy nhất (`employee_profiles.id`); UNIQUE nên mỗi hồ sơ gắn tối đa một tài khoản đăng nhập. |
| `username` | `varchar(30)` | Không | — | UK | Tên đăng nhập, duy nhất, 4–30 ký tự. |
| `password_hash` | `varchar(255)` | Không | — | — | Mật khẩu đã băm bcrypt; không bao giờ trả ra UI/DTO. |
| `role` | `varchar(20)` | Không | — | — | `ADMIN` / `DIRECTOR` / `MANAGER` / `STAFF` / `KITCHEN` / `INVENTORY`; backend cấp quyền tối thiểu theo từng thao tác. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `INACTIVE` / `LOCKED`. Chỉ ACTIVE đăng nhập được. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |
| `auth_version` | `int unsigned` | Không | `0` | — | Phiên bản xác thực; tăng khi đổi/đặt lại mật khẩu để thu hồi phiên cũ. |
| `must_change_password` | `tinyint(1)` | Không | `0` | — | TRUE khi tài khoản đang dùng mật khẩu tạm và phải đổi trước khi thao tác. |
| `password_changed_at` | `datetime` | Có | — | — | Thời điểm đổi hoặc đặt lại mật khẩu gần nhất (UTC), có thể NULL với dữ liệu cũ. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_employees_profile` (`profile_id`)
- UNIQUE `uq_employees_username` (`username`)
- FOREIGN KEY `fk_employees_profile` (`profile_id`) → `employee_profiles` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_employees_password_hash_not_blank`: `(char_length(trim(password_hash)) > 0)`
- CHECK `chk_employees_role`: `(role in ('ADMIN','DIRECTOR','MANAGER','STAFF','KITCHEN','INVENTORY'))`
- CHECK `chk_employees_status`: `(status in ('ACTIVE','INACTIVE','LOCKED'))`
- CHECK `chk_employees_username_length`: `(char_length(username) between 4 and 30)`

### employee_profiles

Nguồn sự thật duy nhất về hồ sơ nhân sự (mã, tên, cơ sở chính, trạng thái làm việc); độc lập với thông tin đăng nhập tại `employees` (chuẩn 3NF NF-03).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã hồ sơ nhân sự, duy nhất. |
| `home_store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở công tác chính. |
| `full_name` | `varchar(100)` | Không | — | — | Họ tên nhân sự. |
| `employment_status` | `varchar(10)` | Không | `ACTIVE` | — | `ACTIVE` / `INACTIVE`, tách khỏi trạng thái khóa đăng nhập. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_employee_profiles_code` (`code`)
- FOREIGN KEY `fk_employee_profiles_store` (`home_store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_employee_profiles_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_employee_profiles_full_name_not_blank`: `(char_length(trim(full_name)) > 0)`
- CHECK `chk_employee_profiles_status`: `(employment_status in ('ACTIVE','INACTIVE'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_employee_profiles_store_status` (`home_store_id, employment_status`)

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
- FOREIGN KEY `fk_employee_assignments_employee` (`employee_id`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_employee_assignments_granter` (`granted_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_employee_assignments_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION

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
| `email` | `varchar(254)` | Có | — | UK | Email đăng ký/kích hoạt tài khoản; NULL với tài khoản cũ chưa xác minh, UNIQUE nếu có. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customers_code` (`code`)
- UNIQUE `uq_customers_email` (`email`)
- UNIQUE `uq_customers_phone` (`phone`)
- CHECK `chk_customers_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_customers_full_name_length`: `(char_length(trim(full_name)) between 2 and 100)`
- CHECK `chk_customers_phone_format`: `regexp_like(phone,'^0[0-9]{9}$','c')`
- CHECK `chk_customers_status`: `(status in ('ACTIVE','INACTIVE'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_customers_full_name` (`full_name`)

### customer_store_links

Phạm vi khách hàng tại từng cơ sở, suy ra từ giao dịch/phiên hoặc liên kết được xác minh tại quầy.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `customer_id` | `bigint unsigned` | Không | — | PK, FK → `customers.id` | Khách hàng; phần thứ nhất của khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | PK, FK → `stores.id` | Cơ sở liên quan; phần thứ hai của khóa chính. |
| `source` | `varchar(24)` | Không | — | — | Nguồn chứng minh liên kết, ví dụ `INVOICE`, `SESSION` hoặc đăng ký tại quầy. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm lập liên kết (UTC). |

Ràng buộc:

- PRIMARY KEY (`customer_id,store_id`)
- FOREIGN KEY `fk_customer_links_customer` (`customer_id`) → `customers` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_customer_links_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION

### accounts

Tài khoản đăng nhập máy trạm và ví tiền của khách; mỗi khách đúng một tài khoản.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã tài khoản, duy nhất (`ACC-` + hex). |
| `customer_id` | `bigint unsigned` | Không | — | UK, FK → `customers.id` | Khách sở hữu tài khoản; UNIQUE nên mỗi khách tối đa một tài khoản. |
| `username` | `varchar(30)` | Không | — | UK | Tên đăng nhập máy trạm, duy nhất, chữ/số/`_`/`.`, 4–30 ký tự. |
| `password_hash` | `varchar(255)` | Có | — | — | Mật khẩu đã băm bcrypt. |
| `balance` | `bigint` | Không | `0` | — | Số dư sổ cái (VND), có dấu để hỗ trợ dữ liệu nợ. Cảnh báo âm trong phiên dùng số dư dự kiến; checkout P0 phải bù đủ để số dư cuối không âm. Mọi thay đổi phải kèm `account_transactions`. |
| `status` | `varchar(20)` | Không | `ACTIVE` | — | `ACTIVE` / `LOCKED`. LOCKED không mở phiên được nhưng vẫn nạp tiền để trả nợ. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |
| `bonus_balance` | `bigint` | Không | `0` | — | Số dư khuyến mãi (VND), dùng trước, không quy đổi tiền mặt. Số dư chính `cash_balance` tính qua view `v_accounts`. |
| `auth_version` | `bigint unsigned` | Không | `0` | — | Phiên bản xác thực khách hàng; tăng khi đổi mật khẩu để thu hồi các phiên cũ. |
| `web_login_enabled` | `tinyint(1)` | Không | `1` | — | FALSE khi tài khoản đăng ký tại quầy chưa kích hoạt email; TRUE mới cho đăng nhập web. |
| `email_verified_at` | `datetime` | Có | — | — | Thời điểm email được xác minh khi kích hoạt (UTC); NULL nếu chưa xác minh. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_accounts_code` (`code`)
- UNIQUE `uq_accounts_customer` (`customer_id`)
- UNIQUE `uq_accounts_username` (`username`)
- FOREIGN KEY `fk_accounts_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_accounts_bonus_nonnegative`: `(bonus_balance >= 0)`
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

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_machines_store_active_status` (`store_id, is_active, status`)

### usage_sessions

Một lần khách dùng một máy, từ lúc mở đến lúc checkout; ràng buộc chiếm dụng đang hoạt động nằm tại `active_usage_sessions` (chuẩn 3NF).

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
- CHECK `chk_usage_sessions_state`: `(((status = 'ACTIVE') and (ended_at is null) and (cost is null)) or ((status = 'COMPLETED') and (ended_at is not null) and (cost is not null)) or ((status = 'CANCELLED') and (ended_at is not null)))`
- CHECK `chk_usage_sessions_status`: `(status in ('ACTIVE','COMPLETED','CANCELLED'))`
- CHECK `chk_usage_sessions_time_order`: `((ended_at is null) or (ended_at >= started_at))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_usage_sessions_customer_started_at` (`customer_id, started_at`)
- INDEX `idx_usage_sessions_machine_started_at` (`machine_id, started_at`)
- INDEX `idx_usage_sessions_status_started_at` (`status, started_at`)

### active_usage_sessions

Bảng chiếm dụng 3NF ghi nhận các phiên đang ACTIVE; UNIQUE trên `machine_id` và `customer_id` thay cột sinh để chặn mở trùng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `session_id` | `bigint unsigned` | Không | — | PK, FK → `usage_sessions.id` | Phiên đang ACTIVE; PK/FK tới `usage_sessions.id` (tự đồng bộ qua trigger khi mở/đóng phiên). |
| `machine_id` | `bigint unsigned` | Không | — | UK, FK → `machines.id` | Máy đang bị chiếm dụng; UNIQUE ⇒ mỗi máy tối đa một phiên ACTIVE. |
| `customer_id` | `bigint unsigned` | Không | — | UK, FK → `customers.id` | Khách đang chơi; UNIQUE ⇒ mỗi khách tối đa một phiên ACTIVE. |

Ràng buộc:

- PRIMARY KEY (`session_id`)
- UNIQUE `uq_active_usage_customer` (`customer_id`)
- UNIQUE `uq_active_usage_machine` (`machine_id`)
- FOREIGN KEY `fk_active_usage_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_active_usage_machine` (`machine_id`) → `machines` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_active_usage_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE CASCADE

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

Hóa đơn tạo khi checkout thành công; khóa ứng viên `session_id` (UNIQUE), tham chiếu phiên bản chính sách điểm bất biến (`loyalty_policy_versions`). Các giá trị dẫn xuất (`total_amount`, `loyalty_eligible_amount`, `loyalty_points`, `loyalty_unit`) tính qua view `v_invoices`.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã hóa đơn, duy nhất (`INV-` + hex). |
| `session_id` | `bigint unsigned` | Không | — | UK, FK → `usage_sessions.id` | Phiên được thanh toán; UNIQUE ⇒ mỗi phiên tối đa một hóa đơn. |
| `customer_id` | `bigint unsigned` | Không | — | FK → `customers.id` | Khách (khớp `usage_sessions.customer_id` nhờ trigger `trg_invoices_bi/bu`). |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên checkout. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cửa hàng (khớp `machines.store_id` của phiên nhờ trigger `trg_invoices_bi/bu`). |
| `usage_cost` | `bigint` | Không | — | — | Phí sử dụng (VND). Doanh thu ngày = tổng `usage_cost` của hóa đơn PAID. |
| `settlement_amount` | `bigint` | Không | `0` | — | Phần tiền bù thực ghi nhận, bằng đúng `settlement_required` khi checkout; không cộng lần nữa vào doanh thu. |
| `status` | `varchar(20)` | Không | `PAID` | — | `PAID` / `VOID`. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm checkout (UTC); báo cáo quy đổi sang giờ Việt Nam (UTC+7). |
| `bonus_used` | `bigint` | Không | `0` | — | Phần phí sử dụng trừ từ khuyến mãi, chụp tại checkout. |
| `loyalty_rule_version` | `int unsigned` | Không | `1` | FK → `loyalty_policy_versions.version` | FK tới `loyalty_policy_versions.version` chụp bất biến tại lúc lập hóa đơn. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_invoices_code` (`code`)
- UNIQUE `uq_invoices_session` (`session_id`)
- FOREIGN KEY `fk_invoices_customer` (`customer_id`) → `customers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_loyalty_version` (`loyalty_rule_version`) → `loyalty_policy_versions` (`version`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_session` (`session_id`) → `usage_sessions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_invoices_store` (`store_id`) → `stores` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_invoices_bonus_used`: `((bonus_used >= 0) and (bonus_used <= usage_cost))`
- CHECK `chk_invoices_code_not_blank`: `(char_length(trim(code)) > 0)`
- CHECK `chk_invoices_money`: `((usage_cost >= 0) and (settlement_amount >= 0))`
- CHECK `chk_invoices_settlement`: `(settlement_amount <= usage_cost)`
- CHECK `chk_invoices_status`: `(status in ('PAID','VOID'))`

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
- CHECK `chk_machine_room_type`: `(room_type in ('STANDARD','VIP','COUPLE','SUPER_VIP'))`

### loyalty_policy_versions

Phiên bản bất biến của chính sách tích điểm và xét hạng thành viên; hóa đơn lịch sử tham chiếu đúng version đã áp dụng (NF-01/NF-04).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `version` | `int unsigned` | Không | — | PK | Khóa chính — số phiên bản tăng dần (≥ 1). |
| `enabled` | `tinyint(1)` | Không | `1` | — | Bật/tắt tích điểm cho hóa đơn mới thuộc phiên bản này. |
| `unit_amount` | `bigint` | Không | `10000` | — | VND hợp lệ / 1 điểm, làm tròn xuống theo từng hóa đơn. |
| `silver_spend` | `bigint` | Không | `1000000` | — | Mốc chi tiêu hợp lệ hạng Bạc. |
| `gold_spend` | `bigint` | Không | `3000000` | — | Mốc chi tiêu hợp lệ hạng Vàng. |
| `platinum_spend` | `bigint` | Không | `5000000` | — | Mốc chi tiêu hợp lệ hạng Kim cương (mã PLATINUM). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm ban hành phiên bản (UTC). |

Ràng buộc:

- PRIMARY KEY (`version`)
- CHECK `chk_loyalty_ver_tiers`: `((silver_spend > 0) and (gold_spend > silver_spend) and (platinum_spend > gold_spend))`
- CHECK `chk_loyalty_ver_unit`: `((unit_amount > 0) and (unit_amount <= 100000000))`
- CHECK `chk_loyalty_ver_version`: `(version >= 1)`

### loyalty_settings

Con trỏ singleton (id=1) trỏ tới phiên bản chính sách tích điểm đang hiệu lực; chỉ Admin được cập nhật kèm khóa lạc quan theo version.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `tinyint unsigned` | Không | — | PK | Singleton id=1. |
| `current_version` | `int unsigned` | Không | — | FK → `loyalty_policy_versions.version` | FK tới `loyalty_policy_versions.version` đang áp dụng. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật con trỏ gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_loyalty_settings_version` (`current_version`) → `loyalty_policy_versions` (`version`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_loyalty_singleton`: `(id = 1)`

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

Món ăn/đồ uống của cơ sở; cơ sở suy ra từ `menu_categories.store_id` (NF-02), tên món duy nhất toàn cơ sở qua trigger `trg_menu_items_bi/bu`.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `category_id` | `bigint unsigned` | Không | — | FK → `menu_categories.id` | Nhóm món (xác định cơ sở bán món). |
| `name` | `varchar(80)` | Không | — | — | Tên món, duy nhất trong một cơ sở. |
| `description` | `varchar(200)` | Không | `` | — | Mô tả ngắn hiển thị cho khách. |
| `price` | `bigint` | Không | — | — | Giá bán (VND, 1.000–10.000.000); backend đọc lại khi khách đặt. |
| `sort_order` | `int` | Không | `0` | — | Thứ tự trong nhóm. |
| `is_visible` | `tinyint(1)` | Không | `1` | — | FALSE = ẩn khỏi menu khách. |
| `is_available` | `tinyint(1)` | Không | `1` | — | FALSE = hết món; khách không chọn/đặt được. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |
| `is_stock_tracked` | `tinyint(1)` | Không | `0` | — | TRUE = món dùng công thức kho và phải giữ chỗ nguyên liệu theo vòng đời đơn. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_items_category_name` (`category_id,name`)
- FOREIGN KEY `fk_menu_items_category` (`category_id`) → `menu_categories` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_items_name`: `(char_length(trim(name)) > 0)`
- CHECK `chk_menu_items_price`: `(price between 1000 and 10000000)`
- CHECK `chk_menu_items_sort`: `(sort_order between 0 and 9999)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_menu_items_category_sort` (`category_id, sort_order`)

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

Đơn POS đồ ăn/thức uống của khách đang chơi; cơ sở, máy và tài khoản suy ra từ `usage_sessions` (NF-02), đọc đầy đủ qua `v_menu_orders`.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã yêu cầu, duy nhất (`ORD-` + hex). |
| `session_id` | `bigint unsigned` | Không | — | FK → `usage_sessions.id` | Phiên ACTIVE lúc đặt (xác định khách, máy và cơ sở phục vụ). |
| `note` | `varchar(200)` | Không | `` | — | Ghi chú của khách (≤ 200 ký tự). |
| `total_amount` | `bigint` | Không | — | — | Tổng tiền theo giá chụp lúc đặt (VND). |
| `status` | `varchar(12)` | Không | `NEW` | — | `NEW` / `PREPARING` / `SERVED` / `PAID` / `CANCELLED` / `REFUNDED`. |
| `handled_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên tiếp nhận/phục vụ/hủy; NULL khi còn NEW. |
| `payment_method` | `varchar(10)` | Có | — | — | `CASH` / `TRANSFER` khi đã thanh toán (bắt buộc NOT NULL); NULL trước đó. |
| `paid_at` | `datetime` | Có | — | — | Thời điểm thanh toán tại quầy (UTC). |
| `paid_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên xác nhận thanh toán. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đặt (UTC). |
| `reservation_expires_at` | `datetime` | Có | — | — | Hạn giữ tồn cho đơn mới (UTC); tác vụ timeout dùng để giải phóng idempotent. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật trạng thái (UTC). |
| `cancel_reason` | `varchar(255)` | Có | — | — | Lý do hủy đơn; giữ được cả với đơn cũ chưa có ảnh chụp công thức. |

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

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_menu_orders_hold_expiry` (`status, reservation_expires_at, id`)
- INDEX `idx_menu_orders_paid_at` (`paid_at`)
- INDEX `idx_menu_orders_session` (`session_id, status, created_at`)
- INDEX `idx_menu_orders_status_created` (`status, created_at`)

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

### inventory_ingredients

Nguyên liệu tồn kho theo từng cửa hàng; lượng khả dụng bằng tồn thực tế trừ lượng đã giữ chỗ.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cửa hàng sở hữu nguyên liệu; cùng `id` tạo khóa tham chiếu ghép cho sổ kho. |
| `code` | `varchar(32)` | Không | — | — | Mã nguyên liệu duy nhất trong cửa hàng. |
| `name` | `varchar(100)` | Không | — | — | Tên nguyên liệu. |
| `unit` | `varchar(4)` | Không | — | — | Đơn vị nguyên tử: `g`, `ml` hoặc `each` (cái). |
| `on_hand` | `bigint` | Không | `0` | — | Lượng thực tế đang có, không âm. |
| `reserved` | `bigint` | Không | `0` | — | Lượng đã giữ cho đơn chưa tiêu thụ/hủy; không vượt `on_hand`. |
| `reorder_point` | `bigint` | Không | `0` | — | Ngưỡng cảnh báo sắp hết. |
| `is_active` | `tinyint(1)` | Không | `1` | — | FALSE = ngừng nhập/dùng mới nhưng vẫn giữ lịch sử kho. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_inventory_ingredients_store_code` (`store_id,code`)
- UNIQUE `uq_inventory_ingredients_store_id` (`store_id,id`)
- FOREIGN KEY `fk_inventory_ingredients_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_inventory_ingredients_balance`: `((on_hand >= 0) and (reserved >= 0) and (reserved <= on_hand) and (reorder_point >= 0))`
- CHECK `chk_inventory_ingredients_unit`: `(unit in ('g','ml','each'))`

### menu_item_recipes

Công thức hiện hành của món có theo dõi kho.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `item_id` | `bigint unsigned` | Không | — | PK, FK → `menu_items.id` | Món dùng nguyên liệu; phần thứ nhất của khóa chính. |
| `ingredient_id` | `bigint unsigned` | Không | — | PK, FK → `inventory_ingredients.id` | Nguyên liệu; phần thứ hai của khóa chính. |
| `quantity_per_unit` | `bigint` | Không | — | — | Lượng nguyên liệu cần cho một đơn vị món, phải lớn hơn 0. |

Ràng buộc:

- PRIMARY KEY (`item_id,ingredient_id`)
- FOREIGN KEY `fk_menu_item_recipes_ingredient` (`ingredient_id`) → `inventory_ingredients` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_menu_item_recipes_item` (`item_id`) → `menu_items` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_menu_item_recipes_quantity`: `(quantity_per_unit > 0)`

### menu_order_recipe_snapshots

Ảnh chụp nhu cầu nguyên liệu của từng dòng đơn, giúp đổi công thức sau này không làm sai giữ/xuất kho cũ.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `order_id` | `bigint unsigned` | Không | — | PK | Đơn chứa dòng món; thuộc khóa chính và FK ghép tới `menu_order_items`. |
| `item_id` | `bigint unsigned` | Không | — | PK | Món trong đơn; thuộc khóa chính và FK ghép tới `menu_order_items`. |
| `ingredient_id` | `bigint unsigned` | Không | — | PK, FK → `inventory_ingredients.id` | Nguyên liệu đã được chụp cho dòng món. |
| `quantity` | `bigint` | Không | — | — | Tổng lượng nguyên liệu cần cho số lượng món đã đặt, phải lớn hơn 0. |

Ràng buộc:

- PRIMARY KEY (`order_id,item_id,ingredient_id`)
- FOREIGN KEY `fk_menu_order_recipe_snapshots_ingredient` (`ingredient_id`) → `inventory_ingredients` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_menu_order_recipe_snapshots_line` (`order_id,item_id`) → `menu_order_items` (`order_id,item_id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_menu_order_recipe_snapshots_quantity`: `(quantity > 0)`

### inventory_movements

Sổ cái kho bất biến: nhập, giữ chỗ, hoàn giữ chỗ, tiêu thụ, hao hụt, trả và điều chỉnh; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `ingredient_id` | `bigint unsigned` | Không | — | FK → `inventory_ingredients.id` | Nguyên liệu bị thay đổi. |
| `order_id` | `bigint unsigned` | Có | — | FK → `menu_orders.id` | Đơn POS liên quan; NULL với nhập/kiểm kê độc lập. |
| `employee_id` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên thực hiện hoặc phê duyệt; NULL với tác vụ hệ thống. |
| `account_id` | `bigint unsigned` | Có | — | FK → `accounts.id` | Tài khoản khách liên quan; NULL nếu không gắn khách. |
| `kind` | `varchar(10)` | Không | — | — | `RECEIVE` / `RESERVE` / `RELEASE` / `CONSUME` / `WASTE` / `RETURN` / `ADJUST` / `ISSUE`. |
| `quantity` | `bigint` | Không | — | — | Độ lớn biến động theo đơn vị nguyên liệu, luôn dương. |
| `on_hand_delta` | `bigint` | Không | `0` | — | Biến động có dấu áp vào tồn thực tế. |
| `reserved_delta` | `bigint` | Không | `0` | — | Biến động có dấu áp vào lượng giữ chỗ. |
| `idempotency_key` | `varchar(100)` | Không | — | UK | Khóa duy nhất chống ghi trùng khi retry. |
| `reference_code` | `varchar(60)` | Có | — | — | Mã chứng từ/nguồn nghiệp vụ để đối soát. |
| `note` | `varchar(255)` | Có | — | — | Ghi chú nghiệp vụ, không chứa bí mật. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm ghi sổ (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_inventory_movements_key` (`idempotency_key`)
- FOREIGN KEY `fk_inventory_movements_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_inventory_movements_employee` (`employee_id`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_inventory_movements_ingredient` (`ingredient_id`) → `inventory_ingredients` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_inventory_movements_order` (`order_id`) → `menu_orders` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_inventory_movements_kind`: `(kind in ('RECEIVE','RESERVE','RELEASE','CONSUME','WASTE','RETURN','ADJUST','ISSUE'))`
- CHECK `chk_inventory_movements_quantity`: `(quantity > 0)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_inventory_movements_ingredient_id` (`ingredient_id, id`)
- INDEX `idx_inventory_movements_time` (`created_at, id`)

### inventory_counts

Phiếu kiểm kê đề xuất; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02), người phê duyệt bắt buộc khác `proposed_by` (CHECK SoD).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `ingredient_id` | `bigint unsigned` | Không | — | FK → `inventory_ingredients.id` | Nguyên liệu được kiểm kê. |
| `request_id` | `char(32)` | Không | — | UK | Khóa yêu cầu duy nhất để chống tạo phiếu trùng. |
| `expected_on_hand` | `bigint` | Không | — | — | Tồn thực tế hệ thống tại lúc đề xuất. |
| `expected_reserved` | `bigint` | Không | — | — | Lượng giữ chỗ hệ thống tại lúc đề xuất. |
| `expected_movement_id` | `bigint unsigned` | Không | — | — | Mốc sổ kho gần nhất dùng phát hiện dữ liệu đã thay đổi trước khi duyệt. |
| `counted_on_hand` | `bigint` | Không | — | — | Lượng thực đếm do người đề xuất nhập. |
| `proposed_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên đề xuất kiểm kê. |
| `decided_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên khác phê duyệt/từ chối; NULL khi đang chờ. |
| `status` | `varchar(10)` | Không | `PENDING` | — | `PENDING` / `APPROVED` / `REJECTED`. |
| `reason` | `varchar(255)` | Không | — | — | Lý do kiểm kê hoặc giải trình chênh lệch. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đề xuất (UTC). |
| `decided_at` | `datetime` | Có | — | — | Thời điểm quyết định (UTC); NULL khi PENDING. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_inventory_counts_request` (`request_id`)
- FOREIGN KEY `fk_inventory_counts_decider` (`decided_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_inventory_counts_ingredient` (`ingredient_id`) → `inventory_ingredients` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_inventory_counts_proposer` (`proposed_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_inventory_counts_decision`: `(((status = 'PENDING') and (decided_by is null) and (decided_at is null)) or ((status in ('APPROVED','REJECTED')) and (decided_by is not null) and (decided_at is not null) and (decided_by <> proposed_by) and (decided_at >= created_at)))`
- CHECK `chk_inventory_counts_quantities`: `((expected_on_hand >= 0) and (expected_reserved >= 0) and (counted_on_hand >= 0))`
- CHECK `chk_inventory_counts_status`: `(status in ('PENDING','APPROVED','REJECTED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_inventory_counts_status` (`status, created_at, id`)

### customer_notification_events

Sổ sự kiện thông báo bền vững cho khách theo vòng đời đơn; khóa sự kiện chống phát trùng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `notification_key` | `varchar(100)` | Không | — | UK | Khóa idempotency duy nhất, phân biệt hoa/thường. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản khách nhận thông báo. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cửa hàng phát sinh thông báo. |
| `kind` | `varchar(40)` | Không | — | — | Loại sự kiện vòng đời đơn, ví dụ tiếp nhận, chuẩn bị, phục vụ, thanh toán hoặc hết món. |
| `code` | `varchar(20)` | Không | — | — | Mã đối tượng hiển thị cho khách, thường là mã đơn. |
| `amount` | `int unsigned` | Không | `0` | — | Số tiền liên quan để hiển thị; 0 nếu sự kiện không có tiền. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo sự kiện (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customer_notification_event_key` (`notification_key`)
- FOREIGN KEY `fk_customer_notification_event_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_customer_notification_event_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_customer_notification_account_created` (`account_id, created_at, id`)

### pos_order_reversals

Yêu cầu hoàn/hủy toàn bộ đơn POS có maker-checker và quyết định hoàn kho hoặc ghi hao hụt; cơ sở suy ra từ `menu_orders` qua `usage_sessions`→`machines` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `order_id` | `bigint unsigned` | Không | — | UK, FK → `menu_orders.id` | Đơn POS; UNIQUE nên mỗi đơn có tối đa một yêu cầu hoàn/hủy. |
| `requested_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên đề nghị. |
| `reason` | `varchar(255)` | Không | — | — | Lý do bắt buộc. |
| `disposition` | `varchar(8)` | Không | — | — | `RESTOCK` hoặc `WASTE`. |
| `status` | `varchar(10)` | Không | `PENDING` | — | `PENDING` / `APPROVED` / `REJECTED`. |
| `decided_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Quản lý quyết định (khác `requested_by`); NULL khi đang chờ. |
| `decided_at` | `datetime` | Có | — | — | Thời điểm quyết định (UTC). |
| `refund_amount` | `bigint unsigned` | Không | `0` | — | Số tiền hoàn VND. |
| `refund_method` | `varchar(10)` | Có | — | — | `CASH` / `TRANSFER`. |
| `refund_reference` | `varchar(100)` | Có | — | — | Tham chiếu giao dịch hoàn. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_pos_reversal_order` (`order_id`)
- FOREIGN KEY `fk_pos_reversal_approver` (`decided_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_pos_reversal_order` (`order_id`) → `menu_orders` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_pos_reversal_requester` (`requested_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_pos_reversal_decision`: `(((status = 'PENDING') and (decided_by is null) and (decided_at is null)) or ((status <> 'PENDING') and (decided_by is not null) and (decided_at is not null)))`
- CHECK `chk_pos_reversal_disposition`: `(disposition in ('RESTOCK','WASTE'))`
- CHECK `chk_pos_reversal_method`: `((refund_method is null) or (refund_method in ('CASH','TRANSFER')))`
- CHECK `chk_pos_reversal_refund`: `(((status <> 'APPROVED') and (refund_amount = 0) and (refund_method is null) and (refund_reference is null)) or ((status = 'APPROVED') and (refund_amount = 0) and (refund_method is null) and (refund_reference is null)) or ((status = 'APPROVED') and (refund_amount > 0) and (refund_method is not null) and (refund_method in ('CASH','TRANSFER'))))`
- CHECK `chk_pos_reversal_sod`: `((decided_by is null) or (decided_by <> requested_by))`
- CHECK `chk_pos_reversal_status`: `(status in ('PENDING','APPROVED','REJECTED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_pos_reversal_status` (`status, id`)

### menu_promotions

Chính sách khuyến mãi POS hiện hành theo cơ sở; mỗi lần lưu tạo một phiên bản bất biến tại `menu_promotion_versions` (NF-04).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở áp dụng. |
| `code` | `varchar(30)` | Không | — | — | Mã duy nhất trong cơ sở. |
| `kind` | `varchar(16)` | Không | — | — | `BOGO` / `PLAY_DRINK` / `TIER_PERCENT`. |
| `item_id` | `bigint unsigned` | Có | — | FK → `menu_items.id` | Món áp dụng (cùng cơ sở nhờ trigger); NULL khi ưu đãi không gắn một món. |
| `value` | `int unsigned` | Không | — | — | Giá trị cấu hình theo loại ưu đãi. |
| `minimum_tier` | `varchar(12)` | Có | — | — | Hạng tối thiểu nếu có. |
| `starts_at` | `datetime` | Không | — | — | Bắt đầu hiệu lực (UTC). |
| `ends_at` | `datetime` | Không | — | — | Kết thúc hiệu lực (UTC). |
| `is_active` | `tinyint(1)` | Không | `0` | — | Bật/tắt chính sách. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_promo_store_code` (`store_id,code`)
- FOREIGN KEY `fk_menu_promo_item` (`item_id`) → `menu_items` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_menu_promo_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_menu_promo_kind`: `(kind in ('BOGO','PLAY_DRINK','TIER_PERCENT'))`
- CHECK `chk_menu_promo_period`: `(starts_at < ends_at)`
- CHECK `chk_menu_promo_tier`: `((minimum_tier is null) or (minimum_tier in ('BRONZE','SILVER','GOLD','PLATINUM')))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_menu_promo_active` (`store_id, is_active, starts_at, ends_at`)

### menu_promotion_versions

Phiên bản bất biến của chính sách khuyến mãi POS để hóa đơn/đơn hàng lịch sử tham chiếu đúng quy tắc đã áp dụng (NF-04).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `promotion_id` | `bigint unsigned` | Không | — | FK → `menu_promotions.id` | Chính sách khuyến mãi cha. |
| `version` | `int unsigned` | Không | — | — | Số phiên bản tăng dần (≥ 1); cùng `promotion_id` là UNIQUE. |
| `code` | `varchar(30)` | Không | — | — | Mã khuyến mãi chụp tại phiên bản. |
| `kind` | `varchar(16)` | Không | — | — | Loại ưu đãi chụp tại phiên bản. |
| `item_id` | `bigint unsigned` | Có | — | FK → `menu_items.id` | Món áp dụng chụp tại phiên bản; NULL nếu không gắn món. |
| `value` | `int unsigned` | Không | — | — | Giá trị ưu đãi chụp tại phiên bản. |
| `minimum_tier` | `varchar(12)` | Có | — | — | Hạng tối thiểu chụp tại phiên bản. |
| `starts_at` | `datetime` | Không | — | — | Bắt đầu hiệu lực (UTC). |
| `ends_at` | `datetime` | Không | — | — | Kết thúc hiệu lực (UTC). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo phiên bản (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_menu_promo_ver` (`promotion_id,version`)
- FOREIGN KEY `fk_menu_promo_ver_item` (`item_id`) → `menu_items` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_promo_ver_promo` (`promotion_id`) → `menu_promotions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_promo_ver_kind`: `(kind in ('BOGO','PLAY_DRINK','TIER_PERCENT'))`
- CHECK `chk_menu_promo_ver_period`: `(starts_at < ends_at)`
- CHECK `chk_menu_promo_ver_tier`: `((minimum_tier is null) or (minimum_tier in ('BRONZE','SILVER','GOLD','PLATINUM')))`
- CHECK `chk_menu_promo_ver_version`: `(version >= 1)`

### menu_order_pricing

Kết quả định giá POS dạng cấu trúc chuẩn 3NF (không còn `snapshot_json` hay cột dẫn xuất `final_amount`, đọc qua `v_menu_order_pricing`).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `order_id` | `bigint unsigned` | Không | — | PK, FK → `menu_orders.id` | Đơn POS; khóa chính/FK. |
| `promotion_version_id` | `bigint unsigned` | Có | — | FK → `menu_promotion_versions.id` | Phiên bản khuyến mãi bất biến đã chọn; NULL nếu không áp dụng. |
| `applied_source` | `varchar(12)` | Không | `NONE` | — | Nguồn ưu đãi đang hiệu lực: `NONE` / `PROMOTION` / `VOUCHER`. |
| `member_tier` | `varchar(12)` | Không | `BRONZE` | — | Hạng thành viên tại lúc đặt đơn (`BRONZE` / `SILVER` / `GOLD` / `PLATINUM`). |
| `discount_amount` | `bigint unsigned` | Không | `0` | — | Số tiền giảm từ khuyến mãi POS (VND). |
| `voucher_id` | `bigint unsigned` | Có | — | FK → `customer_vouchers.id` | Voucher đồ ăn/đồ uống đã áp nếu có. |
| `voucher_discount_amount` | `bigint unsigned` | Không | `0` | — | Số tiền giảm từ voucher (VND). |

Ràng buộc:

- PRIMARY KEY (`order_id`)
- FOREIGN KEY `fk_menu_pricing_order` (`order_id`) → `menu_orders` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_menu_pricing_promo_version` (`promotion_version_id`) → `menu_promotion_versions` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_menu_pricing_voucher` (`voucher_id`) → `customer_vouchers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_menu_pricing_promo_consistency`: `(((promotion_version_id is null) and (discount_amount = 0)) or (promotion_version_id is not null))`
- CHECK `chk_menu_pricing_source`: `(applied_source in ('NONE','PROMOTION','VOUCHER'))`
- CHECK `chk_menu_pricing_tier`: `(member_tier in ('BRONZE','SILVER','GOLD','PLATINUM'))`
- CHECK `chk_menu_pricing_voucher_consistency`: `(((voucher_id is null) and (voucher_discount_amount = 0)) or ((voucher_id is not null) and (voucher_discount_amount > 0)))`

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
- CHECK `chk_customer_vouchers_revoked`: `(((status = 'REVOKED') and (revoked_reason is not null) and (char_length(trim(revoked_reason)) > 0)) or ((status <> 'REVOKED') and (revoked_reason is null)))`
- CHECK `chk_customer_vouchers_source`: `(source in ('MANUAL','GAME','AD'))`
- CHECK `chk_customer_vouchers_status`: `(status in ('ISSUED','USED','REVOKED'))`
- CHECK `chk_customer_vouchers_type`: `(reward_type in ('FOOD_DISCOUNT','FREE_DRINK','PLAYTIME_CREDIT','MEMBER_POINTS'))`
- CHECK `chk_customer_vouchers_used`: `(((status = 'USED') and (used_at is not null) and (used_by is not null) and (used_store_id is not null)) or ((status <> 'USED') and (used_at is null) and (used_by is null) and (used_store_id is null) and (used_order_id is null)))`
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

### games

Cấu hình trò chơi (giai đoạn đầu: vòng quay may mắn), dùng chung mọi cơ sở.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã game, duy nhất (`LUCKY_WHEEL`). |
| `name` | `varchar(60)` | Không | — | — | Tên hiển thị. |
| `is_active` | `tinyint(1)` | Không | `1` | — | FALSE = tạm dừng, không quay được. |
| `daily_limit` | `int` | Không | — | — | Số lượt mỗi tài khoản mỗi ngày (giờ Việt Nam). |
| `min_interval_seconds` | `int` | Không | — | — | Khoảng cách tối thiểu giữa hai lượt; nhanh hơn bị tính là bất thường. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm sửa gần nhất (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_games_code` (`code`)
- CHECK `chk_games_daily_limit`: `(daily_limit between 1 and 20)`
- CHECK `chk_games_interval`: `(min_interval_seconds between 1 and 60)`

### game_prizes

Các ô thưởng trên vòng quay và tỉ lệ trúng tương đối.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `game_id` | `bigint unsigned` | Không | — | FK → `games.id` | Game sở hữu ô thưởng. |
| `sort_order` | `int` | Không | — | — | Vị trí ô trên vòng quay (0, 1, ...). |
| `label` | `varchar(40)` | Không | — | — | Nhãn hiển thị. |
| `coins` | `int` | Không | — | — | Số xu nhận được (0 = chúc may mắn). |
| `weight` | `int` | Không | — | — | Trọng số; xác suất = weight / tổng weight. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_game_prizes_slot` (`game_id,sort_order`)
- FOREIGN KEY `fk_game_prizes_game` (`game_id`) → `games` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_game_prizes_coins`: `(coins between 0 and 1000)`
- CHECK `chk_game_prizes_label`: `(char_length(trim(label)) > 0)`
- CHECK `chk_game_prizes_weight`: `(weight between 1 and 1000)`

### game_wallets

Ví xu game của tài khoản; xu không phải tiền và không phải điểm thành viên.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `account_id` | `bigint unsigned` | Không | — | PK, FK → `accounts.id` | Tài khoản khách; PK/FK. |
| `balance` | `bigint` | Không | `0` | — | Số xu hiện có (≥ 0). |
| `is_locked` | `tinyint(1)` | Không | `0` | — | TRUE = tạm khóa quay/đổi thưởng. |
| `locked_reason` | `varchar(200)` | Có | — | — | Lý do khóa (tự động hoặc quản lý). |
| `locked_at` | `datetime` | Có | — | — | Thời điểm khóa (UTC). |
| `suspicious_count` | `int` | Không | `0` | — | Số lần bị chặn (hết lượt/quá nhanh) trong ngày. |
| `suspicious_on` | `date` | Có | — | — | Ngày (giờ Việt Nam) của bộ đếm bất thường. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật (UTC). |

Ràng buộc:

- PRIMARY KEY (`account_id`)
- FOREIGN KEY `fk_game_wallets_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_game_wallets_balance`: `(balance >= 0)`
- CHECK `chk_game_wallets_lock`: `(((is_locked = true) and (locked_reason is not null) and (locked_at is not null)) or ((is_locked = false) and (locked_reason is null) and (locked_at is null)))`

### game_sessions

Lịch sử từng lượt quay; kết quả do máy chủ bốc thăm và được chụp lại.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản chơi. |
| `game_id` | `bigint unsigned` | Không | — | FK → `games.id` | Game. |
| `prize_index` | `int` | Không | — | — | Ô trúng (chụp). |
| `prize_label` | `varchar(40)` | Không | — | — | Nhãn ô trúng (chụp). |
| `coins` | `int` | Không | — | — | Xu nhận được (chụp). |
| `played_on` | `date` | Không | — | — | Ngày chơi theo giờ Việt Nam, dùng đếm lượt. |
| `created_at` | `datetime` | Không | — | — | Thời điểm quay (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_game_sessions_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_game_sessions_game` (`game_id`) → `games` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_game_sessions_coins`: `(coins between 0 and 1000)`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_game_sessions_account_day` (`account_id, played_on`)
- INDEX `idx_game_sessions_game_time` (`game_id, created_at`)

### game_coin_ledger

Sổ cái xu: mọi thay đổi số dư xu có đúng một dòng; chỉ thêm.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản. |
| `delta` | `bigint` | Không | — | — | Số xu cộng (+) hoặc trừ (−), khác 0. |
| `reason` | `varchar(10)` | Không | — | — | `PLAY` / `REDEEM` / `AD` / `ADJUST`. |
| `ref` | `varchar(64)` | Không | — | — | Tham chiếu duy nhất theo `reason` (vd. `session:12`, khóa yêu cầu đổi thưởng). |
| `balance_after` | `bigint` | Không | — | — | Số dư xu sau thay đổi (≥ 0). |
| `voucher_id` | `bigint unsigned` | Có | — | FK → `customer_vouchers.id` | Voucher nhận được khi đổi xu. |
| `created_at` | `datetime` | Không | — | — | Thời điểm (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_game_coin_ledger_ref` (`reason,ref`)
- FOREIGN KEY `fk_game_coin_ledger_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_game_coin_ledger_voucher` (`voucher_id`) → `customer_vouchers` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_game_coin_ledger_balance`: `(balance_after >= 0)`
- CHECK `chk_game_coin_ledger_delta`: `(delta <> 0)`
- CHECK `chk_game_coin_ledger_reason`: `(reason in ('PLAY','REDEEM','AD','ADJUST'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_game_coin_ledger_account` (`account_id, created_at`)

### ad_settings

Cấu hình chương trình quảng cáo nhận thưởng (một dòng duy nhất).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `tinyint unsigned` | Không | — | PK | Luôn bằng 1. |
| `enabled` | `tinyint(1)` | Không | `1` | — | Bật/tắt chương trình. |
| `mode` | `varchar(10)` | Không | `HOUSE` | — | `HOUSE` (quảng cáo nội bộ, máy chủ đo thời lượng) / `NETWORK` (callback có chữ ký HMAC). |
| `daily_cap` | `int` | Không | `3` | — | Số lần nhận thưởng tối đa mỗi tài khoản mỗi ngày. |
| `reward_type` | `varchar(12)` | Không | `EXTRA_SPIN` | — | `EXTRA_SPIN` (thêm lượt quay) / `COINS` (xu game). |
| `reward_amount` | `int` | Không | `1` | — | Số lượt (1–3) hoặc số xu (1–100) mỗi lần. |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- CHECK `chk_ad_settings_cap`: `(daily_cap between 1 and 10)`
- CHECK `chk_ad_settings_mode`: `(mode in ('HOUSE','NETWORK'))`
- CHECK `chk_ad_settings_reward`: `(((reward_type = 'EXTRA_SPIN') and (reward_amount between 1 and 3)) or ((reward_type = 'COINS') and (reward_amount between 1 and 100)))`
- CHECK `chk_ad_settings_singleton`: `(id = 1)`

### ad_creatives

Nội dung quảng cáo nội bộ do CyberHub tự soạn.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(20)` | Không | — | UK | Mã nội dung, duy nhất. |
| `title` | `varchar(80)` | Không | — | — | Tiêu đề. |
| `body` | `varchar(300)` | Không | — | — | Nội dung hiển thị. |
| `cta` | `varchar(40)` | Không | `` | — | Lời kêu gọi hành động. |
| `duration_seconds` | `int` | Không | — | — | Thời lượng phải xem (5–60 giây). |
| `is_active` | `tinyint(1)` | Không | `1` | — | FALSE = không phát. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_ad_creatives_code` (`code`)
- CHECK `chk_ad_creatives_duration`: `(duration_seconds between 5 and 60)`
- CHECK `chk_ad_creatives_title`: `(char_length(trim(title)) > 0)`

### ad_reward_events

Mỗi lần bắt đầu xem quảng cáo; token dùng một lần, độc lập với kết quả game.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `token` | `char(32)` | Không | — | UK | Token ngẫu nhiên do máy chủ cấp; UNIQUE, chỉ dùng một lần. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản xem. |
| `creative_id` | `bigint unsigned` | Có | — | FK → `ad_creatives.id` | Nội dung đã phát. |
| `provider` | `varchar(10)` | Không | — | — | `HOUSE` / `NETWORK`. |
| `reward_type` | `varchar(12)` | Không | — | — | Loại thưởng (chụp từ cấu hình). |
| `reward_amount` | `int` | Không | — | — | Số lượng thưởng (chụp). |
| `status` | `varchar(10)` | Không | `ISSUED` | — | `ISSUED` / `COMPLETED` / `REJECTED`; hết hạn suy ra từ `expires_at`. |
| `played_on` | `date` | Không | — | — | Ngày theo giờ Việt Nam, dùng giới hạn mỗi ngày. |
| `issued_at` | `datetime` | Không | — | — | Thời điểm cấp token (UTC). |
| `min_complete_at` | `datetime` | Không | — | — | Sớm nhất được nhận thưởng = bắt đầu + thời lượng (UTC). |
| `expires_at` | `datetime` | Không | — | — | Hạn token (UTC). |
| `completed_at` | `datetime` | Có | — | — | Thời điểm hoàn thành hợp lệ (UTC). |
| `provider_txn_id` | `varchar(80)` | Có | — | UK | Mã giao dịch của mạng quảng cáo; UNIQUE chống gửi lại. |
| `reject_reason` | `varchar(40)` | Có | — | — | `TOO_EARLY` / `EXPIRED` / `CAP` / `LOCKED` / `SUPERSEDED`. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_ad_reward_events_token` (`token`)
- UNIQUE `uq_ad_reward_events_txn` (`provider_txn_id`)
- FOREIGN KEY `fk_ad_reward_events_account` (`account_id`) → `accounts` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_ad_reward_events_creative` (`creative_id`) → `ad_creatives` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- CHECK `chk_ad_reward_events_done`: `(((status = 'COMPLETED') and (completed_at is not null) and (reject_reason is null)) or ((status = 'REJECTED') and (reject_reason is not null)) or ((status = 'ISSUED') and (completed_at is null)))`
- CHECK `chk_ad_reward_events_period`: `((min_complete_at >= issued_at) and (expires_at > min_complete_at))`
- CHECK `chk_ad_reward_events_provider`: `(provider in ('HOUSE','NETWORK'))`
- CHECK `chk_ad_reward_events_reward`: `((reward_type in ('EXTRA_SPIN','COINS')) and (reward_amount > 0))`
- CHECK `chk_ad_reward_events_status`: `(status in ('ISSUED','COMPLETED','REJECTED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_ad_reward_events_account_day` (`account_id, played_on, status`)
- INDEX `idx_ad_reward_events_day` (`played_on`)

### cash_shifts

Ca làm việc và đối chiếu két tiền của một nhân viên tại một cơ sở; chênh lệch `variance` tính qua `v_cash_shifts`, chiếm dụng ca mở nằm tại `active_employee_shifts`.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(24)` | Không | — | UK | Mã ca duy nhất. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở mở ca. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên chịu trách nhiệm ca. |
| `status` | `varchar(16)` | Không | `OPEN` | — | `OPEN` / `PENDING_REVIEW` / `CLOSED`. |
| `opening_cash` | `bigint unsigned` | Không | — | — | Tiền mặt đầu ca. |
| `expected_cash` | `bigint unsigned` | Có | — | — | Tiền mặt hệ thống tính cuối ca. |
| `counted_cash` | `bigint unsigned` | Có | — | — | Tiền mặt thực đếm cuối ca. |
| `opened_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm mở ca (UTC). |
| `submitted_at` | `datetime` | Có | — | — | Thời điểm nhân viên nộp đối chiếu (UTC). |
| `closed_at` | `datetime` | Có | — | — | Thời điểm đóng ca (UTC). |
| `reviewed_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Quản lý duyệt chênh lệch (khác `employee_id`). |
| `review_note` | `varchar(255)` | Có | — | — | Ghi chú duyệt. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_cash_shifts_code` (`code`)
- FOREIGN KEY `fk_cash_shifts_employee` (`employee_id`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_cash_shifts_reviewer` (`reviewed_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_cash_shifts_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_cash_shifts_close`: `((((status = 'OPEN') and (expected_cash is null) and (counted_cash is null) and (submitted_at is null) and (closed_at is null) and (reviewed_by is null) and (review_note is null)) or ((status = 'PENDING_REVIEW') and (expected_cash is not null) and (counted_cash is not null) and (submitted_at is not null) and (closed_at is null) and (reviewed_by is null)) or ((status = 'CLOSED') and (expected_cash is not null) and (counted_cash is not null) and (submitted_at is not null) and (closed_at is not null) and (((reviewed_by is null) and (review_note is null)) or ((reviewed_by is not null) and (reviewed_by <> employee_id) and (review_note is not null) and (char_length(trim(review_note)) > 0))))) and ((submitted_at is null) or (submitted_at >= opened_at)) and ((closed_at is null) or ((submitted_at is not null) and (closed_at >= submitted_at))))`
- CHECK `chk_cash_shifts_status`: `(status in ('OPEN','PENDING_REVIEW','CLOSED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_cash_shifts_store_time` (`store_id, opened_at, id`)

### active_employee_shifts

Bảng chiếm dụng 3NF bảo đảm mỗi nhân viên chỉ có tối đa một ca `OPEN`/`PENDING_REVIEW` cùng lúc (thay cột sinh `active_employee_id`).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `shift_id` | `bigint unsigned` | Không | — | PK, FK → `cash_shifts.id` | Ca đang mở hoặc chờ duyệt; PK/FK tới `cash_shifts.id` (tự đồng bộ qua trigger). |
| `employee_id` | `bigint unsigned` | Không | — | UK, FK → `employees.id` | Nhân viên đang mở ca; UNIQUE ⇒ không thể mở đồng thời hai ca. |

Ràng buộc:

- PRIMARY KEY (`shift_id`)
- UNIQUE `uq_active_shift_employee` (`employee_id`)
- FOREIGN KEY `fk_active_shift_employee` (`employee_id`) → `employees` (`id`) ON UPDATE RESTRICT ON DELETE RESTRICT
- FOREIGN KEY `fk_active_shift_shift` (`shift_id`) → `cash_shifts` (`id`) ON UPDATE RESTRICT ON DELETE CASCADE

### cash_shift_entries

Sổ bất biến thu, chi, hoàn và điều chỉnh theo ca; cơ sở suy ra từ `cash_shifts.store_id` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `shift_id` | `bigint unsigned` | Không | — | FK → `cash_shifts.id` | Ca sở hữu bút toán. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên ghi nhận. |
| `kind` | `varchar(12)` | Không | — | — | `RECEIPT` / `EXPENSE` / `REFUND` / `ADJUSTMENT_IN` / `ADJUSTMENT_OUT`. |
| `payment_method` | `varchar(10)` | Không | — | — | `CASH` / `TRANSFER`. |
| `amount` | `bigint unsigned` | Không | — | — | Số tiền dương (VND). |
| `source_type` | `varchar(24)` | Không | — | — | Loại chứng từ nguồn. |
| `source_id` | `varchar(64)` | Không | — | — | Mã nguồn; kết hợp phương thức thanh toán để chống ghi trùng. |
| `note` | `varchar(255)` | Không | `` | — | Ghi chú nghiệp vụ. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm ghi sổ (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_cash_shift_entries_source` (`source_type,source_id,payment_method`)
- FOREIGN KEY `fk_cash_entries_employee` (`employee_id`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_cash_entries_shift` (`shift_id`) → `cash_shifts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_cash_entries_amount`: `(amount > 0)`
- CHECK `chk_cash_entries_kind`: `(kind in ('RECEIPT','EXPENSE','REFUND','ADJUSTMENT_IN','ADJUSTMENT_OUT'))`
- CHECK `chk_cash_entries_method`: `(payment_method in ('CASH','TRANSFER'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_cash_entries_shift_time` (`shift_id, created_at, id`)

### machine_incidents

Phiếu sự cố và vòng đời bảo trì máy từ báo lỗi đến nghiệm thu; cơ sở suy ra từ `machines.store_id` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(24)` | Không | — | UK | Mã sự cố duy nhất. |
| `machine_id` | `bigint unsigned` | Không | — | FK → `machines.id` | Máy gặp sự cố. |
| `reported_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Người báo lỗi. |
| `assigned_to` | `bigint unsigned` | Có | — | FK → `employees.id` | Người được phân công; có thể NULL trước khi phân công. |
| `severity` | `varchar(10)` | Không | — | — | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`. |
| `status` | `varchar(20)` | Không | `REPORTED` | — | `REPORTED` / `ASSIGNED` / `IN_PROGRESS` / `WAITING_PARTS` / `COMPLETED` / `VERIFIED` / `CANCELLED`. |
| `title` | `varchar(120)` | Không | — | — | Tiêu đề ngắn. |
| `description` | `varchar(1000)` | Không | — | — | Mô tả lỗi. |
| `resolution` | `varchar(1000)` | Có | — | — | Kết quả xử lý. |
| `labor_cost` | `bigint unsigned` | Không | `0` | — | Chi phí nhân công. |
| `parts_cost` | `bigint unsigned` | Không | `0` | — | Chi phí linh kiện. |
| `reported_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm báo (UTC). |
| `started_at` | `datetime` | Có | — | — | Thời điểm bắt đầu sửa (UTC). |
| `completed_at` | `datetime` | Có | — | — | Thời điểm hoàn thành sửa (UTC). |
| `verified_at` | `datetime` | Có | — | — | Thời điểm nghiệm thu (UTC). |
| `verified_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Người nghiệm thu (khác `assigned_to`). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_machine_incidents_code` (`code`)
- FOREIGN KEY `fk_incidents_assignee` (`assigned_to`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_incidents_machine` (`machine_id`) → `machines` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_incidents_reporter` (`reported_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_incidents_verifier` (`verified_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_incidents_cost`: `((labor_cost <= 1000000000) and (parts_cost <= 1000000000))`
- CHECK `chk_incidents_lifecycle`: `((((status = 'REPORTED') and (started_at is null) and (completed_at is null) and (verified_at is null) and (verified_by is null)) or ((status = 'ASSIGNED') and (assigned_to is not null) and (completed_at is null) and (verified_at is null) and (verified_by is null)) or ((status = 'IN_PROGRESS') and (started_at is not null) and (completed_at is null) and (verified_at is null) and (verified_by is null)) or ((status = 'WAITING_PARTS') and (completed_at is null) and (verified_at is null) and (verified_by is null)) or ((status = 'COMPLETED') and (completed_at is not null) and (resolution is not null) and (char_length(trim(resolution)) > 0) and (verified_at is null) and (verified_by is null)) or ((status = 'VERIFIED') and (completed_at is not null) and (resolution is not null) and (char_length(trim(resolution)) > 0) and (verified_at is not null) and (verified_by is not null) and ((assigned_to is null) or (verified_by <> assigned_to))) or ((status = 'CANCELLED') and (verified_at is null) and (verified_by is null))) and ((started_at is null) or (started_at >= reported_at)) and ((completed_at is null) or (completed_at >= reported_at)) and ((verified_at is null) or ((completed_at is not null) and (verified_at >= completed_at))))`
- CHECK `chk_incidents_severity`: `(severity in ('LOW','MEDIUM','HIGH','CRITICAL'))`
- CHECK `chk_incidents_status`: `(status in ('REPORTED','ASSIGNED','IN_PROGRESS','WAITING_PARTS','COMPLETED','VERIFIED','CANCELLED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_incidents_machine_history` (`machine_id, reported_at, id`)
- INDEX `idx_incidents_status_time` (`status, reported_at, id`)

### machine_incident_parts

Linh kiện sử dụng cho một phiếu sửa máy.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `incident_id` | `bigint unsigned` | Không | — | FK → `machine_incidents.id` | Phiếu sự cố. |
| `name` | `varchar(120)` | Không | — | — | Tên linh kiện. |
| `quantity` | `int unsigned` | Không | — | — | Số lượng. |
| `unit_cost` | `bigint unsigned` | Không | — | — | Đơn giá VND. |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_incident_parts_incident` (`incident_id`) → `machine_incidents` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_incident_parts_cost`: `(unit_cost <= 1000000000)`
- CHECK `chk_incident_parts_quantity`: `(quantity between 1 and 1000)`

### machine_incident_events

Lịch sử chuyển trạng thái sự cố máy, chỉ thêm.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `incident_id` | `bigint unsigned` | Không | — | FK → `machine_incidents.id` | Phiếu sự cố. |
| `employee_id` | `bigint unsigned` | Không | — | FK → `employees.id` | Người thực hiện. |
| `from_status` | `varchar(20)` | Có | — | — | Trạng thái trước; NULL ở sự kiện đầu. |
| `to_status` | `varchar(20)` | Không | — | — | Trạng thái sau. |
| `note` | `varchar(500)` | Không | `` | — | Ghi chú chuyển trạng thái. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_incident_events_employee` (`employee_id`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_incident_events_incident` (`incident_id`) → `machine_incidents` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_incident_events_history` (`incident_id, created_at, id`)

### suppliers

Nhà cung cấp theo cơ sở và điều khoản thanh toán.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở quản lý nhà cung cấp. |
| `code` | `varchar(24)` | Không | — | — | Mã duy nhất trong cơ sở. |
| `name` | `varchar(120)` | Không | — | — | Tên nhà cung cấp. |
| `phone` | `varchar(20)` | Có | — | — | Số điện thoại. |
| `email` | `varchar(120)` | Có | — | — | Email liên hệ. |
| `address` | `varchar(255)` | Có | — | — | Địa chỉ. |
| `payment_terms_days` | `int unsigned` | Không | `0` | — | Số ngày công nợ. |
| `is_active` | `tinyint(1)` | Không | `1` | — | FALSE khi ngừng giao dịch mới. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_suppliers_store_code` (`store_id,code`)
- FOREIGN KEY `fk_suppliers_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_suppliers_terms`: `(payment_terms_days <= 365)`

### purchase_requests

Đề nghị nhập hàng có người lập và người quyết định (tách nhiệm vụ `decided_by <> requested_by`).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(24)` | Không | — | UK | Mã đề nghị duy nhất. |
| `store_id` | `bigint unsigned` | Không | — | FK → `stores.id` | Cơ sở đề nghị. |
| `requested_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Người lập. |
| `status` | `varchar(12)` | Không | `PENDING` | — | `PENDING` / `APPROVED` / `REJECTED` / `ORDERED`. |
| `reason` | `varchar(255)` | Không | — | — | Lý do nhập. |
| `decided_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Người duyệt/từ chối. |
| `decided_at` | `datetime` | Có | — | — | Thời điểm quyết định (UTC). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_purchase_requests_code` (`code`)
- FOREIGN KEY `fk_purchase_requests_decider` (`decided_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_purchase_requests_requester` (`requested_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_purchase_requests_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_purchase_requests_decision`: `(((status = 'PENDING') and (decided_by is null) and (decided_at is null)) or ((status <> 'PENDING') and (decided_by is not null) and (decided_at is not null)))`
- CHECK `chk_purchase_requests_sod`: `((decided_by is null) or (decided_by <> requested_by))`
- CHECK `chk_purchase_requests_status`: `(status in ('PENDING','APPROVED','REJECTED','ORDERED'))`

### purchase_request_lines

Nguyên liệu và số lượng trong đề nghị nhập.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `request_id` | `bigint unsigned` | Không | — | PK, FK → `purchase_requests.id` | Đề nghị; phần thứ nhất khóa chính. |
| `ingredient_id` | `bigint unsigned` | Không | — | PK, FK → `inventory_ingredients.id` | Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính. |
| `quantity` | `bigint unsigned` | Không | — | — | Số lượng đề nghị. |

Ràng buộc:

- PRIMARY KEY (`request_id,ingredient_id`)
- FOREIGN KEY `fk_purchase_request_lines_ingredient` (`ingredient_id`) → `inventory_ingredients` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_purchase_request_lines_request` (`request_id`) → `purchase_requests` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_purchase_request_lines_quantity`: `(quantity > 0)`

### purchase_orders

Đơn mua hàng tạo từ đề nghị đã duyệt và gắn nhà cung cấp; cơ sở suy ra từ `purchase_requests.store_id` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(24)` | Không | — | UK | Mã đơn mua duy nhất. |
| `request_id` | `bigint unsigned` | Không | — | UK, FK → `purchase_requests.id` | Đề nghị nguồn; UNIQUE. |
| `supplier_id` | `bigint unsigned` | Không | — | FK → `suppliers.id` | Nhà cung cấp (cùng cơ sở với đề nghị nhờ trigger). |
| `created_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Người tạo đơn. |
| `status` | `varchar(20)` | Không | `OPEN` | — | `OPEN` / `PARTIALLY_RECEIVED` / `RECEIVED` / `CANCELLED`. |
| `ordered_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đặt (UTC). |
| `expected_at` | `datetime` | Có | — | — | Thời điểm dự kiến nhận (UTC). |
| `total_amount` | `bigint unsigned` | Không | — | — | Tổng giá trị VND. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_purchase_orders_code` (`code`)
- UNIQUE `uq_purchase_orders_request` (`request_id`)
- FOREIGN KEY `fk_purchase_orders_creator` (`created_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_purchase_orders_request` (`request_id`) → `purchase_requests` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_purchase_orders_supplier` (`supplier_id`) → `suppliers` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_purchase_orders_status`: `(status in ('OPEN','PARTIALLY_RECEIVED','RECEIVED','CANCELLED'))`
- CHECK `chk_purchase_orders_total`: `(total_amount > 0)`

### purchase_order_lines

Dòng đơn mua và tiến độ nhận theo nguyên liệu.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `order_id` | `bigint unsigned` | Không | — | PK, FK → `purchase_orders.id` | Đơn mua; phần thứ nhất khóa chính. |
| `ingredient_id` | `bigint unsigned` | Không | — | PK, FK → `inventory_ingredients.id` | Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính. |
| `quantity` | `bigint unsigned` | Không | — | — | Số lượng đặt. |
| `unit_cost` | `bigint unsigned` | Không | — | — | Đơn giá nhập. |
| `received_quantity` | `bigint unsigned` | Không | `0` | — | Số lượng đã nhận đạt. |
| `damaged_quantity` | `bigint unsigned` | Không | `0` | — | Số lượng đã nhận hỏng. |

Ràng buộc:

- PRIMARY KEY (`order_id,ingredient_id`)
- FOREIGN KEY `fk_purchase_order_lines_ingredient` (`ingredient_id`) → `inventory_ingredients` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_purchase_order_lines_order` (`order_id`) → `purchase_orders` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_purchase_order_lines_quantity`: `((quantity > 0) and (unit_cost > 0))`
- CHECK `chk_purchase_order_lines_received`: `((received_quantity + damaged_quantity) <= quantity)`

### goods_receipts

Phiếu nhận hàng idempotent, tạo nhập kho và công nợ theo số lượng đạt; cơ sở suy ra từ `purchase_orders`→`purchase_requests` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(24)` | Không | — | UK | Mã phiếu nhận duy nhất. |
| `order_id` | `bigint unsigned` | Không | — | FK → `purchase_orders.id` | Đơn mua. |
| `received_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Người nhận. |
| `request_id` | `char(32)` | Không | — | UK | Khóa idempotency của yêu cầu nhận. |
| `note` | `varchar(255)` | Không | `` | — | Ghi chú. |
| `received_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm nhận (UTC). |
| `accepted_amount` | `bigint unsigned` | Không | — | — | Giá trị hàng đạt được nhận. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_goods_receipts_code` (`code`)
- UNIQUE `uq_goods_receipts_request` (`request_id`)
- FOREIGN KEY `fk_goods_receipts_order` (`order_id`) → `purchase_orders` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_goods_receipts_receiver` (`received_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION

### goods_receipt_lines

Chi tiết hàng đạt, hỏng và thiếu trong một lần nhận.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `receipt_id` | `bigint unsigned` | Không | — | PK, FK → `goods_receipts.id` | Phiếu nhận; phần thứ nhất khóa chính. |
| `ingredient_id` | `bigint unsigned` | Không | — | PK, FK → `inventory_ingredients.id` | Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính. |
| `accepted_quantity` | `bigint unsigned` | Không | — | — | Số lượng đạt nhập kho. |
| `damaged_quantity` | `bigint unsigned` | Không | `0` | — | Số lượng hỏng. |
| `missing_quantity` | `bigint unsigned` | Không | `0` | — | Số lượng thiếu. |
| `unit_cost` | `bigint unsigned` | Không | — | — | Đơn giá chụp khi nhận. |

Ràng buộc:

- PRIMARY KEY (`receipt_id,ingredient_id`)
- FOREIGN KEY `fk_goods_receipt_lines_ingredient` (`ingredient_id`) → `inventory_ingredients` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_goods_receipt_lines_receipt` (`receipt_id`) → `goods_receipts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_goods_receipt_lines_quantity`: `(((accepted_quantity + damaged_quantity) + missing_quantity) > 0)`

### supplier_payables

Công nợ phát sinh từ phiếu nhận hàng và trạng thái thanh toán; cơ sở và nhà cung cấp suy ra từ `goods_receipts`→`purchase_orders`→`purchase_requests` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `receipt_id` | `bigint unsigned` | Không | — | UK, FK → `goods_receipts.id` | Phiếu nhận nguồn; UNIQUE. |
| `amount` | `bigint unsigned` | Không | — | — | Tổng phải trả. |
| `paid_amount` | `bigint unsigned` | Không | `0` | — | Số đã trả. |
| `due_date` | `date` | Không | — | — | Hạn thanh toán. |
| `status` | `varchar(10)` | Không | `UNPAID` | — | `UNPAID` / `PAID`. |
| `paid_at` | `datetime` | Có | — | — | Thời điểm thanh toán (UTC). |
| `paid_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Người thanh toán (khác người duyệt nhờ trigger). |
| `payment_method` | `varchar(10)` | Có | — | — | `CASH` / `TRANSFER`; NULL khi chưa trả. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_supplier_payables_receipt` (`receipt_id`)
- FOREIGN KEY `fk_supplier_payables_employee` (`paid_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_supplier_payables_receipt` (`receipt_id`) → `goods_receipts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_supplier_payables_amount`: `((amount > 0) and (paid_amount <= amount))`
- CHECK `chk_supplier_payables_method`: `((payment_method is null) or (payment_method in ('CASH','TRANSFER')))`
- CHECK `chk_supplier_payables_state`: `(((status = 'UNPAID') and (paid_amount = 0) and (paid_at is null) and (paid_by is null) and (payment_method is null)) or ((status = 'PAID') and (paid_amount = amount) and (paid_at is not null) and (paid_by is not null) and (payment_method is not null) and (payment_method in ('CASH','TRANSFER'))))`
- CHECK `chk_supplier_payables_status`: `(status in ('UNPAID','PAID'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_supplier_payables_status_due` (`status, due_date`)

### commercial_partners

Đối tác cung cấp game hoặc mạng quảng cáo.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `code` | `varchar(24)` | Không | — | UK | Mã đối tác, duy nhất. |
| `name` | `varchar(120)` | Không | — | — | Tên pháp lý hoặc tên giao dịch. |
| `partner_type` | `varchar(12)` | Không | — | — | `GAME` / `AD_NETWORK` / `BOTH`. |
| `status` | `varchar(12)` | Không | `ACTIVE` | — | `ACTIVE` / `SUSPENDED` / `TERMINATED`. |
| `callback_secret_ref` | `varchar(80)` | Có | — | — | Tham chiếu bí mật xác minh callback; không lưu secret thô trong bảng. |
| `contact_name` | `varchar(100)` | Có | — | — | Người liên hệ. |
| `contact_email` | `varchar(120)` | Có | — | — | Email liên hệ. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `updated_at` | `datetime` | Không | `CURRENT_TIMESTAMP`, tự cập nhật khi sửa | — | Thời điểm cập nhật (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_partners_code` (`code`)
- CHECK `chk_commercial_partners_status`: `(status in ('ACTIVE','SUSPENDED','TERMINATED'))`
- CHECK `chk_commercial_partners_type`: `(partner_type in ('GAME','AD_NETWORK','BOTH'))`

### commercial_contracts

Hợp đồng thương mại có maker-checker và mô hình tính doanh thu.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `partner_id` | `bigint unsigned` | Không | — | FK → `commercial_partners.id` | Đối tác ký hợp đồng. |
| `code` | `varchar(24)` | Không | — | UK | Mã hợp đồng, duy nhất. |
| `status` | `varchar(12)` | Không | `DRAFT` | — | `DRAFT` / `ACTIVE` / `SUSPENDED` / `EXPIRED` / `TERMINATED`. |
| `revenue_model` | `varchar(8)` | Không | — | — | `CPM` / `CPC` / `CPA` / `FIXED`. |
| `rate_amount` | `bigint unsigned` | Không | — | — | Đơn giá nguyên theo VND; CPM tính trên 1.000 impression. |
| `currency` | `char(3)` | Không | `VND` | — | Tiền tệ; P1 chỉ hỗ trợ `VND`. |
| `starts_on` | `date` | Không | — | — | Ngày bắt đầu hiệu lực. |
| `ends_on` | `date` | Không | — | — | Ngày kết thúc hiệu lực. |
| `created_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên lập hợp đồng. |
| `approved_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Người duyệt; phải khác người lập theo service. |
| `approved_at` | `datetime` | Có | — | — | Thời điểm duyệt (UTC). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_contracts_code` (`code`)
- FOREIGN KEY `fk_commercial_contracts_approver` (`approved_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_contracts_creator` (`created_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_contracts_partner` (`partner_id`) → `commercial_partners` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_contracts_approval`: `(((status = 'DRAFT') and (approved_by is null) and (approved_at is null)) or ((status <> 'DRAFT') and (approved_by is not null) and (approved_at is not null)))`
- CHECK `chk_commercial_contracts_currency`: `(currency = 'VND')`
- CHECK `chk_commercial_contracts_model`: `(revenue_model in ('CPM','CPC','CPA','FIXED'))`
- CHECK `chk_commercial_contracts_period`: `(ends_on >= starts_on)`
- CHECK `chk_commercial_contracts_status`: `(status in ('DRAFT','ACTIVE','SUSPENDED','EXPIRED','TERMINATED'))`

### commercial_campaigns

Chiến dịch game/quảng cáo thuộc một hợp đồng đã duyệt.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `contract_id` | `bigint unsigned` | Không | — | FK → `commercial_contracts.id` | Hợp đồng chi phối chiến dịch. |
| `code` | `varchar(24)` | Không | — | UK | Mã chiến dịch, duy nhất. |
| `name` | `varchar(120)` | Không | — | — | Tên chiến dịch. |
| `kind` | `varchar(8)` | Không | — | — | `AD` / `GAME`. |
| `status` | `varchar(10)` | Không | `DRAFT` | — | `DRAFT` / `ACTIVE` / `PAUSED` / `ENDED`; `ENDED` là trạng thái cuối. |
| `starts_at` | `datetime` | Không | — | — | Thời điểm bắt đầu (UTC). |
| `ends_at` | `datetime` | Không | — | — | Thời điểm kết thúc (UTC). |
| `budget_amount` | `bigint unsigned` | Có | — | — | Ngân sách giám sát vận hành; không tự ý cắt tiền đối soát. |
| `reward_type` | `varchar(12)` | Không | `NONE` | — | `NONE` / `COINS` / `VOUCHER` / `EXTRA_SPIN`. |
| `reward_amount` | `int unsigned` | Không | `0` | — | Số lượng phần thưởng chụp tại chiến dịch. |
| `created_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên tạo. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_campaigns_code` (`code`)
- FOREIGN KEY `fk_commercial_campaigns_contract` (`contract_id`) → `commercial_contracts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_campaigns_creator` (`created_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_campaigns_kind`: `(kind in ('AD','GAME'))`
- CHECK `chk_commercial_campaigns_period`: `(ends_at > starts_at)`
- CHECK `chk_commercial_campaigns_reward`: `(((reward_type = 'NONE') and (reward_amount = 0)) or ((reward_type in ('COINS','VOUCHER','EXTRA_SPIN')) and (reward_amount > 0)))`
- CHECK `chk_commercial_campaigns_status`: `(status in ('DRAFT','ACTIVE','PAUSED','ENDED'))`

### commercial_placements

Vị trí phát game/quảng cáo, có thể giới hạn theo cửa hàng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `campaign_id` | `bigint unsigned` | Không | — | FK → `commercial_campaigns.id` | Chiến dịch sở hữu vị trí. |
| `store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cửa hàng áp dụng; NULL = toàn hệ thống. |
| `code` | `varchar(32)` | Không | — | UK | Mã vị trí, duy nhất. |
| `placement_type` | `varchar(8)` | Không | — | — | `AD` / `GAME`. |
| `surface` | `varchar(24)` | Không | — | — | `PORTAL_BANNER` / `REWARDED_AD` / `GAME_CENTER`. |
| `embed_url` | `varchar(500)` | Có | — | — | URL HTTPS của game ngoài. |
| `allowed_origin` | `varchar(255)` | Có | — | — | Origin HTTPS được phép gửi thông điệp. |
| `sandbox_policy` | `varchar(120)` | Không | `allow-scripts allow-pointer-lock` | — | Chính sách iframe sandbox đã được allowlist ở backend. |
| `legacy_game_id` | `bigint unsigned` | Có | — | FK → `games.id` | Game nội bộ cũ nếu vị trí ánh xạ vào game có sẵn. |
| `legacy_ad_creative_id` | `bigint unsigned` | Có | — | FK → `ad_creatives.id` | Nội dung quảng cáo nội bộ cũ nếu có. |
| `status` | `varchar(10)` | Không | `ACTIVE` | — | `ACTIVE` / `INACTIVE`. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_placements_code` (`code`)
- FOREIGN KEY `fk_commercial_placements_ad` (`legacy_ad_creative_id`) → `ad_creatives` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_placements_campaign` (`campaign_id`) → `commercial_campaigns` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_placements_game` (`legacy_game_id`) → `games` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_placements_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_placements_embed`: `(((placement_type = 'GAME') and (embed_url is not null) and (allowed_origin is not null)) or (placement_type = 'AD'))`
- CHECK `chk_commercial_placements_status`: `(status in ('ACTIVE','INACTIVE'))`
- CHECK `chk_commercial_placements_surface`: `(surface in ('PORTAL_BANNER','REWARDED_AD','GAME_CENTER'))`
- CHECK `chk_commercial_placements_type`: `(placement_type in ('AD','GAME'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_commercial_placements_store` (`store_id, status`)

### commercial_play_sessions

Phiên chơi ngoài có token một lần và hạn sử dụng.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `placement_id` | `bigint unsigned` | Không | — | FK → `commercial_placements.id` | Vị trí game được mở. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản khách chơi. |
| `token_hash` | `char(64)` | Không | — | UK | SHA-256 của token; không lưu token thô. |
| `status` | `varchar(10)` | Không | `ISSUED` | — | `ISSUED` / `COMPLETED` / `EXPIRED` / `REJECTED`. |
| `reward_type` | `varchar(12)` | Không | — | — | Loại thưởng chụp tại lúc phát hành. |
| `reward_amount` | `int unsigned` | Không | — | — | Số lượng thưởng chụp. |
| `issued_at` | `datetime` | Không | — | — | Thời điểm phát hành (UTC). |
| `expires_at` | `datetime` | Không | — | — | Hạn token (UTC). |
| `completed_at` | `datetime` | Có | — | — | Thời điểm hoàn tất đã xác minh (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_play_sessions_token` (`token_hash`)
- FOREIGN KEY `fk_commercial_play_sessions_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_play_sessions_placement` (`placement_id`) → `commercial_placements` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_play_sessions_period`: `(expires_at > issued_at)`
- CHECK `chk_commercial_play_sessions_reward`: `(((reward_type = 'NONE') and (reward_amount = 0)) or ((reward_type in ('COINS','VOUCHER','EXTRA_SPIN')) and (reward_amount > 0)))`
- CHECK `chk_commercial_play_sessions_status`: `(status in ('ISSUED','COMPLETED','EXPIRED','REJECTED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_commercial_play_sessions_account` (`account_id, status, issued_at`)

### commercial_events

Sổ sự kiện impression/start/complete/click, chống ghi trùng; chiến dịch suy ra từ `commercial_placements.campaign_id` (NF-02).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `placement_id` | `bigint unsigned` | Không | — | FK → `commercial_placements.id` | Vị trí phát sinh sự kiện. |
| `play_session_id` | `bigint unsigned` | Có | — | FK → `commercial_play_sessions.id` | Phiên chơi liên quan; có thể NULL. |
| `account_id` | `bigint unsigned` | Có | — | FK → `accounts.id` | Tài khoản liên quan; có thể NULL. |
| `event_type` | `varchar(10)` | Không | — | — | `IMPRESSION` / `START` / `COMPLETE` / `CLICK`. |
| `event_key` | `varchar(80)` | Không | — | UK | Khóa idempotency nội bộ, duy nhất. |
| `provider_event_id` | `varchar(100)` | Có | — | UK | Mã sự kiện phía đối tác, duy nhất nếu có. |
| `verification_method` | `varchar(8)` | Không | — | — | `CLIENT` / `SERVER` / `SSV`; COMPLETE không được dùng CLIENT. |
| `accepted` | `tinyint(1)` | Không | `1` | — | TRUE nếu hợp lệ để thống kê/đối soát. |
| `occurred_at` | `datetime` | Không | — | — | Thời điểm xảy ra (UTC). |
| `verified_at` | `datetime` | Có | — | — | Thời điểm server xác minh (UTC). |
| `payload_digest` | `char(64)` | Có | — | — | SHA-256 payload đã xác minh. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm ghi nhận (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_events_key` (`event_key`)
- UNIQUE `uq_commercial_events_provider` (`provider_event_id`)
- FOREIGN KEY `fk_commercial_events_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_events_placement` (`placement_id`) → `commercial_placements` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_events_session` (`play_session_id`) → `commercial_play_sessions` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_events_complete`: `((event_type <> 'COMPLETE') or (verification_method in ('SERVER','SSV')))`
- CHECK `chk_commercial_events_type`: `(event_type in ('IMPRESSION','START','COMPLETE','CLICK'))`
- CHECK `chk_commercial_events_verification`: `(verification_method in ('CLIENT','SERVER','SSV'))`
- CHECK `chk_commercial_events_verified`: `(((verification_method = 'CLIENT') and (verified_at is null)) or ((verification_method in ('SERVER','SSV')) and (verified_at is not null)))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_commercial_events_placement_time` (`placement_id, event_type, accepted, occurred_at`)

### commercial_reward_grants

Outbox phần thưởng; callback không được cộng xu/phát voucher trực tiếp.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `event_id` | `bigint unsigned` | Không | — | UK, FK → `commercial_events.id` | COMPLETE event đã xác minh; duy nhất. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản nhận thưởng (khớp sự kiện nhờ trigger `trg_commercial_reward_grants_bi`). |
| `reward_type` | `varchar(12)` | Không | — | — | `COINS` / `VOUCHER` / `EXTRA_SPIN`. |
| `reward_amount` | `int unsigned` | Không | — | — | Số lượng thưởng. |
| `status` | `varchar(10)` | Không | `PENDING` | — | `PENDING` / `APPLIED` / `FAILED`. |
| `attempts` | `int unsigned` | Không | `0` | — | Số lần worker thử áp dụng. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |
| `applied_at` | `datetime` | Có | — | — | Thời điểm áp dụng thành công (UTC). |
| `failure_reason` | `varchar(255)` | Có | — | — | Lý do thất bại cuối cùng. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_reward_grants_event` (`event_id`)
- FOREIGN KEY `fk_commercial_reward_grants_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_reward_grants_event` (`event_id`) → `commercial_events` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_reward_grants_reward`: `((reward_type in ('COINS','VOUCHER','EXTRA_SPIN')) and (reward_amount > 0))`
- CHECK `chk_commercial_reward_grants_status`: `(status in ('PENDING','APPLIED','FAILED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_commercial_reward_grants_pending` (`status, created_at`)

### commercial_settlements

Kỳ đối soát doanh thu có maker-checker; `net_amount` tính qua `v_commercial_settlements` (NF-01).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `contract_id` | `bigint unsigned` | Không | — | FK → `commercial_contracts.id` | Hợp đồng được đối soát. |
| `period_start` | `date` | Không | — | — | Ngày đầu kỳ. |
| `period_end` | `date` | Không | — | — | Ngày cuối kỳ. |
| `gross_amount` | `bigint unsigned` | Không | — | — | Doanh thu gộp tính từ snapshot sự kiện. |
| `adjustment_amount` | `bigint` | Không | `0` | — | Điều chỉnh có dấu. |
| `adjustment_reason` | `varchar(255)` | Có | — | — | Lý do bắt buộc (NOT NULL, ≥ 5 ký tự) khi điều chỉnh khác 0. |
| `status` | `varchar(10)` | Không | `DRAFT` | — | `DRAFT` / `APPROVED` / `PAID` / `VOID`. |
| `generated_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên tạo kỳ. |
| `reviewed_by` | `bigint unsigned` | Có | — | FK → `employees.id` | Người duyệt (khác `generated_by` nhờ CHECK SoD). |
| `reviewed_at` | `datetime` | Có | — | — | Thời điểm duyệt (UTC). |
| `paid_at` | `datetime` | Có | — | — | Thời điểm ghi nhận đã thanh toán (UTC). |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_commercial_settlements_period` (`contract_id,period_start,period_end`)
- FOREIGN KEY `fk_commercial_settlements_contract` (`contract_id`) → `commercial_contracts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_settlements_generator` (`generated_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_settlements_reviewer` (`reviewed_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_settlements_adjustment`: `(((adjustment_amount = 0) and (adjustment_reason is null)) or ((adjustment_amount <> 0) and (adjustment_reason is not null) and (char_length(trim(adjustment_reason)) >= 5)))`
- CHECK `chk_commercial_settlements_lifecycle`: `(((status = 'DRAFT') and (reviewed_by is null) and (reviewed_at is null) and (paid_at is null)) or ((status = 'APPROVED') and (reviewed_by is not null) and (reviewed_at is not null) and (reviewed_by <> generated_by) and (paid_at is null)) or ((status = 'PAID') and (reviewed_by is not null) and (reviewed_at is not null) and (reviewed_by <> generated_by) and (paid_at is not null) and (paid_at >= reviewed_at)) or ((status = 'VOID') and (paid_at is null)))`
- CHECK `chk_commercial_settlements_net_nonnegative`: `((cast(gross_amount as signed) + adjustment_amount) >= 0)`
- CHECK `chk_commercial_settlements_period`: `(period_end >= period_start)`
- CHECK `chk_commercial_settlements_status`: `(status in ('DRAFT','APPROVED','PAID','VOID'))`

### commercial_settlement_lines

Dòng snapshot đối soát theo vị trí và loại sự kiện; thành tiền `amount` tính qua `v_commercial_settlement_lines` (NF-01).

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `settlement_id` | `bigint unsigned` | Không | — | PK, FK → `commercial_settlements.id` | Kỳ đối soát. |
| `placement_id` | `bigint unsigned` | Không | — | PK, FK → `commercial_placements.id` | Vị trí được tính tiền. |
| `event_type` | `varchar(10)` | Không | — | PK | `IMPRESSION` / `CLICK` / `COMPLETE` / `FIXED`. |
| `units` | `bigint unsigned` | Không | — | — | Số đơn vị hợp lệ. |
| `unit_rate` | `bigint unsigned` | Không | — | — | Đơn giá VND chụp từ hợp đồng. |

Ràng buộc:

- PRIMARY KEY (`settlement_id,placement_id,event_type`)
- FOREIGN KEY `fk_commercial_settlement_lines_placement` (`placement_id`) → `commercial_placements` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_commercial_settlement_lines_settlement` (`settlement_id`) → `commercial_settlements` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_commercial_settlement_lines_event`: `(event_type in ('IMPRESSION','CLICK','COMPLETE','FIXED'))`

### supplier_payable_approvals

Bản ghi duyệt công nợ nhà cung cấp; dùng kiểm soát phân tách người duyệt và người chi.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `payable_id` | `bigint unsigned` | Không | — | PK, FK → `supplier_payables.id` | Công nợ được duyệt; khóa chính/FK nên mỗi công nợ được duyệt tối đa một lần. |
| `approved_by` | `bigint unsigned` | Không | — | FK → `employees.id` | Nhân viên phê duyệt, phải khác người thanh toán theo service trong chính sách tách quyền. |
| `approved_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm duyệt (UTC). |
| `note` | `varchar(255)` | Không | — | — | Ghi chú duyệt bắt buộc. |

Ràng buộc:

- PRIMARY KEY (`payable_id`)
- FOREIGN KEY `fk_payable_approval_employee` (`approved_by`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_payable_approval_payable` (`payable_id`) → `supplier_payables` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION

### customer_email_tokens

Token kích hoạt/đặt lại mật khẩu khách; chỉ lưu hash và nonce dẫn xuất, token thô không được lưu.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản khách nhận token. |
| `purpose` | `varchar(12)` | Không | — | — | `ACTIVATE` hoặc `RESET`. |
| `token_hash` | `char(64)` | Không | — | UK | SHA-256 token thô; UNIQUE, dùng tra cứu/xác thực. |
| `nonce` | `char(64)` | Không | — | — | Nonce ngẫu nhiên dùng dẫn xuất token cho worker, không phải token thô. |
| `expires_at` | `datetime` | Không | — | — | Hạn sử dụng (UTC). |
| `used_at` | `datetime` | Có | — | — | Thời điểm dùng thành công; NULL nếu chưa dùng. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm phát hành (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customer_email_token_hash` (`token_hash`)
- FOREIGN KEY `fk_customer_email_token_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_customer_email_token_purpose`: `(purpose in ('ACTIVATE','RESET'))`
- CHECK `chk_customer_email_token_times`: `((expires_at > created_at) and ((used_at is null) or (used_at >= created_at)))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_customer_email_token_account` (`account_id, purpose, created_at`)

### customer_mail_outbox

Transactional outbox gửi email khách sau khi transaction đăng ký/reset đã commit.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `token_id` | `bigint unsigned` | Không | — | UK, FK → `customer_email_tokens.id` | Token cần gửi; UNIQUE để tránh gửi trùng outbox. |
| `status` | `varchar(12)` | Không | `PENDING` | — | `PENDING` / `SENDING` / `SENT` / `FAILED`. |
| `attempts` | `int unsigned` | Không | `0` | — | Số lần worker đã thử gửi. |
| `next_attempt_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm đủ điều kiện thử lại (UTC). |
| `sent_at` | `datetime` | Có | — | — | Thời điểm gửi thành công (UTC). |
| `last_error` | `varchar(120)` | Có | — | — | Thông báo lỗi rút gọn của lần gửi gần nhất. |

Ràng buộc:

- PRIMARY KEY (`id`)
- UNIQUE `uq_customer_mail_outbox_token` (`token_id`)
- FOREIGN KEY `fk_customer_mail_outbox_token` (`token_id`) → `customer_email_tokens` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- CHECK `chk_customer_mail_outbox_status`: `(status in ('PENDING','SENDING','SENT','FAILED'))`

Index bổ sung (`002_indexes.sql`):

- INDEX `idx_customer_mail_outbox_due` (`status, next_attempt_at`)

### customer_security_audit

Audit bất biến cho thao tác kích hoạt, đặt lại mật khẩu và các sự kiện bảo mật khách.

| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |
|---|---|:---:|---|---|---|
| `id` | `bigint unsigned` | Không | AUTO_INCREMENT | PK | Khóa chính. |
| `account_id` | `bigint unsigned` | Không | — | FK → `accounts.id` | Tài khoản khách chịu tác động. |
| `employee_id` | `bigint unsigned` | Có | — | FK → `employees.id` | Nhân viên liên quan nếu thao tác tại quầy; NULL với luồng email tự phục vụ. |
| `store_id` | `bigint unsigned` | Có | — | FK → `stores.id` | Cơ sở liên quan nếu có; NULL với luồng web tự phục vụ. |
| `action` | `varchar(40)` | Không | — | — | Tên sự kiện bảo mật. |
| `created_at` | `datetime` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm ghi audit (UTC). |

Ràng buộc:

- PRIMARY KEY (`id`)
- FOREIGN KEY `fk_customer_security_account` (`account_id`) → `accounts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_customer_security_employee` (`employee_id`) → `employees` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
- FOREIGN KEY `fk_customer_security_store` (`store_id`) → `stores` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
