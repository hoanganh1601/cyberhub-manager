---
id: manager-revenue-policy
title: Chính sách truy cập và diễn giải báo cáo doanh thu
audience:
  - MANAGER
  - ADMIN
status: DRAFT
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - revenue
  - authorization
  - phase-zero
---

# Chính sách truy cập và diễn giải báo cáo doanh thu

## Trạng thái và phạm vi

Không đưa tài liệu vào RAG trước khi Đợt 0 nghiệm thu quyền doanh thu ở backend
và giao diện. Chính sách mục tiêu: STAFF không được xem doanh thu; MANAGER chỉ
xem cơ sở được phân công; ADMIN xem phạm vi hệ thống qua chức năng được cấp.

## Nguyên tắc ghi nhận

Báo cáo doanh thu sử dụng hóa đơn PAID theo khoảng ngày và cơ sở. Loại hóa đơn
VOID; không cộng TOP_UP vào doanh thu phí chơi để tránh đếm trùng.
Tiền bù nằm trong phí hóa đơn, không cộng riêng lần thứ hai.
Tổng phí sử dụng không đồng nghĩa tiền mặt thực thu hoặc lợi nhuận.

## Trợ lý và số liệu thực tế

Đợt 5A chỉ giải thích chính sách tĩnh; không trả số tiền thực tế của cửa hàng.
Hỏi đáp số liệu là phạm vi 5B, cần backend truy vấn đúng quyền, kỳ và cơ sở,
rồi mới cung cấp dữ liệu đã lọc cho mô hình. Không để AI tự sinh SQL tự do.

## Điều kiện duyệt

Có kiểm thử STAFF bị từ chối API/route, MANAGER không vượt cơ sở, ADMIN được
đúng phạm vi. Người làm Đợt 0 xác nhận cách lọc ngày, timezone và quyền báo cáo
sau khi merge, rồi cập nhật trạng thái, ngày và tăng version tài liệu.

## Nguồn đối chiếu

- `docs/HANDOVER_BUSINESS_DISCUSSION.md` — Đợt 0 và Đợt 5
- `docs/P1_DESKTOP_WEB.md` — Quyền cũ cần rà soát
