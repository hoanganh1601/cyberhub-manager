# ERD hiện hành — đối chiếu migration 001–027

Nguồn: `sql/001_initial_schema.sql` → `sql/027_customer_email_activation.sql`, theo thứ tự [runner](../../scripts/init_db.py). 70 bảng nghiệp vụ dưới đây đã được đối chiếu bằng [data dictionary](data_dictionary.md) sinh từ `INFORMATION_SCHEMA` của MySQL test. Bảng kỹ thuật `schema_migrations` do runner tạo riêng.

Mỗi quan hệ có tên **cột FK của bảng con** sau dấu `:`; đường liên kết không thay thế định nghĩa NULL, UNIQUE, `ON DELETE` hay CHECK trong SQL. Bảng độc lập có khối riêng. PK mặc định `id`, ngoại trừ các bảng liệt kê dưới đây. Dùng [data dictionary](data_dictionary.md) để xem kiểu cột, index và ràng buộc đầy đủ.

| Bảng | PK từ migration (các cột này cũng là FK nếu có quan hệ tương ứng trong sơ đồ) |
|---|---|
| `customer_avatars`, `game_wallets` | `account_id` |
| `machine_room_types` | `machine_id` |
| `menu_item_images` | `item_id` |
| `menu_order_pricing` | `order_id` |
| `customer_notification_reads` | `(account_id, notification_key)` |
| `menu_item_recipes` | `(item_id, ingredient_id)` |
| `menu_order_items` | `(order_id, item_id)` |
| `menu_order_recipe_snapshots` | `(order_id, item_id, ingredient_id)` |
| `purchase_request_lines` | `(request_id, ingredient_id)` |
| `purchase_order_lines` | `(order_id, ingredient_id)` |
| `goods_receipt_lines` | `(receipt_id, ingredient_id)` |
| `commercial_settlement_lines` | `(settlement_id, placement_id, event_type)` |
| `employee_store_assignments` | `(employee_id, store_id)` |
| `customer_store_links` | `(customer_id, store_id)` |
| `supplier_payable_approvals` | `payable_id` |

## Cửa hàng, định danh, phiên và tiền (14 bảng)

```mermaid
erDiagram
    stores ||--o{ employees : store_id
    stores ||--o{ machines : store_id
    stores ||--o{ invoices : store_id
    stores o|--o{ promotions : store_id
    stores ||--o{ management_audit : store_id
    customers ||--o| accounts : customer_id
    customers ||--o{ usage_sessions : customer_id
    customers ||--o{ invoices : customer_id
    machines ||--o{ usage_sessions : machine_id
    machines ||--o| machine_room_types : machine_id
    employees ||--o{ usage_sessions : opened_by
    employees ||--o{ invoices : employee_id
    employees ||--o{ management_audit : employee_id
    accounts ||--o{ account_transactions : account_id
    accounts ||--o{ customer_notification_reads : account_id
    accounts ||--o| customer_avatars : account_id
    usage_sessions ||--o| invoices : session_id
    usage_sessions o|--o{ account_transactions : session_id
    promotions o|--o{ account_transactions : promotion_id
    loyalty_settings {
        bigint id PK
    }
```

## Menu, đơn POS và kho (15 bảng)

```mermaid
erDiagram
    stores ||--o{ menu_categories : store_id
    stores ||--o{ menu_items : store_id
    menu_categories ||--o{ menu_items : category_id
    menu_items ||--o| menu_item_images : item_id
    menu_items ||--o{ menu_item_changes : item_id
    employees ||--o{ menu_item_changes : employee_id
    stores ||--o{ menu_orders : store_id
    accounts ||--o{ menu_orders : account_id
    usage_sessions ||--o{ menu_orders : session_id
    machines ||--o{ menu_orders : machine_id
    menu_orders ||--o{ menu_order_items : order_id
    menu_items ||--o{ menu_order_items : item_id
    stores ||--o{ inventory_ingredients : store_id
    menu_items ||--o{ menu_item_recipes : item_id
    inventory_ingredients ||--o{ menu_item_recipes : ingredient_id
    menu_order_items ||--o{ menu_order_recipe_snapshots : "order_id,item_id"
    inventory_ingredients ||--o{ menu_order_recipe_snapshots : ingredient_id
    inventory_ingredients ||--o{ inventory_movements : "store_id,ingredient_id"
    inventory_ingredients ||--o{ inventory_counts : "store_id,ingredient_id"
    menu_orders ||--o{ inventory_movements : order_id
    accounts ||--o{ customer_notification_events : account_id
    stores ||--o{ customer_notification_events : store_id
    menu_orders ||--o| pos_order_reversals : order_id
    stores ||--o{ menu_promotions : store_id
    menu_items o|--o{ menu_promotions : item_id
    menu_orders ||--o| menu_order_pricing : order_id
    menu_promotions o|--o{ menu_order_pricing : promotion_id
```

