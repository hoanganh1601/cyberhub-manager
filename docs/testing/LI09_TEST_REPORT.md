# LI-09 Test Report

Đây là kết quả lịch sử của LI-09. Kết quả chạy lại sau khi tích hợp LI-10, HA-09,
HA-10 và UI desktop/web hiện tại nằm trong [HA_LI_NG_RELEASE_AUDIT.md](HA_LI_NG_RELEASE_AUDIT.md).

## 1. Phạm vi

Báo cáo xác nhận automated test suite sau khi LI-07, LI-08 và các thay đổi mới
nhất từ `develop` đã được tích hợp vào nhánh review LI-09.

Toàn bộ integration test bắt buộc chạy trên `cyberhub_manager_test`. Test harness
từ chối kết nối nếu phát hiện database khác.

## 2. Thông tin phiên kiểm thử

- Ngày chạy: 2026-11-04
- Người chạy: Hoàng Anh — final review
- Review branch: `fix/LI-09-final-review`
- LI-09 source branch:
  `phalinh20072006/cyb-22-li-09-automated-va-acceptance-test-suite`
- Base `develop`: `57faf5c`
- Python: 3.13.14
- MySQL: 8.4.11
- Database: `cyberhub_manager_test`
- Hệ điều hành: Windows 11, build 26200

## 3. Kết quả automated test

| Nhóm | Lệnh | Kết quả | Thời gian |
|---|---|---:|---:|
| Unit test | `python -m pytest tests/unit -q` | 587 passed | 4.91 giây |
| Integration test | `python -m pytest tests/integration -q` | 189 passed | 44.78 giây |
| Toàn bộ test suite | `python -m pytest -q` | 776 passed | 43.80 giây |

Kết quả cuối:

- Passed: 776
- Failed: 0
- Skipped: 0
- Error: 0

Kiểm tra bổ sung:

| Kiểm tra | Kết quả |
|---|---|
| `python -m compileall -q src scripts tests` | Không lỗi |
| `git diff --check` | Sạch |
| Database guard | Chỉ chấp nhận `cyberhub_manager_test` |
| Migration test database | Đã áp dụng thành công |
| LI-07 checkout tests | Pass |
| LI-08 report tests | Pass |
| Test harness và prepare DB | Pass |

## 4. Chuẩn hóa database test

Các file LI-07 và LI-08 đã được chuyển từ
`cyberhub_manager_migration_test` sang `cyberhub_manager_test`:

- `tests/integration/test_checkout_flow.py`
- `tests/integration/test_checkout_repositories.py`
- `tests/integration/test_report_flow.py`
- `tests/integration/test_report_repositories.py`

Việc cấu hình database được quản lý tập trung bởi `tests/conftest.py`. Các test
không tự thay đổi `MYSQL_DATABASE` hoặc reset connection pool.

`test_harness.py` vẫn cố ý sử dụng một số tên database không hợp lệ để xác nhận
cơ chế bảo vệ từ chối chạy nhầm database.

## 5. Ma trận kiểm thử P0

| Khu vực | Happy path | Validation | Permission/store scope | Conflict | Rollback | DB unavailable |
|---|---:|---:|---:|---:|---:|---:|
| Authentication | ✓ | ✓ | ✓ | N/A | N/A | ✓ |
| Customer/account | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Wallet/top-up | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Machine management | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Open session/live estimate | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Checkout/invoice | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Invoice/revenue report | ✓ | ✓ | ✓ | N/A | N/A | ✓ |

`N/A` áp dụng cho thao tác chỉ đọc, không phát sinh cập nhật cần rollback hoặc
xung đột ghi.

## 6. Các flow nghiệp vụ chính

| # | Flow | Trạng thái |
|---:|---|---|
| 1 | Đăng nhập nhân viên hợp lệ | Pass |
| 2 | Từ chối nhân viên bị khóa hoặc cửa hàng ngừng hoạt động | Pass |
| 3 | Tạo khách hàng và tài khoản trong cùng transaction | Pass |
| 4 | Cập nhật hồ sơ khách hàng | Pass |
| 5 | Khóa/mở khóa khách hàng và tài khoản đồng bộ | Pass |
| 6 | Nạp tiền và ghi lịch sử atomically | Pass |
| 7 | Quản lý máy, bảo trì và lưu trữ máy | Pass |
| 8 | Mở phiên sử dụng | Pass |
| 9 | Chặn nhiều active session trên cùng máy hoặc khách | Pass |
| 10 | Tính live estimate | Pass |
| 11 | Preview checkout không thay đổi database | Pass |
| 12 | Complete checkout | Pass |
| 13 | Trừ số dư tài khoản | Pass |
| 14 | Ghi khoản thanh toán bổ sung đúng phương thức | Pass |
| 15 | Hoàn tất session và trả máy về `AVAILABLE` | Pass |
| 16 | Chỉ tạo một invoice cho mỗi session | Pass |
| 17 | Checkout lỗi rollback toàn bộ transaction | Pass |
| 18 | Danh sách và chi tiết hóa đơn đúng cửa hàng | Pass |
| 19 | Doanh thu chỉ cộng invoice `PAID` | Pass |
| 20 | Invoice `VOID` không được tính doanh thu | Pass |
| 21 | Khoảng ngày Việt Nam được chuyển sang UTC đúng | Pass |
| 22 | Không truy cập dữ liệu thuộc cửa hàng khác | Pass |

## 7. Manual acceptance

Manual acceptance chưa được thực hiện trong phiên review này.

- Checklist: `tests/manual/CHECKLIST.md`
- Tổng số test case: 24
- Passed: 0
- Failed: 0
- Chưa thực hiện: 24
- Evidence: chưa có

Không được tự đánh dấu các test case manual là pass chỉ dựa trên unit hoặc
integration test. Mỗi test case phải được chạy trên UI thực tế và lưu ảnh bằng
chứng trước khi phát hành P0.

## 8. Bug và hạn chế

### Bug

Không phát hiện bug blocker trong automated test suite.

BUG-01 trong báo cáo cũ không còn áp dụng. `CustomerService` và
`MachineService` hiện đã đối chiếu actor với nhân viên đang `ACTIVE` trong
database; các kiểm thử quyền tương ứng đều pass.

### Hạn chế còn lại

- Manual UI acceptance chưa được thực hiện.
- Chưa có performance/load test.
- Chưa có penetration/security test chuyên biệt.
- CI/CD cloud nằm ngoài phạm vi LI-09 hiện tại.

## 9. Kết luận

### Automated test scope

**READY**

- LI-07 và LI-08 đã được tích hợp.
- Toàn bộ automated suite đạt `776 passed`.
- Không có failed, skipped hoặc collection error.
- Test database được cô lập và có guard chống chạy nhầm database.

### P0 release

**PENDING MANUAL ACCEPTANCE**

P0 chỉ được chuyển sang trạng thái release-ready sau khi:

1. Chạy đủ 24 test case trong `tests/manual/CHECKLIST.md`.
2. Lưu evidence cho các flow UI quan trọng.
3. Ghi nhận và xử lý mọi lỗi phát hiện trong manual test.
4. Cập nhật kết quả manual vào báo cáo này.
