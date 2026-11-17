---
id: staff-inventory-operation
title: Nghiệp vụ Thủ kho và kiểm kê nguyên liệu
audience:
  - INVENTORY
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-15
tags:
  - inventory
  - warehouse
  - counting
---

# Nghiệp vụ Thủ kho và kiểm kê nguyên liệu

## Phạm vi của Thủ kho

Tài khoản INVENTORY chỉ thấy không gian Kho nguyên liệu. Thủ kho được xem tồn thực
tế, lượng đang giữ và tồn khả dụng; tạo nguyên liệu, đặt ngưỡng sắp hết, cấu hình
công thức món, nhập kho, xuất kho, trả kho, xem sổ biến động và đề xuất kiểm kê.

Thủ kho không được xem hoặc xử lý đơn gọi món, không chuyển trạng thái Bếp, không
thu tiền POS, không hoàn tiền và không duyệt phiếu kiểm kê. MANAGER hoặc ADMIN có
quyền phù hợp mới duyệt đề xuất; người đề xuất không tự duyệt phiếu của mình.

## Nhập, xuất và sổ kho

Mỗi nghiệp vụ kho ghi một movement bất biến gồm nguyên liệu, loại nghiệp vụ, số
lượng, biến động tồn/giữ, tham chiếu, ghi chú, người thực hiện và thời điểm. Request
idempotency ngăn gửi lại cùng yêu cầu làm tăng hoặc giảm tồn hai lần. Không được
xuất nhiều hơn tồn khả dụng `on_hand - reserved`.

## Kiểm kê

Phiếu kiểm kê chụp tồn thực tế, lượng giữ và movement cuối tại thời điểm đề xuất.
Nếu tồn thay đổi trước lúc duyệt, phiếu cũ bị từ chối và phải kiểm kê lại. Số đếm
không được thấp hơn lượng đang giữ cho đơn. Khi duyệt, chênh lệch được ghi bằng
movement `ADJUST`, không sửa lịch sử cũ.

Chế độ demo mô phỏng kho trong bộ nhớ và mất khi workspace/server được tạo lại.
Nghiệm thu tính đồng thời, khóa dòng và lưu trữ lâu dài phải dùng MySQL.

## Đề nghị và nhận hàng nhà cung cấp

Thủ kho tạo đề nghị theo nguyên liệu và số lượng, nhưng không tự duyệt.
Sau khi quản lý duyệt và tạo đơn mua, Thủ kho ghi nhận riêng số lượng
chấp nhận, hư hỏng và thiếu. Chỉ hàng chấp nhận được cộng tồn và tính công
nợ. Không gửi lại phiếu bằng mã yêu cầu mới khi trình duyệt chậm; thao tác retry
phải giữ nguyên mã yêu cầu để hệ thống không nhập trùng.

## Nguồn đối chiếu

- `src/cyberhub_manager/domain/p1.py` — Permission của INVENTORY
- `src/cyberhub_manager/repositories/inventory_repository.py` — Sổ kho và kiểm kê
- `docs/features/POS_INVENTORY_LIFECYCLE.md` — Quy tắc tồn, giữ và hoàn kho
- `docs/features/OPERATIONS_PHASE7.md` — Đề nghị, đơn mua, nhận hàng và công nợ
