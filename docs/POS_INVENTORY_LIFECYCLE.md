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
và sổ ghi nhận. Một đơn `NEW` chưa xử lý giữ nguyên chỗ cho tới khi nhân viên hủy;
cần hiển thị cảnh báo đơn chờ quá lâu. Chính sách tự hủy theo thời gian sẽ được chốt
khi có cơ chế gửi thông báo và tác vụ nền, tránh tự ý hủy đơn khách chưa được báo.
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

P0/P1 hiện chỉ có `STAFF`, `MANAGER`, `ADMIN`. Tiếp tục dùng ba role này, nhưng kiểm
tra **từng quyền tại backend** bằng actor ACTIVE đọc lại từ DB. Mọi thao tác chỉ trong
cửa hàng được phân công; `ADMIN` muốn thao tác cửa hàng khác phải chọn cửa hàng rõ
ràng và hệ thống kiểm tra quyền. Việc ẩn nút chỉ là hỗ trợ giao diện.

| Thao tác hiện có | STAFF | MANAGER | ADMIN |
|---|:---:|:---:|:---:|
| Xem đơn, chuẩn bị, phục vụ, hủy đơn chưa phục vụ, thu tiền | ✓ | ✓ | ✓ |
| Xem tồn khả dụng và cảnh báo hết nguyên liệu | ✓ | ✓ | ✓ |
| Tạo nguyên liệu và sửa công thức |  | ✓ | ✓ |
| Nhập kho |  | ✓ | ✓ |
| Đề xuất kiểm kê | ✓ | ✓ | ✓ |
| Xuất/trả thủ công và duyệt kiểm kê người khác |  | ✓ | ✓ |
| Xem báo cáo doanh thu POS |  | ✓ | ✓ |
| Quản lý nhiều cửa hàng và phân quyền |  |  | ✓ |

STAFF có quyền gửi phiếu kiểm kê; MANAGER/ADMIN có quyền xuất/trả kho và duyệt
phiếu của người khác. Ngưỡng cảnh báo được cấu hình lúc tạo nguyên liệu.

Năm quyền POS (`POS_VIEW_ORDERS`, `POS_PREPARE_ORDERS`, `POS_SERVE_ORDERS`,
`POS_CANCEL_ORDERS`, `POS_COLLECT_PAYMENT`) được kiểm tra riêng tại service.
Kho dùng `INVENTORY_VIEW` để xem, `INVENTORY_CONFIGURE` để tạo nguyên liệu
và sửa công thức, `INVENTORY_RECEIVE` để nhập kho, `INVENTORY_ISSUE` để xuất/trả,
`INVENTORY_COUNT` để đề xuất và `INVENTORY_APPROVE` để duyệt. UI chỉ hiện thao tác
tương ứng với quyền mà service trả về; service luôn kiểm tra actor ACTIVE và store.
Khi thật sự có người bếp hoặc thủ kho làm việc riêng, thêm
`KITCHEN`/`INVENTORY` bằng migration
role, cấp từng quyền rõ ràng và test backend; không gán hai role này cho tài
khoản hiện tại trước.

## 5. Thông báo và khuyến mãi liên quan

- Mỗi trạng thái `NEW`, `PREPARING`, `SERVED`, `PAID`, `CANCELLED` ghi một sự kiện
  bền vững vào `customer_notification_events` trong cùng transaction với đơn. Khóa
  `menu-order:{order_id}:{status}` khiến retry không tạo thông báo trùng. Portal đọc
  sổ sự kiện sau commit; lỗi hiển thị hoặc đánh dấu đã đọc không làm rollback POS.
  Số tiền hiển thị là tiền thực trả sau giảm giá. Dispatcher email/push bên ngoài
  (nếu bổ sung) phải đọc sổ này và tự retry, không gửi trực tiếp trong transaction.
- Nếu thiếu hàng lúc khách đặt, trả lỗi ngay cho khách. Nếu thiếu do dữ liệu cũ hoặc
  điều chỉnh bất thường, nhân viên phải hủy hoặc xử lý thay món và thông báo khách;
  không chuyển đơn sang `PREPARING` với tồn âm.
- Voucher, combo và mua tặng phải chốt giá, công thức, số lượng tặng và điều kiện
  ở thời điểm nhận đơn; chỉ ghi doanh thu khi `PAID`. Quy tắc cộng gộp ưu đãi sẽ
  được đặc tả riêng trước khi triển khai khuyến mãi món.

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
