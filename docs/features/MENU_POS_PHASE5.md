# POS đồ ăn và đồ uống

Quy tắc tồn kho và quyền: [Chốt nghiệp vụ tồn kho và quyền POS](POS_INVENTORY_LIFECYCLE.md).
Với MySQL đã chạy migration `013_inventory.sql`, món bật quản lý tồn sẽ giữ nguyên liệu
khi tạo đơn, xuất dùng lúc bắt đầu chuẩn bị và không trừ tiếp khi thu tiền. Món chưa
bật quản lý tồn vẫn dùng cờ còn/hết thủ công; demo bộ nhớ không có sổ kho.

POS menu dùng chung danh mục món hiện có và lưu giá tại thời điểm khách đặt. Quy trình đơn:

`NEW` → `PREPARING` → `SERVED` → `PAID`

Nhân viên có thể hủy đơn ở `NEW` hoặc `PREPARING`. Hủy đơn đã chuẩn bị phải nhập lý do; nguyên liệu đã xuất được ghi hao hụt, không tự hoàn kho. Đơn đã `SERVED` chỉ chuyển sang `PAID`; đơn đã thanh toán hoặc đã hủy là trạng thái kết thúc.

## Thao tác trên web

- Khách đang có phiên máy chọn món trong `/customer` và gửi yêu cầu.
- STAFF/MANAGER/ADMIN mở **Menu đồ ăn** để xem toàn bộ đơn của cơ sở.
- Bấm **Bắt đầu chuẩn bị**, **Đã phục vụ**, sau đó **Thanh toán**.
- Thanh toán chọn `CASH` hoặc `TRANSFER`. Nhân viên xác nhận đã nhận tiền trước khi hoàn tất.

Tiền món ăn được thu tại quầy và không tự trừ ví giờ chơi. Giá, tên món và số lượng được chụp vào đơn lúc khách đặt; sửa giá menu sau đó không làm thay đổi đơn cũ.

## Cập nhật MySQL

Migration `sql/012_menu_pos.sql` thêm trạng thái POS; `sql/013_inventory.sql` thêm kho và công thức; `sql/014_inventory_counting.sql` thêm phiếu kiểm kê, duyệt chênh lệch và xuất kho thủ công. Với database test, chạy:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_test_db.py
```

Với database ứng dụng đang dùng trong `.env`, sau khi sao lưu hãy chạy:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
```

Demo web tạo workspace riêng cho mỗi lần đăng nhập; để kiểm tra phối hợp khách và nhân viên lâu dài, dùng MySQL thật hoặc thực hiện trên cùng workspace demo.

## Đơn mẫu và báo cáo trong demo

Đăng xuất rồi đăng nhập lại bằng tài khoản nhân viên hoặc quản lý để tạo workspace demo mới. Trang **Menu đồ ăn** có đơn mẫu ở đủ trạng thái `NEW`, `PREPARING`, `SERVED`, `PAID`, `CANCELLED`; chọn **Tất cả** để xem. Có thể tiếp nhận, phục vụ và thanh toán các đơn chưa hoàn tất. Workspace khách hàng riêng không được nạp các đơn mẫu này.

Trang **Doanh thu** tách tiền giờ chơi, tiền món ăn đã thanh toán, số đơn món đã thanh toán và tổng cộng. Bảng theo ngày dùng giờ Việt Nam; tiền món được ghi vào ngày thu tiền, trừ voucher đồ ăn đã sử dụng. Món bán chạy chỉ tính số lượng trong đơn `PAID`. Đơn chưa thu tiền và đơn hủy không làm tăng doanh thu. Tiền nạp ví không được tính lại. Các đơn demo chỉ nằm trong bộ nhớ, không ghi vào MySQL.
