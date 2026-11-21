# RBAC design for the reduced schema

Services and routes enforce permissions. The UI may hide actions, but the backend still checks role, account status, active store, and record ownership before changing data.

## Scope

RBAC applies to the 22 business tables listed in [DATA_MODEL](architecture/DATA_MODEL.md): stores, employees and profiles, customers and accounts, machines and sessions, invoices, menu/POS, and customer order notifications. Warehouse, procurement, cash shifts, maintenance, voucher/points, games/ads, commercial partners, and forecasting are outside the reduced application scope.

## Roles

- `ADMIN`: manages employee access and system configuration.
- `DIRECTOR`: manages chain-wide operations.
- `MANAGER`: manages an assigned store or assigned stores.
- `STAFF`: performs permitted store operations.
- `KITCHEN`: handles permitted POS order steps.
- Customers: access only records belonging to their account.

`employee_store_assignments` and `customer_store_links` represent cross-store scope. Sensitive changes should be recorded in the relevant audit table.
