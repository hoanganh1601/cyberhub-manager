# Chốt nghiệp vụ tồn kho và quyền POS

Trạng thái: **đã có lõi kho theo đơn trong MySQL** qua migration `013_inventory.sql`
và phiếu kiểm kê qua `014_inventory_counting.sql`:
nguyên liệu, công thức, snapshot, giữ chỗ, xuất dùng, giải phóng và sổ biến động.
Màn Menu cho quản lý tạo nguyên liệu, nhập kho và cấu hình công thức; STAFF xem tồn.
API xem kho chỉ trả công thức và cấu hình theo dõi tồn cho MANAGER/ADMIN.
Màn Menu cho STAFF đề xuất kiểm kê; MANAGER/ADMIN duyệt hoặc từ chối phiếu của
người khác, xuất/trả thủ công. Thông báo khách và khuyến mãi món là bước tiếp theo.
Demo bộ nhớ không mô phỏng sổ kho.

## 1. Số lượng và phạm vi

- Mỗi nguyên liệu thuộc **một cửa hàng** và có đơn vị gốc cố định (g, ml hoặc cái).
  Số lượng dùng số nguyên theo đơn vị gốc; không đổi đơn vị bằng số thực khi giao dịch.
- `on_hand` là lượng thực có thể xuất; `reserved` là lượng đã giữ cho đơn `NEW`;
  `available = on_hand - reserved`. Không cho `on_hand < 0`, `reserved < 0` hoặc
  `reserved > on_hand`.
- Công thức món định nghĩa lượng nguyên liệu cho một suất. Khi nhận đơn, lưu **snapshot
  công thức** theo từng dòng món; sửa công thức sau đó không đổi lượng của đơn cũ.
- Món chưa được cấu hình quản lý kho tiếp tục dùng cờ còn/hết thủ công trong giai đoạn
  chuyển tiếp. Món đã bật quản lý kho phải có công thức hợp lệ; cờ thủ công không được
  vượt qua kiểm tra thiếu nguyên liệu. Combo và món tặng áp dụng cùng quy tắc.

## 2. Vòng đời đơn và tồn kho

| Chuyển trạng thái | Tồn kho | Kết quả khi thiếu hoặc lỗi |
|---|---|---|
| Tạo `NEW` | Kiểm tra `available` của toàn bộ nguyên liệu; giữ chỗ đúng lượng từ snapshot trong cùng transaction tạo đơn. | Không tạo đơn, không giữ một phần. Trả tên món thiếu và yêu cầu chọn món khác. |
| `NEW → PREPARING` | Chuyển lượng đã giữ thành xuất dùng: giảm đồng thời `reserved` và `on_hand`, ghi sổ `CONSUME`. | Giữ nguyên `NEW`; không xuất một phần. |
| `NEW → SERVED` | Đường tắt hiện có: thực hiện cùng bước xuất dùng như khi bắt đầu chuẩn bị, rồi chuyển trạng thái. | Giữ nguyên `NEW`. |
| `PREPARING → SERVED` | Không đụng tồn lần hai. | Giữ nguyên `PREPARING` nếu cập nhật thất bại. |
| `NEW → CANCELLED` | Giải phóng lượng giữ chỗ, ghi `RELEASE`. | Rollback toàn bộ việc hủy. |
| `PREPARING → CANCELLED` | Nguyên liệu đã dùng **không** tự cộng lại. Ghi nhận lý do hủy và hao hụt; nguyên liệu thật sự còn dùng được phải nhập trả bằng giao dịch riêng. | Rollback toàn bộ việc hủy nếu ghi nhận không thành công. |
| `SERVED → PAID` | Chỉ thu tiền và ghi nhận doanh thu; **không trừ kho lần nữa**. | Đơn vẫn `SERVED` nếu thanh toán không thành công. |

`PAID` và `CANCELLED` là trạng thái cuối. Đơn `SERVED` không được hủy trong luồng P0/POS
hiện tại; hoàn tiền hoặc trả món sau phục vụ cần một nghiệp vụ đảo riêng, có phê duyệt
và sổ ghi nhận. Đơn `NEW` mới có thời hạn giữ tồn và worker xử lý như mục 7.
Lý do hủy được lưu trên đơn kể cả khi món chưa theo dõi kho; hủy sau chuẩn bị bắt buộc
có lý do, còn hủy trước chuẩn bị có thể để trống.

## 3. Giao dịch, sổ kho và kiểm kê

