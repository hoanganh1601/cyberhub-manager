---
id: shared-role-policy
title: Chính sách phân quyền vận hành CyberHub
audience:
  - STAFF
  - KITCHEN
  - MANAGER
  - ADMIN
status: APPROVED
version: 3
language: vi
updated_at: 2026-11-22
tags:
  - authorization
  - roles
---

# Chính sách phân quyền vận hành CyberHub

## Phân quyền hiện hành

- STAFF vận hành máy, khách hàng, phiên chơi, hóa đơn và thanh toán trong phạm vi
  được giao; không xem báo cáo doanh thu.
- KITCHEN chỉ xem đơn POS và chuyển đơn sang đang chuẩn bị/đã phục vụ.
  Bếp không thu tiền hoặc hủy/hoàn đơn.
- MANAGER vận hành và quản lý trong cửa hàng được phân công, xem doanh thu, duyệt
  hoàn hủy theo quyền; không quản trị cơ sở khác.
- DIRECTOR quản trị chuỗi cửa hàng và báo cáo tổng hợp theo phạm vi được cấp.
- ADMIN có quyền quản trị toàn hệ thống theo API cho phép, có thể chuyển phạm vi
  cơ sở và tạo tài khoản theo vai trò; thao tác xuyên cơ sở vẫn phải chọn phạm vi rõ ràng.

Backend đọc lại trạng thái ACTIVE, role và cơ sở từ phiên/DB; không tin role hoặc
store ID do trình duyệt tự gửi. Việc ẩn menu chỉ hỗ trợ giao diện, service vẫn kiểm
tra từng permission. Quyền mới không tự động cấp cho role hiện có.

## Nguồn đối chiếu

- `src/cyberhub_manager/domain/p1.py` — Ma trận permission hiện hành
- `docs/features/POS_INVENTORY_LIFECYCLE.md` — Phân quyền POS và kho
