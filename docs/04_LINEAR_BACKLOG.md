# 4. Phân công 3 thành viên và backlog Linear

## 4.1. Ownership chính

| Thành viên | Vai trò | Module sở hữu | Quyền review bắt buộc |
|---|---|---|---|
| **Hoàng Anh** | Tech Lead, Database & Backend Foundation | `sql/`, `database/`, toàn bộ `repositories/`, schema/ERD, migration/seed, auth data, query báo cáo; thêm `ui/login_view.py` | Mọi thay đổi schema, SQL, repository contract, transaction; Ngát review phần Login UI |
| **Linh** | Business Logic & Quality | `domain/`, toàn bộ `services/`, công thức tính phí, ví tiền, phiên, exception, automated tests | Mọi thay đổi business rule, service contract, cách tính tiền |
| **Ngát** | UI/UX & Integration | `ui/`, theme, component, screen/dialog, manual E2E, screenshot/demo flow | Mọi thay đổi theme, navigation, UI state và wording |

Nguyên tắc: ownership là người chịu trách nhiệm cuối, không có nghĩa là làm một mình. Mỗi PR phải được ít nhất một người khác review.

Phân bổ sau khi cân lại: Hoàng Anh **44 points**, Linh **45 points**, Ngát **45 points**. Hoàng Anh nhận thêm Login UI/Auth integration; packaging thuộc Hoàng Anh; test acceptance do Linh điều phối; Ngát tập trung design system, app shell và các UI nghiệp vụ còn lại.

## 4.2. Thiết lập Linear

### Project

- Project: `CyberHub Manager — MVP`
- Cycle: 1 tuần
- Estimate: Fibonacci `1, 2, 3, 5, 8`
- Priority: Urgent = blocker; High = P0; Medium = P1; Low = nice-to-have.

### Labels

- Module: `database`, `backend`, `business`, `frontend`, `testing`, `docs`.
- Type: `feature`, `chore`, `bug`.
- Scope: `P0`, `P1`.
- Milestone: `S0-foundation`, `S1-customer`, `S2-session`, `S3-release`.

### Epics

1. Foundation & Authentication
2. Customer & Wallet
3. Machine & Session
4. Checkout, Invoice & Revenue
5. Stabilization & Demo

## 4.3. Task của Hoàng Anh — Database & Backend

### HA-01 — Khởi tạo repository và skeleton

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: cấu trúc package `cyberhub_manager`, `.gitignore`, environment mẫu, `docker-compose.yml` pin `mysql:8.4`, lệnh run/test trong README.
- Acceptance: project import được dù các module còn placeholder; không commit DB/env; cả nhóm clone, khởi động MySQL 8.4 và setup theo README được.
- Dependency: không.

### HA-02 — ERD và initial schema

- Epic: Foundation & Authentication; Estimate: 5; Priority: High.
- Output: ERD + `001_initial_schema.sql` cho 8 bảng P0; bảng promotion có thể thêm ở P1.
- Acceptance: schema MySQL dùng InnoDB/utf8mb4; đủ PK/FK/UNIQUE/CHECK; tiền là BIGINT có dấu; dùng generated column + unique index để chặn active session trùng machine/customer; paid invoice không cascade delete.
- Dependency: HA-01; review bởi Linh.

### HA-03 — Migration, seed và reset dữ liệu demo

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: script init/seed idempotent; 1 store, 1 manager, 2 staff, 20 machines, 5 customers.
- Acceptance: chạy hai lần không nhân đôi; password seed được hash; có hướng dẫn reset DB dev.
- Dependency: HA-02.

### HA-04 — Connection và transaction manager

- Epic: Foundation & Authentication; Estimate: 5; Priority: High.
- Output: MySQL connection pool/factory, charset/timezone, timeout, begin/commit/rollback, logging lỗi.
- Acceptance: credential đọc từ environment; service dùng một connection cho nhiều repository; test chứng minh exception rollback toàn bộ; không giữ connection sau khi use case kết thúc.
- Dependency: HA-02; contract với Linh.

### HA-05 — Auth repository và dữ liệu phân quyền

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: query nhân viên active theo username, store và role; helper hash/verify password đặt tại module dùng chung đã thống nhất.
- Acceptance: query parameterized; không trả password ra UI/DTO; nhân viên/store inactive không đăng nhập được.
- Dependency: HA-03, HA-04.

