# Nghiệm thu POS và kho trên MySQL

Tài liệu này hướng dẫn nạp dữ liệu mẫu và kiểm tra tay các luồng POS/kho theo từng vai trò.
Quy tắc nghiệp vụ gốc: [POS_INVENTORY_LIFECYCLE.md](POS_INVENTORY_LIFECYCLE.md). Chế độ demo
(bộ nhớ) **không** có sổ kho, nên mọi mục dưới đây cần MySQL.

## 1. Chuẩn bị

```powershell
docker compose up -d mysql
python scripts/init_db.py                  # migration 001–021
python -c "from scripts.seed_db import run_seed; run_seed(expected_database='cyberhub_manager')"  # chỉ nếu chưa có cửa hàng/khách/máy DEMO
python scripts/seed_pos_demo.py            # dữ liệu mẫu POS + kho (hỏi xác nhận)
```

Mật khẩu của hai tài khoản mới (`demo.kitchen`, `demo.inventory`) là mật khẩu demo bạn nhập lúc chạy
script (hoặc biến `CYBERHUB_DEMO_PASSWORD` khi dùng `--yes`). Nên dùng **cùng mật khẩu** với các tài khoản
`seed_db.py` để đăng nhập thuận tiện. Script:

- chạy lại an toàn: phần đã có được bỏ qua (`[SKIP]`), tồn đầu kỳ không nhập hai lần, đơn mẫu (ghi chú
  bắt đầu bằng `DEMO:`) không tạo thêm;
- đi qua service nghiệp vụ nên sổ kho, thông báo, audit khớp thao tác thật;
- từ chối chạy trên `cyberhub_manager_test`;
- `--no-orders` chỉ tạo tài khoản, menu, kho (không mở phiên máy, không tạo đơn).

Chạy web và hai worker ở các terminal riêng:

```powershell
$env:CYBERHUB_WEB_MODE = "mysql"
python -m cyberhub_manager.web --port 8000
python -m scripts.run_pos_maintenance --interval 30
python -m scripts.run_notification_worker --interval 15
```

## 2. Dữ liệu mẫu

Cửa hàng `DEMO_STORE_01`. Mật khẩu: mật khẩu demo.

| Vai trò | Tài khoản | Ghi chú |
|---|---|---|
| Quản lý | `demo.manager` | từ `seed_db.py` |
| Nhân viên | `demo.staff01`, `demo.staff02` | từ `seed_db.py` (dùng `staff01` làm nhân viên quầy) |
| Bếp | `demo.kitchen` | role `KITCHEN`, mới |
| Thủ kho | `demo.inventory` | role `INVENTORY`, mới |
| Khách | `demo.customer01`–`05` | mỗi khách đang ngồi máy `DEMO_PC_01`–`05`, đã nạp 100.000đ |

Đăng nhập khách ở trang khách (`/customer`); nhân viên ở trang đăng nhập nhân viên.

**Menu**

| Món | Giá | Công thức |
|---|---|---|
| Coca | 15.000 | 1 Lon Coca |
| Nước suối | 8.000 | 1 Chai nước suối |
| Cà phê sữa | 25.000 | 20 g Cà phê bột + 30 ml Sữa đặc |
| Mì trứng | 30.000 | 1 Mì gói + 1 Trứng gà |
| Cơm chiên trứng | 40.000 | 250 g Cơm nguội + 1 Trứng gà |
| Xúc xích chiên | 20.000 | 2 Xúc xích |
| Khoai tây chiên | 25.000 | 150 g Khoai tây đông lạnh |

**Tồn đầu kỳ** (ngưỡng cảnh báo trong ngoặc): Lon Coca 48 (12), Chai nước suối 36 (12), Cà phê bột 3000 g
(500), Sữa đặc 450 ml (500), Mì gói 40 (10), Trứng gà 30 (12), Cơm nguội 8000 g (2000), Xúc xích 6 (10),
Khoai tây đông lạnh 0 (1000).

- Sau khi nạp: **Sữa đặc** và **Xúc xích** dưới ngưỡng (cảnh báo sắp hết); **Khoai tây đông lạnh** hết hàng,
  nên **Khoai tây chiên** không đặt được (khách sẽ thấy thông báo món vừa hết).
- Hiện có 5 phiên máy đang chạy (khách chưa thanh toán giờ chơi): đóng phiên bằng luồng thanh toán phiên
  ở máy tính tiền khi muốn dọn.

**Đơn mẫu** (7 đơn, ghi chú bắt đầu bằng `DEMO:`)

