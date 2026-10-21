# Thiết kế cơ sở dữ liệu — CyberHub Manager

## 1. Mục tiêu

Thiết kế cơ sở dữ liệu được trình bày theo ba giai đoạn riêng biệt để phục vụ cả báo cáo và triển khai:

1. [Mô hình quan niệm](conceptual_erd.md) — xác định thực thể, quan hệ và cardinality từ yêu cầu nghiệp vụ.
2. [Mô hình logic và chuẩn hóa](logical_erd.md) — chuyển thực thể thành quan hệ, xác định thuộc tính, khóa và chuẩn hóa dữ liệu.
3. [Mô hình vật lý](physical_erd.md) — ánh xạ mô hình logic sang MySQL 8.4 với kiểu dữ liệu, ràng buộc và index.

```mermaid
flowchart LR
    A[Requirements] --> B[Conceptual ERD]
    B --> C[Logical Model]
    C --> D[Normalization]
    D --> E[Physical Model]
    E --> F[MySQL DDL]
```

## 2. Phạm vi P0

MVP gồm tám thực thể chính:

1. `stores` — cửa hàng.
2. `employees` — nhân viên quản lý hệ thống.
3. `customers` — thông tin khách hàng.
4. `accounts` — tài khoản và số dư khách hàng.
5. `machines` — máy tính thuộc cửa hàng.
6. `usage_sessions` — phiên sử dụng máy.
7. `account_transactions` — lịch sử thay đổi số dư.
8. `invoices` — hóa đơn kết thúc phiên.

`promotions`, `products`, `invoice_items`, `shifts`, `machine_groups` và `zones` nằm ngoài phạm vi P0.

## 3. Artefact triển khai

- [`001_initial_schema.sql`](../../sql/001_initial_schema.sql) — tạo bảng và ràng buộc nền tảng.
- [`002_indexes.sql`](../../sql/002_indexes.sql) — index phục vụ truy vấn và unique index chống phiên hoạt động trùng.
- [`seed.sql`](../../sql/seed.sql) — dữ liệu demo, được thực hiện trong HA-03.

Mô hình quan niệm là nguồn giải thích nghiệp vụ; mô hình logic là nguồn mô tả cấu trúc dữ liệu; script SQL là nguồn triển khai cuối cùng. Khi thay đổi schema, phải cập nhật các tài liệu liên quan trong cùng pull request.
