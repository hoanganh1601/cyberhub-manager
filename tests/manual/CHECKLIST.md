# Manual acceptance checklist — P0

<!-- LI-09: Linh điều phối và xác nhận kết quả; Ngát cung cấp screenshot/evidence UI;
Hoàng Anh hỗ trợ database/repository và kiểm tra release. -->

- Người thực hiện:
- Ngày thực hiện:
- Commit/SHA:
- Branch:
- Python version:
- MySQL version:
- Hệ điều hành:
- Database test:
- Kết quả tổng thể: PASS / FAIL

## Chuẩn bị

Checklist kiểm tra **ứng dụng thật** nên dùng database ứng dụng `cyberhub_manager`
với dữ liệu demo, không dùng `cyberhub_manager_test` của automated test. Không chạy
trên database đang có dữ liệu cần giữ.

```powershell
docker compose up -d mysql
python -c "from scripts.init_db import run_migrations; run_migrations()"
python -c "from scripts.seed_db import run_seed; run_seed(expected_database='cyberhub_manager')"
cyberhub-manager
```

Dữ liệu demo sau khi seed:

| Dữ liệu | Giá trị |
|---|---|
| Quản lý | `demo.manager` |
| Nhân viên | `demo.staff01`, `demo.staff02` |
| Khách hàng | `DEMO_CUS_01` đến `DEMO_CUS_05`, số dư ban đầu 0đ |
| Máy | `DEMO_PC_01` đến `DEMO_PC_20`, đơn giá 10.000đ/giờ |
| Số dư tối thiểu để mở phiên | 5.000đ (đủ 30 phút theo SES-01) |
| Mật khẩu | Mật khẩu demo nhập khi chạy seed |

Quy ước ghi kết quả:

- Lưu evidence tại `docs/screenshots/li09/`, tên file theo mã `AC-XX`.
- Trạng thái FAIL phải có bug: ghi mã bug, mức độ và owner vào mục Ghi chú, đồng
  thời ghi vào mục Bug còn tồn tại của `docs/testing/LI09_TEST_REPORT.md`.
- Ngôn ngữ đúng theo `docs/03_UI_THEME.md` mục Quy chuẩn ngôn ngữ hiển thị.

---

## Đăng nhập

### AC-01 — Đăng nhập thành công

- Người thực hiện:
- Điều kiện ban đầu: Ứng dụng đang ở màn hình đăng nhập.
- Các bước thực hiện:
  1. Nhập `demo.manager` và mật khẩu demo.
  2. Bấm Enter hoặc nút đăng nhập.
- Kết quả mong đợi: Vào App Shell; header hiển thị tên cửa hàng, họ tên nhân viên và badge `MANAGER`; sidebar có menu Quản lý máy.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-02 — Đăng nhập thất bại

- Người thực hiện:
- Điều kiện ban đầu: Ứng dụng đang ở màn hình đăng nhập.
- Các bước thực hiện:
  1. Nhập username đúng, mật khẩu sai.
  2. Nhập username không tồn tại.
  3. Để trống username hoặc mật khẩu.
- Kết quả mong đợi: Ở lại màn hình đăng nhập. Hai trường hợp đầu hiện cùng một thông báo, không tiết lộ username có tồn tại hay không. Không có traceback.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-03 — Phân quyền theo vai trò STAFF

- Người thực hiện:
- Điều kiện ban đầu: Đăng xuất, đăng nhập bằng `demo.staff01`.
- Các bước thực hiện:
  1. Xem sidebar và header.
  2. Mở màn hình Khách hàng, chọn một khách.
  3. Tìm trên Dashboard một máy đang bảo trì (nếu có).
- Kết quả mong đợi: Badge `STAFF`; không có menu Quản lý máy; không có nút Khóa/Mở khóa khách; máy bảo trì chỉ có nhãn, không có nút bật lại.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

---

## Khách hàng

### AC-04 — Tạo khách hàng

- Người thực hiện:
- Điều kiện ban đầu: Đã đăng nhập, đang ở màn hình Khách hàng.
- Các bước thực hiện:
  1. Bấm Tạo khách hàng.
  2. Nhập họ tên, SĐT, username, mật khẩu hợp lệ và chưa ai dùng.
  3. Xác nhận.
- Kết quả mong đợi: Khách mới xuất hiện trong danh sách với số dư 0đ, trạng thái hoạt động; có Toast thành công.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-05 — Sửa khách hàng

