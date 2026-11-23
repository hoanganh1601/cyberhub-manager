# Permission matrix for the reduced scope

Routes and services check both role and data scope. UI visibility is not an authorization check: the backend verifies the store or record owner for every operation.

| Function | Typical roles | Main tables |
|---|---|---|
| Stores, employees, profiles, assignments | `ADMIN`, `DIRECTOR`, `MANAGER` as permitted | `stores`, `employee_profiles`, `employees`, `employee_store_assignments` |
| Customers, accounts, wallet ledger, top-up offers | `DIRECTOR`, `MANAGER`, or `STAFF` as permitted; customers read/manage their own account | `customers`, `accounts`, `promotions`, `account_transactions`, `session_transactions` |
| Machines, room types, sessions, invoices | `MANAGER` or `STAFF` as permitted (`MANAGER` / legacy `ADMIN` for voiding invoices) | `machines`, `machine_room_types`, `usage_sessions`, `active_usage_sessions`, `invoices` |
| Menu, POS promotions, orders, reversals | `MANAGER`, `STAFF`, `KITCHEN` as permitted; customers place orders during active sessions | `menu_categories`, `menu_items`, `menu_orders`, `menu_order_items`, `menu_promotions`, `menu_promotion_versions`, `menu_order_pricing`, `pos_order_reversals` |
| Customer order notifications | Customers (own active/past orders) | `customer_notification_events`, `customer_notification_reads` |
| Administrative & operational audit | Written by backend on privileged/sensitive operations | `management_audit` |

`ADMIN` manages credentials and system configuration. `DIRECTOR` operates across the chain. `MANAGER` operates within assigned stores. `STAFF` and `KITCHEN` have narrower operational permissions. Customers can access only records owned by their own account.
