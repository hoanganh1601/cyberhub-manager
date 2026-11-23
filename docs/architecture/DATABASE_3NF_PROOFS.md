# Phụ lục chứng minh chuẩn hóa 3NF và toàn vẹn cơ sở dữ liệu — CyberHub Manager

- **Ngày lập và nghiệm thu:** 21–23/11/2026
- **Phiên bản schema:** Migration `sql/001_initial_schema.sql` → `sql/032_strict_3nf_ledger_and_immutability.sql` (MySQL 8.4 LTS, 100% InnoDB, `utf8mb4_0900_ai_ci`)
- **Nhánh triển khai:** `refactor/four-layer-architecture` (kiến trúc 4 tầng: Domain / Application / Infrastructure / Presentation)
- **Căn cứ đối chiếu:** [Kế hoạch chuẩn hóa 3NF](DATABASE_3NF_REMEDIATION_PLAN.md), [Data dictionary](../diagrams/data_dictionary.md), [ERD hiện hành](../diagrams/current_erd.md), [UML hệ thống](../diagrams/system_uml.md), [Bộ kiểm thử 3NF & toàn vẹn](../../tests/integration/test_3nf_and_integrity.py).

## 1. Tóm tắt kết quả chuẩn hóa và kiểm chứng

| Chỉ tiêu (đọc từ `INFORMATION_SCHEMA` của `cyberhub_manager_test` & `cyberhub_manager`) | Trước chuẩn hóa (`027`) | Sau chuẩn hóa (`032`) |
|---|---:|---:|
| Bảng nghiệp vụ cơ sở (BASE TABLE, không tính `schema_migrations`) | 70 | **75** |
| View đọc tương thích / dẫn xuất (`v_*`) | 0 | **18** |
| Trigger đồng bộ chiếm dụng, kiểm soát chéo & bất biến sổ cái | 0 | **28** |
| PRIMARY KEY (gồm cả `schema_migrations`) | 71 | **76** (75 nghiệp vụ + 1 kỹ thuật) |
| UNIQUE constraint | 62 | **62** |
| FOREIGN KEY constraint | 152 | **150** |
| CHECK constraint | 170 | **186** |
| Cột sinh (GENERATED COLUMN) trong bảng nghiệp vụ cơ sở | 4 | **0** |
| Cột JSON trong bảng nghiệp vụ cơ sở | 1 (`snapshot_json`) | **0** |
| Bảng thiếu khai báo `InnoDB` / `utf8mb4_0900_ai_ci` | 4 (phụ thuộc default) | **0** |

### Phân tách rõ ba nội dung theo nguyên tắc báo cáo BTL

1. **Chuẩn hóa 3NF (đạt trên cả 75/75 bảng nghiệp vụ cơ sở):** Mọi phụ thuộc hàm nội quan hệ không tầm thường $X \to A \in F^+$ trên từng bảng cơ sở đều thỏa mãn $X$ là siêu khóa hoặc $A$ là thuộc tính nguyên tố. Toàn bộ cột dẫn xuất/công thức (NF-01), cột lặp bắc cầu từ bảng cha (NF-02), nguồn nhân sự trùng lặp hai chiều (NF-03), cấu hình/snapshot JSON không phiên bản hóa (NF-04), hai ngày nghiệp vụ suy ra từ timestamp (`game_sessions.played_on`, `ad_reward_events.played_on` — `031`) và liên kết phiên rải rác nullable `account_transactions.session_id` (tách sang `session_transactions` kèm `store_id NOT NULL` và trigger bất biến sổ cái — `032`) đã được chuẩn hóa triệt để. Ngày Việt Nam được tạo ở read model từ timestamp UTC và truy vấn giới hạn ngày dùng khoảng nửa mở `[start_utc, end_utc)`.
2. **Toàn vẹn liên bảng & số dư tổng hợp (NF-05, INT-01..INT-04):** Các trường số dư/tổng tổng hợp liên bảng (`accounts.balance`, `accounts.bonus_balance`, `game_wallets.balance`, `inventory_ingredients.on_hand/reserved`, `menu_orders.total_amount`, `purchase_orders.total_amount`, `goods_receipts.accepted_amount`, `machine_incidents.parts_cost`) được công bố tường minh là projection vật lý có khóa hàng `FOR UPDATE` và đồng bộ nguyên tử cùng sổ cái/bảng chi tiết trong cùng transaction (không che giấu và không gọi nhầm là không có dư thừa liên bảng). Ràng buộc cùng cơ sở/đúng chủ sở hữu (INT-01) và CHECK chống lỗ hổng `NULL/UNKNOWN` + tách nhiệm vụ SoD (INT-02) được thực thi trực tiếp tại MySQL 8.4.
3. **Giới hạn phạm vi công bố trung thực (Mục 7 & 13):**
   - Hai cột tham chiếu đa hình `cash_shift_entries.(source_type, source_id)` và `management_audit.entity_id` không có FK cứng tới từng bảng nguồn; tính duy nhất được khóa bằng `UNIQUE(source_type, source_id, payment_method)` và kiểm soát tại tầng application service.
   - Tài khoản DB demo hiện dùng chung `cyberhub_app` có quyền DML rộng hơn mức tối thiểu; tách tài khoản DB runtime chỉ-INSERT cho bảng audit/ledger thuộc phạm vi triển khai vận hành sản xuất.
   - Dữ liệu demo lịch sử trước migration `030` trong `cyberhub_manager` có 2 hợp đồng seed (`CTR-VNG-2026`, `CTR-ADS-2026`) ghi `created_by = approved_by = 9`; theo nguyên tắc không tự suy đoán/giả mạo người duyệt (Mục 10.5), 2 bản ghi lịch sử này được giữ nguyên trong khi trigger `trg_commercial_contracts_sod_bi/bu` chặn tuyệt đối tự duyệt với mọi hợp đồng thêm/sửa mới.
   - Dữ liệu seed lịch sử trước migration `031` trong `cyberhub_manager` có 4 dòng `game_sessions` (`id = 1..4`, `created_at = 2026-11-16 17:17:31` UTC) từng ghi `played_on = 2026-11-16` (theo ngày UTC) thay vì ngày Việt Nam `2026-11-17` (`UTC+7`). Trước khi chạy `031`, quá trình nâng cấp đã backup `cyberhub_manager`, diễn tập trên bản sao `cyberhub_manager_migration_test`, chuẩn hóa minh bạch 4 dòng seed này về ngày `UTC+7` tương ứng rồi mới áp dụng `031` (4 dòng phát sinh từ ứng dụng và 5 dòng `ad_reward_events` khớp sẵn 100%, 0 sai lệch sau nâng cấp).

## 2. Chốt 10 quyết định nghiệp vụ (B01–B10)

| Mã | Quyết định nghiệp vụ đã chốt | Tác động chuẩn hóa & phạm vi |
|---|---|---|
| **B01** | Mỗi máy cố định tại một cửa hàng; mỗi phiên sử dụng cố định trên một máy (chưa hỗ trợ điều chuyển máy hoặc đổi máy giữa phiên). | Xác lập FD `machine_id -> store_id` và `session_id -> (machine_id, customer_id)`, là cơ sở toán học để loại `store_id`/`machine_id`/`account_id` lặp ở `menu_orders`, `pos_order_reversals`, `machine_incidents`. |
| **B02** | `machine_room_types` phân loại từng máy trạm (`STANDARD`/`VIP`/`COUPLE`/`SUPER_VIP`), không phải nghiệp vụ đặt trọn phòng nhiều máy. | Giữ PK 1–1 theo `machine_id`; không tạo bảng room booking ngoài phạm vi ứng dụng. |
| **B03** | Đơn giá tính theo máy/giờ (VND nguyên), làm tròn lên theo phút, và chụp bất biến vào `usage_sessions.hourly_rate` lúc mở phiên. | `hourly_rate` trên phiên là snapshot thời điểm mở, không phải phụ thuộc bắc cầu từ `machines.hourly_rate` hiện tại. |
| **B04** | Nhà cung cấp (`suppliers`) được quản lý riêng theo từng cửa hàng (`store_id`). | Xác lập `supplier_id -> store_id`; kết hợp trigger `trg_purchase_orders_bi/bu` bảo đảm PO dùng đúng nhà cung cấp cùng cơ sở và loại bỏ `store_id` lặp trên `purchase_orders`, `supplier_payables`. |
| **B05** | Mỗi công nợ nhà cung cấp (`supplier_payables`) thanh toán một lần đủ 100% số tiền (`paid_amount = amount`). | Thực thi cứng bởi `chk_supplier_payables_state`; chưa hỗ trợ trả góp nhiều đợt. |
| **B06** | Một đề nghị mua (`purchase_requests`) tạo tối đa một đơn mua (`purchase_orders`, `request_id` UNIQUE). | `request_id` là khóa ứng viên của `purchase_orders`, xác định duy nhất cơ sở mua. |
| **B07** | Mỗi đơn POS áp dụng tối đa một ưu đãi xác định (khuyến mãi POS hoặc voucher) và chỉ hoàn/hủy toàn bộ đơn (`pos_order_reversals.order_id` UNIQUE). | Mô hình hóa gọn trên `menu_order_pricing` cấu trúc và `pos_order_reversals` 1–0..1 theo đơn. |
| **B08** | Tách bạch tiền nạp (`TOP_UP`), doanh thu tiêu dùng giờ chơi (`invoices.usage_cost`), doanh thu POS (`menu_orders`), tiền thưởng không rút (`bonus_balance`), thu/chi két (`cash_shift_entries`), điểm và xu game. | Không cộng trùng dòng tiền nạp ví với doanh thu tiêu dùng. |
| **B09** | Hạng thành viên xét theo tổng chi tiêu hợp lệ (`usage_cost - bonus_used`) của hóa đơn `PAID`; hóa đơn `VOID` tự động đảo chi tiêu/điểm khi tính từ `v_invoices`; đổi chính sách tạo phiên bản mới trong `loyalty_policy_versions`. | Bảo toàn tuyệt đối điểm của hóa đơn lịch sử khi Admin đổi `unit_amount`. |
| **B10** | Mỗi nhân viên chỉ mở tối đa một ca làm việc chưa đóng (`OPEN`/`PENDING_REVIEW`) tại một thời điểm; nhiều nhân viên có thể mở ca song song tại cùng cơ sở. | Thực thi 3NF bằng bảng chiếm dụng `active_employee_shifts(shift_id PK, employee_id UNIQUE)`. |

## 3. Chứng minh nối không mất mát và bảo toàn phụ thuộc cho các phép phân rã (`028`–`029`)

Áp dụng **Định lý Heath**: phép phân rã quan hệ $R$ thành $R_1, R_2$ là **nối không mất mát (lossless-join)** khi và chỉ khi $(R_1 \cap R_2) \to R_1$ hoặc $(R_1 \cap R_2) \to R_2$ thuộc $F^+$; và **bảo toàn phụ thuộc (dependency-preserving)** khi $(\pi_{R_1}(F) \cup \pi_{R_2}(F))^+ = F^+$.

### 3.1. Phân rã NF-01 & NF-04 — Chính sách điểm và hóa đơn (`028`)
- **Trước phân rã:** `invoices` chứa `{loyalty_rule_version -> loyalty_unit}`, `{(usage_cost, bonus_used) -> loyalty_eligible_amount}`, `{(usage_cost) -> total_amount}` và `{(loyalty_eligible_amount, loyalty_unit, enabled) -> loyalty_points}` — đều có vế trái không phải siêu khóa (vi phạm 3NF).
- **Phân rã:**
  - $R_1 = \text{loyalty\_policy\_versions}(\underline{\text{version}}, \text{enabled}, \text{unit\_amount}, \text{silver\_spend}, \text{gold\_spend}, \text{platinum\_spend}, \text{created\_at})$
  - $R_2 = \text{loyalty\_settings}(\underline{\text{id}}, \text{current\_version}, \text{updated\_at})$ với `current_version` FK $\to R_1$
  - $R_3 = \text{invoices}(\underline{\text{id}}, \text{code}, \text{session\_id}, \text{customer\_id}, \text{employee\_id}, \text{store\_id}, \text{usage\_cost}, \text{settlement\_amount}, \text{bonus\_used}, \text{loyalty\_rule\_version}, \text{status}, \text{created\_at})$ với `loyalty_rule_version` FK $\to R_1$
- **Nối không mất mát:** $R_3 \cap R_1 = \{\text{loyalty\_rule\_version} \equiv \text{version}\}$, là khóa chính của $R_1$ nên $(R_3 \cap R_1) \to R_1 \in F^+$. Phép chiếu bỏ các cột hàm xác định (`total_amount`, `loyalty_eligible_amount`, `loyalty_points`, `loyalty_unit`) tái tạo chính xác 100% qua view `v_invoices`.
- **Bảo toàn phụ thuộc:** $\text{version} \to \text{unit\_amount}$ được bảo toàn trực tiếp tại $R_1$; toàn bộ FD khóa của hóa đơn bảo toàn tại $R_3$.

### 3.2. Projection trạng thái NF-01 — Bảng chiếm dụng đang hoạt động (`028`)
- **Trước phân rã:** `usage_sessions` chứa cột sinh `active_machine_id`, `active_customer_id` (`(status, machine_id) -> active_machine_id`); `cash_shifts` chứa `active_employee_id` (`(status, employee_id) -> active_employee_id`).
- **Thiết kế sau chuẩn hóa:** `active_usage_sessions(session_id PK, machine_id UNIQUE, customer_id UNIQUE)` và `active_employee_shifts(shift_id PK, employee_id UNIQUE)` là projection vật lý chỉ chứa tập con phiên/ca đang hoạt động, được đồng bộ cùng transaction bằng trigger `AFTER INSERT` / `AFTER UPDATE`.
- **Lập luận toàn vẹn đúng:** Đây không phải phép phân rã dọc dùng để tái tạo toàn bộ bảng gốc bằng `INNER JOIN`, nên không áp dụng Định lý Heath cho quan hệ này. Tập đầy đủ luôn nằm ở `usage_sessions`/`cash_shifts`; bảng projection chỉ hiện thực hóa ràng buộc duy nhất có điều kiện. Tính tương đương trạng thái được bảo đảm bởi trigger thêm/xóa projection, `UNIQUE` trên tài nguyên đang bị chiếm dụng và trigger chặn mở lại bản ghi đã kết thúc.

### 3.3. Phân rã NF-02 — Loại bỏ 11 phụ thuộc bắc cầu từ khóa ngoại cha (`028`)
- Các quan hệ con bỏ cột cha lặp bắc cầu: `cash_shift_entries` (`shift_id -> store_id`), `commercial_events` (`placement_id -> campaign_id`), `goods_receipts` (`order_id -> store_id`), `supplier_payables` (`receipt_id -> (supplier_id, store_id)`), `purchase_orders` (`request_id -> store_id`), `pos_order_reversals` (`order_id -> store_id`), `inventory_movements` (`ingredient_id -> store_id`), `inventory_counts` (`ingredient_id -> store_id`), `machine_incidents` (`machine_id -> store_id`), `menu_orders` (`session_id -> (store_id, machine_id, account_id)`), `menu_items` (`category_id -> store_id`).
- **Nối không mất mát:** Trong cả 11 trường hợp, phép nối giữa bảng con $R_{\text{child}}$ và bảng cha $R_{\text{parent}}$ đi qua khóa ngoại `NOT NULL` trỏ đúng vào khóa chính của $R_{\text{parent}}$, tức $(R_{\text{child}} \cap R_{\text{parent}}) \to R_{\text{parent}} \in F^+$ (đạt Định lý Heath).
- **Bảo toàn phụ thuộc:** FD bắc cầu thuộc về bảng cha đã được bảo toàn nguyên vẹn trên bảng cha; riêng ràng buộc tên món duy nhất toàn cơ sở trên `menu_items` (trước đây là `UNIQUE(store_id, name)`) được bảo toàn bằng `UNIQUE(category_id, name)` kết hợp trigger `trg_menu_items_bi/bu`. Các view `v_*` tái lập chính xác mọi cột dẫn xuất.

### 3.4. Phân rã NF-03 — Tách nguồn sự thật nhân sự và tài khoản đăng nhập (`029`)
- **Trước phân rã:** Cả `employees` và `employee_profiles` cùng lưu `(code, store_id/home_store_id, full_name)` gây dị thường cập nhật hai nguồn sự thật.
- **Phân rã:** `employee_profiles(id PK, code UK, home_store_id, full_name, employment_status, ...)` là nguồn sự thật nhân sự duy nhất; `employees(id PK, profile_id NOT NULL UK FK -> employee_profiles.id, username UK, password_hash, role, status, ...)` chỉ giữ định danh xác thực & RBAC.
- **Nối không mất mát & bảo toàn phụ thuộc:** Giao là `profile_id` (= `employee_profiles.id`), là khóa ứng viên của **cả hai** quan hệ (`employee_profiles.id` PK và `employees.profile_id` UNIQUE NOT NULL). Mọi FD nhân sự bảo toàn trên `employee_profiles`; mọi FD xác thực bảo toàn trên `employees`; quan hệ `1 : 0..1` cho phép tạo hồ sơ nhân sự trước khi cấp tài khoản; view `v_employees` tái lập đầy đủ góc nhìn hợp nhất.

### 3.5. Phân rã NF-04 — Phiên bản khuyến mãi POS và định giá có cấu trúc (`029`)
- **Trước phân rã:** `menu_order_pricing` lưu `promotion_id`, `promotion_code`, `promotion_kind`, `final_amount`, và `snapshot_json` (trộn lẫn thuộc tính chính sách, giá trị công thức và payload JSON).
- **Phân rã:** Tạo `menu_promotion_versions(id PK, promotion_id, version, code, kind, item_id, value, minimum_tier, starts_at, ends_at, created_at)` với `UNIQUE(promotion_id, version)`; chuẩn hóa `menu_order_pricing(order_id PK, promotion_version_id FK, applied_source, member_tier, discount_amount, voucher_id FK, voucher_discount_amount)`.
- **Nối không mất mát & bảo toàn phụ thuộc:** `menu_order_pricing` nối với `menu_promotion_versions` qua `promotion_version_id` (PK của bảng version) và với `menu_orders` qua `order_id` (PK chung). Phép chiếu `v_menu_order_pricing` tái tạo đầy đủ `promotion_code`, `promotion_kind`, `effective_discount_amount`, `final_amount` mà không cần `snapshot_json`.

### 3.6. Phân rã sổ cái gắn phiên & bất biến sổ cái tài chính (`032`)
- **Trước phân rã:** `account_transactions` chứa cột `session_id` nullable (chỉ có giá trị với `USAGE_PAYMENT` và `DEBT_SETTLEMENT`, tạo FD cục bộ `session_id -> (account_id, store_id)` trên các dòng gắn phiên), đồng thời `store_id` cho phép `NULL` khiến tầng service phải ghi `INSERT` rồi `UPDATE store_id` hai bước.
- **Phân rã:**
  - $R_1 = \text{account\_transactions}(\underline{\text{id}}, \text{code}, \text{account\_id}, \text{employee\_id}, \text{store\_id NOT NULL}, \text{promotion\_id}, \text{type}, \text{amount}, \text{method}, \text{created\_at})$
  - $R_2 = \text{session\_transactions}(\underline{\text{transaction\_id}}, \text{session\_id})$ với `transaction_id` PK/FK $\to R_1$, `session_id` FK $\to \text{usage\_sessions}(\text{id})$.
- **Nối không mất mát & bảo toàn phụ thuộc:** $R_1 \cap R_2 = \{\text{transaction\_id} \equiv \text{id}\}$ là khóa chính của cả $R_1$ và $R_2$, nên $(R_1 \cap R_2) \to R_1$ và $(R_1 \cap R_2) \to R_2$ đều thuộc $F^+$ (đạt Định lý Heath); phép nối trái `account_transactions LEFT JOIN session_transactions` tái tạo nguyên vẹn 100% ánh xạ phiên lịch sử. Bốn trigger `trg_account_transactions_bi/bu` và `trg_session_transactions_bi/bu` thực thi bất biến sổ cái tài chính, chặn gán phiên cho `TOP_UP`/`PROMOTION`, và khóa chặt tính khớp `account_id`/`store_id` giữa giao dịch và phiên.

## 4. Hồ sơ chứng minh 3NF chi tiết cho 75/75 bảng nghiệp vụ

Tất cả 75 bảng nghiệp vụ (theo đúng thứ tự trình bày của `scripts/gen_data_dictionary.py`) đều được lập phiếu theo đầy đủ 13 trường của Mục 3.3 trong `DATABASE_3NF_REMEDIATION_PLAN.md`. Quy ước ký hiệu: khóa chính gạch chân bằng `PK`, khóa ứng viên chỉ tính các bộ cột `NOT NULL` có ràng buộc `PRIMARY KEY` hoặc `UNIQUE` (các chỉ mục `UNIQUE` chứa cột cho phép `NULL` được ghi riêng là *ràng buộc duy nhất có điều kiện NULL*, không xem là khóa ứng viên theo mô hình quan hệ cổ điển).

