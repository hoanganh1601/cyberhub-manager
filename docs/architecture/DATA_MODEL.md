# Current database model

The application schema contains **24 normalized (3NF) business tables**, **8 read views (`v_*`)**, and **15 integrity triggers** (100% InnoDB, `utf8mb4_0900_ai_ci`, zero JSON columns, zero generated columns). `schema_migrations` is technical metadata and is not included in that count. See the [current ERD](../diagrams/current_erd.md) and [data dictionary](../diagrams/data_dictionary.md) for entities, attributes, constraints, and relationships.

## Table groups

| Migration | Domain group | Tables |
|---|---|---|
| `001_stores_and_identity.sql` | Organization & identity | `stores`, `employee_profiles`, `employees`, `employee_store_assignments`, `management_audit` |
| `002_customers_and_accounts.sql` | Customers & wallet setup | `customers`, `accounts`, `promotions` |
| `003_machines_sessions_and_billing.sql` | Workstations, sessions & billing | `machines`, `machine_room_types`, `usage_sessions`, `active_usage_sessions`, `account_transactions`, `invoices` |
| `004_menu_and_pos_orders.sql` | Menu & POS orders | `menu_categories`, `menu_items`, `menu_orders`, `menu_order_items` |
| `005_pos_promotions_and_reversals.sql` | POS promotions & reversals | `menu_promotions`, `menu_promotion_versions`, `menu_order_pricing`, `pos_order_reversals` |
| `006_customer_notifications.sql` | Customer notifications | `customer_notification_events`, `customer_notification_reads` |

## Supporting database objects

- `007_indexes.sql`: secondary indexes for operational lookups and revenue reporting.
- `008_read_views.sql`: 8 read views (`v_employees`, `v_accounts`, `v_invoices`, `v_menu_items`, `v_menu_orders`, `v_menu_order_pricing`, `v_pos_order_reversals`, `v_customer_notification_events`).
- `009_integrity_triggers.sql`: 15 triggers enforcing active session occupancy, store-wide unique menu names, cross-store/cross-owner guards, and reversal refund ceilings.

Run `python scripts/init_db.py` to initialize a fresh database.
