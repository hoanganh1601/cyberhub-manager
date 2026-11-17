# Dữ liệu và migration

Schema MySQL được định nghĩa trong `sql/001_*.sql` đến `sql/024_*.sql`. `scripts/init_db.py` áp dụng file theo thứ tự tên và lưu checksum trong `schema_migrations`; không sửa migration đã chạy để tránh sai checksum. Với thay đổi schema, thêm file số tiếp theo.

## Tìm dữ liệu ở đâu

| Cần xem | Nguồn |
|---|---|
| Quan hệ tổng quan theo migration | [ERD hiện hành](../diagrams/current_erd.md) |
| Cột, kiểu, index sau khi kết nối MySQL | `INFORMATION_SCHEMA` và file [data dictionary](../diagrams/data_dictionary.md) được sinh từ DB |
| SQL gốc | `sql/` |
| Truy vấn ứng dụng | `src/cyberhub_manager/repositories/` |
| Giao dịch | `src/cyberhub_manager/database/transaction.py` |

**Giới hạn đã xác định:** ERD hiện hành suy từ migration trong Git, chưa đối chiếu database đang chạy. Data dictionary hiện liệt kê 47/63 bảng nghiệp vụ, thiếu 16 bảng thuộc các migration sau P0; không dùng file này để khẳng định schema đầy đủ. Xem [biên bản kiểm kê](../../history/docs/architecture/DATABASE_SCHEMA_AUDIT.md) trước khi bổ sung generator và chạy lại trên MySQL test.

## Khi thêm bảng hoặc cột

1. Thêm migration mới trong `sql/`, giữ nguyên các migration cũ.
2. Cập nhật repository và service trong cùng thay đổi; kiểm tra trường hợp rollback, quyền và cửa hàng.
3. Chạy migration trên `cyberhub_manager_test`, đối chiếu `INFORMATION_SCHEMA`, rồi chạy integration test tương ứng.
4. Cập nhật ERD hiện hành. Chỉ tái sinh dictionary khi generator đã bao phủ bảng mới và kết nối đúng DB test.

MySQL sản xuất/demo có dữ liệu thật và database test là hai cơ sở riêng. Không chạy seed hoặc test ghi dữ liệu trên database đang dùng để trình diễn.
