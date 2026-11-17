---
id: admin-employee-password-reset
title: Đặt lại mật khẩu tài khoản nhân viên
audience:
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-15
tags:
  - employee
  - password
  - audit
---

# Đặt lại mật khẩu tài khoản nhân viên

## Khi nhân viên quên mật khẩu

Admin chọn tài khoản STAFF, KITCHEN, INVENTORY, MANAGER hoặc ADMIN khác và dùng
chức năng Đặt lại mật khẩu. Mật khẩu tạm thời phải dài ít nhất 8 ký tự và không
quá 72 byte UTF-8. Hệ thống băm mật khẩu trước khi lưu; không thể xem lại mật khẩu
cũ từ hash và không được hiển thị danh sách mật khẩu cho Admin.

Admin không đặt lại mật khẩu của chính mình bằng luồng quản trị. Nếu chính Admin
quên mật khẩu và không còn Admin khác hỗ trợ, dùng script bootstrap/reset dành cho
vận hành tại máy chủ với quyền truy cập database, không sửa hash thủ công.

## Bắt buộc đổi mật khẩu tạm

Sau khi đặt lại, tài khoản có cờ bắt buộc đổi mật khẩu. Người dùng đăng nhập bằng
mật khẩu tạm chỉ được vào màn đổi mật khẩu; mật khẩu mới phải dài 8–72 byte, khác
mật khẩu tạm và xác nhận khớp. Hoàn tất đổi mật khẩu mới mở lại các chức năng theo
role. Backend ghi audit cho cả đặt lại và đổi mật khẩu nhưng không ghi giá trị mật khẩu.

## Nguồn đối chiếu

- `history/docs/features/EMPLOYEE_PASSWORD_RESET.md` — Quy trình vận hành hoàn chỉnh
- `src/cyberhub_manager/services/management_service.py` — Admin đặt lại mật khẩu
- `src/cyberhub_manager/services/auth_service.py` — Nhân viên đổi mật khẩu
