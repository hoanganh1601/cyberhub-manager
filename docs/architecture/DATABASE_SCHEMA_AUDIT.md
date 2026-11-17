# Kiểm kê schema và sai lệch ERD

Kiểm kê ngày 17/11/2026 trên `refactor/docs-tests-db-audit` tại commit gốc `960beb1a0a0ffa4b4e517f6cc75f9e1ef1b6300f`. Nguồn có thể kiểm tra: 24 file `sql/001_*.sql` → `sql/024_*.sql` theo [migration runner](../../scripts/init_db.py), các repository trong `src/cyberhub_manager/repositories/`, [ERD P0](../diagrams/erd.md) và [data dictionary](../diagrams/data_dictionary.md).

## Nguồn sự thật và giới hạn xác minh

`001_initial_schema.sql` tạo 8 bảng nền. Migration `002` thêm index; `003`–`024` tạo thêm 55 bảng nghiệp vụ và thay đổi cột/constraint của các bảng sẵn có. Tổng cộng 63 bảng nghiệp vụ; bảng `schema_migrations` do runner tạo thêm để kiểm tra checksum. Kiểm kê bằng cách đọc SQL theo thứ tự tên file, không chạy DDL.

Docker daemon không chạy và kết nối chỉ đọc đến `cyberhub_manager_test` tại `127.0.0.1:3307` bị từ chối (10061). Vì vậy **schema thực tế, trạng thái migration và checksum trên MySQL: NOT VERIFIED**. Không suy diễn database đang chạy đã ở phiên bản `024`.

## Ma trận sai lệch

| Nhóm/bảng | Migration | Repository đang dùng | ERD P0/Dictionary hiện có | Sai lệch và hành động |
|---|---|---|---|---|
| Nền tảng (8 bảng) | `001`, bổ sung `002`–`020` | Auth, account, session, invoice, machine | ERD P0 có 8 bảng; dictionary có cột về sau | Giữ P0 làm lịch sử, dùng [ERD hiện hành](../diagrams/current_erd.md) cho toàn hệ thống. |
| Menu/kho/voucher/game/ads (30 bảng) | `003`–`017` | Menu, inventory, voucher, game, ad | Dictionary có; ERD P0 không có | Giữ mô tả chi tiết, mở rộng sơ đồ hiện hành. |
| `pos_order_reversals`, `menu_promotions`, `menu_order_pricing` | `018`, `019` | `menu_repository.py` | Không có ở dictionary và ERD P0 | Bổ sung vào dictionary sau khi có schema MySQL test để sinh lại file. |
| `cash_shifts`, `cash_shift_entries` | `021` | `cash_shift_repository.py` | Không có | Bổ sung sơ đồ/description và kiểm tra cột, unique index. |
| `machine_incidents`, `machine_incident_parts`, `machine_incident_events` | `022` | `maintenance_repository.py` | Không có | Bổ sung sơ đồ/description, quan hệ người báo/người nhận/người xác minh. |
| `suppliers`, `purchase_requests`, `purchase_request_lines`, `purchase_orders`, `purchase_order_lines`, `goods_receipts`, `goods_receipt_lines`, `supplier_payables` | `023` | `procurement_repository.py` | Không có | Bổ sung sơ đồ/description, PK ghép của các dòng và UNIQUE công nợ theo phiếu nhận. |
| Đối tác thương mại (9 bảng) | `024` | `commercial_repository.py` | Dictionary có; ERD P0 không có | Duy trì dictionary, vẽ luồng hợp đồng → chiến dịch → sự kiện/đối soát. |

Tổng cộng **16 bảng thiếu** trong [danh sách `TABLES` của generator](../../scripts/gen_data_dictionary.py) và trong dictionary. [Integration test HA-10](../../tests/integration/test_ha10_data_dictionary.py) hiện chỉ kiểm tra 47 bảng được liệt kê thủ công; phép so sánh nội dung sinh ra với file có thể pass dù 16 bảng không được kiểm kê. Dòng “14 khóa ngoại” trong [erd.md](../diagrams/erd.md) chỉ đúng phạm vi P0; không đại diện schema hiện tại.

## Khóa và quan hệ quan trọng từ migration

- PK phổ biến là `id`; 13 ngoại lệ và cột FK trên từng cạnh được liệt kê trong [ERD hiện hành](../diagrams/current_erd.md). Khóa ghép gồm cả `customer_notification_reads` và `commercial_settlement_lines`; xem DDL để kiểm tra thứ tự cột.
- `pos_order_reversals.order_id` là UNIQUE, mỗi đơn tối đa một hồ sơ hoàn/hủy; `supplier_payables.receipt_id` là UNIQUE, mỗi phiếu nhận tối đa một công nợ. `menu_order_pricing.order_id` là PK/FK. Quan hệ nhiều `employee_id` và `store_id` là FK về bảng nền.
- `customer_notification_events` có FK tới `accounts` và `stores` nhưng **không có** cột `order_id`; mối liên hệ đơn nằm ở `notification_key`/dữ liệu sự kiện trong ứng dụng, không vẽ FK giả.
- Các CHECK, nullable, `ON DELETE`, index và giá trị mặc định phải đối chiếu SQL và `INFORMATION_SCHEMA` trước khi cập nhật dictionary dạng sinh tự động. Sơ đồ chia theo miền để đọc được; sơ đồ không thay thế DDL.

## Việc cần xác minh khi MySQL test sẵn sàng

1. Xác nhận `SELECT DATABASE()` trả `cyberhub_manager_test` trước mọi kiểm tra; truy vấn metadata `INFORMATION_SCHEMA` ở chế độ chỉ đọc.
2. So sánh 24 dòng trong `schema_migrations` với file trong Git và kiểm tra đủ 63 bảng nghiệp vụ, cột, FK, index, CHECK.
3. Bổ sung 16 bảng và mô tả cột vào `scripts/gen_data_dictionary.py`, sinh lại dictionary từ **database test đã migrate** (thao tác này thuộc lượt thay đổi riêng vì cần DB và sẽ chạm script). Mở rộng test HA-10 để phát hiện bảng SQL mới bị bỏ sót.
4. Render sơ đồ Mermaid, rà cardinality cho mọi FK nullable/UNIQUE, xuất lại PNG nếu sử dụng ảnh trong báo cáo.

Không thay đổi migration hoặc schema ứng dụng trong lượt tài liệu này.
