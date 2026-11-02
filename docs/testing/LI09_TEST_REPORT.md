# LI-09 Test Report

> Báo cáo này phản ánh trạng thái **trước khi** LI-07 và LI-08 được merge vào
> `develop` và **trước khi** UI hoàn thành. Phải cập nhật lại sau hai mốc đó.

## Thông tin phiên bản

- Commit/SHA: `<điền SHA sau khi commit LI-09>` (dựng trên `1f9f7f4`)
- Branch: `phalinh20072006/cyb-22-li-09-automated-va-acceptance-test-suite`
- Ngày chạy: 2026-11-02
- Người chạy: Linh (điền xác nhận sau khi chạy lại)
- Python: 3.13.11
- MySQL: 8.4.13
- Hệ điều hành: Windows 11 Pro (build 26300)

## Kết quả automated test

Đây là kết quả trên branch LI-09, chưa có code LI-07 và LI-08.

- Tổng số test: 575 (448 unit, 127 integration)
- Passed: 575
- Failed: 0
- Skipped: 0
- Thời gian chạy: khoảng 45 giây
- Lệnh đã chạy: `python -m pytest -q`

### Kiểm tra độ ổn định

| Kiểm tra | Kết quả |
|---|---|
| Chạy toàn bộ suite 2 lần liên tiếp | 575 passed cả 2 lần |
| Chạy theo thứ tự đảo ngược | 575 passed |
| Chạy riêng từng integration test trong tiến trình mới | 127 test, 0 failed |
| Dữ liệu còn lại trong `cyberhub_manager_test` sau khi chạy | 0 dòng ở cả 8 bảng nghiệp vụ |
| Unit test khi MySQL không truy cập được | 448 passed |
| `python -m compileall -q src scripts tests` | Không lỗi |
| `git diff --check` | Sạch |

### Diễn tập merge LI-07 và LI-08

Diễn tập trên bản clone tạm, gộp `cyb-20` (head `9d08951`) và `cyb-21` (head
`99d83c9`) vào LI-09. **Đây chưa phải kết quả chính thức của bản release.**

| Kiểm tra | Kết quả |
|---|---|
| Merge cả hai branch | Không có conflict |
| Trước khi chuyển test của LI-07/LI-08 sang database chuẩn | Guard chặn 59 test đang trỏ vào `cyberhub_manager_migration_test`, không có ghi dữ liệu |
| Sau khi chuyển 4 file test sang `cyberhub_manager_test` | 765 passed (579 unit, 186 integration) |
| Coverage toàn dự án, gồm cả UI chưa kiểm thử | 84% |

Coverage service trên bản diễn tập:

| Service | Coverage |
|---|---|
| `auth_service` | 100% |
| `customer_service` | 100% |
| `report_service` | 100% |
| `session_service` | 98% |
| `machine_service` | 93% |
| `wallet_service` | 93% |

Coverage chỉ là chỉ báo hỗ trợ, không thay thế việc kiểm tra đúng nghiệp vụ.

### Ma trận kiểm thử P0

Ô có dấu * chỉ được xác nhận trên bản diễn tập, vì test nằm ở branch LI-07 hoặc
LI-08.

| Khu vực | Happy path | Validation | Permission/store scope | Conflict | Rollback | DB unavailable |
|---|---|---|---|---|---|---|
| Authentication | ✓ | ✓ | ✓ | N/A (1) | N/A (1) | ✓ |
| Customer/account | ✓ | ✓ | ✓ (2) | ✓ | ✓ | ✓ |
| Wallet/top-up | ✓ | ✓ | ✓ | ✓ (3) | ✓ | ✓ |
| Machine management | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Open session/live estimate | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Checkout/invoice | ✓* | ✓* | ✓* | ✓* | ✓* | ✓* |
| Invoice/revenue report | ✓* | ✓* | ✓* | N/A (1) | N/A (1) | ✓* |

1. Thao tác chỉ đọc dữ liệu, không ghi nên không có xung đột ghi và không có gì để
   rollback.
2. Bảng `customers` trong schema P0 không có `store_id`, nên phạm vi cửa hàng chỉ áp
   dụng cho actor: session phải khớp cửa hàng trong database.
3. `top_up` không có đường `ConflictError`; khóa `FOR UPDATE` xử lý tranh chấp. Test
   `test_concurrent_top_ups_do_not_lose_money` cho 4 lần nạp đồng thời và kiểm tra
   không mất tiền.

### Đối chiếu 22 flow integration tối thiểu

