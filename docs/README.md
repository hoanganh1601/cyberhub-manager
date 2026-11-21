# CyberHub Manager documentation

The current schema has **22 business tables**. See the [data model](architecture/DATA_MODEL.md) and [ERD](diagrams/current_erd.md).

| Need | Document |
|---|---|
| Install and run | [Quickstart](guides/QUICKSTART.md) |
| Application structure | [Architecture overview](architecture/OVERVIEW.md) |
| Business flows | [Business flows](architecture/BUSINESS_FLOWS.md) |
| Access control | [RBAC design](RBAC_DESIGN.md), [permission matrix](RBAC_PERMISSION_MATRIX.md) |
| Change schema | Add a migration under `sql/`; do not edit applied migrations |

Migration 030 removes four tables: customer email tokens, queued mail, customer security events, and customer-to-store history. This also removes email activation/recovery flows and customer-to-store filtering. Back up existing data before applying the migration.

Migration 031 restores in-app customer notifications for menu-order status changes using an event table and a per-customer read table.
