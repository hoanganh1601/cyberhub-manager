# Ca làm việc, bảo trì và mua hàng

Ba phân hệ này chỉ hoạt động trong `CYBERHUB_WEB_MODE=mysql`. Chúng dùng chung
transaction boundary, phân quyền backend và audit log; giao diện không phải là lớp
bảo vệ quyền.

## 1. Ca làm việc và két tiền

Luồng chuẩn:

```text
Mở ca -> ghi nhận thu/chi theo phương thức -> kiểm đếm ->
không chênh lệch: đóng ca
có chênh lệch: chờ quản lý duyệt -> đóng ca
```

- Database ngăn một nhân viên có hai ca `OPEN/PENDING_REVIEW` cùng lúc.
- Nạp tiền, thanh toán phiên, POS và công nợ nhà cung cấp ghi sổ két trong
  cùng transaction nghiệp vụ.
- Tiền mặt và chuyển khoản được tách riêng. Chỉ tiền mặt tham gia
  công thức tiền cuối ca.
- Nhân viên không được tự duyệt chênh lệch ca của mình.
- Mỗi bút toán hệ thống có khóa `(source_type, source_id, payment_method)`
  để chống ghi trùng.

## 2. Bảo trì và sự cố máy

```text
REPORTED -> ASSIGNED -> IN_PROGRESS <-> WAITING_PARTS
IN_PROGRESS/WAITING_PARTS -> COMPLETED -> VERIFIED
```

- `MANAGER` phân công, hủy và nghiệm thu.
- `STAFF` báo sự cố và chỉ cập nhật phiếu được phân công.
- Khi bắt đầu sửa, máy phải đang trống và chuyển sang `MAINTENANCE`.
- Linh kiện, chi phí nhân công, người thao tác và mốc thời gian được lưu
  trong lịch sử. Người sửa không được tự nghiệm thu.
- Chỉ sau `VERIFIED` máy mới quay lại `AVAILABLE`.

## 3. Nhà cung cấp và nhập hàng

```text
Thủ kho tạo đề nghị -> Quản lý duyệt -> Quản lý tạo đơn mua ->
Thủ kho nhận/kiểm hàng -> nhập tồn + ghi ledger -> tạo công nợ -> thanh toán
```

- Người tạo đề nghị không được tự duyệt.
- Đơn mua phải khớp đúng mặt hàng và số lượng đã duyệt.
- Phiếu nhận tách số nhận, hỏng và thiếu. Chỉ số chấp nhận được cộng tồn
  và tạo công nợ.
- `request_id` UUID của phiếu nhận là idempotency key: retry cùng yêu cầu
  trả lại kết quả cũ, không cộng tồn lần hai.
- Thanh toán công nợ yêu cầu ca đang mở và ghi khoản chi tiền mặt/chuyển khoản.

## Phân quyền

| Role | Ca/két | Sự cố | Mua hàng |
|---|---|---|---|
| `ADMIN`, `MANAGER` | Xem, vận hành, duyệt chênh lệch | Toàn quyền | Toàn quyền |
| `STAFF` | Mở/vận hành ca của mình | Báo và cập nhật phiếu được giao | Không |
| `KITCHEN` | Không | Xem, báo | Không |
| `INVENTORY` | Không | Xem, báo | Xem, đề nghị, nhận hàng |

## Khởi tạo và kiểm tra

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
$env:CYBERHUB_WEB_MODE="mysql"
python -m cyberhub_manager.web --port 8000
```

Sau khi đăng nhập, menu tương ứng là **Ca & két**, **Sự cố & bảo trì**
và **Nhà cung cấp & nhập hàng**. Migration liên quan: `021`, `022`, `023`.