1. Nhập kho tăng `on_hand`; ghi số chứng từ, người nhập, đơn vị, số lượng và ghi chú.
   Gửi lại cùng khóa yêu cầu không nhập hai lần. Xuất kho thủ công và trả hàng
   cũng dùng giao dịch, chứng từ, khóa yêu cầu và sổ kho; không sửa trực tiếp số dư.
2. Mỗi thay đổi kho có một bút toán bất biến: `RECEIVE`, `RESERVE`, `RELEASE`,
   `CONSUME`, `WASTE`, `ISSUE`, `RETURN`, `ADJUST`. Mỗi bút toán gắn cửa hàng, nguyên liệu,
   đơn (nếu có), nhân viên, thời gian và khóa idempotency duy nhất.
   `WASTE` sau `CONSUME` chỉ phân loại phần đã xuất là hao hụt, có biến động
   tồn bằng 0; không trừ `on_hand` thêm lần nữa.
3. Khóa các dòng nguyên liệu theo **ID tăng dần** trong transaction MySQL; kiểm tra
   đủ `available` rồi cập nhật có điều kiện. Tạo đơn, đổi trạng thái, giữ/giải phóng/
   tiêu hao và ghi sổ phải cùng commit hoặc cùng rollback. Yêu cầu gửi lại hoặc hai
   nhân viên xử lý đồng thời không được tạo hai lần bút toán.
4. Kiểm kê ghi số đếm thực tế, tồn và bút toán tại lúc đề xuất, cùng người đề xuất.
   MANAGER/ADMIN khác người đề xuất mới được duyệt. Nếu có bất kỳ giao dịch kho nào
   sau lúc đề xuất, phiếu cũ không được duyệt và phải kiểm kê lại. Duyệt mới cập
   nhật `on_hand` và ghi `ADJUST` khi có chênh lệch; từ chối không đổi tồn. Mọi
   quyết định có người duyệt và audit; không xóa sổ kho.
5. Cảnh báo sắp hết khi `available <= reorder_point` của cửa hàng. Mọi điều chỉnh
   vẫn phải giữ `reserved <= on_hand`; không cho điều chỉnh âm làm mất hàng đã giữ.
6. Với đơn cũ tạo trước khi triển khai giữ chỗ: lúc bắt đầu chuẩn bị phải kiểm tra
   và xuất kho nguyên tử theo công thức snapshot tương ứng, hoặc đánh dấu là
   `legacy_untracked` nếu không có snapshot. Không tự suy diễn lượng tiêu hao từ
   công thức hiện tại và không ghi xuất kho giả.

## 4. Quyền và phạm vi

P0/P1 ban đầu có `STAFF`, `MANAGER`, `ADMIN`; nay thêm `KITCHEN` và `INVENTORY` nhưng kiểm
tra **từng quyền tại backend** bằng actor ACTIVE đọc lại từ DB. Mọi thao tác chỉ trong
cửa hàng được phân công; `ADMIN` muốn thao tác cửa hàng khác phải chọn cửa hàng rõ
ràng và hệ thống kiểm tra quyền. Việc ẩn nút chỉ là hỗ trợ giao diện.

| Thao tác | STAFF | KITCHEN | INVENTORY | MANAGER | ADMIN |
|---|:---:|:---:|:---:|:---:|:---:|
| Xem đơn | ✓ | ✓ | ✓ | ✓ | ✓ |
| Chuẩn bị và phục vụ | ✓ | ✓ |  | ✓ | ✓ |
| Hủy đơn trước phục vụ và thu tiền | ✓ |  |  | ✓ | ✓ |
| Đề xuất hủy/hoàn sau phục vụ | ✓ |  |  | ✓ | ✓ |
| Duyệt đề xuất của người khác |  |  |  | ✓ | ✓ |
| Xem tồn khả dụng | ✓ | ✓ | ✓ | ✓ | ✓ |
| Tạo nguyên liệu và sửa công thức |  |  | ✓ | ✓ | ✓ |
| Nhập/xuất kho |  |  | ✓ | ✓ | ✓ |
| Đề xuất kiểm kê | ✓ |  | ✓ | ✓ | ✓ |
| Duyệt kiểm kê của người khác |  |  |  | ✓ | ✓ |
| Quản lý khuyến mãi POS |  |  |  | ✓ | ✓ |

STAFF có quyền gửi phiếu kiểm kê; MANAGER/ADMIN có quyền xuất/trả kho và duyệt
phiếu của người khác. Ngưỡng cảnh báo được cấu hình lúc tạo nguyên liệu.

