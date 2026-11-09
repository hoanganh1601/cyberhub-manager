---
id: shared-role-policy
title: Chính sách phân quyền sau Đợt 0
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: DRAFT
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - authorization
  - phase-zero
---

# Chính sách phân quyền sau Đợt 0

## Trạng thái

Đây là chính sách đã thống nhất để triển khai, đang chờ Đợt 0 nghiệm thu.
Không index tài liệu này vào RAG. Quyền trong nhánh hiện tại chưa chứng minh
đã chặn STAFF xem doanh thu; không thông báo cho người dùng rằng yêu cầu đã hoàn tất.

## Phân quyền mục tiêu

- STAFF vận hành máy, khách hàng, phiên chơi, hóa đơn và thanh toán trong phạm vi
  được giao; không xem báo cáo doanh thu.
- MANAGER xem doanh thu và báo cáo của cửa hàng được phân công.
- ADMIN quản trị dữ liệu, cấu hình và báo cáo toàn hệ thống theo API cho phép.
- Quyền quản lý máy, khóa khách, nhân viên và khuyến mãi vẫn kiểm tra riêng;
  quyền vận hành không tự cấp quyền quản trị.

## Điều kiện chuyển sang APPROVED

Đợt 0 phải xác nhận STAFF bị chặn ở menu, route và API doanh thu; MANAGER không
truy cập cơ sở ngoài phạm vi; ADMIN được cấp đúng phạm vi. Vai trò và cửa hàng
lấy từ backend sau xác thực lại, không tin dữ liệu do client tự gửi.
Sau nghiệm thu, cập nhật trạng thái, ngày và tăng version trước khi đánh chỉ mục.

## Nguồn đối chiếu

- `docs/HANDOVER_BUSINESS_DISCUSSION.md` — mục 1 và Đợt 0
- `docs/P1_DESKTOP_WEB.md` — quyền cũ cần được rà soát sau Đợt 0
