---
id: staff-kitchen-operation
title: Nghiệp vụ Bếp và vòng đời đơn POS
audience:
  - KITCHEN
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-15
tags:
  - kitchen
  - pos
  - orders
---

# Nghiệp vụ Bếp và vòng đời đơn POS

## Phạm vi của Bếp

Tài khoản KITCHEN chỉ thấy không gian Menu đồ ăn. Bếp được xem đơn của cơ sở,
tiếp nhận đơn `NEW` để chuyển sang `PREPARING`, sau đó xác nhận `SERVED` khi món
đã phục vụ. Bếp được xem tồn nguyên liệu để biết khả năng phục vụ nhưng không được
nhập, xuất, trả, kiểm kê, tạo nguyên liệu hoặc sửa công thức.

Bếp không thu tiền, không đánh dấu `PAID`, không hủy hoặc hoàn tiền, không duyệt
đề xuất hoàn/hủy và không quản trị danh mục món. Biết URL không thay đổi quyền vì
backend kiểm tra permission cho từng thao tác.

## Tồn kho theo trạng thái đơn

Khi khách đặt đơn hợp lệ, hệ thống giữ nguyên liệu theo công thức. Chuyển sang
`PREPARING` không giải phóng phần giữ. Khi đơn đã chuẩn bị bị hủy theo luồng có
thẩm quyền, nguyên liệu được ghi hao hụt thay vì tự trả lại. Đơn `SERVED → PAID`
không trừ kho lần thứ hai. Bếp không tự điều chỉnh các bút toán này.

## Nguồn đối chiếu

- `src/cyberhub_manager/domain/p1.py` — Permission của KITCHEN
- `src/cyberhub_manager/application/services/menu_service.py` — Chuyển trạng thái đơn
- `docs/features/POS_INVENTORY_LIFECYCLE.md` — Vòng đời đơn và tồn kho
