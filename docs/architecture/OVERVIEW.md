# Architecture overview

The application uses Flask for web, CustomTkinter for desktop, Python services for business rules, and MySQL 8.4 for storage. The current business schema has **25 tables**, **8 read views**, and **18 triggers** in [DATA_MODEL](DATA_MODEL.md); `schema_migrations` is technical metadata.

| Layer | Responsibility |
|---|---|
| Web | `web/application.py`, `web/operations_routes.py`, and `web/feature_routes.py` provide authenticated APIs for stores, customers, employees, machines, sessions, invoices, and POS. |
| Services | `services/bootstrap.py` composes the active services. Services enforce business rules, transactions, and permissions. |
| Repositories | Pure domain-oriented MySQL repositories (`account`, `auth`, `customer`, `invoice`, `machine`, `management`, `menu`, `portal`, `session`) execute parameterized SQL. |
| User interfaces | `web/static/` provides the web UI; `ui/` provides the desktop UI. |
| Database | Numbered migrations `001`–`011` establish and upgrade the current 3NF schema. Applied migration files remain immutable because the runner verifies their checksums. |

A request flows from a UI to a route, then a service, then a repository. The service checks permissions and transaction rules before the repository performs SQL.
