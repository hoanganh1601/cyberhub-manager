# Mock services — LI-02

Bộ service giả chạy hoàn toàn trong bộ nhớ, cùng chữ ký với `services/contracts.py`,
để dựng UI/gallery/Login khi chưa có MySQL hoặc service thật.

- Không cần Docker, MySQL hay file `.env`; không import UI.
- Trả đúng DTO/entity/exception của `cyberhub_manager.domain`; không trả password/hash.
- Dữ liệu demo hoàn toàn giả.

## 1. Tạo bundle

```python
from cyberhub_manager.services.mocks import MockClock, MockScenario, build_mock_services

clock = MockClock()                                   # tùy chọn, để điều khiển thời gian
services = build_mock_services(MockScenario.SUCCESS, clock=clock)

actor = services.auth.login("quanly01", "demo123")    # EmployeeSession
machines = services.machines.list_machines(actor.store_id)
```

`services` là `ServiceBundle` với 6 trường `auth`, `customers`, `wallet`, `machines`,
`sessions`, `reports`. View nhận bundle từ ngoài, không tự khởi tạo service.

- Sáu service trong **một** bundle dùng chung dữ liệu: nạp tiền xong thì
  `search_customers`, `get_customer`, `get_history` và `list_machines` đều thấy số dư mới.
- Mỗi lần gọi `build_mock_services()` tạo **một bộ dữ liệu mới, độc lập**.
- `scenario` nhận enum hoặc chuỗi (`"EMPTY"`).

## 2. Tài khoản demo (giả, không phải credential MySQL)

| Username | Mật khẩu | Vai trò |
|---|---|---|
| `quanly01` | `demo123` | MANAGER |
| `nhanvien01` | `demo123` | STAFF |
| `nhanvien02` | `demo123` | STAFF |

Username được trim, password không trim. Sai thông tin luôn báo
`AuthenticationError` với nội dung "Tên đăng nhập hoặc mật khẩu không đúng".

## 3. Dữ liệu demo (SUCCESS)

Mốc giờ mặc định `2026-10-18 09:00 UTC` (16:00 giờ Việt Nam). 1 cửa hàng `CH01`,
1 manager, 2 staff, 20 máy (10.000 VND/giờ), 5 khách.

| Máy | Trạng thái | Ghi chú |
|---|---|---|
| PC01, PC04, PC06–PC20 | AVAILABLE | PC04/06/07/08 có lịch sử → archive ra `ARCHIVED`; máy khác → `DELETED` |
| PC02 | IN_USE | KH002, 90 phút, estimated_cost 15.000, projected_balance **-10.000** |
| PC03 | MAINTENANCE | |
| PC05 | IN_USE | KH005, 30 phút, estimated_cost 5.000, projected_balance 95.000 |

| Khách | Customer | Account | Số dư | Dùng để demo |
|---|---|---|---:|---|
| KH001 | ACTIVE | ACTIVE | 50.000 | Mở phiên/checkout bình thường |
| KH002 | ACTIVE | ACTIVE | 5.000 | Đang chơi PC02, checkout cần bù tiền |
| KH003 | ACTIVE | LOCKED | 20.000 | Tài khoản bị khóa |
| KH004 | INACTIVE | LOCKED | -5.000 | Khách ngừng hoạt động, đang nợ |
| KH005 | ACTIVE | ACTIVE | 100.000 | Đang chơi PC05 |

Hóa đơn: HD0001–HD0004 (HD0003 là `VOID`). HD0004 tạo lúc 17:00 UTC = 00:00 ngày
18/10 giờ Việt Nam. Doanh thu 16–18/10: 30.000 / 20.000 / 10.000.

Lấy `machine_id`, `customer_id` từ kết quả `list_machines`/`search_customers`,
không viết cứng id trong UI.

## 4. Kịch bản

| Scenario | Dữ liệu | Operation bị lỗi | Exception |
|---|---|---|---|
| `SUCCESS` | Đầy đủ | Không | Chỉ lỗi nghiệp vụ thật (sai SĐT, thiếu tiền, …) |
| `EMPTY` | Chỉ cửa hàng + 3 nhân viên | Không | Danh sách trả `[]`; tìm theo id → `NotFoundError` |
| `VALIDATION_ERROR` | Đầy đủ | `create_customer` (phone, password), `update_customer` (full_name), `top_up` (amount), `create_machine` (hourly_rate) | `ValidationError` có `field_errors` |
| `CONFLICT` | Đầy đủ | `create_customer` (phone), `open_session` (machine_id), `create_machine` (code) | `ConflictError` có `field_errors` |
| `UNAVAILABLE` | Đầy đủ | `search_customers`, `get_history`, `list_machines`, `list_invoices`, `daily_revenue` | `ServiceUnavailableError` |

Operation không có trong bảng chạy bình thường ở mọi kịch bản (ví dụ `login` vẫn
đăng nhập được ở `UNAVAILABLE`). Nguồn chính thức: `AFFECTED_OPERATIONS` trong
`scenarios.py`.

Phân quyền kiểm tra ở mọi kịch bản: STAFF gọi `set_customer_status`,
`create_machine`, `update_machine`, `set_maintenance`, `archive_machine` →
`PermissionDeniedError`. Actor phải lấy từ `login`; actor tự dựng hoặc sửa role cũng bị từ chối.

## 5. Điều khiển thời gian

```python
clock = MockClock()                       # 2026-10-18 09:00 UTC
services = build_mock_services(clock=clock)

clock.advance(minutes=30)                 # tiến 30 phút; không cho lùi
clock.set(datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc))
clock.reset()                             # về mốc ban đầu (không reset dữ liệu)
```

Mock không gọi `datetime.now()`. Khi gọi `preview_checkout`, truyền
`clock.now()` (không truyền giờ thật), vì `complete_checkout` tính lại theo clock.

## 6. Reset dữ liệu

Gọi lại `build_mock_services()` để có bộ dữ liệu sạch. Đổi kịch bản cũng là tạo
bundle mới với scenario khác.

## 7. Luồng mẫu

```python
from cyberhub_manager.domain.enums import PaymentMethod

kh001 = services.customers.search_customers("KH001")[0]
pc01 = next(m for m in services.machines.list_machines(actor.store_id)
            if m.machine_code == "PC01")

services.wallet.top_up(kh001.customer_id, 20_000, PaymentMethod.CASH, actor.employee_id)
services.sessions.preview_open(kh001.customer_id, pc01.machine_id, actor)  # can_open=True
services.sessions.open_session(kh001.customer_id, pc01.machine_id, actor)

clock.advance(minutes=45)
services.sessions.preview_checkout(pc01.machine_id, clock.now())           # usage_cost=7.500
result = services.sessions.complete_checkout(pc01.machine_id, actor, 0, None)
# result.invoice.invoice.invoice_code == "HD0005", result.balance_after == 62.500
```

Checkout cần bù: `complete_checkout(machine_id, actor, settlement_amount, PaymentMethod.CASH)`.
Bù thiếu → `SettlementRequiredError`, `details["settlement_required"]` là số cần thu;
dữ liệu chưa thay đổi.

## 8. Giới hạn

Mock chỉ mô phỏng thay đổi cần cho demo: không có SQL, transaction, locking hay
nhiều cửa hàng. Thao tác lỗi không để lại thay đổi dở dang vì mock kiểm tra hết
rồi mới ghi. Không dùng mock trong `app.py` production.

## 9. Kiểm thử

```powershell
python -m pytest tests/unit -q
```