- Người thực hiện:
- Điều kiện ban đầu: Đã có khách hàng từ AC-04.
- Các bước thực hiện:
  1. Mở form sửa của khách đó.
  2. Đổi họ tên và SĐT.
  3. Xác nhận, rồi tìm lại khách bằng SĐT mới.
- Kết quả mong đợi: Thông tin mới được lưu và tìm thấy bằng SĐT mới; số dư không đổi.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-06 — Validation từng field quan trọng

- Người thực hiện:
- Điều kiện ban đầu: Mở form Tạo khách hàng.
- Các bước thực hiện:
  1. Họ tên 1 ký tự.
  2. SĐT không đủ 10 số hoặc không bắt đầu bằng 0.
  3. Username dưới 4 ký tự hoặc có dấu cách.
  4. Mật khẩu dưới 6 ký tự.
  5. SĐT đã có người dùng; username đã có người dùng.
- Kết quả mong đợi: Lỗi hiện đúng tại từng trường bằng tiếng Anh; giá trị đã nhập được giữ nguyên; form không đóng; không tạo khách mới.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-07 — Khóa và mở khóa khách hàng

- Người thực hiện:
- Điều kiện ban đầu: Đăng nhập `demo.manager`; khách không có phiên đang chạy.
- Các bước thực hiện:
  1. Chọn khách, bấm Khóa và xác nhận.
  2. Thử mở phiên cho khách đó.
  3. Bấm Mở khóa và xác nhận, rồi thử mở phiên lại.
- Kết quả mong đợi: Khi khóa, khách và tài khoản cùng chuyển trạng thái, và không mở phiên được. Sau khi mở khóa, mở phiên lại được (nếu đủ số dư).
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

---

## Ví

### AC-08 — Nạp tiền và xem lịch sử

- Người thực hiện:
- Điều kiện ban đầu: Khách `DEMO_CUS_01`, số dư 0đ.
- Các bước thực hiện:
  1. Nạp 50.000đ bằng tiền mặt.
  2. Nạp 20.000đ bằng chuyển khoản.
  3. Mở lịch sử giao dịch.
  4. Thử nạp số tiền 0 hoặc số âm.
- Kết quả mong đợi: Số dư 70.000đ; lịch sử có 2 giao dịch mới nhất trước, đúng số tiền, phương thức, tên nhân viên; số tiền không hợp lệ bị báo lỗi và số dư không đổi.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

---

## Quản lý máy

### AC-09 — Thêm, sửa và ngừng sử dụng máy

- Người thực hiện:
- Điều kiện ban đầu: Đăng nhập `demo.manager`, mở Quản lý máy.
- Các bước thực hiện:
  1. Thêm máy mới với mã chưa dùng.
  2. Thêm máy trùng mã đã có.
  3. Sửa tên và đơn giá máy vừa tạo.
  4. Archive máy vừa tạo (chưa có lịch sử).
  5. Archive một máy đã có lịch sử phiên.
  6. Archive một máy đang có phiên.
- Kết quả mong đợi: Bước 2 báo trùng mã tại trường. Bước 4 xóa máy. Bước 5 chỉ ngừng sử dụng, lịch sử giữ nguyên. Bước 6 bị từ chối.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-10 — Trạng thái bảo trì

- Người thực hiện:
- Điều kiện ban đầu: Đăng nhập `demo.manager`; có một máy AVAILABLE và một máy IN_USE.
- Các bước thực hiện:
  1. Bật bảo trì máy AVAILABLE.
  2. Thử mở phiên trên máy đó.
  3. Thử bật bảo trì máy IN_USE.
  4. Bật lại máy bảo trì.
- Kết quả mong đợi: Máy bảo trì không mở phiên được; máy IN_USE không vào bảo trì được; sau khi bật lại, máy trở về AVAILABLE.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

---

## Phiên sử dụng

### AC-11 — Mở phiên thành công

- Người thực hiện:
- Điều kiện ban đầu: Khách có số dư từ 5.000đ trở lên; máy AVAILABLE, đơn giá 10.000đ/giờ.
- Các bước thực hiện:
  1. Trên Dashboard, bấm Mở máy.
  2. Chọn khách, xem preview.
  3. Bấm Xác nhận mở.
