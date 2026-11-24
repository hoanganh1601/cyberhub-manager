---
id: staff-operations-control
title: Ca làm việc, két tiền và bảo trì máy
audience:
  - STAFF
  - KITCHEN
  - INVENTORY
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-16
tags:
  - cash-shift
  - reconciliation
  - maintenance
---

# Ca làm việc, két tiền và bảo trì máy

## Ca và két tiền

Nhân viên thu ngân phải mở ca và khai báo tiền mặt đầu ca trước khi thu tiền
nạp, thanh toán phiên hoặc POS. Mỗi nhân viên chỉ có một ca đang hoạt động.
Hệ thống tách tiền mặt và chuyển khoản; chỉ dòng tiền mặt tham gia đối
chiếu tiền thực tế trong két.

Cuối ca, nhân viên nhập số tiền mặt kiểm đếm. Ca không chênh lệch được
đóng ngay. Ca có chênh lệch chuyển sang chờ quản lý xem biên bản và xác nhận;
người vận hành ca không được tự duyệt chênh lệch của mình. Không xóa hoặc
sửa trực tiếp bút toán đã ghi; sai sót phải ghi bút toán điều chỉnh có lý do.

## Sự cố và bảo trì

Nhân sự có thể báo máy hỏng kèm mức độ, tiêu đề và mô tả. Quản lý phân
công người xử lý. Người được giao chuyển phiếu qua đang sửa, chờ linh kiện
và hoàn thành; khi hoàn thành phải ghi giải pháp, chi phí nhân công và linh
kiện đã dùng.

Máy chỉ chuyển sang bảo trì khi đang trống. Người sửa không được tự nghiệm
thu. Sau khi quản lý kiểm tra và xác nhận, máy mới trở lại trạng thái sẵn sàng.

## Nguồn đối chiếu

- `docs/features/OPERATIONS.md` — quy trình, phân quyền và hướng dẫn nghiệm thu
- `src/cyberhub_manager/domain/policies.py` — quyền ca và bảo trì