### HA-06 — Customer và account repositories

- Epic: Customer & Wallet; Estimate: 5; Priority: High.
- Output: create/get/search/update customer, đổi trạng thái customer/account, get/update account, transaction history queries.
- Acceptance: parameterized SQL; search mã/tên/SĐT/username; repository không commit; số dư không có API “set tùy ý”; khóa/mở khóa không làm mất lịch sử.
- Dependency: HA-04; dùng contract LI-01.

### HA-07 — Machine và session repositories

- Epic: Machine & Session; Estimate: 5; Priority: High.
- Output: create/update/maintenance/archive máy, list theo store, create/get/complete active session.
- Acceptance: list máy trả dữ liệu phiên đang chạy để dashboard render; conflict DB được map cho service; chỉ xóa cứng máy chưa có lịch sử; máy có phiên phải archive; không thao tác máy `IN_USE` trái rule.
- Dependency: HA-04, HA-02.

### HA-08 — Transaction, invoice và revenue repositories

- Epic: Checkout, Invoice & Revenue; Estimate: 5; Priority: High.
- Output: insert giao dịch, insert/get invoice, filter invoice, revenue theo ngày.
- Acceptance: doanh thu chỉ tính invoice `PAID`, đúng timezone local; query có index hỗ trợ; một session không có hai invoice.
- Dependency: HA-04, HA-06, HA-07.

### HA-09 — Review DB, đóng gói và tối ưu query

- Epic: Stabilization & Demo; Estimate: 5; Priority: High.
- Output: review transaction và `SELECT ... FOR UPDATE`, chạy EXPLAIN/query test, bổ sung index, chuẩn hóa lệnh setup/run/package trên máy sạch.
- Acceptance: không có service tự commit; test rollback pass; thao tác demo dưới 2 giây; khóa ngoại không lỗi; máy sạch chạy được theo README.
- Dependency: LI-07, HA-08.

### HA-10 — ERD/data dictionary cho báo cáo

- Epic: Stabilization & Demo; Estimate: 2; Priority: Medium.
- Output: ảnh ERD, data dictionary, giải thích normalization và transaction để đưa vào báo cáo.
- Acceptance: khớp schema cuối; có mô tả PK/FK/cardinality.
- Dependency: HA-09.

### HA-11 — Login UI và Auth integration

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: `login_view.py`, form username/password, show/hide password, loading/disabled state và kết nối `AuthService.login`.
- Acceptance: dùng toàn bộ token/component của NG-01; Enter submit; login sai giữ username và xóa password; không double-submit; login thành công chuyển app shell; không hiển thị lỗi kỹ thuật; Ngát review UI và Linh review auth behavior.
- Dependency: NG-01, HA-05, LI-03; có thể dựng bằng mock LI-02 trước khi auth thật hoàn thành.

## 4.4. Task của Linh — Domain, Service và Test

### LI-01 — Domain models, enums và exceptions

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: model/DTO/enum/exception theo tài liệu skeleton và Class Diagram cho domain/service chính.
- Acceptance: không phụ thuộc UI; không dùng status string rải rác; DTO đủ dữ liệu cho mock UI; Class Diagram khớp contract đã duyệt.
- Dependency: review requirement; phối hợp HA-02 và NG-01.

### LI-02 — Service contracts và mock services

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: khóa public contract; mock responses để Ngát dựng UI không chờ DB.
- Acceptance: input/output/error của mỗi operation được ghi rõ; mock cover success, empty, validation và conflict.
- Dependency: LI-01.

### LI-03 — Auth và customer services

- Epic: Customer & Wallet; Estimate: 5; Priority: High.
- Output: login, create/search/update customer, khóa/mở khóa customer/account, validation.
- Acceptance: password verify đúng; trùng phone/username thành lỗi nghiệp vụ; tạo customer+account là một transaction; chỉ Manager/Admin đổi trạng thái.
- Dependency: HA-05, HA-06, LI-01.

### LI-04 — Wallet/top-up service

- Epic: Customer & Wallet; Estimate: 5; Priority: High.
- Output: nạp tiền, lịch sử; promotion để feature flag/P1.
- Acceptance: amount hợp lệ; update balance + transaction atomically; test rollback; nhân viên được ghi nhận.
- Dependency: HA-06, HA-04.

