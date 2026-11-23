# In-scope business flows

## Stores and employees

Stores scope employees, machines, menu data, and POS operations. `employee_profiles` separates HR personnel records (home store, name, employment status) from `employees` login credentials, and `employee_store_assignments` grants additional cross-store access to `MANAGER` accounts. Sensitive administrative and operational actions are recorded in `management_audit`.

## Customers, accounts, and wallet

A customer owns one account (`customers` → `accounts`). `account_transactions` is an append-only, immutable financial ledger (protected by `BEFORE UPDATE` triggers and `ON DELETE RESTRICT`) recording top-ups (`TOP_UP`), promotional credits (`PROMOTION`), usage payments (`USAGE_PAYMENT`), and debt settlements (`DEBT_SETTLEMENT`). `session_transactions` normalizes the 1:0..1 link between usage/settlement ledger rows and `usage_sessions`. `promotions` stores general store-level or global top-up offers. The reduced scope does not award loyalty points or member tiers.

## Machines, sessions, and invoices

`machines` and `machine_room_types` model store workstations and room classifications (`STANDARD`, `VIP`, `COUPLE`, `SUPER_VIP`). An employee opens a `usage_sessions` record for a customer on a machine; `active_usage_sessions` enforces at most one active session per machine and per customer via `UNIQUE` constraints. Active sessions can be checked out to produce a `PAID` record in `invoices` or cancelled (`CANCELLED`, blocked if open POS orders exist, with `SESSION_CANCEL` audit). Paid invoices can be voided (`VOID`) by authorized managers (`INVOICE_VOID` audit) and are automatically excluded from net revenue reports.

## Menu and POS

`menu_categories` and `menu_items` define each store's food and drink catalog. A customer with an active workstation session places orders into `menu_orders` and `menu_order_items` (storing snapshotted item names and unit prices). `menu_promotions` and immutable `menu_promotion_versions` snapshots feed `menu_order_pricing` for BOGO and drink discounts. Completed or paid orders can be cancelled or refunded via a two-step Maker-Checker workflow in `pos_order_reversals`.

## Customer order notifications

POS order lifecycle changes append durable events to `customer_notification_events` (keyed per order and status). Per-event read acknowledgments are stored in `customer_notification_reads`, allowing customers to track order status updates in `/customer` without mutating financial records.
