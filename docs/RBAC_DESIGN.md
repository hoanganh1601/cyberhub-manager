# RBAC design for the reduced schema

Services and routes enforce permissions. The UI may hide actions, but the backend still checks role, account status, active store, and record ownership before changing data.

## Scope

RBAC applies to the **25 business tables** listed in [DATA_MODEL](architecture/DATA_MODEL.md): stores, employees and profiles, customers and accounts, wallet ledger and top-up promotions, machines and sessions, invoices, menu/POS with versioned promotions and reversals, and customer order notifications. Warehouse, procurement, cash shifts, maintenance, loyalty/points, email tokens/outbox, customer security audit, games/ads, commercial partners, and forecasting are outside the reduced application scope.

## Roles

- `ADMIN`: manages employee credentials, store assignments, and system configuration.
- `DIRECTOR`: manages chain-wide operations across all stores.
- `MANAGER`: manages an assigned home store (and any cross-store assignments granted via `employee_store_assignments`), including voiding invoices and approving POS reversals.
- `STAFF`: performs permitted store counter operations (customers, top-ups, sessions, checkout/cancel, POS payments and reversal requests).
- `KITCHEN`: handles permitted POS order preparation and service steps.
- Customers: self-service access on `/customer`, strictly scoped to records owned by their own account.

`employee_store_assignments` represents cross-store scope for `MANAGER` accounts. Sensitive administrative and operational actions are recorded in `management_audit`.