- Kết quả mong đợi: Preview hiện số dư và số phút ước tính `floor(số dư × 60 / đơn giá)`. Sau khi mở, card chuyển IN_USE, hiện tên khách và giờ bắt đầu. Số dư chưa bị trừ.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-12 — Không đủ số dư

- Người thực hiện:
- Điều kiện ban đầu: Khách có số dư 4.999đ hoặc thấp hơn.
- Các bước thực hiện:
  1. Mở dialog Mở máy và chọn khách đó.
  2. Nạp thêm tiền theo số tiền được gợi ý.
  3. Xem lại preview.
- Kết quả mong đợi: Ban đầu không xác nhận mở được và có hiển thị số tiền cần nạp. Sau khi nạp đủ thì mở được.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-13 — Trùng active session

- Người thực hiện:
- Điều kiện ban đầu: Khách A đang có phiên trên máy 1. Mở ứng dụng trên hai cửa sổ hoặc hai máy nếu có thể.
- Các bước thực hiện:
  1. Thử mở phiên khác cho khách A trên máy 2.
  2. Ở cửa sổ thứ hai, thử mở máy 1 cho khách B khi dashboard chưa kịp refresh.
- Kết quả mong đợi: Cả hai bị từ chối với thông báo thân thiện; dashboard refresh đúng trạng thái; không có hai phiên ACTIVE.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-14 — Live estimate

- Người thực hiện:
- Điều kiện ban đầu: Có máy đang IN_USE; khách có số dư thấp.
- Các bước thực hiện:
  1. Quan sát card máy qua vài lần refresh.
  2. Đổi đơn giá máy (Quản lý máy) trong khi phiên đang chạy.
  3. Đợi tới khi chi phí tạm tính vượt số dư.
- Kết quả mong đợi: Thời lượng và số dư ước tính cập nhật; đổi đơn giá không làm đổi chi phí phiên đang chạy; số dư ước tính âm thì card cảnh báo đỏ nhưng phiên không tự kết thúc.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

---

## Checkout và hóa đơn

### AC-15 — Checkout đủ số dư

- Người thực hiện:
- Điều kiện ban đầu: Máy IN_USE, số dư lớn hơn chi phí.
- Các bước thực hiện:
  1. Bấm Checkout, xem preview.
  2. Xác nhận.
- Kết quả mong đợi: Preview hiện thời lượng, số phút tính phí, phí và số dư sau. Không yêu cầu bù tiền. Sau khi xác nhận: số dư bị trừ đúng phí, máy về AVAILABLE, hiện hóa đơn.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-16 — Checkout cần thanh toán bổ sung

- Người thực hiện:
- Điều kiện ban đầu: Máy IN_USE, chi phí đã vượt số dư (dùng phiên ở AC-14).
- Các bước thực hiện:
  1. Bấm Checkout, xem số tiền cần bù.
  2. Nhập số tiền nhỏ hơn số cần bù và xác nhận.
  3. Nhập số tiền lớn hơn phí phiên và xác nhận.
  4. Nhập đúng số cần bù và xác nhận.
- Kết quả mong đợi: Bước 2 và 3 bị từ chối, phiên vẫn chạy, dữ liệu không đổi. Bước 4 hoàn tất, số dư còn 0đ.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-17 — Thanh toán tiền mặt và chuyển khoản

- Người thực hiện:
- Điều kiện ban đầu: Hai phiên cần bù tiền.
- Các bước thực hiện:
  1. Checkout phiên thứ nhất, bù bằng tiền mặt.
  2. Checkout phiên thứ hai, bù bằng chuyển khoản.
  3. Xem lịch sử giao dịch của từng khách.
- Kết quả mong đợi: Chỉ có hai phương thức tiền mặt và chuyển khoản để chọn. Lịch sử có giao dịch bù đúng phương thức và giao dịch trừ phí. Tiền thừa do UI tính không được ghi vào hóa đơn.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-18 — Hóa đơn sau checkout

- Người thực hiện:
- Điều kiện ban đầu: Vừa checkout xong.
- Các bước thực hiện:
  1. Xem biên lai sau checkout.
  2. Mở màn hình Hóa đơn, lọc theo ngày, theo mã hóa đơn.
  3. Mở chi tiết hóa đơn đó.
- Kết quả mong đợi: Biên lai có mã hóa đơn, máy, khách, thời gian, số phút, phí, số dư còn lại. Danh sách có đúng một hóa đơn cho phiên, mới nhất trước. Chi tiết khớp biên lai.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