### LI-05 — Machine service và permission

- Epic: Machine & Session; Estimate: 3; Priority: High.
- Output: list machine summary, create/update/maintenance/archive, kiểm tra store/role.
- Acceptance: staff không quản trị máy; không sửa/bảo trì/archive máy `IN_USE`; máy có lịch sử không xóa cứng; DTO có live status cho UI.
- Dependency: HA-07, LI-01.

### LI-06 — Open session và live estimate

- Epic: Machine & Session; Estimate: 5; Priority: High.
- Output: preview/open session, minimum balance, estimated play time, live projected balance và Activity Diagram mở phiên.
- Acceptance: đủ rules SES-01 đến SES-06; transaction insert session + đổi máy; conflict double click được xử lý thân thiện.
- Dependency: HA-07, LI-04, LI-05.

### LI-07 — Checkout và invoice orchestration

- Epic: Checkout, Invoice & Revenue; Estimate: 8; Priority: High.
- Output: preview checkout, tính phút/phí, settlement, complete checkout, invoice result và Activity Diagram checkout.
- Acceptance: công thức SES-07; thiếu settlement không thay đổi DB; complete chạy một transaction; machine về AVAILABLE; invoice duy nhất; test các biên 1 giây/60 giây/61 giây.
- Dependency: HA-08, LI-06.

### LI-08 — Report service

- Epic: Checkout, Invoice & Revenue; Estimate: 3; Priority: High.
- Output: filter invoice và doanh thu ngày.
- Acceptance: validate date range; staff chỉ store hiện tại; tổng khớp invoice PAID.
- Dependency: HA-08.

### LI-09 — Automated và acceptance test suite

- Epic: Stabilization & Demo; Estimate: 7; Priority: High.
- Output: unit/integration test; điều phối manual acceptance checklist với Ngát; tổng hợp test result cho báo cáo.
- Acceptance: DB test độc lập; test đủ happy path và các nhánh lỗi nghiệm thu; manual checklist có người thực hiện/evidence; chạy automated test bằng một lệnh; không phụ thuộc thứ tự.
- Dependency: LI-03 đến LI-08.

### LI-10 — Error mapping và stabilization

- Epic: Stabilization & Demo; Estimate: 3; Priority: High.
- Output: chuẩn hóa exception/message, map MySQL duplicate key/deadlock/lock timeout thành lỗi nghiệp vụ hoặc retry phù hợp, hỗ trợ Ngát integration.
- Acceptance: UI không nhận raw exception/traceback; không crash trên invalid input; toàn bộ automated test pass.
- Dependency: NG-08, LI-09.

## 4.5. Task của Ngát — UI/UX và Integration

### NG-01 — Design system và component catalog

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: `theme.py`, button/input/badge/table/dialog/toast/machine-card states theo `03_UI_THEME.md`.
- Acceptance: không hard-code token ngoài theme; có screenshot component states; hiển thị đúng 1280×720.
- Dependency: không; thống nhất DTO với LI-01.

### NG-02 — App shell và navigation

- Epic: Foundation & Authentication; Estimate: 3; Priority: High.
- Output: sidebar, header, content container, route đổi view, role-based menu và logout.
- Acceptance: role/store hiển thị đúng; menu Manager/Admin ẩn với STAFF; logout xóa session UI và quay về Login do HA-11 cung cấp; shell không phụ thuộc repository/SQL.
- Dependency: NG-01, contract LI-02; phối hợp HA-11 cho điểm chuyển Login ↔ App shell.

### NG-03 — Dashboard và quản lý máy

- Epic: Machine & Session; Estimate: 8; Priority: High.
- Output: dashboard summary/filter/grid; màn Manager thêm/sửa/bảo trì/archive máy; machine dialog; refresh 15 giây.
- Acceptance: ba trạng thái đúng theme; live duration/balance; cảnh báo âm rõ; role ẩn/hiện action đúng; không quản trị máy `IN_USE`; archive có confirm; loading/empty/error; chống double click.
- Dependency: NG-01, mock LI-02; tích hợp LI-05/LI-06.

### NG-04 — Màn khách hàng và nạp tiền

- Epic: Customer & Wallet; Estimate: 8; Priority: High.
- Output: search/table, create/edit dialog, khóa/mở khóa theo role, customer detail, top-up dialog, transaction history.
- Acceptance: field validation; format tiền; số dư âm đỏ; STAFF không có action khóa; refresh đúng sau save/top-up/status; không có SQL/business calculation trong UI.
- Dependency: NG-01, LI-03, LI-04.

