# CyberHub Manager documentation

The current schema has **25 business tables**, **8 read views (`v_*`)**, and **18 integrity triggers** built by migrations `sql/001`–`sql/011` (`schema_migrations` is technical metadata). See the [data model](architecture/DATA_MODEL.md), [ERD](diagrams/current_erd.md), [DBML](diagrams/cyberhub_manager.dbml), and [data dictionary](diagrams/data_dictionary.md).

| Need | Document |
|---|---|
| Install and run | [Quickstart](guides/QUICKSTART.md) |
| Application structure | [Architecture overview](architecture/OVERVIEW.md) |
| Business flows | [Business flows](architecture/BUSINESS_FLOWS.md) |
| Access control | [RBAC design](RBAC_DESIGN.md), [permission matrix](RBAC_PERMISSION_MATRIX.md) |
| Change schema | Add a new numbered migration under `sql/`; do not edit applied migrations |

The reduced 3NF scope covers multi-store administration, employee profiles and RBAC, customer wallets and top-up promotions, workstation sessions and invoicing, POS food/drink orders with versioned promotions and Maker-Checker reversals, and in-app customer order notifications. Warehouse, procurement, cash shifts, maintenance, loyalty/points, email tokens/outbox, and customer security audit tables are intentionally outside this scope.