## Voucher, game và quảng cáo nhận thưởng (12 bảng)

```mermaid
erDiagram
    stores ||--o{ reward_catalog : store_id
    reward_catalog ||--o{ customer_vouchers : catalog_id
    accounts ||--o{ customer_vouchers : account_id
    customer_vouchers o|--o{ voucher_events : voucher_id
    customer_vouchers ||--o| loyalty_point_grants : voucher_id
    games ||--o{ game_prizes : game_id
    games ||--o{ game_sessions : game_id
    accounts ||--o| game_wallets : account_id
    accounts ||--o{ game_sessions : account_id
    accounts ||--o{ game_coin_ledger : account_id
    customer_vouchers o|--o{ game_coin_ledger : voucher_id
    ad_creatives o|--o{ ad_reward_events : creative_id
    accounts ||--o{ ad_reward_events : account_id
    ad_settings {
        bigint id PK
    }
```

## Ca/két, bảo trì và mua hàng (13 bảng)

```mermaid
erDiagram
    stores ||--o{ cash_shifts : store_id
    employees ||--o{ cash_shifts : employee_id
    cash_shifts ||--o{ cash_shift_entries : shift_id
    stores ||--o{ machine_incidents : store_id
    machines ||--o{ machine_incidents : machine_id
    machine_incidents ||--o{ machine_incident_parts : incident_id
    machine_incidents ||--o{ machine_incident_events : incident_id
    stores ||--o{ suppliers : store_id
    stores ||--o{ purchase_requests : store_id
    purchase_requests ||--o{ purchase_request_lines : request_id
    inventory_ingredients ||--o{ purchase_request_lines : ingredient_id
    purchase_requests ||--o| purchase_orders : request_id
    suppliers ||--o{ purchase_orders : supplier_id
    purchase_orders ||--o{ purchase_order_lines : order_id
    inventory_ingredients ||--o{ purchase_order_lines : ingredient_id
    purchase_orders ||--o{ goods_receipts : order_id
    goods_receipts ||--o{ goods_receipt_lines : receipt_id
    goods_receipts ||--o| supplier_payables : receipt_id
    suppliers ||--o{ supplier_payables : supplier_id
```

## Đối tác thương mại (9 bảng)

```mermaid
erDiagram
    commercial_partners ||--o{ commercial_contracts : partner_id
    commercial_contracts ||--o{ commercial_campaigns : contract_id
    commercial_campaigns ||--o{ commercial_placements : campaign_id
    stores o|--o{ commercial_placements : store_id
    commercial_placements ||--o{ commercial_play_sessions : placement_id
    accounts ||--o{ commercial_play_sessions : account_id
    commercial_placements ||--o{ commercial_events : placement_id
    commercial_campaigns ||--o{ commercial_events : campaign_id
    commercial_events ||--o| commercial_reward_grants : event_id
    commercial_contracts ||--o{ commercial_settlements : contract_id
    commercial_settlements ||--o{ commercial_settlement_lines : settlement_id
    commercial_placements ||--o{ commercial_settlement_lines : placement_id
```

## RBAC theo cơ sở và email khách hàng (7 bảng mới ở migration 026–027)

```mermaid
erDiagram
    employees o|--o| employee_profiles : employee_id
    stores ||--o{ employee_profiles : home_store_id
    employees ||--o{ employee_store_assignments : employee_id
    stores ||--o{ employee_store_assignments : store_id
    employees ||--o{ employee_store_assignments : granted_by
    customers ||--o{ customer_store_links : customer_id
    stores ||--o{ customer_store_links : store_id
    supplier_payables ||--o| supplier_payable_approvals : payable_id
    employees ||--o{ supplier_payable_approvals : approved_by
    accounts ||--o{ customer_email_tokens : account_id
    customer_email_tokens ||--o| customer_mail_outbox : token_id
    accounts ||--o{ customer_security_audit : account_id
    employees o|--o{ customer_security_audit : employee_id
    stores o|--o{ customer_security_audit : store_id
```

Quan hệ còn lại (đặc biệt nhiều FK tới `employees`, `stores`, `accounts` và các FK nullable) xem trực tiếp SQL tương ứng. Các sơ đồ con tách theo nghiệp vụ để dễ đọc; một bảng có thể xuất hiện ở nhiều sơ đồ khi là bảng cha chung.
