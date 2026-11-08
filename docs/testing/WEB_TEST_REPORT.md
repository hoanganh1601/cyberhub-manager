# Web adapter — verification report

Date: 2026-11-08 (Asia/Ho_Chi_Minh).

## Automated verification

- Full suite with `.[web,dev]`: **1,068 passed** on Linux, Python 3.11.15.
- A separate temporary MySQL 8.4 container hosted only `cyberhub_manager_test`.
- Web-specific tests: **38 passed** (36 unit cases + 2 real-MySQL integration cases).
- Desktop lifecycle tests still cover login → AppShell → logout.
- `pip check`: no broken requirements; JavaScript syntax check passed.
- Docker image built from `Dockerfile.web`, ran as the non-root `cyberhub` user,
  and served HTML, CSS, logo and `/healthz` successfully under Python 3.13.18.
- Installed-wheel web startup does not import Tkinter/CustomTkinter or require DISPLAY.

The MySQL integration tests exercise real login, customer creation, wallet credit,
opening a session, checkout, invoices and revenue. A separate case changes the employee
role/status after login and verifies the next request uses the new database state.

## Browser verification

Google Chrome via Playwright, desktop viewport 1440×900 / 1280×720 and mobile 390×844:

- Login and navigation across all five views.
- Create/edit customer; amount shortcuts; top-up remains disabled until receipt is confirmed.
- Lock/unlock customer and synchronize account status.
- Open session with service eligibility preview.
- Checkout from sufficient account balance, cash settlement and manually confirmed bank transfer.
- Payment receipt and invoice detail lookup.
- Revenue chart and VI/EN switching.
- STAFF does not see machine-management navigation; HTTP tests independently reject its mutations.
- Mobile viewport has no document-wide horizontal overflow; customer dialog stays inside the viewport.
- Logout returns to the login form; no browser JavaScript errors in the successful runs.

## Deployment boundary

`render.yaml` and `railway.json` / `Dockerfile.web` are ready for a connected hosting account.
This report does **not** claim that a public Render/Railway deployment has been created.
Demo data is per-login, in memory and temporary. Real data uses the existing MySQL services.
The current configuration is one Gunicorn worker and one instance. Redis/shared-session
and rate-limiting infrastructure must be added before horizontal scaling.

Payment collection is manual P0 recording. There is no payment gateway, bank webhook,
automatic QR verification, or public employee registration in this version.