Năm quyền POS (`POS_VIEW_ORDERS`, `POS_PREPARE_ORDERS`, `POS_SERVE_ORDERS`,
`POS_CANCEL_ORDERS`, `POS_COLLECT_PAYMENT`) được kiểm tra riêng tại service.
Kho dùng `INVENTORY_VIEW` để xem, `INVENTORY_CONFIGURE` để tạo nguyên liệu
và sửa công thức, `INVENTORY_RECEIVE` để nhập kho, `INVENTORY_ISSUE` để xuất/trả,
`INVENTORY_COUNT` để đề xuất và `INVENTORY_APPROVE` để duyệt. UI chỉ hiện thao tác
tương ứng với quyền mà service trả về; service luôn kiểm tra actor ACTIVE và store.
`KITCHEN` và `INVENTORY` chỉ được quản trị viên tạo/gán; các tài khoản cũ giữ
nguyên role sau migration.

## 5. Thông báo và khuyến mãi liên quan

- Mỗi trạng thái `NEW`, `PREPARING`, `SERVED`, `PAID`, `CANCELLED` ghi một sự kiện
  bền vững vào `customer_notification_events` trong cùng transaction với đơn. Khóa
  `menu-order:{order_id}:{status}` khiến retry không tạo thông báo trùng. Portal đọc
  sổ sự kiện sau commit; lỗi hiển thị hoặc đánh dấu đã đọc không làm rollback POS.
  Số tiền hiển thị là tiền thực trả sau giảm giá. Dispatcher email/push bên ngoài
  (nếu bổ sung) phải đọc sổ này và tự retry, không gửi trực tiếp trong transaction.
- Nếu món bị tắt/hết lúc đặt, khách nhận lỗi ngay và có một sự kiện cảnh báo riêng
  sau khi giao dịch đặt bị từ chối. Nếu thiếu nguyên liệu, giao dịch đặt bị rollback
  và không được giữ tồn âm.
- Giá ưu đãi được chụp tại lúc nhận đơn. Một đơn chỉ dùng ưu đãi có số tiền giảm
  lớn nhất; voucher có giá trị cao hơn mới thay thế ưu đãi đó.
- Quản lý bật/tắt khuyến mãi bằng nút trên thẻ ưu đãi (migration `020_pos_promotion_history.sql`).
  Ưu đãi đã quá ngày kết thúc không bật lại được; phải sửa ngày kết thúc. Ưu đãi chỉ dài tối đa
  366 ngày, ngày kết thúc phải sau ngày bắt đầu, và ưu đãi đang bật phải kết thúc trong tương lai.
  Giờ lưu UTC và trả về có múi giờ để trình duyệt hiển thị đúng.
- Mỗi lần tạo, sửa, bật hoặc tắt ưu đãi ghi một dòng bất biến vào `menu_promotion_changes`
  (người thực hiện, thời điểm, giá trị cũ và mới); lưu lại y nguyên thì không ghi. Sửa hay tắt ưu đãi
  không đổi đơn đã đặt vì giá nằm trong bản chụp `menu_order_pricing`.
- Trên thẻ ưu đãi, quản lý thấy tổng tiền đã giảm và số đơn đã dùng (đơn hủy/hoàn không tính).
  Trong đơn, nhân viên thấy mã ưu đãi và số tiền giảm; khách thấy báo giá có số tiền giảm ngay trong giỏ
  (`POST /api/portal/menu/quote`, không ghi dữ liệu). Khi đặt, máy chủ tính lại toàn bộ.

## 6. Tiêu chí nghiệm thu hoàn chỉnh

- Hai đơn đồng thời chỉ đặt được tổng lượng không vượt `available`; rollback không
  để lại giữ chỗ hoặc bút toán rời.
- Hủy `NEW` trả chỗ; hủy `PREPARING` ghi hao hụt; `SERVED → PAID` không xuất kho lần hai.
- Một lần retry không nhân đôi giữ chỗ, tiêu hao, nhập kho, thanh toán hoặc thông báo.
- STAFF không gọi được API duyệt điều chỉnh hay sửa công thức dù biết URL;
  MANAGER không thao tác được cửa hàng khác; ADMIN có audit khi thao tác xuyên cửa hàng.

Kiểm thử lõi hiện có kiểm tra snapshot, thiếu hàng, giải phóng, xuất dùng và hao hụt.
Các tiêu chí thông báo và thao tác xuyên cửa hàng cần kiểm thử khi triển khai
các luồng tương ứng. Kiểm kê cần chạy integration test trên MySQL đã áp dụng
`013_inventory.sql` và `014_inventory_counting.sql`.

