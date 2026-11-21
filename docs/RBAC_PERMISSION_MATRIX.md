# Permission matrix for the reduced scope

Routes and services check both role and data scope. UI visibility is not an authorization check: the backend verifies the store or record owner for every operation.

| Function | Typical roles | Main tables |
|---|---|---|
| Stores, employees, profiles, assignments | ADMIN, DIRECTOR, MANAGER as permitted | `stores`, `employees`, `employee_profiles`, `employee_store_assignments` |
| Customers, accounts, wallet transactions | MANAGER or STAFF as permitted; customers read their own records | `customers`, `accounts`, `account_transactions`, `customer_store_links` |
| Machines, rooms, usage, invoices | MANAGER or STAFF as permitted | `machines`, `machine_room_types`, `usage_sessions`, `invoices` |
| Menu and POS | MANAGER, STAFF, KITCHEN as permitted | `menu_categories`, `menu_items`, `menu_orders`, `menu_order_items`, `menu_promotions`, `menu_order_pricing`, `pos_order_reversals` |
| Administrative and customer security audit | The relevant administrative permission | `management_audit`, `customer_security_audit` |

ADMIN manages access and system configuration. DIRECTOR operates across the chain. MANAGER operates within assigned stores. STAFF and KITCHEN have narrower operational permissions. Customers can access records owned by their own account.
