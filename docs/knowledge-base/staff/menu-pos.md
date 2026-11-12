---
id: staff-menu-pos
title: Quy trình POS đồ ăn và đồ uống
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-10
tags:
  - menu
  - pos
  - payment
---

# Quy trình POS đồ ăn và đồ uống

Đơn đồ ăn/thức uống đi qua các trạng thái: NEW (mới nhận), PREPARING (đang chuẩn bị), SERVED (đã phục vụ), PAID (đã thanh toán). Nhân viên có thể hủy đơn ở NEW hoặc PREPARING. Đơn SERVED phải được thanh toán để hoàn tất.

Thanh toán POS chọn tiền mặt hoặc chuyển khoản và được nhân viên xác nhận tại quầy. Tiền món ăn không tự trừ ví giờ chơi. Giá món được chụp tại thời điểm đặt; sửa giá menu sau đó không đổi đơn cũ.

Khách chỉ đặt món khi đang có phiên chơi tại cơ sở. Nhân viên chỉ xử lý đơn thuộc cơ sở mình đang làm việc.

## Nguồn đối chiếu

- `src/cyberhub_manager/services/menu_service.py`
- `src/cyberhub_manager/domain/menu.py`
- `docs/POS_INVENTORY_LIFECYCLE.md`