## 7. Role riêng và thời hạn giữ tồn

Migration `016_pos_roles.sql` cho phép `KITCHEN` và `INVENTORY`. `KITCHEN` chỉ xem,
chuẩn bị, phục vụ đơn và xem tồn; `INVENTORY` xem đơn, cấu hình, nhập, xuất và đề xuất
kiểm kê nhưng không duyệt phiếu, không thu tiền POS. Quyền của `MANAGER` và `ADMIN`
vẫn liệt kê tường minh trong `domain/p1.py`; thêm quyền mới không tự động cấp cho
role nào. Chỉ `ADMIN` được tạo tài khoản role chuyên trách.

Migration `017_pos_hold_timeout.sql` thêm `reservation_expires_at` cho đơn mới.
`CYBERHUB_POS_HOLD_MINUTES` nhận giá trị 5–120, mặc định 15 phút. Đơn cũ có giá trị
`NULL` được giữ nguyên, không tự hủy. Chạy worker riêng:

```powershell
python -m scripts.run_pos_maintenance --interval 30
```

Worker tạo cảnh báo tối đa một lần trong 2 phút trước hạn. Khi quá hạn, worker chỉ
hủy đơn còn `NEW`, giải phóng lượng giữ trong cùng transaction và phát thông báo
cho khách. Đơn `PREPARING` không bị tác động. Có thể chạy `--once` để kiểm tra
một lượt (mã thoát 1 nếu lỗi); chạy lại sau lỗi không giải phóng kho hai lần. Demo không
mô phỏng sổ kho; nghiệm thu số dư và sổ biến động cần MySQL.

Độ bền của worker giữ tồn: mỗi đơn xử lý trong một transaction riêng, nên một đơn lỗi
được rollback, ghi log kèm traceback và đếm vào `failed`; các đơn còn lại trong lô vẫn
được xử lý, đơn lỗi sẽ được thử lại ở lượt sau. Mất kết nối MySQL thì dừng lượt đó. Sau
lỗi, worker chờ `interval × 2^n` (tối đa 300 giây, hoặc `interval` nếu lớn hơn) rồi chạy
lại và về nhịp bình thường khi một lượt thành công. `Ctrl+C`/`SIGTERM` dừng êm sau lượt
đang chạy. Chỉ lượt có việc mới ghi log mức INFO (`warned`, `expired`, `failed`).

## 8. Hủy/hoàn toàn bộ đơn sau phục vụ

Migration `018_pos_reversals.sql` ghi một yêu cầu hủy/hoàn cho mỗi đơn đã `SERVED`
hoặc `PAID`. Người đề xuất phải nhập lý do và chọn `RESTOCK` hoặc `WASTE`.
`MANAGER`/`ADMIN` khác người đề xuất quyết định. Đơn chưa thanh toán chuyển sang
`CANCELLED`; đơn đã thanh toán chỉ chuyển `REFUNDED` sau khi quản lý xác nhận đã
hoàn tiền mặt hoặc chuyển khoản (chuyển khoản cần mã giao dịch). Không có lệnh
chuyển tiền tự động. Số tiền hoàn là toàn bộ số đã thu sau ưu đãi/voucher; voucher đã dùng
không được phát lại tự động. Phiên bản này chưa hỗ trợ hoàn từng món.

Khi duyệt, số lượng nhập trả/hao hụt lấy từ **snapshot công thức của đơn**, trong
cùng transaction với quyết định, đổi trạng thái, audit và thông báo khách. Doanh thu
POS giữ khoản thu tại ngày thanh toán và ghi khoản âm vào ngày duyệt hoàn tiền;
đơn hoàn không còn tính trong danh sách món bán chạy. Mỗi đơn chỉ có một yêu cầu
hủy/hoàn; yêu cầu bị từ chối là kết thúc, cần quy trình quản lý riêng nếu muốn mở lại.

## 9. Khuyến mãi POS và thông báo trong web

Migration `019_pos_promotions.sql` tạo quy tắc theo cơ sở và bảng `menu_order_pricing`.
Quản lý sửa ở **Menu đồ ăn → Khuyến mãi POS**. Ba quy tắc demo đang bật:
giảm 5.000đ mỗi Coca khi đang chơi, mua 3 Coca trả 2, GOLD/PLATINUM giảm 10%.
Đây chỉ là dữ liệu demo; MySQL bắt đầu không có khuyến mãi, quản lý tự tạo trên UI.
Quy tắc không cộng dồn: chọn giảm nhiều tiền nhất; nếu hòa, ưu tiên mua 3 trả 2,
rồi giảm nước, rồi giảm theo hạng. Voucher chỉ thay thế nếu giảm **nhiều hơn**;
voucher kém hơn được giữ lại cho đơn khác. Sổ giá lưu dòng món, giá từng món,
hạng thành viên, quy tắc và tổng trước/sau giảm. Sửa quy tắc không đổi giá đơn cũ.

