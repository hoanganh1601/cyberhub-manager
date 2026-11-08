# HA-09 — Review database, đóng gói và tối ưu query

- Ngày review: 08/11/2026
- Môi trường: Windows 11, Python 3.13.7, MySQL 8.4.13 (Docker), mysql-connector-python 26.7.0
- Nhánh: `phalinh20072006/cyb-XX-ha-09-review-db-va-dong-goi` (tách từ LI-10)

Các số đo Windows bên dưới là báo cáo gốc của Linh. Kết quả kiểm tra lại trên nhánh tích hợp,
công cụ benchmark đã cô lập dữ liệu, và giới hạn nghiệm thu hiện tại ở
[HA_LI_NG_RELEASE_AUDIT.md](HA_LI_NG_RELEASE_AUDIT.md).

## 1. Kết quả theo tiêu chí nghiệm thu

| Tiêu chí (backlog HA-09) | Kết quả | Bằng chứng |
|---|---|---|
| Không có service tự commit | Đạt | Không có `commit()` nào ngoài `database/transaction.py`; mọi service mở transaction qua `transaction()` |
| Test rollback pass | Đạt | `tests/integration/test_transaction_manager.py`, các test rollback checkout/open session; integration 189 passed |
| Thao tác demo dưới 2 giây | Đạt | Mục 3: chậm nhất 460ms trên 60.000 hóa đơn |
| Khóa ngoại không lỗi | Đạt | 14 FK (mục 4); script đo nạp 145.000 dòng có FK không lỗi |
| Máy sạch chạy được theo README | Đạt sau khi bổ sung README | Mục 5 |

## 2. Transaction và `SELECT ... FOR UPDATE`

Thứ tự khóa chính trong mở phiên/checkout: **máy → tài khoản → phiên**. Giữ cùng thứ tự giúp
giảm nguy cơ khóa chéo; vẫn cần xử lý deadlock do cạnh tranh hoặc khóa index của MySQL.

| Nghiệp vụ | Dòng bị khóa (theo thứ tự) |
|---|---|
| Mở phiên (`open_session`) | `machines` → `accounts` → `usage_sessions` theo máy → `usage_sessions` theo khách |
| Checkout (`complete_checkout`) | `machines` → `accounts` → `usage_sessions` theo máy |
| Nạp tiền (`top_up`) | `accounts` |
| Bảo trì / ngừng dùng máy | `machines` |

Lưới an toàn cuối là unique index: `uq_usage_sessions_active_machine`, `uq_usage_sessions_active_customer`
(tối đa một phiên ACTIVE mỗi máy/khách) và `uq_invoices_session` (mỗi phiên một hóa đơn).
LI-10 đổi các vi phạm này thành `ConflictError` có field cho UI và tự chạy lại thao tác ghi khi MySQL báo deadlock.

## 3. Thời gian thao tác và EXPLAIN

Đo bằng `python scripts/perf_check.py` trên `cyberhub_manager_test` với 5.000 khách, 60 máy,
60.000 phiên/hóa đơn trong 90 ngày, 80.000 giao dịch ví. Service thật, transaction thật.

| Thao tác | Thời gian |
|---|---:|
| Đăng nhập (gồm bcrypt) | 249ms |
| Danh sách máy | 27ms |
| Tìm khách theo tên / SĐT | 33ms / 23ms |
| Nạp tiền | 15ms |
| Lịch sử giao dịch | 7ms |
| Xem trước / mở phiên | 13ms / 26ms |
| Xem trước / hoàn tất checkout | 8ms / 45ms |
| Hóa đơn hôm nay | 21ms |
| Hóa đơn 30 ngày (~20.000 dòng) | 460ms |
| Hóa đơn 30 ngày + từ khóa | 86ms |
| Chi tiết hóa đơn | 15ms |
| Doanh thu 30 / 90 ngày | 32ms / 48ms |

EXPLAIN 20 câu SELECT khác nhau. Các dòng không dùng index hoặc có filesort, và lý do không thêm index:

| Truy vấn | Quan sát | Kết luận |
|---|---|---|
| Danh sách máy | Quét bảng `machines` (60 dòng), filesort theo mã | Bảng nhỏ, quét nhanh hơn dùng index |
| Phiên ACTIVE theo cửa hàng | Dùng `idx_usage_sessions_status_started_at`, filesort trên vài dòng | Chỉ các phiên đang chạy |
| Lịch sử giao dịch | Dùng `idx_account_transactions_account_created_at` | Đúng index; filesort sau JOIN trên ≤ 50 dòng |
| Danh sách hóa đơn | Filesort sau khi lọc theo ngày | ORDER BY trên tập đã lọc |
| Doanh thu theo ngày | Optimizer quét `invoices` | Dữ liệu đo chỉ có một cửa hàng; quét có thể rẻ hơn tra index. Khi phân bố dữ liệu thay đổi phải đo lại EXPLAIN, không giả định optimizer luôn chọn index |

**Không thêm index mới**: mọi thao tác đã dưới 2 giây và các index trong `sql/002_indexes.sql`
được dùng đúng chỗ. Thêm index chỉ làm chậm thao tác ghi mà không cải thiện rõ.

## 4. Khóa ngoại

14 FK, tất cả `ON UPDATE RESTRICT ON DELETE RESTRICT`:
`employees→stores`, `machines→stores`, `accounts→customers`,
`usage_sessions→customers/machines/employees(opened_by, closed_by)`,
`account_transactions→accounts/employees/usage_sessions`,
`invoices→usage_sessions/customers/employees/stores`.

## 5. Chạy trên máy sạch theo README

Clone mới, `py -m venv .venv`, `pip install -e ".[dev]"`, `pip check`:

| Bước | Kết quả |
|---|---|
| Cài dependencies | OK, `No broken requirements found` |
| `cyberhub-manager` khi thiếu cấu hình | Dừng trước khi mở cửa sổ, hướng dẫn cấu hình `.env` hoặc dùng `--mock`; thông báo/exit code thực tế được kiểm tra lại trong test HA-11 |
| `python scripts/prepare_test_db.py` | `Test database cyberhub_manager_test is ready.` |
| `python scripts/init_db.py` | Áp dụng/bỏ qua migration đúng thứ tự |
| `python -m pytest -q` (một lệnh) | 1063 passed (874 unit + 189 integration) |

**Đã sửa README:** thiếu bước chuẩn bị database ứng dụng (`init_db.py` + seed) trước `cyberhub-manager`,
nên máy mới đăng nhập sẽ báo *Service is temporarily unavailable*. README nay có mục
"Chuẩn bị database ứng dụng", bảng tài khoản demo và các lệnh `--mock`, `--lang`.

## 6. Giới hạn đã biết

- Màn Hóa đơn tải toàn bộ hóa đơn trong khoảng ngày rồi phân trang ở UI (10 dòng/trang) để tính tổng.
  Với ~20.000 hóa đơn mất ~0,5 giây; nếu dữ liệu lớn hơn nhiều nên chuyển sang phân trang ở SQL (`LIMIT/OFFSET`).
- Lock-wait timeout (1205) không tự chạy lại (xem LI-10): người dùng đã chờ `innodb_lock_wait_timeout`.
