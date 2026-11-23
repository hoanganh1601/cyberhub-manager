# Current ERD — 25 business tables

The current business schema contains **25 business tables**, **8 read views (`v_*`)**, **18 integrity triggers**, **46 foreign keys**, and **74 `CHECK` constraints** after migrations `001`–`011`. `schema_migrations` is technical metadata and is not counted.

```mermaid
erDiagram
    stores ||--o{ employee_profiles : home_store
    stores ||--o{ employee_store_assignments : assigns
    stores ||--o{ machines : owns
    stores ||--o{ account_transactions : records
    stores ||--o{ invoices : bills_snapshot
    stores o|--o{ promotions : offers
    stores ||--o{ management_audit : logs
    stores ||--o{ menu_categories : organizes
    stores ||--o{ menu_promotions : offers_pos

    employee_profiles ||--o| employees : login_account
    employees ||--o{ employee_store_assignments : assigned_or_grants
    employees ||--o{ usage_sessions : opens_or_closes
    employees ||--o{ account_transactions : handles
    employees ||--o{ invoices : creates
    employees ||--o{ management_audit : performs
    employees o|--o{ menu_orders : handles_or_pays
    employees ||--o{ pos_order_reversals : requests_or_decides

    customers ||--o| accounts : owns
    customers ||--o{ usage_sessions : uses
    customers ||--o{ invoices : billed
    customers ||--o| active_usage_sessions : currently_playing

    accounts ||--o{ account_transactions : ledger
    machines ||--o{ usage_sessions : hosts
    machines ||--o| active_usage_sessions : currently_hosting
    machines ||--o| machine_room_types : classified_as

    usage_sessions ||--o| active_usage_sessions : active_lock
    usage_sessions ||--o{ session_transactions : related_transactions
    usage_sessions ||--o| invoices : billed_by
    usage_sessions ||--o{ menu_orders : associated_with
    account_transactions ||--o| session_transactions : session_link
    promotions o|--o{ account_transactions : bonus_source

    menu_categories ||--o{ menu_items : groups
    menu_items ||--o{ menu_order_items : ordered_as
    menu_items o|--o{ menu_promotions : eligible_item
    menu_items o|--o{ menu_promotion_versions : snapshot_item
    menu_orders ||--o{ menu_order_items : contains
    menu_orders ||--o| menu_order_pricing : priced_by
    menu_orders ||--o| pos_order_reversals : may_be_reversed
    menu_orders ||--o{ customer_notification_events : status_history
    customer_notification_events ||--o| customer_notification_reads : read_state
    menu_promotions ||--o{ menu_promotion_versions : versions
    menu_promotion_versions o|--o{ menu_order_pricing : applied_to

    stores {
        bigint id PK
        string code UK
        string name
        string address
        string status
    }
    employee_profiles {
        bigint id PK
        string code UK
        bigint home_store_id FK
        string full_name
        string employment_status
    }
    employees {
        bigint id PK
        bigint profile_id FK,UK
        string username UK
        string role
        string status
    }
    employee_store_assignments {
        bigint employee_id PK,FK
        bigint store_id PK,FK
        bigint granted_by FK
    }
    management_audit {
        bigint id PK
        bigint employee_id FK
        bigint store_id FK
        string action
        bigint entity_id
    }
    customers {
        bigint id PK
        string code UK
        string full_name
        string phone UK
        string status
    }
    accounts {
        bigint id PK
        bigint customer_id FK,UK
        string code UK
        string username UK
        bigint balance
        bigint bonus_balance
        string status
    }
    promotions {
        bigint id PK
        bigint store_id FK
        string code UK
        bigint minimum_amount
        int bonus_percent
        datetime starts_at
        datetime ends_at
    }
    machines {
        bigint id PK
        bigint store_id FK
        string code UK
        string status
        bigint hourly_rate
    }
    machine_room_types {
        bigint machine_id PK,FK
        string room_type
    }
    usage_sessions {
        bigint id PK
        bigint customer_id FK
        bigint machine_id FK
        bigint opened_by FK
        bigint closed_by FK
        datetime started_at
        datetime ended_at
        bigint hourly_rate
        bigint cost
        string status
    }
    active_usage_sessions {
        bigint session_id PK,FK
        bigint machine_id FK,UK
        bigint customer_id FK,UK
    }
    account_transactions {
        bigint id PK
        string code UK
        bigint account_id FK
        bigint employee_id FK
        bigint store_id FK
        bigint promotion_id FK
        string type
        bigint amount
        string method
    }
    session_transactions {
        bigint transaction_id PK,FK
        bigint session_id FK
    }
    invoices {
        bigint id PK
        string code UK
        bigint session_id FK,UK
        bigint customer_id FK
        bigint employee_id FK
        bigint store_id FK
        bigint usage_cost
        bigint settlement_amount
        bigint bonus_used
        string status
    }
    menu_categories {
        bigint id PK
        bigint store_id FK
        string page
        string name
    }
    menu_items {
        bigint id PK
        bigint category_id FK
        string name
        bigint price
    }
    menu_orders {
        bigint id PK
        bigint session_id FK
        bigint handled_by FK
        bigint paid_by FK
        string status
        bigint total_amount
    }
    menu_order_items {
        bigint order_id PK,FK
        bigint item_id PK,FK
        string item_name
        bigint unit_price
        int quantity
    }
    menu_promotions {
        bigint id PK
        bigint store_id FK
        bigint item_id FK
        string code
        string kind
        int value
    }
    menu_promotion_versions {
        bigint id PK
        bigint promotion_id FK
        int version
        string code
        string kind
        bigint item_id FK
    }
    menu_order_pricing {
        bigint order_id PK,FK
        bigint promotion_version_id FK
        bigint discount_amount
    }
    pos_order_reversals {
        bigint id PK
        bigint order_id FK,UK
        bigint requested_by FK
        bigint decided_by FK
        string status
    }
    customer_notification_events {
        bigint id PK
        bigint order_id FK
        string order_status
        datetime created_at
    }
    customer_notification_reads {
        bigint event_id PK,FK
        datetime read_at
    }
```

Key 3NF highlights:
- `employee_profiles` owns HR metadata (`code`, `home_store_id`, `full_name`, `employment_status`); `employees.profile_id` (`UNIQUE`) owns the 1:0..1 link to login credentials.
- `active_usage_sessions` enforces at most one active session per `machine_id` and per `customer_id` via `UNIQUE` constraints without nullable flags or generated columns.
- `session_transactions` (migration `010`, tightened to `ON DELETE RESTRICT` + `BEFORE UPDATE` immutability in migration `011`) isolates session-linked ledger rows (`USAGE_PAYMENT`, `DEBT_SETTLEMENT`) from `account_transactions`.
- `menu_promotion_versions` stores immutable POS promotion snapshots referenced by `menu_order_pricing`.