Thông báo trong web dùng `customer_notification_events` như sổ sự kiện ghi trong
transaction nghiệp vụ với khóa chống trùng. Portal tải lại mỗi 10 giây; đây là
kênh thông báo mặc định.

Kênh ngoài web dùng worker riêng (migration `021_notification_deliveries.sql`):

```powershell
python -m scripts.run_notification_worker --interval 15
```

- Worker đọc sổ sự kiện, tạo một dòng gửi cho mỗi cặp (sự kiện, kênh) trong bảng
  `notification_deliveries` rồi gửi. Sổ sự kiện không bị sửa; POS không biết worker tồn tại.
- Mỗi lượt gồm ba bước độc lập: transaction ngắn "thuê" một lô (`FOR UPDATE SKIP LOCKED`, nên
  chạy nhiều worker không gửi trùng), gọi kênh **ngoài mọi transaction và khóa**, rồi transaction
  ngắn ghi từng kết quả. Một thông báo lỗi không chặn các thông báo khác.
- Giao **ít nhất một lần**: nếu worker chết sau khi gửi mà trước khi ghi kết quả, dòng hết hạn thuê
  (5 phút) và được gửi lại với cùng `idempotency_key` (`notification_key`, ví dụ `menu-order:12:SERVED`);
  bên nhận phải loại trùng theo khóa này.
- Retry có giới hạn: lỗi tạm (mạng, HTTP 408/425/429/5xx) chờ 30s, 60s, 120s... tối đa 1 giờ; sau
  `--max-attempts` (mặc định 6) hoặc lỗi vĩnh viễn (HTTP 4xx khác) thì dòng chuyển `DEAD` và được giữ
  lại để xem, `last_error` lưu lý do ngắn (không lưu nội dung có thể chứa bí mật).
- Chỉ gửi sự kiện trong `--lookback-hours` gần nhất (mặc định 24) để bật kênh mới không xả cả lịch sử.
- Kênh chọn bằng `CYBERHUB_NOTIFY_SINK`: `log` (mặc định, chỉ ghi log) hoặc `webhook` với
  `CYBERHUB_NOTIFY_WEBHOOK_URL` (bắt buộc `https`, riêng `localhost` được dùng `http`; không đi theo
  chuyển hướng) và tùy chọn `CYBERHUB_NOTIFY_WEBHOOK_SECRET`. Có secret thì mỗi yêu cầu kèm
  `X-CyberHub-Timestamp` và `X-CyberHub-Signature: sha256=HMAC(secret, "<timestamp>.<body>")`. Nội dung
  gửi chỉ có mã sự kiện, loại, mã đơn, số tiền, mã tài khoản/cơ sở và thời điểm; không có tên hay số
  điện thoại khách.
- Kiểm tra nhanh: `python -m scripts.run_notification_worker --once` rồi
  `SELECT status, COUNT(*) FROM notification_deliveries GROUP BY status;`. Dòng `DEAD` cần người
  vận hành xem `last_error`; muốn gửi lại, đặt `status='PENDING'`, `attempts=0` cho dòng đó.
Khách thấy các mốc mới, chuẩn bị, phục vụ, thanh toán, hủy/hoàn, sắp hết hạn giữ và
thông báo món vừa hết khi đặt.

## 10. Chạy và nghiệm thu

Áp dụng migration `016`–`021` bằng `python scripts/init_db.py` trên MySQL trước
khi bật chế độ MySQL. Sau đó chạy web và hai worker (`scripts.run_pos_maintenance`,
`scripts.run_notification_worker`) ở các terminal riêng. Worker thông báo không bắt buộc
nếu chỉ dùng thông báo trong web.

Dữ liệu mẫu MySQL (`python scripts/seed_pos_demo.py`) và checklist nghiệm thu cho nhân viên, bếp, thủ kho
và quản lý nằm ở [POS_ACCEPTANCE.md](POS_ACCEPTANCE.md).
Demo hiển thị nhãn "Demo: sổ kho chưa được mô phỏng"; mọi nghiệm thu số dư,
release và bút toán kho dùng MySQL. Không dùng kết quả tồn kho demo để xác nhận
nghiệp vụ thực tế.