### NG-05 — Open session dialog

- Epic: Machine & Session; Estimate: 5; Priority: High.
- Output: chọn khách, preview minimum/estimated time, confirm open.
- Acceptance: không đủ tiền disable action + CTA top-up; conflict hiển thị dễ hiểu; success đóng dialog và refresh dashboard.
- Dependency: NG-03, LI-06.

### NG-06 — Checkout và receipt dialog

- Epic: Checkout, Invoice & Revenue; Estimate: 8; Priority: High.
- Output: checkout preview, settlement form, method, receipt.
- Acceptance: chỉ enable khi bù đủ; confirm trước commit; retry không tạo trùng; hiển thị đủ invoice fields; dashboard refresh.
- Dependency: LI-07, NG-03.

### NG-07 — Hóa đơn và doanh thu UI

- Epic: Checkout, Invoice & Revenue; Estimate: 5; Priority: High.
- Output: filter invoice, detail panel, date range, KPI revenue, daily table.
- Acceptance: filter hợp lệ; empty/loading/error states; tổng tiền format đúng; không cần chart ở MVP.
- Dependency: LI-08, NG-01.

### NG-08 — UI error states và integration sweep

- Epic: Stabilization & Demo; Estimate: 3; Priority: High.
- Output: map exception → field/dialog/toast; focus/keyboard; remove mock còn sót.
- Acceptance: test manual toàn bộ lỗi chính; không lộ traceback; mọi action có loading/disable; theme nhất quán.
- Dependency: NG-02 đến NG-07, LI-10.

### NG-09 — Demo UI assets

- Epic: Stabilization & Demo; Estimate: 2; Priority: High.
- Output: screenshot, video/demo script và dữ liệu trình diễn cho các trạng thái UI chính.
- Acceptance: demo đủ flow nghiệm thu; evidence rõ; ghi known limitations; bàn giao checklist thực thi cho LI-09 và hướng dẫn đóng gói cho HA-09.
- Dependency: NG-08, HA-09, LI-09.

## 4.6. Kế hoạch theo cycle

| Cycle | Mục tiêu | Hoàng Anh | Linh | Ngát | Exit criteria |
|---|---|---|---|---|---|
| 0 — Foundation | Khóa contract và skeleton | HA-01→04 | LI-01→02 | NG-01 | Schema/contract/theme được cả nhóm approve |
| 1 — Customer | Login, khách, nạp tiền | HA-05→06, HA-11 | LI-03→04 | NG-02, NG-04 phần customer | Demo login → tạo khách → top-up |
| 2 — Session | Máy và mở phiên | HA-07 | LI-05→06 | NG-03→05 | Demo máy trống → mở → live dashboard |
| 3 — Billing | Checkout, invoice, report | HA-08 | LI-07→08 | NG-06→07 | Demo checkout → receipt → revenue |
| 4 — Release | Test, fix, báo cáo | HA-09→10 | LI-09→10 | NG-08→09 | Pass checklist và rehearsal demo |

Không bắt đầu P1 khi P0 của cycle hiện tại còn bug blocker.

## 4.7. Điểm bàn giao giữa các thành viên

1. Hoàng Anh bàn giao schema + data dictionary cho Linh trước khi repository/service được code.
2. Linh bàn giao DTO/service mock cho Ngát ngay Cycle 0; UI không chờ backend thật.
3. Hoàng Anh bàn giao repository theo từng vertical slice, không chờ hoàn thành toàn bộ DB layer.
4. Ngát gửi video/screenshot trạng thái UI cho Linh kiểm tra business wording trước integration.
5. Mỗi cuối cycle chạy demo trên cùng seed data, tạo bug Linear ngay tại buổi review.

## 4.8. Definition of Done chung

- Đúng acceptance criteria và requirement ID liên quan.
- Có validation, success, empty, loading và error path phù hợp.
- Không phá architecture/import rule; không hard-code secret/theme/status.
- Automated test pass với business/backend task; manual checklist pass với UI task.
- PR được review; conflict đã resolve; Linear issue có link PR và evidence.
- Tài liệu/ERD/theme cập nhật nếu contract thay đổi.