### 4.1. `stores`

- **Tên quan hệ và ý nghĩa một dòng:** `stores` — Cửa hàng net. Nhân viên, máy và hóa đơn đều thuộc một cửa hàng.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `name` (`varchar(100)`, NOT NULL); `address` (`varchar(255)`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {name, address, status, created_at, updated_at}; {code} → {name, address, status, created_at, updated_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → name; {id} → address; {id} → status; {id} → created_at; {id} → updated_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `stores`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `name`, `address`, `status`, `created_at`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_stores_code`(`code`); CHECK `chk_stores_address_not_blank`; CHECK `chk_stores_code_not_blank`; CHECK `chk_stores_name_not_blank`; CHECK `chk_stores_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.2. `employees`

- **Tên quan hệ và ý nghĩa một dòng:** `employees` — Thông tin xác thực và phân quyền đăng nhập của nhân viên; thông tin nhân sự thuộc `employee_profiles` (chuẩn 3NF NF-03).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (11 cột):** `id` (`bigint unsigned`, NOT NULL); `profile_id` (`bigint unsigned`, NOT NULL); `username` (`varchar(30)`, NOT NULL); `password_hash` (`varchar(255)`, NOT NULL); `role` (`varchar(20)`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL); `auth_version` (`int unsigned`, NOT NULL); `must_change_password` (`tinyint(1)`, NOT NULL); `password_changed_at` (`datetime`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {password_hash, role, status, created_at, updated_at, auth_version, must_change_password, password_changed_at}; {profile_id} → {password_hash, role, status, created_at, updated_at, auth_version, must_change_password, password_changed_at}; {username} → {password_hash, role, status, created_at, updated_at, auth_version, must_change_password, password_changed_at}; {id} → {profile_id}; {profile_id} → {username}; {username} → {id} }`. Mọi thông tin đăng nhập/phân quyền (`username`, `password_hash`, `role`, `status`, `auth_version`, `must_change_password`, `password_changed_at`, `created_at`, `updated_at`) phụ thuộc đầy đủ vào từng khóa ứng viên `{id}`, `{profile_id}`, `{username}`. Thông tin nhân sự (`code`, `home_store_id`, `full_name`) đã tách về `employee_profiles` (NF-03).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → password_hash; {id} → role; {id} → status; {id} → created_at; {id} → updated_at; {id} → auth_version; {id} → must_change_password; {id} → password_changed_at; {profile_id} ↔ {id}; {username} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {profile_id}, {username}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 11 thuộc tính của `employees`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `profile_id`, `username`. Không nguyên tố: `password_hash`, `role`, `status`, `created_at`, `updated_at`, `auth_version`, `must_change_password`, `password_changed_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `029` (NF-03): đảo chiều FK sang `employees.profile_id NOT NULL UNIQUE -> employee_profiles.id`, bỏ `employees.(code, store_id, full_name)` và `employee_profiles.employee_id`; cung cấp view `v_employees`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_employees_profile`(`profile_id`); UK `uq_employees_username`(`username`); FK `fk_employees_profile`(`profile_id` → `employee_profiles.id`, ON DELETE RESTRICT); CHECK `chk_employees_password_hash_not_blank`; CHECK `chk_employees_role`; CHECK `chk_employees_status`; CHECK `chk_employees_username_length`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** `AuthRepository` + `ManagementService` JOIN `employee_profiles` qua `profile_id`; mọi thay đổi mật khẩu/role/store tăng `auth_version` để thu hồi phiên cũ trong cùng transaction.
- **Test và bằng chứng dữ liệu:** `test_auth_repository.py`, `test_rbac_followup_mysql.py`, `test_3nf_and_integrity.py`; 100% map nhân viên khớp trên clone `cyberhub_manager`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.3. `employee_profiles`

- **Tên quan hệ và ý nghĩa một dòng:** `employee_profiles` — Nguồn sự thật duy nhất về hồ sơ nhân sự (mã, tên, cơ sở chính, trạng thái làm việc); độc lập với thông tin đăng nhập tại `employees` (chuẩn 3NF NF-03).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `home_store_id` (`bigint unsigned`, NOT NULL); `full_name` (`varchar(100)`, NOT NULL); `employment_status` (`varchar(10)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {home_store_id, full_name, employment_status, created_at, updated_at}; {code} → {home_store_id, full_name, employment_status, created_at, updated_at}; {id} → {code}; {code} → {id} }`. Nguồn sự thật duy nhất về nhân sự: `{id}` và `{code}` là hai khóa ứng viên; `home_store_id`, `full_name`, `employment_status`, `created_at`, `updated_at` phụ thuộc trực tiếp vào khóa, không còn FK ngược `employee_id`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → home_store_id; {id} → full_name; {id} → employment_status; {id} → created_at; {id} → updated_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `employee_profiles`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `home_store_id`, `full_name`, `employment_status`, `created_at`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `029` (NF-03): bỏ `employee_id` khỏi `employee_profiles` để hồ sơ chưa cấp tài khoản vẫn tồn tại độc lập (quan hệ `1 : 0..1` với `employees`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_employee_profiles_code`(`code`); FK `fk_employee_profiles_store`(`home_store_id` → `stores.id`, ON DELETE NO ACTION); CHECK `chk_employee_profiles_code_not_blank`; CHECK `chk_employee_profiles_full_name_not_blank`; CHECK `chk_employee_profiles_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** DIRECTOR/MANAGER quản lý hồ sơ nhân sự; ADMIN gắn credential bằng `employees.profile_id` trong transaction có khóa `FOR UPDATE`.
- **Test và bằng chứng dữ liệu:** `test_rbac_followup_mysql.py`, `test_3nf_and_integrity.py`; xác minh bảo toàn 3 hồ sơ chưa có tài khoản đăng nhập trên `cyberhub_manager`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.4. `employee_store_assignments`

- **Tên quan hệ và ý nghĩa một dòng:** `employee_store_assignments` — Phân công bổ sung cho MANAGER được vận hành tại nhiều cơ sở; không thay đổi cơ sở chính trong hồ sơ.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (4 cột):** `employee_id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `granted_by` (`bigint unsigned`, NOT NULL); `granted_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {employee_id, store_id} → {granted_by, granted_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {employee_id, store_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {employee_id, store_id} → granted_by; {employee_id, store_id} → granted_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {employee_id, store_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 4 thuộc tính của `employee_store_assignments`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `employee_id`, `store_id`. Không nguyên tố: `granted_by`, `granted_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`employee_id,store_id`); FK `fk_employee_assignments_employee`(`employee_id` → `employees.id`, ON DELETE NO ACTION); FK `fk_employee_assignments_granter`(`granted_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_employee_assignments_store`(`store_id` → `stores.id`, ON DELETE NO ACTION).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.5. `customers`

- **Tên quan hệ và ý nghĩa một dòng:** `customers` — Thông tin cá nhân của khách chơi.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (8 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `full_name` (`varchar(100)`, NOT NULL); `phone` (`char(10)`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL); `email` (`varchar(254)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {full_name, status, created_at, updated_at, email}; {code} → {full_name, status, created_at, updated_at, email}; {phone} → {full_name, status, created_at, updated_at, email}; {id} → {code}; {code} → {phone}; {phone} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code}, {phone} (xác nhận từ migration DDL và repository tầng infrastructure). Lưu ý các UNIQUE nullable (`uq_customers_email`(email)) thực thi duy nhất vật lý khi khác NULL, không tính là khóa ứng viên cổ điển.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → full_name; {id} → status; {id} → created_at; {id} → updated_at; {id} → email; {code} ↔ {id}; {phone} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}, {phone}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 8 thuộc tính của `customers`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu. *(UNIQUE nullable không phải CK: `email`)*.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`, `phone`. Không nguyên tố: `full_name`, `status`, `created_at`, `updated_at`, `email`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_customers_code`(`code`); UK `uq_customers_email`(`email`); UK `uq_customers_phone`(`phone`); CHECK `chk_customers_code_not_blank`; CHECK `chk_customers_full_name_length`; CHECK `chk_customers_phone_format`; CHECK `chk_customers_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.6. `customer_store_links`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_store_links` — Phạm vi khách hàng tại từng cơ sở, suy ra từ giao dịch/phiên hoặc liên kết được xác minh tại quầy.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (4 cột):** `customer_id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `source` (`varchar(24)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {customer_id, store_id} → {source, created_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {customer_id, store_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {customer_id, store_id} → source; {customer_id, store_id} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {customer_id, store_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 4 thuộc tính của `customer_store_links`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `customer_id`, `store_id`. Không nguyên tố: `source`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`customer_id,store_id`); FK `fk_customer_links_customer`(`customer_id` → `customers.id`, ON DELETE NO ACTION); FK `fk_customer_links_store`(`store_id` → `stores.id`, ON DELETE NO ACTION).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.7. `accounts`

- **Tên quan hệ và ý nghĩa một dòng:** `accounts` — Tài khoản đăng nhập máy trạm và ví tiền của khách; mỗi khách đúng một tài khoản.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `customer_id` (`bigint unsigned`, NOT NULL); `username` (`varchar(30)`, NOT NULL); `password_hash` (`varchar(255)`, NULL); `balance` (`bigint`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL); `bonus_balance` (`bigint`, NOT NULL); `auth_version` (`bigint unsigned`, NOT NULL); `web_login_enabled` (`tinyint(1)`, NOT NULL); `email_verified_at` (`datetime`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {password_hash, balance, status, created_at, updated_at, bonus_balance, auth_version, web_login_enabled, email_verified_at}; {code} → {password_hash, balance, status, created_at, updated_at, bonus_balance, auth_version, web_login_enabled, email_verified_at}; {customer_id} → {password_hash, balance, status, created_at, updated_at, bonus_balance, auth_version, web_login_enabled, email_verified_at}; {username} → {password_hash, balance, status, created_at, updated_at, bonus_balance, auth_version, web_login_enabled, email_verified_at}; {id} → {code}; {code} → {customer_id}; {customer_id} → {username}; {username} → {id} }`. Mỗi khách có tối đa 1 tài khoản (`customer_id` UNIQUE NOT NULL). `{id}`, `{code}`, `{customer_id}`, `{username}` đều là khóa ứng viên. Đã loại bỏ cột dẫn xuất `cash_balance = balance - bonus_balance` (NF-01) để không còn FD nội bảng `(balance, bonus_balance) -> cash_balance`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → password_hash; {id} → balance; {id} → status; {id} → created_at; {id} → updated_at; {id} → bonus_balance; {id} → auth_version; {id} → web_login_enabled; {id} → email_verified_at; {code} ↔ {id}; {customer_id} ↔ {id}; {username} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}, {customer_id}, {username}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `accounts`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`, `customer_id`, `username`. Không nguyên tố: `password_hash`, `balance`, `status`, `created_at`, `updated_at`, `bonus_balance`, `auth_version`, `web_login_enabled`, `email_verified_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01): xóa cột sinh `cash_balance`, cung cấp qua view `v_accounts`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_accounts_code`(`code`); UK `uq_accounts_customer`(`customer_id`); UK `uq_accounts_username`(`username`); FK `fk_accounts_customer`(`customer_id` → `customers.id`, ON DELETE RESTRICT); CHECK `chk_accounts_bonus_nonnegative`; CHECK `chk_accounts_code_not_blank`; CHECK `chk_accounts_password_hash_not_blank`; CHECK `chk_accounts_status`; CHECK `chk_accounts_username_format`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** NF-05: `balance` và `bonus_balance` là số dư tổng hợp đồng bộ nguyên tử với sổ cái bất biến `account_transactions` trong cùng transaction có khóa `SELECT ... FOR UPDATE` trên `accounts`.
- **Test và bằng chứng dữ liệu:** `test_wallet_flow.py`, `test_promotion_and_management_flow.py`, `test_3nf_and_integrity.py`; tổng `balance`/`bonus_balance`/`cash_balance` khớp tuyệt đối 0 sai lệch trên clone.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.8. `machines`

- **Tên quan hệ và ý nghĩa một dòng:** `machines` — Máy trạm của cửa hàng và trạng thái hiện tại.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (9 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `name` (`varchar(100)`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `hourly_rate` (`bigint`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {store_id, name, status, hourly_rate, is_active, created_at, updated_at}; {code} → {store_id, name, status, hourly_rate, is_active, created_at, updated_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → store_id; {id} → name; {id} → status; {id} → hourly_rate; {id} → is_active; {id} → created_at; {id} → updated_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 9 thuộc tính của `machines`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `store_id`, `name`, `status`, `hourly_rate`, `is_active`, `created_at`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_machines_code`(`code`); FK `fk_machines_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); CHECK `chk_machines_archived_not_in_use`; CHECK `chk_machines_code_not_blank`; CHECK `chk_machines_hourly_rate`; CHECK `chk_machines_is_active`; CHECK `chk_machines_name_not_blank`; CHECK `chk_machines_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.9. `usage_sessions`

- **Tên quan hệ và ý nghĩa một dòng:** `usage_sessions` — Một lần khách dùng một máy, từ lúc mở đến lúc checkout; ràng buộc chiếm dụng đang hoạt động nằm tại `active_usage_sessions` (chuẩn 3NF).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (11 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `customer_id` (`bigint unsigned`, NOT NULL); `machine_id` (`bigint unsigned`, NOT NULL); `opened_by` (`bigint unsigned`, NOT NULL); `closed_by` (`bigint unsigned`, NULL); `started_at` (`datetime`, NOT NULL); `ended_at` (`datetime`, NULL); `hourly_rate` (`bigint`, NOT NULL); `cost` (`bigint`, NULL); `status` (`varchar(20)`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {customer_id, machine_id, opened_by, closed_by, started_at, ended_at, hourly_rate, cost, status}; {code} → {customer_id, machine_id, opened_by, closed_by, started_at, ended_at, hourly_rate, cost, status}; {id} → {code}; {code} → {id} }`. Mỗi phiên gắn cố định 1 khách và 1 máy (quyết định B01); `hourly_rate` là đơn giá chụp tại lúc mở phiên (B03), không phụ thuộc giá hiện tại của máy. Đã loại bỏ hai cột sinh `active_machine_id`, `active_customer_id` khỏi bảng cơ sở.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → customer_id; {id} → machine_id; {id} → opened_by; {id} → closed_by; {id} → started_at; {id} → ended_at; {id} → hourly_rate; {id} → cost; {id} → status; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 11 thuộc tính của `usage_sessions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `customer_id`, `machine_id`, `opened_by`, `closed_by`, `started_at`, `ended_at`, `hourly_rate`, `cost`, `status`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01 vật lý): tách ràng buộc chiếm dụng đang hoạt động sang bảng 3NF `active_usage_sessions` đồng bộ bằng trigger `trg_usage_sessions_ai/au/bu_no_reopen`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_usage_sessions_code`(`code`); FK `fk_usage_sessions_closed_by`(`closed_by` → `employees.id`, ON DELETE RESTRICT); FK `fk_usage_sessions_customer`(`customer_id` → `customers.id`, ON DELETE RESTRICT); FK `fk_usage_sessions_machine`(`machine_id` → `machines.id`, ON DELETE RESTRICT); FK `fk_usage_sessions_opened_by`(`opened_by` → `employees.id`, ON DELETE RESTRICT); CHECK `chk_usage_sessions_code_not_blank`; CHECK `chk_usage_sessions_cost`; CHECK `chk_usage_sessions_hourly_rate`; CHECK `chk_usage_sessions_state`; CHECK `chk_usage_sessions_status`; CHECK `chk_usage_sessions_time_order`; TRIGGER `trg_usage_sessions_ai`; TRIGGER `trg_usage_sessions_au`; TRIGGER `trg_usage_sessions_bu_no_reopen`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** `SessionService` khóa `machines`, `accounts`, `usage_sessions` theo thứ tự cố định trong transaction để chống deadlock và mở trùng phiên.
- **Test và bằng chứng dữ liệu:** `test_open_session_flow.py`, `test_checkout_flow.py`, `test_3nf_and_integrity.py` (kể cả test concurrent đa kết nối).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.10. `active_usage_sessions`

- **Tên quan hệ và ý nghĩa một dòng:** `active_usage_sessions` — Bảng chiếm dụng 3NF ghi nhận các phiên đang ACTIVE; UNIQUE trên `machine_id` và `customer_id` thay cột sinh để chặn mở trùng.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (3 cột):** `session_id` (`bigint unsigned`, NOT NULL); `machine_id` (`bigint unsigned`, NOT NULL); `customer_id` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {session_id} → {session_id, machine_id, customer_id}; {customer_id} → {session_id, machine_id, customer_id}; {machine_id} → {session_id, machine_id, customer_id} }`. Bảng chiếm dụng 3NF chỉ chứa các phiên `ACTIVE`. Cả ba cột `{session_id}`, `{machine_id}`, `{customer_id}` đều là khóa ứng viên (`PK` và 2 `UNIQUE NOT NULL`) nên mọi thuộc tính đều là thuộc tính nguyên tố — đạt 3NF và BCNF tuyệt đối.
- **Phủ tối thiểu của $F$:** `F_min = { {session_id} → {session_id, machine_id, customer_id}; {customer_id} → {session_id, machine_id, customer_id}; {machine_id} → {session_id, machine_id, customer_id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {session_id}, {customer_id}, {machine_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 3 thuộc tính của `active_usage_sessions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `session_id`, `machine_id`, `customer_id`. Không nguyên tố: *(không có — mọi thuộc tính đều nguyên tố)*.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF) tuyệt đối: không có thuộc tính không nguyên tố; mọi thuộc tính đều thuộc ít nhất một khóa ứng viên.
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01 vật lý): tạo mới thay cho cặp cột sinh `usage_sessions.(active_machine_id, active_customer_id)`; bảo toàn hoàn toàn ràng buộc duy nhất `1 máy / 1 phiên ACTIVE` và `1 khách / 1 phiên ACTIVE`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`session_id`); UK `uq_active_usage_customer`(`customer_id`); UK `uq_active_usage_machine`(`machine_id`); FK `fk_active_usage_customer`(`customer_id` → `customers.id`, ON DELETE RESTRICT); FK `fk_active_usage_machine`(`machine_id` → `machines.id`, ON DELETE RESTRICT); FK `fk_active_usage_session`(`session_id` → `usage_sessions.id`, ON DELETE CASCADE).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Đồng bộ tự động bằng trigger `trg_usage_sessions_ai` (chèn khi mở ACTIVE) và `trg_usage_sessions_au` (xóa khi đóng); `trg_usage_sessions_bu_no_reopen` chặn mở lại phiên đã đóng.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py::test_active_usage_sessions_occupancy_and_no_reopen`, `test_open_session_flow.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.11. `account_transactions`

