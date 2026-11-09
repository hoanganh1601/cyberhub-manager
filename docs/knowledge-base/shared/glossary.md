---
id: shared-glossary
title: Thuật ngữ CyberHub Manager
audience:
  - CUSTOMER
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - glossary
  - wallet
  - membership
---

# Thuật ngữ CyberHub Manager

## Máy và phiên chơi

- `AVAILABLE`: máy đang ở trạng thái trống; để mở phiên còn phải đủ các điều kiện
  hoạt động, số dư và không trùng phiên.
- `IN_USE`: máy đang được sử dụng.
- `MAINTENANCE`: máy bảo trì, không nhận phiên mới.
- Phiên `ACTIVE`: đang diễn ra; `COMPLETED`: đã kết thúc; `CANCELLED`: đã hủy.
- Phòng thường (`STANDARD`) và VIP là phân loại máy. Máy chưa phân loại được
  tính là phòng thường; đổi loại phòng không tự đổi giá giờ.

## Số dư

- Tổng số dư (`balance`) = số dư chính (`cash_balance`) + khuyến mãi (`bonus_balance`).
- Tiền khuyến mãi được dùng trước khi thanh toán phí chơi và không đổi tiền mặt.
- Tiền bù là khoản thanh toán thêm khi số dư chưa đủ kết thúc phiên, không phải
  nạp tiền được hưởng thưởng khuyến mãi.
- Số dư trên tài khoản chưa tự trừ phí ước tính của phiên đang chơi; số dư dự kiến
  sau thanh toán có thể khác số dư hiện tại.

## Hóa đơn và thành viên

- `PAID`: hóa đơn đã thanh toán; `VOID`: hóa đơn đã hủy.
- Điểm thành viên được ghi theo phí chơi hợp lệ từng hóa đơn PAID, không phải
  tiền trong ví và hiện chưa có chức năng tiêu điểm.
- Hạng Đồng/Bạc/Vàng/Kim cương dựa trên tổng chi tiêu hợp lệ, không dựa trực tiếp
  vào số điểm. Mã nội bộ Kim cương là `PLATINUM`.
- Ưu đãi cá nhân hóa phải đồng thời thỏa các điều kiện do chương trình đặt ra.

## Giới hạn trợ lý

Tài liệu giải thích quy trình; không xác nhận số dư, máy trống hoặc ưu đãi hiện tại.
Trợ lý không được tự ghi giao dịch, sửa trạng thái tài khoản hoặc cấp phần thưởng.

## Nguồn đối chiếu

- `src/cyberhub_manager/domain/enums.py`
- `src/cyberhub_manager/domain/p1.py`
- `docs/CUSTOMER_PORTAL_PHASE2.md`
- `docs/CUSTOMER_PORTAL_PHASE3.md`
