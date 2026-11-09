---
id: staff-customer-management
title: Tạo và cập nhật hồ sơ khách hàng
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - customer
  - validation
  - account
---

# Tạo và cập nhật hồ sơ khách hàng

## Dữ liệu cần kiểm tra

- Họ tên: 2–100 ký tự sau khi bỏ khoảng trắng đầu/cuối.
- Điện thoại: 10 chữ số, bắt đầu bằng 0, duy nhất toàn hệ thống.
- Username: 4–30 ký tự gồm chữ Latin, số, gạch dưới và dấu chấm, không trùng.
- Mật khẩu: tối thiểu 6 ký tự, tối đa 72 byte UTF-8; nhập qua form bảo mật.
- Xác nhận mật khẩu phải khớp khi giao diện yêu cầu.

Mã khách và mã tài khoản do hệ thống tạo. Tài khoản mới có số dư khởi tạo 0;
không sửa số dư qua form thông tin khách hàng.

## Tạo khách hàng

1. Mở Khách hàng → Tạo khách hàng.
2. Nhập thông tin hợp lệ, đối chiếu khách đã có để tránh tạo trùng.
3. Xác nhận tạo hồ sơ và tài khoản qua service.
4. Nếu trùng điện thoại hoặc username, chỉnh lại dữ liệu theo thông báo.
5. Nạp tiền bằng chức năng riêng sau khi tạo thành công nếu khách có nhu cầu.

## Cập nhật và khóa tài khoản

Form chỉnh sửa cập nhật thông tin được phép, không sửa mã và định danh tài khoản.
STAFF có thể tra cứu/tạo/sửa theo quyền vận hành; thao tác khóa/mở khách cần
Manager/Admin. Khóa hoặc ngừng hoạt động không xóa lịch sử giao dịch.
Khách/tài khoản không hoạt động không được mở phiên mới.

## Dữ liệu khách hàng

Ví khách dùng chung giữa các cơ sở; không xem đây là ví riêng từng cửa hàng.
Trợ lý tài liệu chỉ mô tả quy trình, không lấy danh sách điện thoại, mật khẩu,
số dư hoặc giao dịch của khách để trả trong chat.

## Nguồn đối chiếu

- `src/cyberhub_manager/services/customer_service.py`
- `docs/P1_DESKTOP_WEB.md` — Quy tắc nghiệp vụ và Phân quyền
- `sql/001_initial_schema.sql` — customers, accounts
