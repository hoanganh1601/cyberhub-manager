---
id: admin-employee-management
title: Quản trị tài khoản nhân viên
audience:
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - employee
  - administration
---

# Quản trị tài khoản nhân viên

## Tạo và sửa tài khoản

Admin quản lý nhân viên toàn hệ thống, gán cơ sở đang hoạt động và vai trò
STAFF/MANAGER/ADMIN. Username không trùng; mật khẩu mới ít nhất 6 ký tự,
tối đa 72 byte UTF-8 và được băm. Khi sửa, để trống mật khẩu giữ giá trị hiện tại.
Không nhập hoặc nhờ AI lưu mật khẩu vào hội thoại.

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

- `src/cyberhub_manager/services/management_service.py` — save_employee
- `src/cyberhub_manager/services/access.py`
- `docs/P1_DESKTOP_WEB.md` — Phân quyền