---

## Báo cáo

### AC-19 — Báo cáo doanh thu

- Người thực hiện:
- Điều kiện ban đầu: Có hóa đơn trong hôm nay; biết tổng phí của các hóa đơn PAID.
- Các bước thực hiện:
  1. Mở Doanh thu, chọn khoảng ngày có hôm nay.
  2. Chọn khoảng ngày không có hóa đơn.
  3. Chọn ngày bắt đầu sau ngày kết thúc.
  4. Hoàng Anh chuyển một hóa đơn sang VOID trong database rồi tải lại báo cáo.
- Kết quả mong đợi: Bước 1 đúng tổng và số hóa đơn. Bước 2 hiện trạng thái rỗng, tổng 0. Bước 3 báo lỗi tại trường ngày. Bước 4 doanh thu giảm đúng hóa đơn VOID.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

---

## Trạng thái UI và độ an toàn

### AC-20 — Empty, loading và error state

- Người thực hiện:
- Điều kiện ban đầu: Đã đăng nhập.
- Các bước thực hiện:
  1. Tìm khách với từ khóa không có kết quả.
  2. Lọc hóa đơn theo khoảng ngày không có dữ liệu.
  3. Quan sát màn hình khi đang tải dữ liệu.
  4. Tắt MySQL (`docker compose stop mysql`) rồi mở lại một màn hình.
- Kết quả mong đợi: Bước 1 và 2 hiện `No matching data found`. Bước 3 hiện `Loading data…`, action phụ thuộc dữ liệu bị disable. Bước 4 hiện `Unable to load data` và nút `Retry`.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-21 — Retry sau service error

- Người thực hiện:
- Điều kiện ban đầu: Đang ở trạng thái lỗi của AC-20, MySQL đang tắt.
- Các bước thực hiện:
  1. Bấm `Retry` khi MySQL vẫn tắt.
  2. Bật lại MySQL (`docker compose start mysql`), đợi `healthy`.
  3. Bấm `Retry`.
- Kết quả mong đợi: Bước 1 vẫn hiện lỗi, ứng dụng không treo hay thoát. Bước 3 dữ liệu tải lại bình thường, không cần khởi động lại ứng dụng.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-22 — Không lộ raw exception hoặc traceback

- Người thực hiện:
- Điều kiện ban đầu: MySQL đang tắt hoặc thao tác gặp lỗi nghiệp vụ.
- Các bước thực hiện:
  1. Tắt MySQL rồi thực hiện đăng nhập, nạp tiền, mở phiên, checkout.
  2. Quan sát mọi Toast và dialog.
- Kết quả mong đợi: Chỉ có thông báo thân thiện. Không có mã lỗi MySQL, câu SQL, tên bảng, đường dẫn file hay traceback trên giao diện.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-23 — Busy/disabled state chặn double click

- Người thực hiện:
- Điều kiện ban đầu: Có máy AVAILABLE và khách đủ số dư.
- Các bước thực hiện:
  1. Bấm liên tục nút Xác nhận mở.
  2. Bấm liên tục nút xác nhận Checkout.
  3. Bấm liên tục nút xác nhận nạp tiền.
- Kết quả mong đợi: Khi đang xử lý, nút hiện `Processing…` và bị disable. Chỉ có một phiên, một hóa đơn, một giao dịch nạp được tạo. Nút trở lại bình thường sau cả thành công lẫn thất bại.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:

### AC-24 — Hiển thị đúng ngôn ngữ quy định

- Người thực hiện:
- Điều kiện ban đầu: Đã đăng nhập; xem lần lượt các màn hình.
- Các bước thực hiện:
  1. Kiểm tra tiêu đề màn hình, nhãn trường, placeholder, tiêu đề cột, sidebar.
  2. Kiểm tra Toast, nút `Confirm`/`Cancel`, các trạng thái ViewState, lỗi nghiệp vụ và lỗi từng trường.
- Kết quả mong đợi: Bước 1 hiển thị tiếng Việt. Bước 2 hiển thị tiếng Anh, đúng `docs/03_UI_THEME.md`. Không có chuỗi lỗi tiếng Việt từ service lọt lên Toast.
- Kết quả thực tế:
- Trạng thái: PASS / FAIL
- Evidence:
- Ghi chú/bug liên quan:
