---
id: shared-role-policy
title: Chính sách phân quyền vận hành CyberHub
audience:
  - STAFF
  - KITCHEN
  - INVENTORY
  - MANAGER
  - ADMIN
status: APPROVED
version: 2
language: vi
updated_at: 2026-11-15
tags:
  - authorization
  - roles
---

# Chính sách phân quyền vận hành CyberHub

## Phân quyền hiện hành

- STAFF vận hành máy, khách hàng, phiên chơi, hóa đơn và thanh toán trong phạm vi
  được giao; có thể xem tồn và đề xuất kiểm kê nhưng không duyệt; không xem báo cáo doanh thu.
- KITCHEN chỉ xem đơn POS, chuyển đơn sang đang chuẩn bị/đã phục vụ và xem tồn.
  Bếp không thu tiền, hủy/hoàn đơn, nhập/xuất kho hoặc sửa công thức.
- INVENTORY dùng không gian Kho nguyên liệu để xem tồn, cấu hình nguyên liệu/công
  thức, nhập/xuất/trả kho và đề xuất kiểm kê. Thủ kho không xem hay xử lý đơn POS,
  không thu tiền và không duyệt phiếu kiểm kê.
- MANAGER vận hành và quản lý trong cửa hàng được phân công, xem doanh thu, duyệt
  kiểm kê/hoàn hủy theo quyền; không quản trị cơ sở khác.
- ADMIN có quyền quản trị toàn hệ thống theo API cho phép, có thể chuyển phạm vi
  cơ sở và tạo role chuyên trách; thao tác xuyên cơ sở vẫn phải chọn phạm vi rõ ràng.

Backend đọc lại trạng thái ACTIVE, role và cơ sở từ phiên/DB; không tin role hoặc
store ID do trình duyệt tự gửi. Việc ẩn menu chỉ hỗ trợ giao diện, service vẫn kiểm
tra từng permission. Quyền mới không tự động cấp cho role hiện có.

## Nguồn đối chiếu

- `src/cyberhub_manager/domain/policies.py` — Ma trận permission hiện hành
- `docs/features/POS_INVENTORY_LIFECYCLE.md` — Phân quyền POS và kho