| Khách | Đơn | Trạng thái cuối | Dùng để thử |
|---|---|---|---|
| customer01 | 2 Coca + 1 Mì trứng | `NEW` | hàng đợi bếp, bắt đầu chuẩn bị, hủy đơn mới |
| customer02 | 2 Cà phê sữa | `PREPARING` | bếp bấm "Đã phục vụ" |
| customer03 | Cơm chiên + Nước suối | `SERVED` | nhân viên thu tiền |
| customer03 | Xúc xích chiên | `PAID` (tiền mặt) | doanh thu POS, đề xuất hủy/hoàn |
| customer04 | Coca | `CANCELLED` | lý do hủy, giải phóng tồn |
| customer04 | Mì trứng | `PAID` + yêu cầu hoàn **đang chờ** | quản lý duyệt/từ chối hoàn |
| customer05 | 2 Nước suối | `REFUNDED` | hao hụt từ hoàn tiền, doanh thu âm |

MySQL bắt đầu **không có khuyến mãi POS**: quản lý tự tạo ở mục 6 để thử.

## 3. Checklist nhân viên quầy (`demo.staff01`)

- [ ] Menu đồ ăn thấy đủ 7 đơn mẫu; lọc theo trạng thái đúng.
- [ ] Đơn `SERVED` (Cơm chiên) → **Thanh toán** → chọn tiền mặt: chuyển `PAID`; tồn kho **không** bị trừ lần hai.
- [ ] Đơn `NEW` (customer01) → **Hủy**: không cần lý do; `Lon Coca` và `Mì gói` được trả lại `reserved`.
- [ ] Đơn đang `PREPARING` (customer02) → **Hủy**: bắt buộc nhập lý do; nguyên liệu ghi hao hụt (`WASTE`), không tự hoàn kho.
- [ ] Đơn `PAID` → **Đề xuất hủy/hoàn** với lý do ≥ 5 ký tự: tạo yêu cầu chờ duyệt; không tự duyệt được.
- [ ] Không thấy (và gọi API bị từ chối): sửa menu, sửa công thức, duyệt kiểm kê, duyệt hoàn.
- [ ] Đánh dấu một món **hết** rồi **còn** lại: khách thấy trạng thái đổi.

## 4. Checklist bếp (`demo.kitchen`)

- [ ] Đăng nhập chỉ thấy **hàng đợi bếp** (đơn mới + đang chuẩn bị), không thấy tiền, khuyến mãi, doanh thu hay thanh toán.
- [ ] Đơn `NEW` → **Bắt đầu chuẩn bị**: tồn `Lon Coca`/`Mì gói` chuyển từ giữ chỗ sang đã xuất (CONSUME), đơn thành `PREPARING`.
- [ ] Đơn `PREPARING` → **Đã phục vụ**: đơn thành `SERVED`.
- [ ] Có chuông thông báo/toast khi khách vừa đặt đơn mới (đợi tối đa ~10 giây).
- [ ] Không có nút hủy, thanh toán, đề xuất hoàn; gọi API tương ứng trả 403.
- [ ] Chỉ xem được tồn kho (không nhập/xuất).

## 5. Checklist thủ kho (`demo.inventory`)

- [ ] Bảng kho hiển thị 9 nguyên liệu; **Sữa đặc** và **Xúc xích** có cảnh báo sắp hết; **Khoai tây đông lạnh** hết hàng.
- [ ] **Nhập kho** 2000 g Khoai tây đông lạnh với mã phiếu: tồn tăng, có bút toán `RECEIVE`; gửi lại cùng yêu cầu (bấm đúp) không nhập hai lần.
- [ ] Sau khi nhập: khách đặt được Khoai tây chiên; đặt một phần → `reserved` tăng, `available` giảm.
- [ ] **Xuất kho** thủ công một lượng nhỏ Sữa đặc kèm lý do: có bút toán `ISSUE`; không xuất quá lượng khả dụng (không tính phần đang giữ).
- [ ] **Đề xuất kiểm kê** Xúc xích với số đếm khác tồn: tạo phiếu `PENDING`; thủ kho **không** tự duyệt được.
- [ ] Sửa công thức một món (vd. tăng Cà phê bột lên 25 g): đơn mới dùng công thức mới, đơn cũ giữ công thức chụp lúc đặt.
- [ ] Không thấy menu, khuyến mãi, thanh toán; không duyệt được hoàn tiền.

## 6. Checklist quản lý (`demo.manager`)