- **Tên quan hệ và ý nghĩa một dòng:** `account_transactions` — Sổ cái biến động số dư bất biến (chuẩn 3NF, bảo vệ qua trigger `trg_account_transactions_bi/bu`): mọi lần cộng/trừ `accounts.balance` đều có đúng một dòng; liên kết phiên tách sang `session_transactions` (migration 032).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (10 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `type` (`varchar(20)`, NOT NULL); `amount` (`bigint`, NOT NULL); `method` (`varchar(20)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `promotion_id` (`bigint unsigned`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {account_id, employee_id, type, amount, method, created_at, store_id, promotion_id}; {code} → {account_id, employee_id, type, amount, method, created_at, store_id, promotion_id}; {id} → {code}; {code} → {id} }`. `{id}` và `{code}` là khóa ứng viên. `store_id` (`NOT NULL`) là cơ sở phát sinh giao dịch lịch sử nên không phụ thuộc bắc cầu vào `employee_id`; cột `session_id` nullable đã được phân rã sang `session_transactions` (migration `032`).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → account_id; {id} → employee_id; {id} → type; {id} → amount; {id} → method; {id} → created_at; {id} → store_id; {id} → promotion_id; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 10 thuộc tính của `account_transactions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `account_id`, `employee_id`, `type`, `amount`, `method`, `created_at`, `store_id`, `promotion_id`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa.
- **Phép phân rã đề xuất / đã thực hiện:** Migration `032`: tách cột `session_id` nullable sang bảng `session_transactions`, bắt buộc `store_id NOT NULL` và gắn trigger bất biến `trg_account_transactions_bi/bu`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3.6 ở trên.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_account_transactions_code`(`code`); FK `fk_account_transactions_account`(`account_id` → `accounts.id`, ON DELETE RESTRICT); FK `fk_account_transactions_employee`(`employee_id` → `employees.id`, ON DELETE RESTRICT); FK `fk_transactions_promotion`(`promotion_id` → `promotions.id`, ON DELETE RESTRICT); FK `fk_transactions_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); CHECK `chk_account_transactions_amount`; CHECK `chk_account_transactions_code_not_blank`; CHECK `chk_account_transactions_method`; CHECK `chk_account_transactions_type`; CHECK `chk_account_transactions_type_method`; TRIGGER `trg_account_transactions_bi`; TRIGGER `trg_account_transactions_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Sổ cái tiền bất biến (append-only); `WalletService` và `SessionService` ghi `store_id` nguyên tử ngay trong `INSERT` cùng thay đổi `accounts.(balance, bonus_balance)`.
- **Test và bằng chứng dữ liệu:** `test_customer_account_repositories.py`, `test_billing_repositories.py`, `test_wallet_flow.py`, `test_promotion_and_management_flow.py`, `test_3nf_and_integrity.py::test_migration_032_ledger_immutability_and_session_transactions`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng trên MySQL 8.4 (`cyberhub_manager_test`), ngày **23/11/2026**.

### 4.11a. `session_transactions`

- **Tên quan hệ và ý nghĩa một dòng:** `session_transactions` — Bảng phân rã 3NF liên kết giao dịch ví (`USAGE_PAYMENT`, `DEBT_SETTLEMENT`) với phiên sử dụng máy (migration `032`).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (2 cột):** `transaction_id` (`bigint unsigned`, NOT NULL); `session_id` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {transaction_id} → {session_id} }`. Mỗi giao dịch gắn phiên chỉ thuộc duy nhất một phiên sử dụng máy; một phiên có thể có 1 (`USAGE_PAYMENT`) hoặc 2 (`DEBT_SETTLEMENT` + `USAGE_PAYMENT`) giao dịch.
- **Phủ tối thiểu của $F$:** `F_min = { {transaction_id} → session_id }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {transaction_id}. Bao đóng $\{transaction\_id\}^+ = U$ (2 cột) và tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `transaction_id`. Không nguyên tố: `session_id`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF, 2NF và 3NF/BCNF tuyệt đối (chỉ có 1 FD duy nhất có vế trái là khóa chính).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `032`: tạo mới để tách quan hệ 0..1 từ `account_transactions.session_id`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3.6 ở trên.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`transaction_id`); FK `fk_session_transactions_tx`(`transaction_id` → `account_transactions.id`, ON DELETE RESTRICT); FK `fk_session_transactions_session`(`session_id` → `usage_sessions.id`, ON DELETE RESTRICT); INDEX `idx_session_transactions_session`(`session_id`); TRIGGER `trg_session_transactions_bi`; TRIGGER `trg_session_transactions_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** `AccountRepository.insert_usage_payment_transaction` và `insert_debt_settlement_transaction` ghi nguyên tử vào `account_transactions` + `session_transactions` trong cùng transaction checkout; trigger kiểm tra loại giao dịch, khớp `account_id`, khớp `store_id` và chặn sửa liên kết.
- **Test và bằng chứng dữ liệu:** `test_billing_repositories.py`, `test_checkout_flow.py`, `test_3nf_and_integrity.py::test_migration_032_ledger_immutability_and_session_transactions`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng trên MySQL 8.4 (`cyberhub_manager_test`), ngày **23/11/2026**.

### 4.12. `invoices`

- **Tên quan hệ và ý nghĩa một dòng:** `invoices` — Hóa đơn tạo khi checkout thành công; khóa ứng viên `session_id` (UNIQUE), tham chiếu phiên bản chính sách điểm bất biến (`loyalty_policy_versions`). Các giá trị dẫn xuất (`total_amount`, `loyalty_eligible_amount`, `loyalty_points`, `loyalty_unit`) tính qua view `v_invoices`.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (12 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `session_id` (`bigint unsigned`, NOT NULL); `customer_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `usage_cost` (`bigint`, NOT NULL); `settlement_amount` (`bigint`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `bonus_used` (`bigint`, NOT NULL); `loyalty_rule_version` (`int unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {customer_id, employee_id, store_id, usage_cost, settlement_amount, status, created_at, bonus_used, loyalty_rule_version}; {code} → {customer_id, employee_id, store_id, usage_cost, settlement_amount, status, created_at, bonus_used, loyalty_rule_version}; {session_id} → {customer_id, employee_id, store_id, usage_cost, settlement_amount, status, created_at, bonus_used, loyalty_rule_version}; {id} → {code}; {code} → {session_id}; {session_id} → {id} }`. `{id}`, `{code}`, `{session_id}` đều là khóa ứng viên (`session_id` UNIQUE NOT NULL). Do `session_id` là siêu khóa, các FD `session_id -> customer_id` và `session_id -> store_id` KHÔNG vi phạm 3NF/BCNF. Các cột dẫn xuất `total_amount`, `loyalty_eligible_amount`, `loyalty_points`, `loyalty_unit` đã loại bỏ (NF-01/NF-04); chỉ giữ FK `loyalty_rule_version -> loyalty_policy_versions(version)`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → customer_id; {id} → employee_id; {id} → store_id; {id} → usage_cost; {id} → settlement_amount; {id} → status; {id} → created_at; {id} → bonus_used; {id} → loyalty_rule_version; {code} ↔ {id}; {session_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}, {session_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 12 thuộc tính của `invoices`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`, `session_id`. Không nguyên tố: `customer_id`, `employee_id`, `store_id`, `usage_cost`, `settlement_amount`, `status`, `created_at`, `bonus_used`, `loyalty_rule_version`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01 + NF-04): tách `loyalty_policy_versions`, xóa 4 cột dẫn xuất trên `invoices`, tạo view `v_invoices`; migration `030` thêm trigger `trg_invoices_bi/bu` khóa chặt `customer_id`/`store_id` khớp `usage_sessions`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_invoices_code`(`code`); UK `uq_invoices_session`(`session_id`); FK `fk_invoices_customer`(`customer_id` → `customers.id`, ON DELETE RESTRICT); FK `fk_invoices_employee`(`employee_id` → `employees.id`, ON DELETE RESTRICT); FK `fk_invoices_loyalty_version`(`loyalty_rule_version` → `loyalty_policy_versions.version`, ON DELETE RESTRICT); FK `fk_invoices_session`(`session_id` → `usage_sessions.id`, ON DELETE RESTRICT); FK `fk_invoices_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); CHECK `chk_invoices_bonus_used`; CHECK `chk_invoices_code_not_blank`; CHECK `chk_invoices_money`; CHECK `chk_invoices_settlement`; CHECK `chk_invoices_status`; TRIGGER `trg_invoices_bi`; TRIGGER `trg_invoices_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** `SessionService.complete_checkout` tạo hóa đơn nguyên tử cùng đóng phiên và trừ ví; `InvoiceRepository` đọc chính sách qua `loyalty_policy_versions` để không làm đổi điểm lịch sử.
- **Test và bằng chứng dữ liệu:** `test_billing_repositories.py`, `test_customer_membership.py`, `test_3nf_and_integrity.py`; tổng doanh thu và điểm khớp tuyệt đối trên clone.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.13. `promotions`

- **Tên quan hệ và ý nghĩa một dòng:** `promotions` — Chính sách thưởng theo mốc nạp, phạm vi và thời gian.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `name` (`varchar(100)`, NOT NULL); `store_id` (`bigint unsigned`, NULL); `minimum_amount` (`bigint`, NOT NULL); `bonus_percent` (`int`, NOT NULL); `starts_at` (`datetime`, NOT NULL); `ends_at` (`datetime`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `minimum_tier` (`varchar(10)`, NOT NULL); `minimum_points` (`bigint`, NOT NULL); `target_customer_id` (`bigint unsigned`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {name, store_id, minimum_amount, bonus_percent, starts_at, ends_at, is_active, created_at, minimum_tier, minimum_points, target_customer_id}; {code} → {name, store_id, minimum_amount, bonus_percent, starts_at, ends_at, is_active, created_at, minimum_tier, minimum_points, target_customer_id}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → name; {id} → store_id; {id} → minimum_amount; {id} → bonus_percent; {id} → starts_at; {id} → ends_at; {id} → is_active; {id} → created_at; {id} → minimum_tier; {id} → minimum_points; {id} → target_customer_id; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `promotions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `name`, `store_id`, `minimum_amount`, `bonus_percent`, `starts_at`, `ends_at`, `is_active`, `created_at`, `minimum_tier`, `minimum_points`, `target_customer_id`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `code`(`code`); FK `fk_promotion_target_customer`(`target_customer_id` → `customers.id`, ON DELETE RESTRICT); FK `fk_promotions_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); CHECK `chk_promotion_points`; CHECK `chk_promotion_tier`; CHECK `chk_promotions_amount`; CHECK `chk_promotions_percent`; CHECK `chk_promotions_period`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.14. `management_audit`

- **Tên quan hệ và ý nghĩa một dòng:** `management_audit` — Lịch sử thay đổi quản trị, không lưu mật khẩu.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (6 cột):** `id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `action` (`varchar(40)`, NOT NULL); `entity_id` (`bigint unsigned`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {employee_id, store_id, action, entity_id, created_at} }`. Khóa chính `{id}` xác định duy nhất mỗi sự kiện audit quản trị (`employee_id`, `store_id`, `action`, `entity_id`, `created_at`). `store_id` là cơ sở đang vận hành tại thời điểm thực hiện (không đồng nghĩa `home_store_id` hiện tại của nhân viên, vì DIRECTOR/MANAGER đổi cơ sở thao tác).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → employee_id; {id} → store_id; {id} → action; {id} → entity_id; {id} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 6 thuộc tính của `management_audit`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `employee_id`, `store_id`, `action`, `entity_id`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_management_audit_employee`(`employee_id` → `employees.id`, ON DELETE RESTRICT); FK `fk_management_audit_store`(`store_id` → `stores.id`, ON DELETE RESTRICT).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Giới hạn công bố (INT-03 & SEC-01): `entity_id` là tham chiếu đa hình; tính bất biến của bảng audit được thực thi qua ứng dụng (chưa tách tài khoản DB runtime chỉ có quyền INSERT).
- **Test và bằng chứng dữ liệu:** `test_report_flow.py`, `test_web_mysql.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.15. `customer_notification_reads`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_notification_reads` — Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (3 cột):** `account_id` (`bigint unsigned`, NOT NULL); `notification_key` (`varchar(100)`, NOT NULL); `read_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {account_id, notification_key} → {read_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {account_id, notification_key} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {account_id, notification_key} → read_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {account_id, notification_key}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 3 thuộc tính của `customer_notification_reads`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `account_id`, `notification_key`. Không nguyên tố: `read_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`account_id,notification_key`); FK `fk_customer_notification_account`(`account_id` → `accounts.id`, ON DELETE RESTRICT).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.16. `machine_room_types`

- **Tên quan hệ và ý nghĩa một dòng:** `machine_room_types` — Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (2 cột):** `machine_id` (`bigint unsigned`, NOT NULL); `room_type` (`varchar(10)`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {machine_id} → {room_type} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {machine_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {machine_id} → room_type }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {machine_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 2 thuộc tính của `machine_room_types`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `machine_id`. Không nguyên tố: `room_type`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`machine_id`); FK `fk_machine_room_machine`(`machine_id` → `machines.id`, ON DELETE CASCADE); CHECK `chk_machine_room_type`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.17. `loyalty_policy_versions`

- **Tên quan hệ và ý nghĩa một dòng:** `loyalty_policy_versions` — Phiên bản bất biến của chính sách tích điểm và xét hạng thành viên; hóa đơn lịch sử tham chiếu đúng version đã áp dụng (NF-01/NF-04).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `version` (`int unsigned`, NOT NULL); `enabled` (`tinyint(1)`, NOT NULL); `unit_amount` (`bigint`, NOT NULL); `silver_spend` (`bigint`, NOT NULL); `gold_spend` (`bigint`, NOT NULL); `platinum_spend` (`bigint`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {version} → {enabled, unit_amount, silver_spend, gold_spend, platinum_spend, created_at} }`. Khóa chính tự nhiên `{version}` xác định duy nhất toàn bộ cấu hình bất biến (`enabled`, `unit_amount`, `silver_spend`, `gold_spend`, `platinum_spend`, `created_at`). Không có FD giữa các thuộc tính không khóa.
- **Phủ tối thiểu của $F$:** `F_min = { {version} → enabled; {version} → unit_amount; {version} → silver_spend; {version} → gold_spend; {version} → platinum_spend; {version} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {version}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `loyalty_policy_versions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `version`. Không nguyên tố: `enabled`, `unit_amount`, `silver_spend`, `gold_spend`, `platinum_spend`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01 + NF-04): tách khỏi `loyalty_settings` và backfill từ `loyalty_settings` + `invoices` lịch sử.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`version`); CHECK `chk_loyalty_ver_tiers`; CHECK `chk_loyalty_ver_unit`; CHECK `chk_loyalty_ver_version`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Bản ghi bất biến (append-only); mỗi lần Admin cập nhật chính sách sẽ tạo `version = current_version + 1` và dịch con trỏ `loyalty_settings.current_version`.
- **Test và bằng chứng dữ liệu:** `test_customer_membership.py`, `test_3nf_and_integrity.py::test_loyalty_policy_version_preserves_historical_invoice_points`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.18. `loyalty_settings`

- **Tên quan hệ và ý nghĩa một dòng:** `loyalty_settings` — Con trỏ singleton (id=1) trỏ tới phiên bản chính sách tích điểm đang hiệu lực; chỉ Admin được cập nhật kèm khóa lạc quan theo version.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (3 cột):** `id` (`tinyint unsigned`, NOT NULL); `current_version` (`int unsigned`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {current_version, updated_at} }`. Bảng singleton `id = 1` chỉ giữ con trỏ `current_version` (FK -> `loyalty_policy_versions.version`) và `updated_at`. Toàn bộ thuộc tính chính sách nằm ở `loyalty_policy_versions`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → current_version; {id} → updated_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 3 thuộc tính của `loyalty_settings`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `current_version`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-04): loại bỏ `enabled`, `unit_amount`, `silver_spend`, `gold_spend`, `platinum_spend`, `version`; thay bằng `current_version`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_loyalty_settings_version`(`current_version` → `loyalty_policy_versions.version`, ON DELETE RESTRICT); CHECK `chk_loyalty_singleton`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Cập nhật dùng khóa lạc quan (`WHERE id = 1 AND current_version = %s`) trong transaction của `ManagementService`.
- **Test và bằng chứng dữ liệu:** `test_customer_membership.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.19. `customer_avatars`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_avatars` — Ảnh đại diện riêng theo tài khoản; WebP 512×512 đã chuẩn hóa, không giữ tên file hay metadata gốc.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (4 cột):** `account_id` (`bigint unsigned`, NOT NULL); `image_data` (`mediumblob`, NOT NULL); `digest` (`char(64)`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {account_id} → {image_data, digest, updated_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {account_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {account_id} → image_data; {account_id} → digest; {account_id} → updated_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {account_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 4 thuộc tính của `customer_avatars`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `account_id`. Không nguyên tố: `image_data`, `digest`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`account_id`); FK `fk_customer_avatar_account`(`account_id` → `accounts.id`, ON DELETE CASCADE).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.20. `menu_categories`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_categories` — Nhóm món theo cơ sở, xếp vào trang Đồ ăn (FOOD) hoặc Đồ uống (DRINK).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `page` (`varchar(10)`, NOT NULL); `name` (`varchar(60)`, NOT NULL); `sort_order` (`int`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {page, sort_order, is_active, created_at}; {store_id, name} → {page, sort_order, is_active, created_at}; {id} → {store_id, name}; {store_id, name} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {store_id, name} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → page; {id} → sort_order; {id} → is_active; {id} → created_at; {store_id, name} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {store_id, name}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `menu_categories`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `store_id`, `name`. Không nguyên tố: `page`, `sort_order`, `is_active`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_menu_categories_store_name`(`store_id,name`); FK `fk_menu_categories_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); CHECK `chk_menu_categories_name`; CHECK `chk_menu_categories_page`; CHECK `chk_menu_categories_sort`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.21. `menu_items`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_items` — Món ăn/đồ uống của cơ sở; cơ sở suy ra từ `menu_categories.store_id` (NF-02), tên món duy nhất toàn cơ sở qua trigger `trg_menu_items_bi/bu`.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (11 cột):** `id` (`bigint unsigned`, NOT NULL); `category_id` (`bigint unsigned`, NOT NULL); `name` (`varchar(80)`, NOT NULL); `description` (`varchar(200)`, NOT NULL); `price` (`bigint`, NOT NULL); `sort_order` (`int`, NOT NULL); `is_visible` (`tinyint(1)`, NOT NULL); `is_available` (`tinyint(1)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL); `is_stock_tracked` (`tinyint(1)`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {description, price, sort_order, is_visible, is_available, created_at, updated_at, is_stock_tracked}; {category_id, name} → {description, price, sort_order, is_visible, is_available, created_at, updated_at, is_stock_tracked}; {id} → {category_id, name}; {category_id, name} → {id} }`. `{id}` và `{category_id, name}` là khóa ứng viên. Đã loại bỏ cột lặp bắc cầu `store_id` (NF-02) vì `category_id -> store_id` theo `menu_categories`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → description; {id} → price; {id} → sort_order; {id} → is_visible; {id} → is_available; {id} → created_at; {id} → updated_at; {id} → is_stock_tracked; {category_id, name} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {category_id, name}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 11 thuộc tính của `menu_items`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `category_id`, `name`. Không nguyên tố: `description`, `price`, `sort_order`, `is_visible`, `is_available`, `created_at`, `updated_at`, `is_stock_tracked`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `menu_items.store_id`, thêm `UNIQUE(category_id, name)` và view `v_menu_items`; migration `030` thêm trigger `trg_menu_items_bi/bu` bảo đảm tên món duy nhất trên toàn cơ sở dù khác nhóm.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_menu_items_category_name`(`category_id,name`); FK `fk_menu_items_category`(`category_id` → `menu_categories.id`, ON DELETE RESTRICT); CHECK `chk_menu_items_name`; CHECK `chk_menu_items_price`; CHECK `chk_menu_items_sort`; TRIGGER `trg_menu_items_bi`; TRIGGER `trg_menu_items_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** `MenuCatalogMixin.save_item` kiểm tra danh mục cùng cơ sở và ghi nhật ký `menu_item_changes` trong cùng transaction.
- **Test và bằng chứng dữ liệu:** `test_dot1_menu_repository.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.22. `menu_item_images`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_item_images` — Ảnh món đã chuẩn hóa (WebP 512×512, không metadata).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (4 cột):** `item_id` (`bigint unsigned`, NOT NULL); `image_data` (`mediumblob`, NOT NULL); `digest` (`char(64)`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {item_id} → {image_data, digest, updated_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {item_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {item_id} → image_data; {item_id} → digest; {item_id} → updated_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {item_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 4 thuộc tính của `menu_item_images`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `item_id`. Không nguyên tố: `image_data`, `digest`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`item_id`); FK `fk_menu_item_images_item`(`item_id` → `menu_items.id`, ON DELETE RESTRICT).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.23. `menu_item_changes`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_item_changes` — Lịch sử thay đổi giá, tên, nhóm, ảnh và trạng thái bán; chỉ thêm, không sửa.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `item_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `field` (`varchar(20)`, NOT NULL); `old_value` (`varchar(200)`, NULL); `new_value` (`varchar(200)`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {item_id, employee_id, field, old_value, new_value, created_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → item_id; {id} → employee_id; {id} → field; {id} → old_value; {id} → new_value; {id} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `menu_item_changes`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `item_id`, `employee_id`, `field`, `old_value`, `new_value`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_menu_item_changes_employee`(`employee_id` → `employees.id`, ON DELETE RESTRICT); FK `fk_menu_item_changes_item`(`item_id` → `menu_items.id`, ON DELETE RESTRICT); CHECK `chk_menu_item_changes_field`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.24. `menu_orders`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_orders` — Đơn POS đồ ăn/thức uống của khách đang chơi; cơ sở, máy và tài khoản suy ra từ `usage_sessions` (NF-02), đọc đầy đủ qua `v_menu_orders`.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (14 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `session_id` (`bigint unsigned`, NOT NULL); `note` (`varchar(200)`, NOT NULL); `total_amount` (`bigint`, NOT NULL); `status` (`varchar(12)`, NOT NULL); `handled_by` (`bigint unsigned`, NULL); `payment_method` (`varchar(10)`, NULL); `paid_at` (`datetime`, NULL); `paid_by` (`bigint unsigned`, NULL); `created_at` (`datetime`, NOT NULL); `reservation_expires_at` (`datetime`, NULL); `updated_at` (`datetime`, NOT NULL); `cancel_reason` (`varchar(255)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {session_id, note, total_amount, status, handled_by, payment_method, paid_at, paid_by, created_at, reservation_expires_at, updated_at, cancel_reason}; {code} → {session_id, note, total_amount, status, handled_by, payment_method, paid_at, paid_by, created_at, reservation_expires_at, updated_at, cancel_reason}; {id} → {code}; {code} → {id} }`. `{id}` và `{code}` là khóa ứng viên. Đã loại bỏ 3 cột lặp bắc cầu `store_id`, `machine_id`, `account_id` (NF-02) vì `session_id` xác định duy nhất phiên -> máy -> cơ sở và khách -> tài khoản (quyết định B01).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → session_id; {id} → note; {id} → total_amount; {id} → status; {id} → handled_by; {id} → payment_method; {id} → paid_at; {id} → paid_by; {id} → created_at; {id} → reservation_expires_at; {id} → updated_at; {id} → cancel_reason; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 14 thuộc tính của `menu_orders`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `session_id`, `note`, `total_amount`, `status`, `handled_by`, `payment_method`, `paid_at`, `paid_by`, `created_at`, `reservation_expires_at`, `updated_at`, `cancel_reason`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, `machine_id`, `account_id`, cung cấp view `v_menu_orders`; migration `030` siết `chk_menu_orders_payment` chống lỗ hổng `NULL/UNKNOWN`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_menu_orders_code`(`code`); FK `fk_menu_orders_handled_by`(`handled_by` → `employees.id`, ON DELETE RESTRICT); FK `fk_menu_orders_paid_by`(`paid_by` → `employees.id`, ON DELETE RESTRICT); FK `fk_menu_orders_session`(`session_id` → `usage_sessions.id`, ON DELETE RESTRICT); CHECK `chk_menu_orders_handled`; CHECK `chk_menu_orders_payment`; CHECK `chk_menu_orders_status`; CHECK `chk_menu_orders_total`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** NF-05: `total_amount` là tổng tiền snapshot chụp từ `menu_order_items` lúc đặt; mọi chuyển trạng thái đơn và giữ/xuất kho nguyên liệu chạy nguyên tử trong cùng transaction.
- **Test và bằng chứng dữ liệu:** `test_dot1_menu_repository.py`, `test_inventory_order_lifecycle.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.25. `menu_order_items`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_order_items` — Từng món trong yêu cầu gọi món, với tên và giá chụp lúc đặt.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (5 cột):** `order_id` (`bigint unsigned`, NOT NULL); `item_id` (`bigint unsigned`, NOT NULL); `item_name` (`varchar(80)`, NOT NULL); `unit_price` (`bigint`, NOT NULL); `quantity` (`int`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {order_id, item_id} → {item_name, unit_price, quantity} }`. Khóa chính ghép `(order_id, item_id)`. `item_name` và `unit_price` là **snapshot lịch sử tại thời điểm đặt đơn**, phụ thuộc đầy đủ vào cả `(order_id, item_id)` (không phụ thuộc riêng `item_id` vì giá/tên món có thể đổi sau khi đặt — Mục 3.2). Do đó không có phụ thuộc một phần -> đạt 2NF & 3NF.
- **Phủ tối thiểu của $F$:** `F_min = { {order_id, item_id} → item_name; {order_id, item_id} → unit_price; {order_id, item_id} → quantity }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {order_id, item_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 5 thuộc tính của `menu_order_items`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `order_id`, `item_id`. Không nguyên tố: `item_name`, `unit_price`, `quantity`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (đạt sẵn 3NF/BCNF).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`order_id,item_id`); FK `fk_menu_order_items_item`(`item_id` → `menu_items.id`, ON DELETE RESTRICT); FK `fk_menu_order_items_order`(`order_id` → `menu_orders.id`, ON DELETE RESTRICT); CHECK `chk_menu_order_items_price`; CHECK `chk_menu_order_items_quantity`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Ghi bất biến trong cùng transaction tạo `menu_orders` và `menu_order_recipe_snapshots`.
- **Test và bằng chứng dữ liệu:** `test_dot1_menu_repository.py`, `test_inventory_order_lifecycle.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.26. `inventory_ingredients`

- **Tên quan hệ và ý nghĩa một dòng:** `inventory_ingredients` — Nguyên liệu tồn kho theo từng cửa hàng; lượng khả dụng bằng tồn thực tế trừ lượng đã giữ chỗ.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (9 cột):** `id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `code` (`varchar(32)`, NOT NULL); `name` (`varchar(100)`, NOT NULL); `unit` (`varchar(4)`, NOT NULL); `on_hand` (`bigint`, NOT NULL); `reserved` (`bigint`, NOT NULL); `reorder_point` (`bigint`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {name, unit, on_hand, reserved, reorder_point, is_active}; {store_id, code} → {name, unit, on_hand, reserved, reorder_point, is_active}; {id} → {store_id, code}; {store_id, code} → {id} }`. `{id}` và `{store_id, code}` là khóa ứng viên (`(store_id, id)` là siêu khóa phụ phục vụ chỉ mục). Không có FD giữa thuộc tính không khóa.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → name; {id} → unit; {id} → on_hand; {id} → reserved; {id} → reorder_point; {id} → is_active; {store_id, code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {store_id, code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 9 thuộc tính của `inventory_ingredients`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `store_id`, `code`. Không nguyên tố: `name`, `unit`, `on_hand`, `reserved`, `reorder_point`, `is_active`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_inventory_ingredients_store_code`(`store_id,code`); UK `uq_inventory_ingredients_store_id`(`store_id,id`); FK `fk_inventory_ingredients_store`(`store_id` → `stores.id`, ON DELETE NO ACTION); CHECK `chk_inventory_ingredients_balance`; CHECK `chk_inventory_ingredients_unit`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** NF-05: `on_hand` và `reserved` là tồn tổng hợp đồng bộ nguyên tử với sổ cái `inventory_movements` dưới khóa `FOR UPDATE`; CHECK bảo đảm `0 <= reserved <= on_hand`.
- **Test và bằng chứng dữ liệu:** `test_inventory_order_lifecycle.py`, `test_operational_workflows.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.27. `menu_item_recipes`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_item_recipes` — Công thức hiện hành của món có theo dõi kho.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (3 cột):** `item_id` (`bigint unsigned`, NOT NULL); `ingredient_id` (`bigint unsigned`, NOT NULL); `quantity_per_unit` (`bigint`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {item_id, ingredient_id} → {quantity_per_unit} }`. Khóa chính ghép `(item_id, ingredient_id)` xác định duy nhất `quantity_per_unit` (> 0). Mọi thuộc tính không khóa phụ thuộc đầy đủ vào cả hai thành phần khóa.
- **Phủ tối thiểu của $F$:** `F_min = { {item_id, ingredient_id} → quantity_per_unit }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {item_id, ingredient_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 3 thuộc tính của `menu_item_recipes`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `item_id`, `ingredient_id`. Không nguyên tố: `quantity_per_unit`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm trigger `trg_menu_item_recipes_bi/bu` bắt buộc món và nguyên liệu thuộc cùng cơ sở.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`item_id,ingredient_id`); FK `fk_menu_item_recipes_ingredient`(`ingredient_id` → `inventory_ingredients.id`, ON DELETE NO ACTION); FK `fk_menu_item_recipes_item`(`item_id` → `menu_items.id`, ON DELETE NO ACTION); CHECK `chk_menu_item_recipes_quantity`; TRIGGER `trg_menu_item_recipes_bi`; TRIGGER `trg_menu_item_recipes_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thay đổi công thức không ảnh hưởng các đơn đã đặt (đã chụp vào `menu_order_recipe_snapshots`).
- **Test và bằng chứng dữ liệu:** `test_inventory_order_lifecycle.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.28. `menu_order_recipe_snapshots`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_order_recipe_snapshots` — Ảnh chụp nhu cầu nguyên liệu của từng dòng đơn, giúp đổi công thức sau này không làm sai giữ/xuất kho cũ.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (4 cột):** `order_id` (`bigint unsigned`, NOT NULL); `item_id` (`bigint unsigned`, NOT NULL); `ingredient_id` (`bigint unsigned`, NOT NULL); `quantity` (`bigint`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {order_id, item_id, ingredient_id} → {quantity} }`. Khóa chính ghép `(order_id, item_id, ingredient_id)` với FK ghép `(order_id, item_id) -> menu_order_items`. `quantity` là tổng lượng nguyên liệu chụp cho dòng đơn tại lúc đặt, phụ thuộc đầy đủ cả 3 thành phần khóa.
- **Phủ tối thiểu của $F$:** `F_min = { {order_id, item_id, ingredient_id} → quantity }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {order_id, item_id, ingredient_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 4 thuộc tính của `menu_order_recipe_snapshots`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `order_id`, `item_id`, `ingredient_id`. Không nguyên tố: `quantity`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (đạt sẵn 3NF/BCNF).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`order_id,item_id,ingredient_id`); FK `fk_menu_order_recipe_snapshots_ingredient`(`ingredient_id` → `inventory_ingredients.id`, ON DELETE NO ACTION); FK `fk_menu_order_recipe_snapshots_line`(`order_id,item_id` → `menu_order_items.order_id,item_id`, ON DELETE NO ACTION); CHECK `chk_menu_order_recipe_snapshots_quantity`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Giúp đổi công thức `menu_item_recipes` về sau không làm sai hoàn giữ tồn/tiêu thụ của đơn cũ.
- **Test và bằng chứng dữ liệu:** `test_inventory_order_lifecycle.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.29. `inventory_movements`

- **Tên quan hệ và ý nghĩa một dòng:** `inventory_movements` — Sổ cái kho bất biến: nhập, giữ chỗ, hoàn giữ chỗ, tiêu thụ, hao hụt, trả và điều chỉnh; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `ingredient_id` (`bigint unsigned`, NOT NULL); `order_id` (`bigint unsigned`, NULL); `employee_id` (`bigint unsigned`, NULL); `account_id` (`bigint unsigned`, NULL); `kind` (`varchar(10)`, NOT NULL); `quantity` (`bigint`, NOT NULL); `on_hand_delta` (`bigint`, NOT NULL); `reserved_delta` (`bigint`, NOT NULL); `idempotency_key` (`varchar(100)`, NOT NULL); `reference_code` (`varchar(60)`, NULL); `note` (`varchar(255)`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {ingredient_id, order_id, employee_id, account_id, kind, quantity, on_hand_delta, reserved_delta, reference_code, note, created_at}; {idempotency_key} → {ingredient_id, order_id, employee_id, account_id, kind, quantity, on_hand_delta, reserved_delta, reference_code, note, created_at}; {id} → {idempotency_key}; {idempotency_key} → {id} }`. `{id}` và `{idempotency_key}` là khóa ứng viên. Đã loại bỏ cột lặp bắc cầu `store_id` (NF-02) vì `ingredient_id -> store_id` trong `inventory_ingredients`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → ingredient_id; {id} → order_id; {id} → employee_id; {id} → account_id; {id} → kind; {id} → quantity; {id} → on_hand_delta; {id} → reserved_delta; {id} → reference_code; {id} → note; {id} → created_at; {idempotency_key} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {idempotency_key}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `inventory_movements`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `idempotency_key`. Không nguyên tố: `ingredient_id`, `order_id`, `employee_id`, `account_id`, `kind`, `quantity`, `on_hand_delta`, `reserved_delta`, `reference_code`, `note`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, chuyển FK sang `ingredient_id -> inventory_ingredients(id)`, cung cấp view `v_inventory_movements`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_inventory_movements_key`(`idempotency_key`); FK `fk_inventory_movements_account`(`account_id` → `accounts.id`, ON DELETE NO ACTION); FK `fk_inventory_movements_employee`(`employee_id` → `employees.id`, ON DELETE NO ACTION); FK `fk_inventory_movements_ingredient`(`ingredient_id` → `inventory_ingredients.id`, ON DELETE RESTRICT); FK `fk_inventory_movements_order`(`order_id` → `menu_orders.id`, ON DELETE NO ACTION); CHECK `chk_inventory_movements_kind`; CHECK `chk_inventory_movements_quantity`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Sổ cái kho append-only; đồng bộ cùng `inventory_ingredients.(on_hand, reserved)` dưới khóa `FOR UPDATE` và khóa chống lặp `idempotency_key`.
- **Test và bằng chứng dữ liệu:** `test_inventory_order_lifecycle.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.30. `inventory_counts`

- **Tên quan hệ và ý nghĩa một dòng:** `inventory_counts` — Phiếu kiểm kê đề xuất; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02), người phê duyệt bắt buộc khác `proposed_by` (CHECK SoD).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `ingredient_id` (`bigint unsigned`, NOT NULL); `request_id` (`char(32)`, NOT NULL); `expected_on_hand` (`bigint`, NOT NULL); `expected_reserved` (`bigint`, NOT NULL); `expected_movement_id` (`bigint unsigned`, NOT NULL); `counted_on_hand` (`bigint`, NOT NULL); `proposed_by` (`bigint unsigned`, NOT NULL); `decided_by` (`bigint unsigned`, NULL); `status` (`varchar(10)`, NOT NULL); `reason` (`varchar(255)`, NOT NULL); `created_at` (`datetime`, NOT NULL); `decided_at` (`datetime`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {ingredient_id, expected_on_hand, expected_reserved, expected_movement_id, counted_on_hand, proposed_by, decided_by, status, reason, created_at, decided_at}; {request_id} → {ingredient_id, expected_on_hand, expected_reserved, expected_movement_id, counted_on_hand, proposed_by, decided_by, status, reason, created_at, decided_at}; {id} → {request_id}; {request_id} → {id} }`. `{id}` và `{request_id}` là khóa ứng viên. Đã loại bỏ cột lặp bắc cầu `store_id` (NF-02) vì `ingredient_id -> store_id`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → ingredient_id; {id} → expected_on_hand; {id} → expected_reserved; {id} → expected_movement_id; {id} → counted_on_hand; {id} → proposed_by; {id} → decided_by; {id} → status; {id} → reason; {id} → created_at; {id} → decided_at; {request_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {request_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `inventory_counts`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `request_id`. Không nguyên tố: `ingredient_id`, `expected_on_hand`, `expected_reserved`, `expected_movement_id`, `counted_on_hand`, `proposed_by`, `decided_by`, `status`, `reason`, `created_at`, `decided_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, cung cấp view `v_inventory_counts`; migration `030` thêm `chk_inventory_counts_decision` (NULL-safe + SoD `decided_by <> proposed_by` + `decided_at >= created_at`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_inventory_counts_request`(`request_id`); FK `fk_inventory_counts_decider`(`decided_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_inventory_counts_ingredient`(`ingredient_id` → `inventory_ingredients.id`, ON DELETE RESTRICT); FK `fk_inventory_counts_proposer`(`proposed_by` → `employees.id`, ON DELETE NO ACTION); CHECK `chk_inventory_counts_decision`; CHECK `chk_inventory_counts_quantities`; CHECK `chk_inventory_counts_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Chặn duyệt khi sổ kho đã phát sinh bút toán mới hơn `expected_movement_id`.
- **Test và bằng chứng dữ liệu:** `test_inventory_order_lifecycle.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.31. `customer_notification_events`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_notification_events` — Sổ sự kiện thông báo bền vững cho khách theo vòng đời đơn; khóa sự kiện chống phát trùng.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (8 cột):** `id` (`bigint unsigned`, NOT NULL); `notification_key` (`varchar(100)`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `kind` (`varchar(40)`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `amount` (`int unsigned`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {account_id, store_id, kind, code, amount, created_at}; {notification_key} → {account_id, store_id, kind, code, amount, created_at}; {id} → {notification_key}; {notification_key} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {notification_key} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → account_id; {id} → store_id; {id} → kind; {id} → code; {id} → amount; {id} → created_at; {notification_key} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {notification_key}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 8 thuộc tính của `customer_notification_events`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `notification_key`. Không nguyên tố: `account_id`, `store_id`, `kind`, `code`, `amount`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_customer_notification_event_key`(`notification_key`); FK `fk_customer_notification_event_account`(`account_id` → `accounts.id`, ON DELETE NO ACTION); FK `fk_customer_notification_event_store`(`store_id` → `stores.id`, ON DELETE NO ACTION).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.32. `pos_order_reversals`

- **Tên quan hệ và ý nghĩa một dòng:** `pos_order_reversals` — Yêu cầu hoàn/hủy toàn bộ đơn POS có maker-checker và quyết định hoàn kho hoặc ghi hao hụt; cơ sở suy ra từ `menu_orders` qua `usage_sessions`→`machines` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (12 cột):** `id` (`bigint unsigned`, NOT NULL); `order_id` (`bigint unsigned`, NOT NULL); `requested_by` (`bigint unsigned`, NOT NULL); `reason` (`varchar(255)`, NOT NULL); `disposition` (`varchar(8)`, NOT NULL); `status` (`varchar(10)`, NOT NULL); `decided_by` (`bigint unsigned`, NULL); `decided_at` (`datetime`, NULL); `refund_amount` (`bigint unsigned`, NOT NULL); `refund_method` (`varchar(10)`, NULL); `refund_reference` (`varchar(100)`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {requested_by, reason, disposition, status, decided_by, decided_at, refund_amount, refund_method, refund_reference, created_at}; {order_id} → {requested_by, reason, disposition, status, decided_by, decided_at, refund_amount, refund_method, refund_reference, created_at}; {id} → {order_id}; {order_id} → {id} }`. `{id}` và `{order_id}` là khóa ứng viên (mỗi đơn tối đa 1 yêu cầu hoàn/hủy — B07). Đã loại bỏ `store_id` lặp bắc cầu qua `order_id -> session_id -> machine_id -> store_id` (NF-02).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → requested_by; {id} → reason; {id} → disposition; {id} → status; {id} → decided_by; {id} → decided_at; {id} → refund_amount; {id} → refund_method; {id} → refund_reference; {id} → created_at; {order_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {order_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 12 thuộc tính của `pos_order_reversals`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `order_id`. Không nguyên tố: `requested_by`, `reason`, `disposition`, `status`, `decided_by`, `decided_at`, `refund_amount`, `refund_method`, `refund_reference`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, tạo view `v_pos_order_reversals`; migration `030` thêm `chk_pos_reversal_sod` (`decided_by <> requested_by`) và `chk_pos_reversal_refund` (NULL-safe).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_pos_reversal_order`(`order_id`); FK `fk_pos_reversal_approver`(`decided_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_pos_reversal_order`(`order_id` → `menu_orders.id`, ON DELETE NO ACTION); FK `fk_pos_reversal_requester`(`requested_by` → `employees.id`, ON DELETE NO ACTION); CHECK `chk_pos_reversal_decision`; CHECK `chk_pos_reversal_disposition`; CHECK `chk_pos_reversal_method`; CHECK `chk_pos_reversal_refund`; CHECK `chk_pos_reversal_sod`; CHECK `chk_pos_reversal_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Phê duyệt hoàn đơn nguyên tử cùng cập nhật `menu_orders`, restock/waste kho và bút toán hoàn tiền `cash_shift_entries`.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.33. `menu_promotions`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_promotions` — Chính sách khuyến mãi POS hiện hành theo cơ sở; mỗi lần lưu tạo một phiên bản bất biến tại `menu_promotion_versions` (NF-04).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (10 cột):** `id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `code` (`varchar(30)`, NOT NULL); `kind` (`varchar(16)`, NOT NULL); `item_id` (`bigint unsigned`, NULL); `value` (`int unsigned`, NOT NULL); `minimum_tier` (`varchar(12)`, NULL); `starts_at` (`datetime`, NOT NULL); `ends_at` (`datetime`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {kind, item_id, value, minimum_tier, starts_at, ends_at, is_active}; {store_id, code} → {kind, item_id, value, minimum_tier, starts_at, ends_at, is_active}; {id} → {store_id, code}; {store_id, code} → {id} }`. `{id}` và `{store_id, code}` là khóa ứng viên. Lưu cấu hình hiện hành của chính sách POS theo cơ sở; lịch sử từng phiên bản tách sang `menu_promotion_versions` (NF-04).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → kind; {id} → item_id; {id} → value; {id} → minimum_tier; {id} → starts_at; {id} → ends_at; {id} → is_active; {store_id, code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {store_id, code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 10 thuộc tính của `menu_promotions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `store_id`, `code`. Không nguyên tố: `kind`, `item_id`, `value`, `minimum_tier`, `starts_at`, `ends_at`, `is_active`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `029` (NF-04): tách bảng phiên bản bất biến `menu_promotion_versions`; migration `030` thêm trigger `trg_menu_promotions_bi/bu` chặn gắn `item_id` khác `store_id`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_menu_promo_store_code`(`store_id,code`); FK `fk_menu_promo_item`(`item_id` → `menu_items.id`, ON DELETE NO ACTION); FK `fk_menu_promo_store`(`store_id` → `stores.id`, ON DELETE NO ACTION); CHECK `chk_menu_promo_kind`; CHECK `chk_menu_promo_period`; CHECK `chk_menu_promo_tier`; TRIGGER `trg_menu_promotions_bi`; TRIGGER `trg_menu_promotions_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** `MenuRepository.save_promotion` luôn ghi kèm bản ghi phiên bản tăng dần vào `menu_promotion_versions` trong cùng transaction.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.34. `menu_promotion_versions`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_promotion_versions` — Phiên bản bất biến của chính sách khuyến mãi POS để hóa đơn/đơn hàng lịch sử tham chiếu đúng quy tắc đã áp dụng (NF-04).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (11 cột):** `id` (`bigint unsigned`, NOT NULL); `promotion_id` (`bigint unsigned`, NOT NULL); `version` (`int unsigned`, NOT NULL); `code` (`varchar(30)`, NOT NULL); `kind` (`varchar(16)`, NOT NULL); `item_id` (`bigint unsigned`, NULL); `value` (`int unsigned`, NOT NULL); `minimum_tier` (`varchar(12)`, NULL); `starts_at` (`datetime`, NOT NULL); `ends_at` (`datetime`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {code, kind, item_id, value, minimum_tier, starts_at, ends_at, created_at}; {promotion_id, version} → {code, kind, item_id, value, minimum_tier, starts_at, ends_at, created_at}; {id} → {promotion_id, version}; {promotion_id, version} → {id} }`. `{id}` và `{promotion_id, version}` là khóa ứng viên. Mọi thuộc tính chính sách chụp (`code`, `kind`, `item_id`, `value`, `minimum_tier`, `starts_at`, `ends_at`, `created_at`) phụ thuộc đầy đủ vào từng phiên bản bất biến.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → code; {id} → kind; {id} → item_id; {id} → value; {id} → minimum_tier; {id} → starts_at; {id} → ends_at; {id} → created_at; {promotion_id, version} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {promotion_id, version}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 11 thuộc tính của `menu_promotion_versions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `promotion_id`, `version`. Không nguyên tố: `code`, `kind`, `item_id`, `value`, `minimum_tier`, `starts_at`, `ends_at`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `029` (NF-04): tạo mới và backfill phiên bản 1 cho mọi `menu_promotions` hiện có.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_menu_promo_ver`(`promotion_id,version`); FK `fk_menu_promo_ver_item`(`item_id` → `menu_items.id`, ON DELETE RESTRICT); FK `fk_menu_promo_ver_promo`(`promotion_id` → `menu_promotions.id`, ON DELETE RESTRICT); CHECK `chk_menu_promo_ver_kind`; CHECK `chk_menu_promo_ver_period`; CHECK `chk_menu_promo_ver_tier`; CHECK `chk_menu_promo_ver_version`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Bất biến (append-only); không bao giờ sửa/xóa phiên bản đã được `menu_order_pricing` tham chiếu.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.35. `menu_order_pricing`

- **Tên quan hệ và ý nghĩa một dòng:** `menu_order_pricing` — Kết quả định giá POS dạng cấu trúc chuẩn 3NF (không còn `snapshot_json` hay cột dẫn xuất `final_amount`, đọc qua `v_menu_order_pricing`).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `order_id` (`bigint unsigned`, NOT NULL); `promotion_version_id` (`bigint unsigned`, NULL); `applied_source` (`varchar(12)`, NOT NULL); `member_tier` (`varchar(12)`, NOT NULL); `discount_amount` (`bigint unsigned`, NOT NULL); `voucher_id` (`bigint unsigned`, NULL); `voucher_discount_amount` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {order_id} → {promotion_version_id, applied_source, member_tier, discount_amount, voucher_id, voucher_discount_amount} }`. Khóa chính `{order_id}`. Đã loại bỏ hoàn toàn cột lặp từ chính sách (`promotion_id`, `promotion_code`, `promotion_kind`), cột dẫn xuất (`final_amount`), và cột bán cấu trúc `snapshot_json` (NF-04). Chỉ giữ các dữ kiện cấu trúc chuẩn 3NF: `promotion_version_id`, `applied_source`, `member_tier`, `discount_amount`, `voucher_id`, `voucher_discount_amount`.
- **Phủ tối thiểu của $F$:** `F_min = { {order_id} → promotion_version_id; {order_id} → applied_source; {order_id} → member_tier; {order_id} → discount_amount; {order_id} → voucher_id; {order_id} → voucher_discount_amount }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {order_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `menu_order_pricing`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `order_id`. Không nguyên tố: `promotion_version_id`, `applied_source`, `member_tier`, `discount_amount`, `voucher_id`, `voucher_discount_amount`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `029` (NF-04): backfill dữ kiện có cấu trúc từ `snapshot_json`, xóa 5 cột vi phạm, cung cấp view `v_menu_order_pricing` tính `effective_discount_amount` và `final_amount`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`order_id`); FK `fk_menu_pricing_order`(`order_id` → `menu_orders.id`, ON DELETE NO ACTION); FK `fk_menu_pricing_promo_version`(`promotion_version_id` → `menu_promotion_versions.id`, ON DELETE RESTRICT); FK `fk_menu_pricing_voucher`(`voucher_id` → `customer_vouchers.id`, ON DELETE RESTRICT); CHECK `chk_menu_pricing_promo_consistency`; CHECK `chk_menu_pricing_source`; CHECK `chk_menu_pricing_tier`; CHECK `chk_menu_pricing_voucher_consistency`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Đảm bảo 1 đơn áp tối đa 1 ưu đãi/voucher xác định (B07); sửa chính sách khuyến mãi sau khi đặt không đổi thông tin đơn lịch sử.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py`; 254 bản ghi lịch sử trên clone đối soát khớp tuyệt đối `discount_amount` và `final_amount`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.36. `reward_catalog`

- **Tên quan hệ và ý nghĩa một dòng:** `reward_catalog` — Danh mục phần thưởng; không có loại nào quy đổi tiền mặt.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (11 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `name` (`varchar(80)`, NOT NULL); `store_id` (`bigint unsigned`, NULL); `reward_type` (`varchar(20)`, NOT NULL); `value` (`bigint`, NOT NULL); `min_order_amount` (`bigint`, NOT NULL); `valid_days` (`int`, NOT NULL); `coin_cost` (`bigint`, NULL); `is_active` (`tinyint(1)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {name, store_id, reward_type, value, min_order_amount, valid_days, coin_cost, is_active, created_at}; {code} → {name, store_id, reward_type, value, min_order_amount, valid_days, coin_cost, is_active, created_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → name; {id} → store_id; {id} → reward_type; {id} → value; {id} → min_order_amount; {id} → valid_days; {id} → coin_cost; {id} → is_active; {id} → created_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 11 thuộc tính của `reward_catalog`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `name`, `store_id`, `reward_type`, `value`, `min_order_amount`, `valid_days`, `coin_cost`, `is_active`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_reward_catalog_code`(`code`); FK `fk_reward_catalog_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); CHECK `chk_reward_catalog_coin`; CHECK `chk_reward_catalog_days`; CHECK `chk_reward_catalog_min_order`; CHECK `chk_reward_catalog_name`; CHECK `chk_reward_catalog_type`; CHECK `chk_reward_catalog_value`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.37. `customer_vouchers`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_vouchers` — Voucher của khách; điều kiện được chụp lúc phát, dùng một lần.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (19 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `catalog_id` (`bigint unsigned`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NULL); `reward_type` (`varchar(20)`, NOT NULL); `value` (`bigint`, NOT NULL); `min_order_amount` (`bigint`, NOT NULL); `status` (`varchar(10)`, NOT NULL); `source` (`varchar(10)`, NOT NULL); `source_ref` (`varchar(64)`, NULL); `issued_by` (`bigint unsigned`, NULL); `issued_at` (`datetime`, NOT NULL); `expires_at` (`datetime`, NOT NULL); `used_at` (`datetime`, NULL); `used_by` (`bigint unsigned`, NULL); `used_store_id` (`bigint unsigned`, NULL); `used_order_id` (`bigint unsigned`, NULL); `revoked_reason` (`varchar(200)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {catalog_id, account_id, store_id, reward_type, value, min_order_amount, status, source, source_ref, issued_by, issued_at, expires_at, used_at, used_by, used_store_id, used_order_id, revoked_reason}; {code} → {catalog_id, account_id, store_id, reward_type, value, min_order_amount, status, source, source_ref, issued_by, issued_at, expires_at, used_at, used_by, used_store_id, used_order_id, revoked_reason}; {id} → {code}; {code} → {id} }`. `{id}` và `{code}` là khóa ứng viên. `used_order_id` và `(source, source_ref)` là `UNIQUE` chứa cột nullable (bảo vệ chống trùng ở mức vật lý, không phải khóa ứng viên cổ điển theo Mục 3.1). `store_id`, `reward_type`, `value`, `min_order_amount` là **snapshot điều kiện tại lúc phát hành** (độc lập với thay đổi sau này của `reward_catalog`), nên phụ thuộc vào `id`, không phải bắc cầu qua `catalog_id`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → catalog_id; {id} → account_id; {id} → store_id; {id} → reward_type; {id} → value; {id} → min_order_amount; {id} → status; {id} → source; {id} → source_ref; {id} → issued_by; {id} → issued_at; {id} → expires_at; {id} → used_at; {id} → used_by; {id} → used_store_id; {id} → used_order_id; {id} → revoked_reason; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 19 thuộc tính của `customer_vouchers`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu. *(UNIQUE nullable không phải CK: `used_order_id`, `source,source_ref`)*.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `catalog_id`, `account_id`, `store_id`, `reward_type`, `value`, `min_order_amount`, `status`, `source`, `source_ref`, `issued_by`, `issued_at`, `expires_at`, `used_at`, `used_by`, `used_store_id`, `used_order_id`, `revoked_reason`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` củng cố `chk_customer_vouchers_used` (yêu cầu `used_store_id IS NULL` khi chưa dùng) và `chk_customer_vouchers_revoked` (bắt buộc lý do khóa không rỗng khi `REVOKED`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_customer_vouchers_code`(`code`); UK `uq_customer_vouchers_order`(`used_order_id`); UK `uq_customer_vouchers_source`(`source,source_ref`); FK `fk_customer_vouchers_account`(`account_id` → `accounts.id`, ON DELETE RESTRICT); FK `fk_customer_vouchers_catalog`(`catalog_id` → `reward_catalog.id`, ON DELETE RESTRICT); FK `fk_customer_vouchers_issued_by`(`issued_by` → `employees.id`, ON DELETE RESTRICT); FK `fk_customer_vouchers_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); FK `fk_customer_vouchers_used_by`(`used_by` → `employees.id`, ON DELETE RESTRICT); FK `fk_customer_vouchers_used_order`(`used_order_id` → `menu_orders.id`, ON DELETE RESTRICT); FK `fk_customer_vouchers_used_store`(`used_store_id` → `stores.id`, ON DELETE RESTRICT); CHECK `chk_customer_vouchers_period`; CHECK `chk_customer_vouchers_revoked`; CHECK `chk_customer_vouchers_source`; CHECK `chk_customer_vouchers_status`; CHECK `chk_customer_vouchers_type`; CHECK `chk_customer_vouchers_used`; CHECK `chk_customer_vouchers_value`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Đổi voucher khóa `FOR UPDATE` và dùng `UPDATE ... WHERE status='ISSUED'` chống dùng hai lần; ghi nhật ký `voucher_events` kể cả lần bị từ chối.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.38. `voucher_events`

- **Tên quan hệ và ý nghĩa một dòng:** `voucher_events` — Nhật ký phát hành, sử dụng, khóa và cả lần bị từ chối; chỉ thêm.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `voucher_id` (`bigint unsigned`, NULL); `action` (`varchar(10)`, NOT NULL); `employee_id` (`bigint unsigned`, NULL); `store_id` (`bigint unsigned`, NULL); `reason` (`varchar(200)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {voucher_id, action, employee_id, store_id, reason, created_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → voucher_id; {id} → action; {id} → employee_id; {id} → store_id; {id} → reason; {id} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `voucher_events`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `voucher_id`, `action`, `employee_id`, `store_id`, `reason`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_voucher_events_employee`(`employee_id` → `employees.id`, ON DELETE RESTRICT); FK `fk_voucher_events_store`(`store_id` → `stores.id`, ON DELETE RESTRICT); FK `fk_voucher_events_voucher`(`voucher_id` → `customer_vouchers.id`, ON DELETE RESTRICT); CHECK `chk_voucher_events_action`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.39. `loyalty_point_grants`

- **Tên quan hệ và ý nghĩa một dòng:** `loyalty_point_grants` — Điểm thành viên tặng qua voucher; cộng vào điểm, không đổi hạng.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (6 cột):** `id` (`bigint unsigned`, NOT NULL); `customer_id` (`bigint unsigned`, NOT NULL); `voucher_id` (`bigint unsigned`, NOT NULL); `points` (`bigint`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {customer_id, points, employee_id, created_at}; {voucher_id} → {customer_id, points, employee_id, created_at}; {id} → {voucher_id}; {voucher_id} → {id} }`. `{id}` và `{voucher_id}` là khóa ứng viên (`voucher_id` UNIQUE NOT NULL). Do `voucher_id` là siêu khóa, FD `voucher_id -> customer_id` không vi phạm 3NF.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → customer_id; {id} → points; {id} → employee_id; {id} → created_at; {voucher_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {voucher_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 6 thuộc tính của `loyalty_point_grants`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `voucher_id`. Không nguyên tố: `customer_id`, `points`, `employee_id`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm trigger `trg_loyalty_point_grants_bi` bắt buộc `customer_id` trùng chủ sở hữu `customer_vouchers.account_id`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_loyalty_point_grants_voucher`(`voucher_id`); FK `fk_loyalty_point_grants_customer`(`customer_id` → `customers.id`, ON DELETE RESTRICT); FK `fk_loyalty_point_grants_employee`(`employee_id` → `employees.id`, ON DELETE RESTRICT); FK `fk_loyalty_point_grants_voucher`(`voucher_id` → `customer_vouchers.id`, ON DELETE RESTRICT); CHECK `chk_loyalty_point_grants_points`; TRIGGER `trg_loyalty_point_grants_bi`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Ghi nguyên tử khi đổi voucher `MEMBER_POINTS`; không làm thay đổi chi tiêu xét hạng.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.40. `games`

- **Tên quan hệ và ý nghĩa một dòng:** `games` — Cấu hình trò chơi (giai đoạn đầu: vòng quay may mắn), dùng chung mọi cơ sở.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `name` (`varchar(60)`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL); `daily_limit` (`int`, NOT NULL); `min_interval_seconds` (`int`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {name, is_active, daily_limit, min_interval_seconds, updated_at}; {code} → {name, is_active, daily_limit, min_interval_seconds, updated_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → name; {id} → is_active; {id} → daily_limit; {id} → min_interval_seconds; {id} → updated_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `games`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `name`, `is_active`, `daily_limit`, `min_interval_seconds`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_games_code`(`code`); CHECK `chk_games_daily_limit`; CHECK `chk_games_interval`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.41. `game_prizes`

- **Tên quan hệ và ý nghĩa một dòng:** `game_prizes` — Các ô thưởng trên vòng quay và tỉ lệ trúng tương đối.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (6 cột):** `id` (`bigint unsigned`, NOT NULL); `game_id` (`bigint unsigned`, NOT NULL); `sort_order` (`int`, NOT NULL); `label` (`varchar(40)`, NOT NULL); `coins` (`int`, NOT NULL); `weight` (`int`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {label, coins, weight}; {game_id, sort_order} → {label, coins, weight}; {id} → {game_id, sort_order}; {game_id, sort_order} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {game_id, sort_order} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → label; {id} → coins; {id} → weight; {game_id, sort_order} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {game_id, sort_order}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 6 thuộc tính của `game_prizes`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `game_id`, `sort_order`. Không nguyên tố: `label`, `coins`, `weight`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_game_prizes_slot`(`game_id,sort_order`); FK `fk_game_prizes_game`(`game_id` → `games.id`, ON DELETE RESTRICT); CHECK `chk_game_prizes_coins`; CHECK `chk_game_prizes_label`; CHECK `chk_game_prizes_weight`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.42. `game_wallets`

- **Tên quan hệ và ý nghĩa một dòng:** `game_wallets` — Ví xu game của tài khoản; xu không phải tiền và không phải điểm thành viên.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (8 cột):** `account_id` (`bigint unsigned`, NOT NULL); `balance` (`bigint`, NOT NULL); `is_locked` (`tinyint(1)`, NOT NULL); `locked_reason` (`varchar(200)`, NULL); `locked_at` (`datetime`, NULL); `suspicious_count` (`int`, NOT NULL); `suspicious_on` (`date`, NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {account_id} → {balance, is_locked, locked_reason, locked_at, suspicious_count, suspicious_on, updated_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {account_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {account_id} → balance; {account_id} → is_locked; {account_id} → locked_reason; {account_id} → locked_at; {account_id} → suspicious_count; {account_id} → suspicious_on; {account_id} → updated_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {account_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 8 thuộc tính của `game_wallets`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `account_id`. Không nguyên tố: `balance`, `is_locked`, `locked_reason`, `locked_at`, `suspicious_count`, `suspicious_on`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`account_id`); FK `fk_game_wallets_account`(`account_id` → `accounts.id`, ON DELETE RESTRICT); CHECK `chk_game_wallets_balance`; CHECK `chk_game_wallets_lock`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.43. `game_sessions`

- **Tên quan hệ và ý nghĩa một dòng:** `game_sessions` — Lịch sử từng lượt quay; kết quả do máy chủ bốc thăm và được chụp lại.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `game_id` (`bigint unsigned`, NOT NULL); `prize_index` (`int`, NOT NULL); `prize_label` (`varchar(40)`, NOT NULL); `coins` (`int`, NOT NULL); `created_at` (`datetime`, NOT NULL, UTC).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {account_id, game_id, prize_index, prize_label, coins, created_at} }`. `played_on` trước migration `031` thỏa FD `created_at → played_on` theo quy tắc UTC+7 trong source và đã bị loại khỏi bảng cơ sở.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → account_id; {id} → game_id; {id} → prize_index; {id} → prize_label; {id} → coins; {id} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `game_sessions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `account_id`, `game_id`, `prize_index`, `prize_label`, `coins`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `031` bỏ `played_on`; repository tính ngày Việt Nam khi đọc và lọc bằng khoảng UTC để giữ hiệu năng index. Quan hệ sau `031` đạt 3NF/BCNF trên tập FD đã công bố.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_game_sessions_account`(`account_id` → `accounts.id`, ON DELETE RESTRICT); FK `fk_game_sessions_game`(`game_id` → `games.id`, ON DELETE RESTRICT); CHECK `chk_game_sessions_coins`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.44. `game_coin_ledger`

- **Tên quan hệ và ý nghĩa một dòng:** `game_coin_ledger` — Sổ cái xu: mọi thay đổi số dư xu có đúng một dòng; chỉ thêm.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (8 cột):** `id` (`bigint unsigned`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `delta` (`bigint`, NOT NULL); `reason` (`varchar(10)`, NOT NULL); `ref` (`varchar(64)`, NOT NULL); `balance_after` (`bigint`, NOT NULL); `voucher_id` (`bigint unsigned`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {account_id, delta, balance_after, voucher_id, created_at}; {reason, ref} → {account_id, delta, balance_after, voucher_id, created_at}; {id} → {reason, ref}; {reason, ref} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {reason, ref} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → account_id; {id} → delta; {id} → balance_after; {id} → voucher_id; {id} → created_at; {reason, ref} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {reason, ref}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 8 thuộc tính của `game_coin_ledger`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `reason`, `ref`. Không nguyên tố: `account_id`, `delta`, `balance_after`, `voucher_id`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_game_coin_ledger_ref`(`reason,ref`); FK `fk_game_coin_ledger_account`(`account_id` → `accounts.id`, ON DELETE RESTRICT); FK `fk_game_coin_ledger_voucher`(`voucher_id` → `customer_vouchers.id`, ON DELETE RESTRICT); CHECK `chk_game_coin_ledger_balance`; CHECK `chk_game_coin_ledger_delta`; CHECK `chk_game_coin_ledger_reason`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.45. `ad_settings`

- **Tên quan hệ và ý nghĩa một dòng:** `ad_settings` — Cấu hình chương trình quảng cáo nhận thưởng (một dòng duy nhất).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`tinyint unsigned`, NOT NULL); `enabled` (`tinyint(1)`, NOT NULL); `mode` (`varchar(10)`, NOT NULL); `daily_cap` (`int`, NOT NULL); `reward_type` (`varchar(12)`, NOT NULL); `reward_amount` (`int`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {enabled, mode, daily_cap, reward_type, reward_amount, updated_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → enabled; {id} → mode; {id} → daily_cap; {id} → reward_type; {id} → reward_amount; {id} → updated_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `ad_settings`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `enabled`, `mode`, `daily_cap`, `reward_type`, `reward_amount`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); CHECK `chk_ad_settings_cap`; CHECK `chk_ad_settings_mode`; CHECK `chk_ad_settings_reward`; CHECK `chk_ad_settings_singleton`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.46. `ad_creatives`

- **Tên quan hệ và ý nghĩa một dòng:** `ad_creatives` — Nội dung quảng cáo nội bộ do CyberHub tự soạn.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (8 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(20)`, NOT NULL); `title` (`varchar(80)`, NOT NULL); `body` (`varchar(300)`, NOT NULL); `cta` (`varchar(40)`, NOT NULL); `duration_seconds` (`int`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {title, body, cta, duration_seconds, is_active, created_at}; {code} → {title, body, cta, duration_seconds, is_active, created_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → title; {id} → body; {id} → cta; {id} → duration_seconds; {id} → is_active; {id} → created_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 8 thuộc tính của `ad_creatives`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `title`, `body`, `cta`, `duration_seconds`, `is_active`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_ad_creatives_code`(`code`); CHECK `chk_ad_creatives_duration`; CHECK `chk_ad_creatives_title`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.47. `ad_reward_events`

- **Tên quan hệ và ý nghĩa một dòng:** `ad_reward_events` — Mỗi lần bắt đầu xem quảng cáo; token dùng một lần, độc lập với kết quả game.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (14 cột):** `id` (`bigint unsigned`, NOT NULL); `token` (`char(32)`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `creative_id` (`bigint unsigned`, NULL); `provider` (`varchar(10)`, NOT NULL); `reward_type` (`varchar(12)`, NOT NULL); `reward_amount` (`int`, NOT NULL); `status` (`varchar(10)`, NOT NULL); `issued_at` (`datetime`, NOT NULL, UTC); `min_complete_at` (`datetime`, NOT NULL); `expires_at` (`datetime`, NOT NULL); `completed_at` (`datetime`, NULL); `provider_txn_id` (`varchar(80)`, NULL); `reject_reason` (`varchar(40)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {token, account_id, creative_id, provider, reward_type, reward_amount, status, issued_at, min_complete_at, expires_at, completed_at, provider_txn_id, reject_reason}; {token} → {id} }`. `played_on` trước migration `031` thỏa FD `issued_at → played_on` theo quy tắc UTC+7 và đã bị loại. `provider_txn_id` nullable chỉ thực thi duy nhất khi khác NULL, không tính là khóa ứng viên cổ điển.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → token; {id} → account_id; {id} → creative_id; {id} → provider; {id} → reward_type; {id} → reward_amount; {id} → status; {id} → issued_at; {id} → min_complete_at; {id} → expires_at; {id} → completed_at; {id} → provider_txn_id; {id} → reject_reason; {token} → id }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {token}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 14 thuộc tính của `ad_reward_events`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu. *(UNIQUE nullable không phải CK: `provider_txn_id`)*.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `token`. Không nguyên tố: `account_id`, `creative_id`, `provider`, `reward_type`, `reward_amount`, `status`, `issued_at`, `min_complete_at`, `expires_at`, `completed_at`, `provider_txn_id`, `reject_reason`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `031` bỏ `played_on`; repository suy ra ngày Việt Nam từ `issued_at` khi đọc và dùng khoảng UTC cho hạn mức/thống kê. Quan hệ sau `031` đạt 3NF/BCNF trên tập FD đã công bố.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_ad_reward_events_token`(`token`); UK `uq_ad_reward_events_txn`(`provider_txn_id`); FK `fk_ad_reward_events_account`(`account_id` → `accounts.id`, ON DELETE RESTRICT); FK `fk_ad_reward_events_creative`(`creative_id` → `ad_creatives.id`, ON DELETE RESTRICT); CHECK `chk_ad_reward_events_done`; CHECK `chk_ad_reward_events_period`; CHECK `chk_ad_reward_events_provider`; CHECK `chk_ad_reward_events_reward`; CHECK `chk_ad_reward_events_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.48. `cash_shifts`

- **Tên quan hệ và ý nghĩa một dòng:** `cash_shifts` — Ca làm việc và đối chiếu két tiền của một nhân viên tại một cơ sở; chênh lệch `variance` tính qua `v_cash_shifts`, chiếm dụng ca mở nằm tại `active_employee_shifts`.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `status` (`varchar(16)`, NOT NULL); `opening_cash` (`bigint unsigned`, NOT NULL); `expected_cash` (`bigint unsigned`, NULL); `counted_cash` (`bigint unsigned`, NULL); `opened_at` (`datetime`, NOT NULL); `submitted_at` (`datetime`, NULL); `closed_at` (`datetime`, NULL); `reviewed_by` (`bigint unsigned`, NULL); `review_note` (`varchar(255)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {store_id, employee_id, status, opening_cash, expected_cash, counted_cash, opened_at, submitted_at, closed_at, reviewed_by, review_note}; {code} → {store_id, employee_id, status, opening_cash, expected_cash, counted_cash, opened_at, submitted_at, closed_at, reviewed_by, review_note}; {id} → {code}; {code} → {id} }`. `{id}` và `{code}` là khóa ứng viên. Đã loại bỏ cột công thức `variance = counted_cash - expected_cash` (NF-01) và cột sinh `active_employee_id` (NF-01 vật lý).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → store_id; {id} → employee_id; {id} → status; {id} → opening_cash; {id} → expected_cash; {id} → counted_cash; {id} → opened_at; {id} → submitted_at; {id} → closed_at; {id} → reviewed_by; {id} → review_note; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `cash_shifts`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `store_id`, `employee_id`, `status`, `opening_cash`, `expected_cash`, `counted_cash`, `opened_at`, `submitted_at`, `closed_at`, `reviewed_by`, `review_note`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028`: xóa `variance` (chuyển sang view `v_cash_shifts`) và tách chiếm dụng sang bảng `active_employee_shifts`; migration `030` thêm `chk_cash_shifts_close` (NULL-safe vòng đời `OPEN/PENDING_REVIEW/CLOSED` + SoD `reviewed_by <> employee_id`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_cash_shifts_code`(`code`); FK `fk_cash_shifts_employee`(`employee_id` → `employees.id`, ON DELETE NO ACTION); FK `fk_cash_shifts_reviewer`(`reviewed_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_cash_shifts_store`(`store_id` → `stores.id`, ON DELETE NO ACTION); CHECK `chk_cash_shifts_close`; CHECK `chk_cash_shifts_status`; TRIGGER `trg_cash_shifts_ai`; TRIGGER `trg_cash_shifts_au`; TRIGGER `trg_cash_shifts_bu_no_reopen`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Mỗi nhân viên tối đa 1 ca chưa đóng (B10); đóng ca khóa hàng ca và tổng hợp từ `cash_shift_entries` trong cùng transaction.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.49. `active_employee_shifts`

- **Tên quan hệ và ý nghĩa một dòng:** `active_employee_shifts` — Bảng chiếm dụng 3NF bảo đảm mỗi nhân viên chỉ có tối đa một ca `OPEN`/`PENDING_REVIEW` cùng lúc (thay cột sinh `active_employee_id`).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (2 cột):** `shift_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {shift_id} → {shift_id, employee_id}; {employee_id} → {shift_id, employee_id} }`. Bảng chiếm dụng 3NF cho các ca `OPEN`/`PENDING_REVIEW`. Cả `{shift_id}` (`PK`) và `{employee_id}` (`UNIQUE NOT NULL`) đều là khóa ứng viên -> mọi thuộc tính đều là thuộc tính nguyên tố, đạt 3NF & BCNF tuyệt đối.
- **Phủ tối thiểu của $F$:** `F_min = { {shift_id} → {shift_id, employee_id}; {employee_id} → {shift_id, employee_id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {shift_id}, {employee_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 2 thuộc tính của `active_employee_shifts`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `shift_id`, `employee_id`. Không nguyên tố: *(không có — mọi thuộc tính đều nguyên tố)*.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF) tuyệt đối: không có thuộc tính không nguyên tố; mọi thuộc tính đều thuộc ít nhất một khóa ứng viên.
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01 vật lý): thay thế cột sinh `cash_shifts.active_employee_id`, đồng bộ tự động bằng `trg_cash_shifts_ai/au/bu_no_reopen`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`shift_id`); UK `uq_active_shift_employee`(`employee_id`); FK `fk_active_shift_employee`(`employee_id` → `employees.id`, ON DELETE RESTRICT); FK `fk_active_shift_shift`(`shift_id` → `cash_shifts.id`, ON DELETE CASCADE).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Chặn mở đồng thời hai ca ở mức DB ngay cả khi chạy đồng thời nhiều kết nối.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py::test_active_employee_shifts_occupancy_and_no_reopen`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.50. `cash_shift_entries`

- **Tên quan hệ và ý nghĩa một dòng:** `cash_shift_entries` — Sổ bất biến thu, chi, hoàn và điều chỉnh theo ca; cơ sở suy ra từ `cash_shifts.store_id` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (10 cột):** `id` (`bigint unsigned`, NOT NULL); `shift_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `kind` (`varchar(12)`, NOT NULL); `payment_method` (`varchar(10)`, NOT NULL); `amount` (`bigint unsigned`, NOT NULL); `source_type` (`varchar(24)`, NOT NULL); `source_id` (`varchar(64)`, NOT NULL); `note` (`varchar(255)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {shift_id, employee_id, kind, amount, note, created_at}; {source_type, source_id, payment_method} → {shift_id, employee_id, kind, amount, note, created_at}; {id} → {source_type, source_id, payment_method}; {source_type, source_id, payment_method} → {id} }`. `{id}` và `{source_type, source_id, payment_method}` là khóa ứng viên. Đã loại bỏ cột lặp bắc cầu `store_id` (NF-02) vì `shift_id -> store_id`; giữ `employee_id` vì người lập bút toán có thể khác chủ ca.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → shift_id; {id} → employee_id; {id} → kind; {id} → amount; {id} → note; {id} → created_at; {source_type, source_id, payment_method} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {source_type, source_id, payment_method}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 10 thuộc tính của `cash_shift_entries`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `payment_method`, `source_type`, `source_id`. Không nguyên tố: `shift_id`, `employee_id`, `kind`, `amount`, `note`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, cung cấp view `v_cash_shift_entries`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_cash_shift_entries_source`(`source_type,source_id,payment_method`); FK `fk_cash_entries_employee`(`employee_id` → `employees.id`, ON DELETE NO ACTION); FK `fk_cash_entries_shift`(`shift_id` → `cash_shifts.id`, ON DELETE NO ACTION); CHECK `chk_cash_entries_amount`; CHECK `chk_cash_entries_kind`; CHECK `chk_cash_entries_method`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Giới hạn công bố (INT-03): cặp `(source_type, source_id)` là tham chiếu đa hình không có FK trực tiếp tới từng loại chứng từ nguồn; tính nhất quán được kiểm soát tại application service và khóa `UNIQUE(source_type, source_id, payment_method)`.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.51. `machine_incidents`

- **Tên quan hệ và ý nghĩa một dòng:** `machine_incidents` — Phiếu sự cố và vòng đời bảo trì máy từ báo lỗi đến nghiệm thu; cơ sở suy ra từ `machines.store_id` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (17 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `machine_id` (`bigint unsigned`, NOT NULL); `reported_by` (`bigint unsigned`, NOT NULL); `assigned_to` (`bigint unsigned`, NULL); `severity` (`varchar(10)`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `title` (`varchar(120)`, NOT NULL); `description` (`varchar(1000)`, NOT NULL); `resolution` (`varchar(1000)`, NULL); `labor_cost` (`bigint unsigned`, NOT NULL); `parts_cost` (`bigint unsigned`, NOT NULL); `reported_at` (`datetime`, NOT NULL); `started_at` (`datetime`, NULL); `completed_at` (`datetime`, NULL); `verified_at` (`datetime`, NULL); `verified_by` (`bigint unsigned`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {machine_id, reported_by, assigned_to, severity, status, title, description, resolution, labor_cost, parts_cost, reported_at, started_at, completed_at, verified_at, verified_by}; {code} → {machine_id, reported_by, assigned_to, severity, status, title, description, resolution, labor_cost, parts_cost, reported_at, started_at, completed_at, verified_at, verified_by}; {id} → {code}; {code} → {id} }`. `{id}` và `{code}` là khóa ứng viên. Đã loại bỏ cột lặp bắc cầu `store_id` (NF-02) theo quyết định B01 (`machine_id -> store_id`).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → machine_id; {id} → reported_by; {id} → assigned_to; {id} → severity; {id} → status; {id} → title; {id} → description; {id} → resolution; {id} → labor_cost; {id} → parts_cost; {id} → reported_at; {id} → started_at; {id} → completed_at; {id} → verified_at; {id} → verified_by; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 17 thuộc tính của `machine_incidents`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `machine_id`, `reported_by`, `assigned_to`, `severity`, `status`, `title`, `description`, `resolution`, `labor_cost`, `parts_cost`, `reported_at`, `started_at`, `completed_at`, `verified_at`, `verified_by`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, cung cấp view `v_machine_incidents`; migration `030` thêm `chk_incidents_lifecycle` kiểm soát chặt vòng đời 7 trạng thái, mốc thời gian và SoD `verified_by <> assigned_to`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_machine_incidents_code`(`code`); FK `fk_incidents_assignee`(`assigned_to` → `employees.id`, ON DELETE NO ACTION); FK `fk_incidents_machine`(`machine_id` → `machines.id`, ON DELETE NO ACTION); FK `fk_incidents_reporter`(`reported_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_incidents_verifier`(`verified_by` → `employees.id`, ON DELETE NO ACTION); CHECK `chk_incidents_cost`; CHECK `chk_incidents_lifecycle`; CHECK `chk_incidents_severity`; CHECK `chk_incidents_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** NF-05: `parts_cost` được đồng bộ nguyên tử từ tổng `machine_incident_parts` khi chuyển trạng thái `COMPLETED`; chuyển `IN_PROGRESS` khóa máy sang `MAINTENANCE`.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.52. `machine_incident_parts`

- **Tên quan hệ và ý nghĩa một dòng:** `machine_incident_parts` — Linh kiện sử dụng cho một phiếu sửa máy.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (5 cột):** `id` (`bigint unsigned`, NOT NULL); `incident_id` (`bigint unsigned`, NOT NULL); `name` (`varchar(120)`, NOT NULL); `quantity` (`int unsigned`, NOT NULL); `unit_cost` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {incident_id, name, quantity, unit_cost} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → incident_id; {id} → name; {id} → quantity; {id} → unit_cost }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 5 thuộc tính của `machine_incident_parts`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `incident_id`, `name`, `quantity`, `unit_cost`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_incident_parts_incident`(`incident_id` → `machine_incidents.id`, ON DELETE NO ACTION); CHECK `chk_incident_parts_cost`; CHECK `chk_incident_parts_quantity`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.53. `machine_incident_events`

- **Tên quan hệ và ý nghĩa một dòng:** `machine_incident_events` — Lịch sử chuyển trạng thái sự cố máy, chỉ thêm.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `incident_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NOT NULL); `from_status` (`varchar(20)`, NULL); `to_status` (`varchar(20)`, NOT NULL); `note` (`varchar(500)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {incident_id, employee_id, from_status, to_status, note, created_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → incident_id; {id} → employee_id; {id} → from_status; {id} → to_status; {id} → note; {id} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `machine_incident_events`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `incident_id`, `employee_id`, `from_status`, `to_status`, `note`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_incident_events_employee`(`employee_id` → `employees.id`, ON DELETE NO ACTION); FK `fk_incident_events_incident`(`incident_id` → `machine_incidents.id`, ON DELETE NO ACTION).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.54. `suppliers`

- **Tên quan hệ và ý nghĩa một dòng:** `suppliers` — Nhà cung cấp theo cơ sở và điều khoản thanh toán.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (10 cột):** `id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `name` (`varchar(120)`, NOT NULL); `phone` (`varchar(20)`, NULL); `email` (`varchar(120)`, NULL); `address` (`varchar(255)`, NULL); `payment_terms_days` (`int unsigned`, NOT NULL); `is_active` (`tinyint(1)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {name, phone, email, address, payment_terms_days, is_active, created_at}; {store_id, code} → {name, phone, email, address, payment_terms_days, is_active, created_at}; {id} → {store_id, code}; {store_id, code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {store_id, code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → name; {id} → phone; {id} → email; {id} → address; {id} → payment_terms_days; {id} → is_active; {id} → created_at; {store_id, code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {store_id, code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 10 thuộc tính của `suppliers`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `store_id`, `code`. Không nguyên tố: `name`, `phone`, `email`, `address`, `payment_terms_days`, `is_active`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_suppliers_store_code`(`store_id,code`); FK `fk_suppliers_store`(`store_id` → `stores.id`, ON DELETE NO ACTION); CHECK `chk_suppliers_terms`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.55. `purchase_requests`

- **Tên quan hệ và ý nghĩa một dòng:** `purchase_requests` — Đề nghị nhập hàng có người lập và người quyết định (tách nhiệm vụ `decided_by <> requested_by`).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (9 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `store_id` (`bigint unsigned`, NOT NULL); `requested_by` (`bigint unsigned`, NOT NULL); `status` (`varchar(12)`, NOT NULL); `reason` (`varchar(255)`, NOT NULL); `decided_by` (`bigint unsigned`, NULL); `decided_at` (`datetime`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {store_id, requested_by, status, reason, decided_by, decided_at, created_at}; {code} → {store_id, requested_by, status, reason, decided_by, decided_at, created_at}; {id} → {code}; {code} → {id} }`. `{id}` và `{code}` là khóa ứng viên. Không có FD giữa các thuộc tính không khóa.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → store_id; {id} → requested_by; {id} → status; {id} → reason; {id} → decided_by; {id} → decided_at; {id} → created_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 9 thuộc tính của `purchase_requests`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `store_id`, `requested_by`, `status`, `reason`, `decided_by`, `decided_at`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm `chk_purchase_requests_sod` chặn tự duyệt (`decided_by <> requested_by`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_purchase_requests_code`(`code`); FK `fk_purchase_requests_decider`(`decided_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_purchase_requests_requester`(`requested_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_purchase_requests_store`(`store_id` → `stores.id`, ON DELETE NO ACTION); CHECK `chk_purchase_requests_decision`; CHECK `chk_purchase_requests_sod`; CHECK `chk_purchase_requests_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Đề nghị đã `APPROVED` mới được chuyển thành tối đa 1 `purchase_orders` (B06).
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.56. `purchase_request_lines`

- **Tên quan hệ và ý nghĩa một dòng:** `purchase_request_lines` — Nguyên liệu và số lượng trong đề nghị nhập.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (3 cột):** `request_id` (`bigint unsigned`, NOT NULL); `ingredient_id` (`bigint unsigned`, NOT NULL); `quantity` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {request_id, ingredient_id} → {quantity} }`. Khóa chính ghép `(request_id, ingredient_id)` xác định duy nhất `quantity` (> 0).
- **Phủ tối thiểu của $F$:** `F_min = { {request_id, ingredient_id} → quantity }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {request_id, ingredient_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 3 thuộc tính của `purchase_request_lines`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `request_id`, `ingredient_id`. Không nguyên tố: `quantity`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm trigger `trg_purchase_request_lines_bi` bảo đảm nguyên liệu cùng cơ sở với đề nghị mua.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`request_id,ingredient_id`); FK `fk_purchase_request_lines_ingredient`(`ingredient_id` → `inventory_ingredients.id`, ON DELETE NO ACTION); FK `fk_purchase_request_lines_request`(`request_id` → `purchase_requests.id`, ON DELETE NO ACTION); CHECK `chk_purchase_request_lines_quantity`; TRIGGER `trg_purchase_request_lines_bi`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Đơn mua tạo từ đề nghị bắt buộc khớp chính xác danh sách nguyên liệu và số lượng đã duyệt.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.57. `purchase_orders`

- **Tên quan hệ và ý nghĩa một dòng:** `purchase_orders` — Đơn mua hàng tạo từ đề nghị đã duyệt và gắn nhà cung cấp; cơ sở suy ra từ `purchase_requests.store_id` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (9 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `request_id` (`bigint unsigned`, NOT NULL); `supplier_id` (`bigint unsigned`, NOT NULL); `created_by` (`bigint unsigned`, NOT NULL); `status` (`varchar(20)`, NOT NULL); `ordered_at` (`datetime`, NOT NULL); `expected_at` (`datetime`, NULL); `total_amount` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {supplier_id, created_by, status, ordered_at, expected_at, total_amount}; {code} → {supplier_id, created_by, status, ordered_at, expected_at, total_amount}; {request_id} → {supplier_id, created_by, status, ordered_at, expected_at, total_amount}; {id} → {code}; {code} → {request_id}; {request_id} → {id} }`. `{id}`, `{code}`, `{request_id}` là các khóa ứng viên (`request_id` UNIQUE theo quyết định B06: 1 PR -> tối đa 1 PO). Đã loại bỏ cột lặp bắc cầu `store_id` (NF-02) vì `request_id -> store_id` và `supplier_id -> store_id`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → supplier_id; {id} → created_by; {id} → status; {id} → ordered_at; {id} → expected_at; {id} → total_amount; {code} ↔ {id}; {request_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}, {request_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 9 thuộc tính của `purchase_orders`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`, `request_id`. Không nguyên tố: `supplier_id`, `created_by`, `status`, `ordered_at`, `expected_at`, `total_amount`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, tạo view `v_purchase_orders`; migration `030` thêm trigger `trg_purchase_orders_bi/bu` khóa chặt `suppliers.store_id = purchase_requests.store_id`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_purchase_orders_code`(`code`); UK `uq_purchase_orders_request`(`request_id`); FK `fk_purchase_orders_creator`(`created_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_purchase_orders_request`(`request_id` → `purchase_requests.id`, ON DELETE NO ACTION); FK `fk_purchase_orders_supplier`(`supplier_id` → `suppliers.id`, ON DELETE NO ACTION); CHECK `chk_purchase_orders_status`; CHECK `chk_purchase_orders_total`; TRIGGER `trg_purchase_orders_bi`; TRIGGER `trg_purchase_orders_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** NF-05: `total_amount` đồng bộ từ tổng `purchase_order_lines` trong cùng transaction tạo đơn.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.58. `purchase_order_lines`

- **Tên quan hệ và ý nghĩa một dòng:** `purchase_order_lines` — Dòng đơn mua và tiến độ nhận theo nguyên liệu.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (6 cột):** `order_id` (`bigint unsigned`, NOT NULL); `ingredient_id` (`bigint unsigned`, NOT NULL); `quantity` (`bigint unsigned`, NOT NULL); `unit_cost` (`bigint unsigned`, NOT NULL); `received_quantity` (`bigint unsigned`, NOT NULL); `damaged_quantity` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {order_id, ingredient_id} → {quantity, unit_cost, received_quantity, damaged_quantity} }`. Khóa chính ghép `(order_id, ingredient_id)` xác định `quantity`, `unit_cost`, `received_quantity`, `damaged_quantity`. `unit_cost` là đơn giá mua của dòng đơn.
- **Phủ tối thiểu của $F$:** `F_min = { {order_id, ingredient_id} → quantity; {order_id, ingredient_id} → unit_cost; {order_id, ingredient_id} → received_quantity; {order_id, ingredient_id} → damaged_quantity }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {order_id, ingredient_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 6 thuộc tính của `purchase_order_lines`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `order_id`, `ingredient_id`. Không nguyên tố: `quantity`, `unit_cost`, `received_quantity`, `damaged_quantity`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm trigger `trg_purchase_order_lines_bi` bảo đảm nguyên liệu cùng cơ sở với đơn mua.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`order_id,ingredient_id`); FK `fk_purchase_order_lines_ingredient`(`ingredient_id` → `inventory_ingredients.id`, ON DELETE NO ACTION); FK `fk_purchase_order_lines_order`(`order_id` → `purchase_orders.id`, ON DELETE NO ACTION); CHECK `chk_purchase_order_lines_quantity`; CHECK `chk_purchase_order_lines_received`; TRIGGER `trg_purchase_order_lines_bi`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** CHECK bảo đảm `received_quantity + damaged_quantity <= quantity`.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.59. `goods_receipts`

- **Tên quan hệ và ý nghĩa một dòng:** `goods_receipts` — Phiếu nhận hàng idempotent, tạo nhập kho và công nợ theo số lượng đạt; cơ sở suy ra từ `purchase_orders`→`purchase_requests` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (8 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `order_id` (`bigint unsigned`, NOT NULL); `received_by` (`bigint unsigned`, NOT NULL); `request_id` (`char(32)`, NOT NULL); `note` (`varchar(255)`, NOT NULL); `received_at` (`datetime`, NOT NULL); `accepted_amount` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {order_id, received_by, note, received_at, accepted_amount}; {code} → {order_id, received_by, note, received_at, accepted_amount}; {request_id} → {order_id, received_by, note, received_at, accepted_amount}; {id} → {code}; {code} → {request_id}; {request_id} → {id} }`. `{id}`, `{code}`, `{request_id}` là các khóa ứng viên (`request_id` chống lặp idempotent). Đã loại bỏ `store_id` lặp bắc cầu qua `order_id -> request_id -> store_id` (NF-02).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → order_id; {id} → received_by; {id} → note; {id} → received_at; {id} → accepted_amount; {code} ↔ {id}; {request_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}, {request_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 8 thuộc tính của `goods_receipts`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`, `request_id`. Không nguyên tố: `order_id`, `received_by`, `note`, `received_at`, `accepted_amount`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `store_id`, cung cấp view `v_goods_receipts`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_goods_receipts_code`(`code`); UK `uq_goods_receipts_request`(`request_id`); FK `fk_goods_receipts_order`(`order_id` → `purchase_orders.id`, ON DELETE NO ACTION); FK `fk_goods_receipts_receiver`(`received_by` → `employees.id`, ON DELETE NO ACTION).
- **Quy tắc cần transaction hoặc service hỗ trợ:** NF-05: `accepted_amount` đồng bộ cùng `goods_receipt_lines`, `inventory_movements`, cập nhật `purchase_order_lines` và tạo `supplier_payables` trong cùng transaction.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.60. `goods_receipt_lines`

- **Tên quan hệ và ý nghĩa một dòng:** `goods_receipt_lines` — Chi tiết hàng đạt, hỏng và thiếu trong một lần nhận.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (6 cột):** `receipt_id` (`bigint unsigned`, NOT NULL); `ingredient_id` (`bigint unsigned`, NOT NULL); `accepted_quantity` (`bigint unsigned`, NOT NULL); `damaged_quantity` (`bigint unsigned`, NOT NULL); `missing_quantity` (`bigint unsigned`, NOT NULL); `unit_cost` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {receipt_id, ingredient_id} → {accepted_quantity, damaged_quantity, missing_quantity, unit_cost} }`. Khóa chính ghép `(receipt_id, ingredient_id)` xác định `accepted_quantity`, `damaged_quantity`, `missing_quantity`, `unit_cost` (chụp đơn giá nhập lúc nhận).
- **Phủ tối thiểu của $F$:** `F_min = { {receipt_id, ingredient_id} → accepted_quantity; {receipt_id, ingredient_id} → damaged_quantity; {receipt_id, ingredient_id} → missing_quantity; {receipt_id, ingredient_id} → unit_cost }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {receipt_id, ingredient_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 6 thuộc tính của `goods_receipt_lines`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `receipt_id`, `ingredient_id`. Không nguyên tố: `accepted_quantity`, `damaged_quantity`, `missing_quantity`, `unit_cost`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm trigger `trg_goods_receipt_lines_bi` bảo đảm nguyên liệu cùng cơ sở với phiếu nhận.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`receipt_id,ingredient_id`); FK `fk_goods_receipt_lines_ingredient`(`ingredient_id` → `inventory_ingredients.id`, ON DELETE NO ACTION); FK `fk_goods_receipt_lines_receipt`(`receipt_id` → `goods_receipts.id`, ON DELETE NO ACTION); CHECK `chk_goods_receipt_lines_quantity`; TRIGGER `trg_goods_receipt_lines_bi`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** CHECK bảo đảm `accepted_quantity + damaged_quantity + missing_quantity > 0`.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.61. `supplier_payables`

- **Tên quan hệ và ý nghĩa một dòng:** `supplier_payables` — Công nợ phát sinh từ phiếu nhận hàng và trạng thái thanh toán; cơ sở và nhà cung cấp suy ra từ `goods_receipts`→`purchase_orders`→`purchase_requests` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (9 cột):** `id` (`bigint unsigned`, NOT NULL); `receipt_id` (`bigint unsigned`, NOT NULL); `amount` (`bigint unsigned`, NOT NULL); `paid_amount` (`bigint unsigned`, NOT NULL); `due_date` (`date`, NOT NULL); `status` (`varchar(10)`, NOT NULL); `paid_at` (`datetime`, NULL); `paid_by` (`bigint unsigned`, NULL); `payment_method` (`varchar(10)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {amount, paid_amount, due_date, status, paid_at, paid_by, payment_method}; {receipt_id} → {amount, paid_amount, due_date, status, paid_at, paid_by, payment_method}; {id} → {receipt_id}; {receipt_id} → {id} }`. `{id}` và `{receipt_id}` là khóa ứng viên (1 phiếu nhận -> tối đa 1 công nợ, thanh toán 1 lần theo B05). Đã loại bỏ cả hai cột lặp bắc cầu `supplier_id` và `store_id` (NF-02) suy ra từ `receipt_id -> order_id -> (supplier_id, request_id -> store_id)`.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → amount; {id} → paid_amount; {id} → due_date; {id} → status; {id} → paid_at; {id} → paid_by; {id} → payment_method; {receipt_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {receipt_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 9 thuộc tính của `supplier_payables`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `receipt_id`. Không nguyên tố: `amount`, `paid_amount`, `due_date`, `status`, `paid_at`, `paid_by`, `payment_method`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `supplier_id` và `store_id`, tạo view `v_supplier_payables`; migration `030` thêm `chk_supplier_payables_state` (NULL-safe UNPAID/PAID) và trigger `trg_supplier_payables_bu` chặn người duyệt tự chi (`paid_by <> approved_by`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_supplier_payables_receipt`(`receipt_id`); FK `fk_supplier_payables_employee`(`paid_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_supplier_payables_receipt`(`receipt_id` → `goods_receipts.id`, ON DELETE NO ACTION); CHECK `chk_supplier_payables_amount`; CHECK `chk_supplier_payables_method`; CHECK `chk_supplier_payables_state`; CHECK `chk_supplier_payables_status`; TRIGGER `trg_supplier_payables_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thanh toán công nợ chạy nguyên tử cùng ghi bút toán `EXPENSE` vào `cash_shift_entries`.
- **Test và bằng chứng dữ liệu:** `test_operational_workflows.py`, `test_rbac_followup_mysql.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.62. `commercial_partners`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_partners` — Đối tác cung cấp game hoặc mạng quảng cáo.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (10 cột):** `id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `name` (`varchar(120)`, NOT NULL); `partner_type` (`varchar(12)`, NOT NULL); `status` (`varchar(12)`, NOT NULL); `callback_secret_ref` (`varchar(80)`, NULL); `contact_name` (`varchar(100)`, NULL); `contact_email` (`varchar(120)`, NULL); `created_at` (`datetime`, NOT NULL); `updated_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {name, partner_type, status, callback_secret_ref, contact_name, contact_email, created_at, updated_at}; {code} → {name, partner_type, status, callback_secret_ref, contact_name, contact_email, created_at, updated_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → name; {id} → partner_type; {id} → status; {id} → callback_secret_ref; {id} → contact_name; {id} → contact_email; {id} → created_at; {id} → updated_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 10 thuộc tính của `commercial_partners`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `name`, `partner_type`, `status`, `callback_secret_ref`, `contact_name`, `contact_email`, `created_at`, `updated_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_partners_code`(`code`); CHECK `chk_commercial_partners_status`; CHECK `chk_commercial_partners_type`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.63. `commercial_contracts`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_contracts` — Hợp đồng thương mại có maker-checker và mô hình tính doanh thu.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `partner_id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `status` (`varchar(12)`, NOT NULL); `revenue_model` (`varchar(8)`, NOT NULL); `rate_amount` (`bigint unsigned`, NOT NULL); `currency` (`char(3)`, NOT NULL); `starts_on` (`date`, NOT NULL); `ends_on` (`date`, NOT NULL); `created_by` (`bigint unsigned`, NOT NULL); `approved_by` (`bigint unsigned`, NULL); `approved_at` (`datetime`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {partner_id, status, revenue_model, rate_amount, currency, starts_on, ends_on, created_by, approved_by, approved_at, created_at}; {code} → {partner_id, status, revenue_model, rate_amount, currency, starts_on, ends_on, created_by, approved_by, approved_at, created_at}; {id} → {code}; {code} → {id} }`. `{id}` và `{code}` là khóa ứng viên. Tất cả thuộc tính hợp đồng (`partner_id`, `status`, `revenue_model`, `rate_amount`, `currency`, `starts_on`, `ends_on`, `created_by`, `approved_by`, `approved_at`, `created_at`) phụ thuộc trực tiếp vào khóa.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → partner_id; {id} → status; {id} → revenue_model; {id} → rate_amount; {id} → currency; {id} → starts_on; {id} → ends_on; {id} → created_by; {id} → approved_by; {id} → approved_at; {id} → created_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `commercial_contracts`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `partner_id`, `status`, `revenue_model`, `rate_amount`, `currency`, `starts_on`, `ends_on`, `created_by`, `approved_by`, `approved_at`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm trigger `trg_commercial_contracts_sod_bi/bu` chặn tự duyệt (`approved_by <> created_by`) cho mọi thao tác thêm/sửa mới mà không sửa giả dữ liệu seed cũ.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_contracts_code`(`code`); FK `fk_commercial_contracts_approver`(`approved_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_commercial_contracts_creator`(`created_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_commercial_contracts_partner`(`partner_id` → `commercial_partners.id`, ON DELETE NO ACTION); CHECK `chk_commercial_contracts_approval`; CHECK `chk_commercial_contracts_currency`; CHECK `chk_commercial_contracts_model`; CHECK `chk_commercial_contracts_period`; CHECK `chk_commercial_contracts_status`; TRIGGER `trg_commercial_contracts_sod_bi`; TRIGGER `trg_commercial_contracts_sod_bu`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Ngoại lệ lịch sử đã công bố: 2 hợp đồng seed trước 030 (`CTR-VNG-2026`, `CTR-ADS-2026` trong DB demo `cyberhub_manager`) có `created_by = approved_by = 9`, được giữ nguyên tính trung thực lịch sử theo Mục 10.5.
- **Test và bằng chứng dữ liệu:** `test_commercial_workflow.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.64. `commercial_campaigns`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_campaigns` — Chiến dịch game/quảng cáo thuộc một hợp đồng đã duyệt.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `contract_id` (`bigint unsigned`, NOT NULL); `code` (`varchar(24)`, NOT NULL); `name` (`varchar(120)`, NOT NULL); `kind` (`varchar(8)`, NOT NULL); `status` (`varchar(10)`, NOT NULL); `starts_at` (`datetime`, NOT NULL); `ends_at` (`datetime`, NOT NULL); `budget_amount` (`bigint unsigned`, NULL); `reward_type` (`varchar(12)`, NOT NULL); `reward_amount` (`int unsigned`, NOT NULL); `created_by` (`bigint unsigned`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {contract_id, name, kind, status, starts_at, ends_at, budget_amount, reward_type, reward_amount, created_by, created_at}; {code} → {contract_id, name, kind, status, starts_at, ends_at, budget_amount, reward_type, reward_amount, created_by, created_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → contract_id; {id} → name; {id} → kind; {id} → status; {id} → starts_at; {id} → ends_at; {id} → budget_amount; {id} → reward_type; {id} → reward_amount; {id} → created_by; {id} → created_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `commercial_campaigns`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `contract_id`, `name`, `kind`, `status`, `starts_at`, `ends_at`, `budget_amount`, `reward_type`, `reward_amount`, `created_by`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_campaigns_code`(`code`); FK `fk_commercial_campaigns_contract`(`contract_id` → `commercial_contracts.id`, ON DELETE NO ACTION); FK `fk_commercial_campaigns_creator`(`created_by` → `employees.id`, ON DELETE NO ACTION); CHECK `chk_commercial_campaigns_kind`; CHECK `chk_commercial_campaigns_period`; CHECK `chk_commercial_campaigns_reward`; CHECK `chk_commercial_campaigns_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.65. `commercial_placements`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_placements` — Vị trí phát game/quảng cáo, có thể giới hạn theo cửa hàng.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `campaign_id` (`bigint unsigned`, NOT NULL); `store_id` (`bigint unsigned`, NULL); `code` (`varchar(32)`, NOT NULL); `placement_type` (`varchar(8)`, NOT NULL); `surface` (`varchar(24)`, NOT NULL); `embed_url` (`varchar(500)`, NULL); `allowed_origin` (`varchar(255)`, NULL); `sandbox_policy` (`varchar(120)`, NOT NULL); `legacy_game_id` (`bigint unsigned`, NULL); `legacy_ad_creative_id` (`bigint unsigned`, NULL); `status` (`varchar(10)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {campaign_id, store_id, placement_type, surface, embed_url, allowed_origin, sandbox_policy, legacy_game_id, legacy_ad_creative_id, status, created_at}; {code} → {campaign_id, store_id, placement_type, surface, embed_url, allowed_origin, sandbox_policy, legacy_game_id, legacy_ad_creative_id, status, created_at}; {id} → {code}; {code} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {code} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → campaign_id; {id} → store_id; {id} → placement_type; {id} → surface; {id} → embed_url; {id} → allowed_origin; {id} → sandbox_policy; {id} → legacy_game_id; {id} → legacy_ad_creative_id; {id} → status; {id} → created_at; {code} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {code}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `commercial_placements`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `code`. Không nguyên tố: `campaign_id`, `store_id`, `placement_type`, `surface`, `embed_url`, `allowed_origin`, `sandbox_policy`, `legacy_game_id`, `legacy_ad_creative_id`, `status`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_placements_code`(`code`); FK `fk_commercial_placements_ad`(`legacy_ad_creative_id` → `ad_creatives.id`, ON DELETE NO ACTION); FK `fk_commercial_placements_campaign`(`campaign_id` → `commercial_campaigns.id`, ON DELETE NO ACTION); FK `fk_commercial_placements_game`(`legacy_game_id` → `games.id`, ON DELETE NO ACTION); FK `fk_commercial_placements_store`(`store_id` → `stores.id`, ON DELETE NO ACTION); CHECK `chk_commercial_placements_embed`; CHECK `chk_commercial_placements_status`; CHECK `chk_commercial_placements_surface`; CHECK `chk_commercial_placements_type`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.66. `commercial_play_sessions`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_play_sessions` — Phiên chơi ngoài có token một lần và hạn sử dụng.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (10 cột):** `id` (`bigint unsigned`, NOT NULL); `placement_id` (`bigint unsigned`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `token_hash` (`char(64)`, NOT NULL); `status` (`varchar(10)`, NOT NULL); `reward_type` (`varchar(12)`, NOT NULL); `reward_amount` (`int unsigned`, NOT NULL); `issued_at` (`datetime`, NOT NULL); `expires_at` (`datetime`, NOT NULL); `completed_at` (`datetime`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {placement_id, account_id, status, reward_type, reward_amount, issued_at, expires_at, completed_at}; {token_hash} → {placement_id, account_id, status, reward_type, reward_amount, issued_at, expires_at, completed_at}; {id} → {token_hash}; {token_hash} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {token_hash} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → placement_id; {id} → account_id; {id} → status; {id} → reward_type; {id} → reward_amount; {id} → issued_at; {id} → expires_at; {id} → completed_at; {token_hash} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {token_hash}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 10 thuộc tính của `commercial_play_sessions`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `token_hash`. Không nguyên tố: `placement_id`, `account_id`, `status`, `reward_type`, `reward_amount`, `issued_at`, `expires_at`, `completed_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_play_sessions_token`(`token_hash`); FK `fk_commercial_play_sessions_account`(`account_id` → `accounts.id`, ON DELETE NO ACTION); FK `fk_commercial_play_sessions_placement`(`placement_id` → `commercial_placements.id`, ON DELETE NO ACTION); CHECK `chk_commercial_play_sessions_period`; CHECK `chk_commercial_play_sessions_reward`; CHECK `chk_commercial_play_sessions_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.67. `commercial_events`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_events` — Sổ sự kiện impression/start/complete/click, chống ghi trùng; chiến dịch suy ra từ `commercial_placements.campaign_id` (NF-02).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `placement_id` (`bigint unsigned`, NOT NULL); `play_session_id` (`bigint unsigned`, NULL); `account_id` (`bigint unsigned`, NULL); `event_type` (`varchar(10)`, NOT NULL); `event_key` (`varchar(80)`, NOT NULL); `provider_event_id` (`varchar(100)`, NULL); `verification_method` (`varchar(8)`, NOT NULL); `accepted` (`tinyint(1)`, NOT NULL); `occurred_at` (`datetime`, NOT NULL); `verified_at` (`datetime`, NULL); `payload_digest` (`char(64)`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {placement_id, play_session_id, account_id, event_type, provider_event_id, verification_method, accepted, occurred_at, verified_at, payload_digest, created_at}; {event_key} → {placement_id, play_session_id, account_id, event_type, provider_event_id, verification_method, accepted, occurred_at, verified_at, payload_digest, created_at}; {id} → {event_key}; {event_key} → {id} }`. `{id}` và `{event_key}` là khóa ứng viên (`provider_event_id` là `UNIQUE` nullable, không tính là khóa ứng viên cổ điển theo Mục 3.1). Đã loại bỏ `campaign_id` lặp bắc cầu từ `placement_id -> campaign_id` (NF-02).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → placement_id; {id} → play_session_id; {id} → account_id; {id} → event_type; {id} → provider_event_id; {id} → verification_method; {id} → accepted; {id} → occurred_at; {id} → verified_at; {id} → payload_digest; {id} → created_at; {event_key} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {event_key}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `commercial_events`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu. *(UNIQUE nullable không phải CK: `provider_event_id`)*.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `event_key`. Không nguyên tố: `placement_id`, `play_session_id`, `account_id`, `event_type`, `provider_event_id`, `verification_method`, `accepted`, `occurred_at`, `verified_at`, `payload_digest`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-02): xóa `campaign_id`, cung cấp view `v_commercial_events`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_events_key`(`event_key`); UK `uq_commercial_events_provider`(`provider_event_id`); FK `fk_commercial_events_account`(`account_id` → `accounts.id`, ON DELETE NO ACTION); FK `fk_commercial_events_placement`(`placement_id` → `commercial_placements.id`, ON DELETE NO ACTION); FK `fk_commercial_events_session`(`play_session_id` → `commercial_play_sessions.id`, ON DELETE NO ACTION); CHECK `chk_commercial_events_complete`; CHECK `chk_commercial_events_type`; CHECK `chk_commercial_events_verification`; CHECK `chk_commercial_events_verified`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Chống replay bằng `UNIQUE(event_key)` và `UNIQUE(provider_event_id)`; sự kiện `COMPLETE` bắt buộc `verification_method IN ('SERVER','SSV')`.
- **Test và bằng chứng dữ liệu:** `test_commercial_workflow.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.68. `commercial_reward_grants`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_reward_grants` — Outbox phần thưởng; callback không được cộng xu/phát voucher trực tiếp.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (10 cột):** `id` (`bigint unsigned`, NOT NULL); `event_id` (`bigint unsigned`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `reward_type` (`varchar(12)`, NOT NULL); `reward_amount` (`int unsigned`, NOT NULL); `status` (`varchar(10)`, NOT NULL); `attempts` (`int unsigned`, NOT NULL); `created_at` (`datetime`, NOT NULL); `applied_at` (`datetime`, NULL); `failure_reason` (`varchar(255)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {account_id, reward_type, reward_amount, status, attempts, created_at, applied_at, failure_reason}; {event_id} → {account_id, reward_type, reward_amount, status, attempts, created_at, applied_at, failure_reason}; {id} → {event_id}; {event_id} → {id} }`. `{id}` và `{event_id}` là khóa ứng viên (`event_id` UNIQUE NOT NULL). Do `event_id` là siêu khóa, FD `event_id -> account_id` KHÔNG vi phạm 3NF (xác nhận theo Mục 4 NF-02).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → account_id; {id} → reward_type; {id} → reward_amount; {id} → status; {id} → attempts; {id} → created_at; {id} → applied_at; {id} → failure_reason; {event_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {event_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 10 thuộc tính của `commercial_reward_grants`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `event_id`. Không nguyên tố: `account_id`, `reward_type`, `reward_amount`, `status`, `attempts`, `created_at`, `applied_at`, `failure_reason`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm trigger `trg_commercial_reward_grants_bi` chặn cấp thưởng sai `account_id` so với `commercial_events`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_reward_grants_event`(`event_id`); FK `fk_commercial_reward_grants_account`(`account_id` → `accounts.id`, ON DELETE NO ACTION); FK `fk_commercial_reward_grants_event`(`event_id` → `commercial_events.id`, ON DELETE NO ACTION); CHECK `chk_commercial_reward_grants_reward`; CHECK `chk_commercial_reward_grants_status`; TRIGGER `trg_commercial_reward_grants_bi`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Outbox pattern: callback xác minh chỉ ghi hàng `PENDING`; worker xử lý ngoài callback để cộng xu/phát voucher idempotent.
- **Test và bằng chứng dữ liệu:** `test_commercial_workflow.py`, `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.69. `commercial_settlements`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_settlements` — Kỳ đối soát doanh thu có maker-checker; `net_amount` tính qua `v_commercial_settlements` (NF-01).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (13 cột):** `id` (`bigint unsigned`, NOT NULL); `contract_id` (`bigint unsigned`, NOT NULL); `period_start` (`date`, NOT NULL); `period_end` (`date`, NOT NULL); `gross_amount` (`bigint unsigned`, NOT NULL); `adjustment_amount` (`bigint`, NOT NULL); `adjustment_reason` (`varchar(255)`, NULL); `status` (`varchar(10)`, NOT NULL); `generated_by` (`bigint unsigned`, NOT NULL); `reviewed_by` (`bigint unsigned`, NULL); `reviewed_at` (`datetime`, NULL); `paid_at` (`datetime`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {gross_amount, adjustment_amount, adjustment_reason, status, generated_by, reviewed_by, reviewed_at, paid_at, created_at}; {contract_id, period_start, period_end} → {gross_amount, adjustment_amount, adjustment_reason, status, generated_by, reviewed_by, reviewed_at, paid_at, created_at}; {id} → {contract_id, period_start, period_end}; {contract_id, period_start, period_end} → {id} }`. `{id}` và `{contract_id, period_start, period_end}` là khóa ứng viên. Đã loại bỏ cột công thức `net_amount = gross_amount + adjustment_amount` (NF-01).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → gross_amount; {id} → adjustment_amount; {id} → adjustment_reason; {id} → status; {id} → generated_by; {id} → reviewed_by; {id} → reviewed_at; {id} → paid_at; {id} → created_at; {contract_id, period_start, period_end} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {contract_id, period_start, period_end}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 13 thuộc tính của `commercial_settlements`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `contract_id`, `period_start`, `period_end`. Không nguyên tố: `gross_amount`, `adjustment_amount`, `adjustment_reason`, `status`, `generated_by`, `reviewed_by`, `reviewed_at`, `paid_at`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01): xóa `net_amount`, thêm `chk_commercial_settlements_net_nonnegative`, cung cấp view `v_commercial_settlements`; migration `030` sửa `chk_commercial_settlements_adjustment` (chặn `NULL/UNKNOWN`) và thêm `chk_commercial_settlements_lifecycle` (kèm SoD `reviewed_by <> generated_by`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_commercial_settlements_period`(`contract_id,period_start,period_end`); FK `fk_commercial_settlements_contract`(`contract_id` → `commercial_contracts.id`, ON DELETE NO ACTION); FK `fk_commercial_settlements_generator`(`generated_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_commercial_settlements_reviewer`(`reviewed_by` → `employees.id`, ON DELETE NO ACTION); CHECK `chk_commercial_settlements_adjustment`; CHECK `chk_commercial_settlements_lifecycle`; CHECK `chk_commercial_settlements_net_nonnegative`; CHECK `chk_commercial_settlements_period`; CHECK `chk_commercial_settlements_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Chống chồng lấn kỳ đối soát và kiểm tra `FIXED` chỉ đối soát 1 lần cho toàn hợp đồng tại `CommercialService`.
- **Test và bằng chứng dữ liệu:** `test_commercial_workflow.py`, `test_3nf_and_integrity.py`; tổng `gross`/`adj`/`net` khớp 100% trên clone.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.70. `commercial_settlement_lines`

- **Tên quan hệ và ý nghĩa một dòng:** `commercial_settlement_lines` — Dòng snapshot đối soát theo vị trí và loại sự kiện; thành tiền `amount` tính qua `v_commercial_settlement_lines` (NF-01).
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (5 cột):** `settlement_id` (`bigint unsigned`, NOT NULL); `placement_id` (`bigint unsigned`, NOT NULL); `event_type` (`varchar(10)`, NOT NULL); `units` (`bigint unsigned`, NOT NULL); `unit_rate` (`bigint unsigned`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {settlement_id, placement_id, event_type} → {units, unit_rate} }`. Khóa chính ghép `(settlement_id, placement_id, event_type)`. Đã loại bỏ cột công thức `amount` (NF-01) vì `(event_type, units, unit_rate) -> amount` theo công thức xác định của `RevenueModel` (`CPM`: `FLOOR(units * unit_rate / 1000)`, `FIXED`: `unit_rate` nếu `units > 0`, `CPC/CPA`: `units * unit_rate`).
- **Phủ tối thiểu của $F$:** `F_min = { {settlement_id, placement_id, event_type} → units; {settlement_id, placement_id, event_type} → unit_rate }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {settlement_id, placement_id, event_type}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 5 thuộc tính của `commercial_settlement_lines`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `settlement_id`, `placement_id`, `event_type`. Không nguyên tố: `units`, `unit_rate`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF: không có thuộc tính không nguyên tố nào phụ thuộc vào tập con thực sự của khóa ứng viên ghép. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Migration `028` (NF-01): chuẩn hóa `unit_rate` theo đơn giá CPM/1000 hợp đồng cho dữ liệu seed cũ trước khi xóa cột `amount`; cung cấp view `v_commercial_settlement_lines`.
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Đã chứng minh chi tiết bằng Định lý Heath tại Mục 3 ở trên; đối soát clone dữ liệu thật đạt 0 sai lệch.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`settlement_id,placement_id,event_type`); FK `fk_commercial_settlement_lines_placement`(`placement_id` → `commercial_placements.id`, ON DELETE NO ACTION); FK `fk_commercial_settlement_lines_settlement`(`settlement_id` → `commercial_settlements.id`, ON DELETE NO ACTION); CHECK `chk_commercial_settlement_lines_event`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Bản ghi snapshot bất biến tạo cùng `commercial_settlements` trong một transaction.
- **Test và bằng chứng dữ liệu:** `test_commercial_workflow.py`, `test_3nf_and_integrity.py`; đối soát `SUM(amount)` trên clone khớp tuyệt đối 2.150.000 VND.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.71. `supplier_payable_approvals`

- **Tên quan hệ và ý nghĩa một dòng:** `supplier_payable_approvals` — Bản ghi duyệt công nợ nhà cung cấp; dùng kiểm soát phân tách người duyệt và người chi.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (4 cột):** `payable_id` (`bigint unsigned`, NOT NULL); `approved_by` (`bigint unsigned`, NOT NULL); `approved_at` (`datetime`, NOT NULL); `note` (`varchar(255)`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {payable_id} → {approved_by, approved_at, note} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {payable_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {payable_id} → approved_by; {payable_id} → approved_at; {payable_id} → note }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {payable_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 4 thuộc tính của `supplier_payable_approvals`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `payable_id`. Không nguyên tố: `approved_by`, `approved_at`, `note`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`payable_id`); FK `fk_payable_approval_employee`(`approved_by` → `employees.id`, ON DELETE NO ACTION); FK `fk_payable_approval_payable`(`payable_id` → `supplier_payables.id`, ON DELETE NO ACTION).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.72. `customer_email_tokens`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_email_tokens` — Token kích hoạt/đặt lại mật khẩu khách; chỉ lưu hash và nonce dẫn xuất, token thô không được lưu.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (8 cột):** `id` (`bigint unsigned`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `purpose` (`varchar(12)`, NOT NULL); `token_hash` (`char(64)`, NOT NULL); `nonce` (`char(64)`, NOT NULL); `expires_at` (`datetime`, NOT NULL); `used_at` (`datetime`, NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {account_id, purpose, nonce, expires_at, used_at, created_at}; {token_hash} → {account_id, purpose, nonce, expires_at, used_at, created_at}; {id} → {token_hash}; {token_hash} → {id} }`. `{id}` và `{token_hash}` là khóa ứng viên. Chỉ lưu SHA-256 hash và nonce dẫn xuất, không lưu token thô.
- **Phủ tối thiểu của $F$:** `F_min = { {id} → account_id; {id} → purpose; {id} → nonce; {id} → expires_at; {id} → used_at; {id} → created_at; {token_hash} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {token_hash}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 8 thuộc tính của `customer_email_tokens`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `token_hash`. Không nguyên tố: `account_id`, `purpose`, `nonce`, `expires_at`, `used_at`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã 3NF; migration `030` thêm `chk_customer_email_token_times` (`expires_at > created_at` và `used_at >= created_at`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_customer_email_token_hash`(`token_hash`); FK `fk_customer_email_token_account`(`account_id` → `accounts.id`, ON DELETE NO ACTION); CHECK `chk_customer_email_token_purpose`; CHECK `chk_customer_email_token_times`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Token dùng một lần, kiểm tra `purpose`, hạn sử dụng và `used_at IS NULL` trong transaction.
- **Test và bằng chứng dữ liệu:** `test_3nf_and_integrity.py`.
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.73. `customer_mail_outbox`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_mail_outbox` — Transactional outbox gửi email khách sau khi transaction đăng ký/reset đã commit.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (7 cột):** `id` (`bigint unsigned`, NOT NULL); `token_id` (`bigint unsigned`, NOT NULL); `status` (`varchar(12)`, NOT NULL); `attempts` (`int unsigned`, NOT NULL); `next_attempt_at` (`datetime`, NOT NULL); `sent_at` (`datetime`, NULL); `last_error` (`varchar(120)`, NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {status, attempts, next_attempt_at, sent_at, last_error}; {token_id} → {status, attempts, next_attempt_at, sent_at, last_error}; {id} → {token_id}; {token_id} → {id} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id}, {token_id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → status; {id} → attempts; {id} → next_attempt_at; {id} → sent_at; {id} → last_error; {token_id} ↔ {id} }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}, {token_id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 7 thuộc tính của `customer_mail_outbox`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`, `token_id`. Không nguyên tố: `status`, `attempts`, `next_attempt_at`, `sent_at`, `last_error`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); UK `uq_customer_mail_outbox_token`(`token_id`); FK `fk_customer_mail_outbox_token`(`token_id` → `customer_email_tokens.id`, ON DELETE NO ACTION); CHECK `chk_customer_mail_outbox_status`.
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

### 4.74. `customer_security_audit`

- **Tên quan hệ và ý nghĩa một dòng:** `customer_security_audit` — Audit bất biến cho thao tác kích hoạt, đặt lại mật khẩu và các sự kiện bảo mật khách.
- **Thuộc tính, miền giá trị, ngữ nghĩa NULL (6 cột):** `id` (`bigint unsigned`, NOT NULL); `account_id` (`bigint unsigned`, NOT NULL); `employee_id` (`bigint unsigned`, NULL); `store_id` (`bigint unsigned`, NULL); `action` (`varchar(40)`, NOT NULL); `created_at` (`datetime`, NOT NULL).
- **Tập FD nghiệp vụ và nguồn xác nhận:** `F = { {id} → {account_id, employee_id, store_id, action, created_at} }`. Mọi thuộc tính không nguyên tố phụ thuộc hàm đầy đủ và trực tiếp vào từng khóa ứng viên {id} (xác nhận từ migration DDL và repository tầng infrastructure).
- **Phủ tối thiểu của $F$:** `F_min = { {id} → account_id; {id} → employee_id; {id} → store_id; {id} → action; {id} → created_at }`.
- **Mọi khóa ứng viên (bao đóng $X^+$ và tính tối thiểu):** {id}. Với mỗi khóa $K$, bao đóng $K^+ = U$ (toàn bộ 6 thuộc tính của `customer_security_audit`), và mọi tập con thực sự $K' \subsetneq K$ có $(K')^+ \neq U$ nên $K$ tối thiểu.
- **Thuộc tính nguyên tố / không nguyên tố:** Nguyên tố: `id`. Không nguyên tố: `account_id`, `employee_id`, `store_id`, `action`, `created_at`.
- **Kiểm tra 1NF, 2NF, 3NF trên $F^+$:** Đạt 1NF (toàn bộ miền nguyên tử, 0 cột lặp/JSON/generated). Đạt 2NF tự động vì mọi khóa ứng viên đều đơn thuộc tính (1 cột), không tồn tại phụ thuộc một phần. Đạt 3NF (và BCNF): với mọi phụ thuộc hàm không tầm thường $X \to A \in F^+$, vế trái $X$ là siêu khóa (không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không nguyên tố).
- **Phép phân rã đề xuất / đã thực hiện:** Không cần phân rã (quan hệ đã đạt 3NF/BCNF trước và sau migration `028`–`030`).
- **Chứng minh nối không mất mát và bảo toàn phụ thuộc:** Không phân rã bảng; quan hệ giữ nguyên toàn bộ thuộc tính và phụ thuộc hàm gốc.
- **PK / UNIQUE / FK / CHECK / TRIGGER hiện thực hóa:** PK(`id`); FK `fk_customer_security_account`(`account_id` → `accounts.id`, ON DELETE NO ACTION); FK `fk_customer_security_employee`(`employee_id` → `employees.id`, ON DELETE NO ACTION); FK `fk_customer_security_store`(`store_id` → `stores.id`, ON DELETE NO ACTION).
- **Quy tắc cần transaction hoặc service hỗ trợ:** Thực thi qua repository trong transaction của application service (`transaction()`), kiểm tra quyền RBAC và phạm vi cửa hàng trước khi ghi.
- **Test và bằng chứng dữ liệu:** Kiểm chứng schema và cấu trúc qua `test_data_dictionary.py`, `test_3nf_and_integrity.py` và bộ integration test theo phân hệ (260/260 pass).
- **Kết luận, người rà soát, ngày rà soát:** **ĐẠT 3NF NGHIÊM NGẶT** — Rà soát & kiểm chứng tự động trên MySQL 8.4 (`cyberhub_manager_test`), ngày **21/11/2026**.

## 5. Danh sách 18 View đọc tương thích (`v_*`) và 28 Trigger toàn vẹn

### 5.1. 18 View đọc chuẩn 3NF

`v_accounts`, `v_cash_shift_entries`, `v_cash_shifts`, `v_commercial_events`, `v_commercial_settlement_lines`, `v_commercial_settlements`, `v_employees`, `v_goods_receipts`, `v_inventory_counts`, `v_inventory_movements`, `v_invoices`, `v_machine_incidents`, `v_menu_items`, `v_menu_order_pricing`, `v_menu_orders`, `v_pos_order_reversals`, `v_purchase_orders`, `v_supplier_payables`.

### 5.2. Danh sách Trigger thực thi toàn vẹn tại MySQL 8.4

| Trigger | Bảng | Thời điểm | Sự kiện |
|---|---|---|---|
| `trg_account_transactions_bi` | `account_transactions` | `BEFORE` | `INSERT` |
| `trg_account_transactions_bu` | `account_transactions` | `BEFORE` | `UPDATE` |
| `trg_cash_shifts_ai` | `cash_shifts` | `AFTER` | `INSERT` |
| `trg_cash_shifts_au` | `cash_shifts` | `AFTER` | `UPDATE` |
| `trg_cash_shifts_bu_no_reopen` | `cash_shifts` | `BEFORE` | `UPDATE` |
| `trg_commercial_contracts_sod_bi` | `commercial_contracts` | `BEFORE` | `INSERT` |
| `trg_commercial_contracts_sod_bu` | `commercial_contracts` | `BEFORE` | `UPDATE` |
| `trg_commercial_reward_grants_bi` | `commercial_reward_grants` | `BEFORE` | `INSERT` |
| `trg_goods_receipt_lines_bi` | `goods_receipt_lines` | `BEFORE` | `INSERT` |
| `trg_invoices_bi` | `invoices` | `BEFORE` | `INSERT` |
| `trg_invoices_bu` | `invoices` | `BEFORE` | `UPDATE` |
| `trg_loyalty_point_grants_bi` | `loyalty_point_grants` | `BEFORE` | `INSERT` |
| `trg_menu_item_recipes_bi` | `menu_item_recipes` | `BEFORE` | `INSERT` |
| `trg_menu_item_recipes_bu` | `menu_item_recipes` | `BEFORE` | `UPDATE` |
| `trg_menu_items_bi` | `menu_items` | `BEFORE` | `INSERT` |
| `trg_menu_items_bu` | `menu_items` | `BEFORE` | `UPDATE` |
| `trg_menu_promotions_bi` | `menu_promotions` | `BEFORE` | `INSERT` |
| `trg_menu_promotions_bu` | `menu_promotions` | `BEFORE` | `UPDATE` |
| `trg_purchase_order_lines_bi` | `purchase_order_lines` | `BEFORE` | `INSERT` |
| `trg_purchase_orders_bi` | `purchase_orders` | `BEFORE` | `INSERT` |
| `trg_purchase_orders_bu` | `purchase_orders` | `BEFORE` | `UPDATE` |
| `trg_purchase_request_lines_bi` | `purchase_request_lines` | `BEFORE` | `INSERT` |
| `trg_session_transactions_bi` | `session_transactions` | `BEFORE` | `INSERT` |
| `trg_session_transactions_bu` | `session_transactions` | `BEFORE` | `UPDATE` |
| `trg_supplier_payables_bu` | `supplier_payables` | `BEFORE` | `UPDATE` |
| `trg_usage_sessions_ai` | `usage_sessions` | `AFTER` | `INSERT` |
| `trg_usage_sessions_au` | `usage_sessions` | `AFTER` | `UPDATE` |
| `trg_usage_sessions_bu_no_reopen` | `usage_sessions` | `BEFORE` | `UPDATE` |
