# Kiểm tra bản tích hợp HA / LI / NG — 08/11/2026

## Phạm vi và nguồn tích hợp

Nhánh an toàn: `integrate/ha-li-ng-release`, tách từ `develop` tại `20a46a4`.
Giữ giao diện Stitch desktop, web, logo, font, VI/EN và bootstrap của bản develop này.

| PR | Task | Head đã review | Phần nhận |
|---|---|---|---|
| [#28](https://github.com/hoanganh1601/cyberhub-manager/pull/28) | LI-10, bổ sung HA-11 | `b5b89db` | Phân loại lỗi MySQL, mapping sáu service, retry deadlock, rollback/logging, kiểm thử |
| [#29](https://github.com/hoanganh1601/cyberhub-manager/pull/29) | HA-09 | `91861c7` | Benchmark/EXPLAIN, hướng dẫn migrate/seed/package, báo cáo review DB |
| [#30](https://github.com/hoanganh1601/cyberhub-manager/pull/30) | HA-10 | `3ba7617` | ERD PNG, data dictionary sinh từ schema, hai test chống lệch tài liệu |

Ba nhánh nối tiếp nhau: #30 đã chứa #29 và #28. Merge head #30 một lần để giữ lịch sử
của Linh, không cherry-pick trùng. Hai conflict `app.py` và `ui/login_view.py` được giải quyết
trên implementation develop hiện tại; không thay bằng controller/login cũ của nhánh #28.

## Những điểm đã sửa khi review

1. Giữ entry point `CyberHubApp` và `services/bootstrap.py` hiện tại, dùng chung service
   cho desktop/web. Bổ sung hook ghi log lỗi Tk; UI chỉ nhận thông báo VI/EN an toàn.
   Test HA-11 chuyển sang API giao diện hiện tại, vẫn kiểm tra actor, CLI, lỗi đăng nhập.
2. LI-10 chỉ retry toàn bộ transaction khi deadlock **1213**, tối đa ba lần.
   Không tự retry lock timeout hoặc mất kết nối vì có thể chưa biết kết quả commit.
   Web cũng dùng mapping chung khi đọc lại actor; lỗi kết nối trả 503 và cho thử lại,
   không làm mất phiên đăng nhập hợp lệ. Không trả `errno`/`db_error` ra HTTP.
3. Benchmark dùng namespace duy nhất mỗi lần chạy, không còn xóa mọi dữ liệu `PERF%`.
   Từ chối database khác `cyberhub_manager_test`; seed lỗi vẫn rollback/dọn/đóng connection;
   phục hồi instrumentation cursor khi xong. Không import Tk, không đổi DB khi import module;
   sinh phí làm tròn đúng và tránh trùng SĐT/username với dữ liệu đã có.
4. Web cho nạp tiền tài khoản bị khóa để trả nợ, vẫn giữ trạng thái khóa và chặn mở phiên.
   Bổ sung CTA nạp tiền khi preview mở phiên thiếu số dư; nạp xong tự quay lại đúng máy/khách
   và tải preview mới. Không tự tính phí hoặc ghi số dư từ trình duyệt.
5. Đồng bộ tài liệu: VI mặc định, EN khi chọn; quản lý được sửa tên/đơn giá máy đang dùng,
   phiên hiện tại giữ đơn giá snapshot; vẫn chặn bảo trì/archive máy đang dùng.
   Làm rõ số dư dự kiến âm và tiền bù, phân biệt cardinality do DDL bảo đảm với rule tạo khách+tài khoản.

## Kết quả kiểm tra

Môi trường: Linux x86_64, Python **3.11.15**, MySQL **8.4.13** trong container riêng,
database `cyberhub_manager_test`. Tk dùng display kiểm thử; không thay DB ứng dụng của người dùng.

| Kiểm tra | Kết quả |
|---|---|
| `python -m pytest -q` | **1.164 passed**, 101,97 giây; không fail/skip |
| Thành phần suite | 970 unit/UI/HTTP, 194 integration MySQL |
| `python -m compileall -q src scripts tests` | Pass |
| `python -m pip check` | Không xung đột dependency |
| Seed hai lần trên DB kiểm thử riêng | Giữ nguyên số dòng: 1 store, 3 nhân viên, 5 khách, 5 account, 20 máy |
| `gen_data_dictionary.py --check` và test HA-10 | Khớp schema, đủ tám bảng nghiệp vụ/14 FK |
| Build wheel; cài vào venv mới ngoài source tree | Web headless, HTML/JS/CSS, logo và font dùng được |
| Build `Dockerfile.web`, chạy Gunicorn | `/healthz` trả 200, demo khởi động được |
| Browser Chromium, 1280×720 và 390×844 | Đăng nhập quản lý/nhân viên, năm màn, VI/EN; không có JavaScript page error |
| Browser flow | Tạo khách → thiếu số dư → nạp → quay lại preview → mở phiên → checkout/receipt; nạp tài khoản khóa không mở khóa |

Log gốc: [pytest](evidence/pytest-release-linux.txt), [benchmark/EXPLAIN](evidence/ha09-perf-linux.txt).

Ảnh browser là evidence kiểm tra tự động, không thay chữ ký nghiệm thu desktop:

- [Tổng quan](../screenshots/release-integration/dashboard-1280.png)
- [Khách hàng](../screenshots/release-integration/customers-1280.png)
- [Thiếu số dư và CTA nạp tiền](../screenshots/release-integration/open-insufficient.png)
- [Thanh toán thành công](../screenshots/release-integration/checkout-success.png)
- [Doanh thu](../screenshots/release-integration/revenue-1280.png)
- [Mobile](../screenshots/release-integration/mobile-customers.png)

### Đo DB/EXPLAIN thực tế

`python scripts/perf_check.py`: 5.000 khách, 60 máy, 60.000 phiên/hóa đơn,
80.000 giao dịch trong khoảng 90 ngày; seed 5,4 giây (không tính vào thời gian thao tác).

| Thao tác | Thời gian |
|---|---:|
| Đăng nhập, gồm bcrypt | 181 ms |
| Danh sách máy | 3 ms |
| Tìm khách tên / SĐT | 12 / 12 ms |
| Nạp tiền / lịch sử | 3 / 2 ms |
| Preview / mở phiên | 2 / 3 ms |
| Preview / hoàn tất checkout | 2 / 5 ms |
| Hóa đơn hôm nay / 30 ngày / từ khóa | 13 / 203 / 58 ms |
| Chi tiết hóa đơn | 2 ms |
| Doanh thu 30 / 90 ngày | 22 / 37 ms |

Cả **18 thao tác dưới 2 giây** trong lần đo này. EXPLAIN 20 SELECT khác nhau có sáu dòng
full scan/filesort cần theo dõi: máy chỉ 60 dòng, lịch sử sau JOIN, hóa đơn theo khoảng ngày,
group doanh thu. Không thêm index khi chưa có bằng chứng cải thiện. Kết quả này không phải
cam kết độ trễ production/nhiều cửa hàng. Đã kiểm tra không còn store thuộc namespace benchmark sau cleanup.

## Đối chiếu từng mã task

“Đạt tự động” nghĩa là đã có implementation và bằng chứng chạy được trong đợt này,
không tự thay trạng thái Linear hoặc chứng nhận nghiệm thu thủ công.

| Mã | Tình trạng implementation / kiểm thử | Evidence chính hoặc phần còn lại |
|---|---|---|
| HA-01 | Đạt tự động | Package import, môi trường mới, README/setup |
| HA-02 | Đạt tự động | Migration MySQL 8.4; PK/FK/UNIQUE/CHECK; generated unique active session |
| HA-03 | Đạt tự động | Migration/seed, test harness và dữ liệu demo; seed không reset dữ liệu đã có |
| HA-04 | Đạt tự động | `test_transaction_manager`, `test_li10_transaction`: rollback, giữ lỗi gốc, trả connection |
| HA-05 | Đạt tự động | `test_ha05_auth_repository`, actor active/store/role ở service thật |
| HA-06 | Đạt tự động | `test_ha06_repositories`, customer/wallet flow |
| HA-07 | Đạt tự động | `test_ha07_repositories`, quản lý máy/mở phiên/khóa chống trùng |
| HA-08 | Đạt tự động | Checkout/report repository tests; PAID, local date, một phiên một hóa đơn |
| HA-09 | Đạt benchmark + đóng gói Python/web | Còn xác nhận máy Windows sạch/DPI và môi trường triển khai đích |
| HA-10 | Đạt tự động | ERD, dictionary, `test_ha10_data_dictionary`; sửa schema phải sinh lại tài liệu |
| HA-11 | Đạt tự động | `test_login_view`, `test_ha11_app`, `test_ha11_login`; UI review Windows còn cần ký |
| LI-01 | Đạt tự động | `test_domain_models`, DTO/enums/errors và kiểm tra kiến trúc |
| LI-02 | Đạt tự động | Nhóm `test_mock_*`, contracts dùng chung |
| LI-03 | Đạt tự động | Auth/customer service và flow thật, active actor, phân quyền |
| LI-04 | Đạt tự động | Wallet tests: tiền hợp lệ, CASH/TRANSFER, rollback, nhân viên thực hiện |
| LI-05 | Đạt tự động | Machine tests: role/store, snapshot giá, maintenance/archive |
| LI-06 | Đạt tự động | Session/open tests: minimum balance, phút/phí, chống trùng, rollback |
| LI-07 | Đạt tự động | Checkout tests: tiền bù đúng số thiếu, không phải tiền khách đưa; receipt, atomicity |
| LI-08 | Đạt tự động | Report tests: khoảng ngày VN, PAID, scope cửa hàng, consistency invoice |
| LI-09 | Automated đạt; manual chưa ký | 1.164 test; cần điền người/ngày/evidence trong checklist AC-01…24 |
| LI-10 | Đạt tự động | Mapping sáu service, retry 1213, log/rollback và HTTP 503 an toàn |
| NG-01 | Code/component tests đạt | Theme/logo/font/catalog; DPI Windows cần kiểm tra thủ công |
| NG-02 | Code/UI tests đạt | Login ↔ AppShell, role menu, logout; giữ giao diện develop |
| NG-03 | Code/UI tests đạt | Dashboard/machine management; cần ký manual layout/DPI |
| NG-04 | Code/UI tests đạt | Customer/top-up; browser kiểm tra nạp tài khoản khóa đúng rule |
| NG-05 | Code/UI tests đạt | Preview/open; CTA top-up và quay lại preview đã chạy trên browser |
| NG-06 | Code/UI tests đạt | Checkout/receipt; cash/change và TRANSFER thủ công, không tích hợp ngân hàng |
| NG-07 | Code/UI tests đạt | Invoice/revenue, filter, chart hiện có, VI/EN; không đổi theme |
| NG-08 | Automated integration đạt | Error/loading/empty, keyboard/localization tests; manual sweep Windows còn cần ký |
| NG-09 | Có script demo và screenshot | Tài liệu demo đã cập nhật; còn quay video/rehearsal trên bản release được nhóm chọn |

## Công việc còn lại để chốt nghiệm thu toàn bộ

1. Chạy [checklist thủ công](../../tests/manual/CHECKLIST.md) trên Windows với database demo riêng,
   xác nhận DPI 100%/125%/150%, resize, bàn phím và mất/kết nối lại MySQL. Điền đúng kết quả thật.
2. Quay video theo [NG09_DEMO_UI.md](../demo/NG09_DEMO_UI.md), gắn link/evidence vào LI-09/NG-09.
3. Chỉ chuyển các task cần manual sang Done sau khi có bằng chứng và người review.
   Bộ test và bản web demo không chứng minh kết quả Windows hoặc triển khai production.
4. Các PR UI cũ #17–#21 không được nhập trong đợt này. Nếu lấy thêm tính năng từ đó,
   phải đối chiếu từng phần với UI hiện tại, tránh thay ngược layout/login đã thống nhất.

## Chạy lại

```powershell
python -m pip install -e ".[web,dev]"
docker compose up -d mysql
python scripts/prepare_test_db.py
python -m pytest -q
```

Desktop: `python -m cyberhub_manager.app --mock` (hoặc bỏ `--mock` để dùng MySQL đã migrate/seed).
Web: `python -m cyberhub_manager.web --port 8000`. Hai bản dùng cùng service nghiệp vụ;
demo memory và MySQL thật là hai chế độ riêng.