- [ ] **Duyệt phiếu kiểm kê** của thủ kho: tồn khớp số đếm, có bút toán `ADJUST`; người đề xuất khác người duyệt.
- [ ] **Yêu cầu hoàn** (đơn Mì trứng của customer04): duyệt kèm xác nhận đã hoàn tiền mặt → đơn `REFUNDED`, hao hụt ghi theo lựa chọn, doanh thu POS có khoản âm ngày duyệt. Thử thêm **từ chối** với một yêu cầu khác.
- [ ] **Khuyến mãi POS**: tạo ưu đãi "giảm 5.000đ mỗi Coca khi đang chơi" (ngày bắt đầu trước ngày kết thúc); khách đặt 3 Coca thấy báo giá có giảm trong giỏ; thẻ ưu đãi tăng "số đơn đã dùng" và "tổng đã giảm".
- [ ] Tắt/bật ưu đãi bằng nút: đơn đã đặt trước đó **không** đổi giá; **Lịch sử** ưu đãi ghi người, thời điểm, giá trị cũ/mới.
- [ ] Ngày kết thúc trước ngày bắt đầu bị từ chối bằng thông báo ở trường ngày.
- [ ] **Menu**: thêm món, đổi giá; đơn cũ giữ giá lúc đặt; lịch sử thay đổi món được ghi.
- [ ] **Báo cáo doanh thu POS** khớp: tổng tiền các đơn `PAID` trừ khoản hoàn.
- [ ] Quản lý tạo tài khoản bếp/thủ kho? **Không**: chỉ `ADMIN` được tạo role chuyên trách.

## 7. Checklist khách và thông báo

- [ ] Đăng nhập `demo.customer01` (đang có phiên): đặt món, thấy đơn `NEW`, huy hiệu chuông tăng.
- [ ] Khi bếp/nhân viên đổi trạng thái (chuẩn bị, phục vụ, thanh toán, hủy/hoàn): khách nhận toast trong ~10 giây và thấy trong danh sách; bấm đã đọc làm huy hiệu giảm.
- [ ] Đặt **Khoai tây chiên** khi chưa nhập kho: bị từ chối và có thông báo món vừa hết.
- [ ] Khách chưa có phiên máy không đặt được món.

## 8. Checklist tác vụ nền

- [ ] Đặt `CYBERHUB_POS_HOLD_MINUTES=5` cho worker và web, đặt một đơn mới: trong 2 phút cuối khách nhận thông báo "sắp hết hạn giữ" đúng **một lần**; hết hạn → đơn tự `CANCELLED` (lý do `AUTO_EXPIRED`), `reserved` được trả lại, khách có thông báo.
- [ ] Đơn đang `PREPARING` không bị hủy tự động dù quá hạn.
- [ ] Dừng worker giữ tồn rồi chạy lại: đơn quá hạn xử lý đúng một lần, không trả kho hai lần (`python -m scripts.run_pos_maintenance --once`).
- [ ] `python -m scripts.run_notification_worker --once` rồi `SELECT status, COUNT(*) FROM notification_deliveries GROUP BY status;` có `SENT` và không có `DEAD`.
- [ ] Đặt `CYBERHUB_NOTIFY_SINK=webhook` với URL không tồn tại: dòng chuyển `PENDING` với `last_error`, chờ lâu dần, cuối cùng `DEAD`; sửa URL không làm gửi lại dòng `DEAD`.

## 9. Truy vấn kiểm tra nhanh

```sql
SELECT name, on_hand, reserved, on_hand - reserved AS available, reorder_point
FROM inventory_ingredients ORDER BY name;
SELECT kind, COUNT(*) FROM inventory_movements GROUP BY kind;
SELECT code, status, total_amount FROM menu_orders ORDER BY id;
SELECT kind, COUNT(*) FROM customer_notification_events GROUP BY kind;
```

Số liệu mong đợi ngay sau khi nạp (trước khi thao tác): Lon Coca 48 / giữ 2, Mì gói 39 / giữ 1, Trứng gà 28 / giữ 1,
Cà phê bột 2960, Sữa đặc 390, Xúc xích 4, Chai nước suối 33, Cơm nguội 7750, Khoai tây 0.

## 10. Làm lại từ đầu

Dữ liệu mẫu nằm chung database với dữ liệu thật của bạn nên **không có lệnh tự xóa**. Lưu ý
`scripts/reset_demo.py` chỉ xóa các bảng giai đoạn đầu (khách, máy, phiên, hóa đơn...), **không** xóa
bảng menu, kho, đơn POS nên không dùng được để làm lại dữ liệu POS. Muốn bắt đầu sạch, dùng một database
dùng thử mới (tạo bằng tài khoản root MySQL), chạy `init_db.py`, `seed_db.py`, `seed_pos_demo.py`. Trên
database ứng dụng, luôn sao lưu trước khi thao tác.
