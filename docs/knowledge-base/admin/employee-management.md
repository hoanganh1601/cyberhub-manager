---
id: admin-employee-management
title: Quản trị tài khoản nhân viên
audience:
  - ADMIN
status: APPROVED
version: 2
language: vi
updated_at: 2026-11-15
tags:
  - employee
  - administration
---

# Quản trị tài khoản nhân viên

## Tạo và sửa tài khoản

Admin quản lý nhân viên toàn hệ thống, gán cơ sở đang hoạt động và vai trò
STAFF, KITCHEN, INVENTORY, MANAGER hoặc ADMIN. Username không trùng; mật khẩu
khi tạo mới ít nhất 8 ký tự, tối đa 72 byte UTF-8 và được băm. Form sửa hồ sơ
không nhận mật khẩu; thay đổi mật khẩu phải dùng chức năng riêng.
Không nhập hoặc nhờ AI lưu mật khẩu vào hội thoại.

## Đặt lại và đổi mật khẩu

Admin có thể đặt mật khẩu tạm thời dài 8 ký tự đến 72 byte cho tài khoản khác ở
mọi role. Admin không được đặt lại chính mình bằng luồng này; tài khoản hiện tại
dùng chức năng đổi mật khẩu và phải nhập mật khẩu đang dùng. Sau khi Admin đặt lại,
hệ thống chỉ lưu hash, đặt cờ bắt buộc đổi mật khẩu và ghi audit
`EMPLOYEE_PASSWORD_RESET`; không hiển thị hoặc khôi phục mật khẩu cũ. Người dùng
đăng nhập bằng mật khẩu tạm phải đổi sang mật khẩu mới trước khi dùng chức năng khác.

## Hạn chế bắt buộc

- Không tự khóa, đổi vai trò hoặc chuyển cơ sở của chính mình qua chức năng này.
- Hệ thống phải còn ít nhất một Admin đang hoạt động.
- Khóa/ngừng tài khoản giữ lịch sử, không xóa giao dịch đã có.
- Ghi audit thao tác, không ghi mật khẩu.

Manager có quyền quản lý giới hạn nhân viên STAFF tại cơ sở của mình theo
nghiệp vụ hiện có; không cấp MANAGER/ADMIN hoặc sửa nhân viên cơ sở khác.
Tài liệu quản trị này chỉ cung cấp cho ADMIN theo audience khai báo.

## Khi thay đổi quyền

Backend phải xác thực trạng thái và vai trò hiện tại trước thao tác nhạy cảm.
Quyền doanh thu mới thuộc Đợt 0, xem bản nháp phân quyền để bàn giao nội bộ;
không tuyên bố đã nghiệm thu khi chưa có kết quả kiểm thử.
Trợ lý không tự tạo, khóa hoặc nâng quyền tài khoản.

## Nguồn đối chiếu

- `src/cyberhub_manager/application/services/management_service.py` — save_employee
- `src/cyberhub_manager/application/services/access.py`
