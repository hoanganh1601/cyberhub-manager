# Dữ liệu và migration

Schema MySQL được định nghĩa trong `sql/001_*.sql` đến `sql/032_*.sql`. `scripts/init_db.py` áp dụng file theo thứ tự tên và lưu checksum trong `schema_migrations`; không sửa migration đã chạy để tránh sai checksum. Với thay đổi schema, thêm file số tiếp theo.

## Tìm dữ liệu ở đâu

| Cần xem | Nguồn |
|---|---|
| Quan hệ tổng quan theo migration | [ERD hiện hành](../diagrams/current_erd.md) |
| Kiến trúc lớp và trình tự nghiệp vụ | [UML hệ thống](../diagrams/system_uml.md) |
| Cột, kiểu, index sau khi kết nối MySQL | `INFORMATION_SCHEMA` và file [data dictionary](../diagrams/data_dictionary.md) được sinh từ DB |
| Hồ sơ chứng minh chuẩn 3NF cho 75 bảng | [Phụ lục chứng minh 3NF](DATABASE_3NF_PROOFS.md) |
| SQL gốc | `sql/` |
| Truy vấn ứng dụng | `src/cyberhub_manager/infrastructure/repositories/` |
| Giao dịch | `src/cyberhub_manager/infrastructure/database/transaction.py` |

**Trạng thái kiểm chứng:** data dictionary hiện bao phủ 75/75 bảng nghiệp vụ qua migration `032` (kèm 18 view `v_*` cho các thuộc tính dẫn xuất và 28 trigger toàn vẹn) và được sinh từ `INFORMATION_SCHEMA` của `cyberhub_manager_test`. Migration `031` loại hai ngày nghiệp vụ lặp khỏi bảng game/quảng cáo; migration `032` tách liên kết phiên `session_transactions(transaction_id PK/FK, session_id FK)` khỏi `account_transactions`, bắt buộc `account_transactions.store_id NOT NULL` và bổ sung trigger bất biến sổ cái tài chính. Integration test sẽ báo lỗi nếu schema, mô tả cột hoặc file sinh ra lệch nhau. ERD hiện hành là bản tổng quan dễ đọc; SQL và dictionary vẫn là nguồn chi tiết cho kiểu, index và ràng buộc.

## Khi thêm bảng hoặc cột

1. Thêm migration mới trong `sql/`, giữ nguyên các migration cũ.
2. Cập nhật repository và service trong cùng thay đổi; kiểm tra trường hợp rollback, quyền và cửa hàng.
3. Chạy migration trên `cyberhub_manager_test`, đối chiếu `INFORMATION_SCHEMA`, rồi chạy integration test tương ứng.
4. Cập nhật ERD hiện hành. Chỉ tái sinh dictionary khi generator đã bao phủ bảng mới và kết nối đúng DB test.

MySQL sản xuất/demo có dữ liệu thật và database test là hai cơ sở riêng. Không chạy seed hoặc test ghi dữ liệu trên database đang dùng để trình diễn.