| # | Flow | Test | Trạng thái |
|---|---|---|---|
| 1 | Đăng nhập nhân viên hợp lệ | `test_customer_flow.py` | Pass |
| 2 | Từ chối nhân viên bị khóa hoặc cửa hàng ngừng hoạt động | `test_customer_flow.py`, `test_ha05_auth_repository.py` | Pass |
| 3 | Tạo khách và tài khoản cùng transaction | `test_customer_flow.py` | Pass |
| 4 | Cập nhật hồ sơ khách | `test_customer_flow.py` | Pass |
| 5 | Khóa/mở khóa khách và tài khoản đồng bộ | `test_customer_flow.py` | Pass |
| 6 | Nạp tiền và ghi lịch sử atomically | `test_wallet_flow.py` | Pass |
| 7 | Tạo, cập nhật, bảo trì, lưu trữ máy | `test_machine_management_flow.py` | Pass |
| 8 | Mở phiên sử dụng | `test_open_session_flow.py` | Pass |
| 9 | Từ chối máy hoặc khách đã có active session | `test_open_session_flow.py` | Pass |
| 10 | Tính live estimate | `test_open_session_flow.py` | Pass |
| 11 | Preview checkout không ghi database | `test_checkout_flow.py` | Pass trên bản diễn tập |
| 12 | Complete checkout | `test_checkout_flow.py` | Pass trên bản diễn tập |
| 13 | Trừ số dư tài khoản | `test_checkout_flow.py` | Pass trên bản diễn tập |
| 14 | Ghi thanh toán bổ sung đúng phương thức | `test_checkout_flow.py` | Pass trên bản diễn tập |
| 15 | Hoàn tất session, trả máy về AVAILABLE | `test_checkout_flow.py` | Pass trên bản diễn tập |
| 16 | Tạo duy nhất một invoice cho session | `test_checkout_flow.py` | Pass trên bản diễn tập |
| 17 | Transaction thất bại rollback toàn bộ | `test_checkout_flow.py` | Pass trên bản diễn tập |
| 18 | Danh sách và chi tiết hóa đơn đúng cửa hàng | `test_report_flow.py` | Pass trên bản diễn tập |
| 19 | Báo cáo chỉ cộng invoice PAID | `test_report_flow.py` | Pass trên bản diễn tập |
| 20 | Invoice VOID không được tính doanh thu | `test_report_flow.py` | Pass trên bản diễn tập |
| 21 | Khoảng ngày Việt Nam chuyển sang UTC đúng | `test_report_flow.py` | Pass trên bản diễn tập |
| 22 | Không đọc hoặc thay đổi dữ liệu cửa hàng khác | Các file flow của máy, phiên, checkout, report | Pass (phần checkout/report trên bản diễn tập) |

## Kết quả manual acceptance

**Chưa thực hiện.** Các màn hình login, dashboard, khách hàng, hóa đơn, doanh thu,
quản lý máy và `app_shell` vẫn là placeholder; `app.py` mới mở cửa sổ trống.

- Tổng số test case: 24 (`tests/manual/CHECKLIST.md`)
- Passed: 0
- Failed: 0
- Chưa thực hiện: 24
- Evidence directory/link: `docs/screenshots/li09/` (chưa có evidence)

## Bug còn tồn tại

| Mã | Mức độ | Mô tả | Owner | Trạng thái |
|---|---|---|---|---|
| BUG-01 | Thấp | `CustomerService.set_customer_status` và các thao tác ghi của `MachineService` nhận `actor=None` mà bỏ qua bước đối chiếu với người đang đăng nhập, trong khi contract yêu cầu `EmployeeSession` và `SessionService` từ chối `None`. Không leo thang được quyền vì danh tính và role vẫn lấy từ `actor_provider` cộng database. | Linh | Mở, chưa sửa trong LI-09 theo phạm vi task |

Chưa ghi nhận bug blocker trong phần nghiệp vụ đã kiểm thử tự động. Giao diện chưa
được kiểm thử nên chưa thể kết luận về bug UI.

## Known limitations

- Automated test chưa chạy trên `develop` có LI-07 và LI-08; kết quả checkout/report
  mới là diễn tập.
- Mock `ReportService` chưa kiểm tra actor như service thật; UI chạy bằng mock sẽ
  không gặp `PermissionDeniedError` cho tới khi nối service thật.
- Múi giờ dùng UTC+7 cố định thay vì `ZoneInfo`, vì venv Windows không có `tzdata`.
  Việt Nam không có giờ mùa hè nên kết quả chính xác.
- Việc service đổi lỗi trùng `uq_usage_sessions_active_*` và `uq_invoices_session`
  thành `ConflictError` chỉ được kiểm tra bằng unit test với lỗi giả lập. Trong các
  test đồng thời trên MySQL thật, khóa `FOR UPDATE` chặn trước khi tới index;
  `uq_invoices_session` được kiểm tra thật ở tầng repository (HA-08).
- Không có performance/load test, penetration test hay CI/CD cloud (ngoài phạm vi
  LI-09).

## Kết luận release

- **NOT READY**
- Lý do:
  1. LI-07 và LI-08 chưa merge vào `develop` (Definition of Done mục 1).
  2. Manual acceptance chưa thực hiện vì UI chưa hoàn thành (mục 5 và 6).
  3. Automated test chưa được chạy chính thức trên bản đã gộp đầy đủ.

### Việc cần làm để chuyển sang READY

1. Merge LI-07 rồi LI-08 vào `develop`, sau đó merge `develop` vào LI-09.
2. Chuyển `test_checkout_flow.py`, `test_checkout_repositories.py`,
   `test_report_flow.py`, `test_report_repositories.py` sang `cyberhub_manager_test`.
3. Chạy lại `python -m pytest -q` và cập nhật mục Kết quả automated test.
4. Hoàn thành UI, chạy `tests/manual/CHECKLIST.md`, lưu evidence.
5. Xử lý hoặc chấp nhận BUG-01 và mọi bug phát hiện khi chạy checklist.
6. Cập nhật commit đã kiểm thử và kết luận trong báo cáo này.
