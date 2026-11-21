# Current database model

The application schema contains **22 business tables**. `schema_migrations` is technical metadata and is not included in that count. See the [current ERD](../diagrams/current_erd.md) for entities, attributes, and relationships.

## Table groups

| Group | Tables |
|---|---|
| Core | `stores`, `employees`, `customers`, `accounts`, `machines`, `usage_sessions`, `account_transactions`, `invoices` |
| Administration | `promotions`, `management_audit`, `machine_room_types`, `employee_profiles`, `employee_store_assignments` |
| Menu and POS | `menu_categories`, `menu_items`, `menu_orders`, `menu_order_items`, `pos_order_reversals`, `menu_promotions`, `menu_order_pricing` |
| Customer notifications | `customer_notification_events`, `customer_notification_reads` |

## Migrations

Migrations 028 and 029 establish the earlier 24-table scope and remove loyalty/tier-based promotion fields. Migration `030_scope_to_20_tables.sql` drops `customer_email_tokens`, `customer_mail_outbox`, `customer_security_audit`, and `customer_store_links`. Email activation/recovery, customer security event history, and customer-to-store history are outside the reduced project.

The four removed tables and their data are permanently deleted when migration 030 is applied. Migration 031 then adds the two order-status notification tables. Back up any existing database before migrating. A fresh database is initialized with `python scripts/init_db.py`; the resulting schema has 22 business tables plus `schema_migrations`.
