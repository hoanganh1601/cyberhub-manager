---
id: customer-account-guide
title: Hướng dẫn tài khoản, hồ sơ và ảnh đại diện
audience:
  - CUSTOMER
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - profile
  - avatar
  - password
---

# Hướng dẫn tài khoản, hồ sơ và ảnh đại diện

## Mở hồ sơ

Đăng nhập cổng `/customer`, bấm avatar góc phải để mở menu. Chọn chỉnh sửa hồ sơ,
cập nhật ảnh, thành viên, đổi mật khẩu hoặc đăng xuất. Khách chỉ xem/sửa dữ liệu
của chính tài khoản đang đăng nhập.

## Sửa thông tin cá nhân

Có thể sửa họ tên và điện thoại, xác nhận bằng mật khẩu hiện tại trong form bảo mật.
Họ tên dài 2–100 ký tự. Điện thoại gồm 10 chữ số, bắt đầu bằng 0 và không trùng
khách hàng khác. Không tự sửa mã khách, username, trạng thái hoặc số dư.
Không gửi mật khẩu vào cuộc hội thoại với trợ lý.

## Cập nhật ảnh

Chọn JPEG, PNG hoặc WebP tĩnh, tối đa 2 MiB và 16 triệu điểm ảnh. Có thể xem trước,
lưu hoặc xóa để trở về chữ viết tắt. Hệ thống căn giữa ảnh vuông, chuẩn hóa WebP
512×512 và bỏ metadata gốc. File không hợp lệ không ghi đè ảnh hiện có.

## Đổi mật khẩu

Nhập mật khẩu hiện tại, mật khẩu mới và xác nhận khớp. Mật khẩu mới tối thiểu
6 ký tự, tối đa 72 byte UTF-8 và phải khác mật khẩu cũ. Sau khi đổi, phiên hiện tại
được giữ; các phiên cũ phải đăng nhập lại. Không lưu mật khẩu vào ghi chú hay chat.

## Vì sao thay đổi trong demo có thể biến mất?

Dữ liệu web demo tách theo lần đăng nhập và không ghi MySQL thật. Đăng nhập lại
hoặc khởi động lại server có thể tạo dữ liệu mẫu mới. Chế độ MySQL lưu dữ liệu
qua các lần đăng nhập; không dùng số liệu mẫu để kết luận tình trạng tài khoản thật.

## Nguồn đối chiếu

- `docs/CUSTOMER_PORTAL_PHASE2.md` — Hồ sơ và mật khẩu
- `docs/CUSTOMER_PORTAL_PHASE3.md` — Avatar và hồ sơ
