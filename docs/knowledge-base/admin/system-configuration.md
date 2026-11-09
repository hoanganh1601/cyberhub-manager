---
id: admin-system-configuration
title: Cấu hình điểm và hạng thành viên toàn hệ thống
audience:
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - loyalty
  - configuration
  - administration
---

# Cấu hình điểm và hạng thành viên toàn hệ thống

## Quyền và vị trí

Chỉ Admin sửa cấu hình thành viên toàn hệ thống tại web nhân viên → Khuyến mãi
→ Cấu hình thành viên. Manager/Staff không được thay các mốc này.

## Tham số

- Bật/tắt tích điểm cho hóa đơn mới.
- Số VND hợp lệ trên một điểm, mặc định 10.000.
- Mốc Bạc/Vàng/Kim cương, mặc định 1.000.000/3.000.000/5.000.000 VND.
- Version cấu hình để ngăn ghi đè từ form cũ.

Số tiền trên một điểm từ 1 đến 100.000.000 VND. Các mốc là số nguyên dương,
thứ tự Bạc < Vàng < Kim cương, mốc cao nhất không quá 1.000.000.000.000 VND.
Backend kiểm tra hợp lệ và ghi audit khi lưu.

## Ảnh hưởng của thay đổi

Đổi tỷ lệ chỉ áp dụng cho hóa đơn mới. Mỗi hóa đơn chụp điểm, chi tiêu hợp lệ,
đơn vị và version trong transaction checkout; không tính lại điểm lịch sử.
Đổi mốc hạng phân loại lại theo chi tiêu hợp lệ hiện có của khách.
Tắt tích điểm mới không xóa điểm cũ; chi tiêu hợp lệ vẫn được tính để xét hạng.

Nếu version đã thay đổi từ khi mở form, không ghi đè. Tải lại cấu hình mới,
kiểm tra nội dung rồi lưu lại theo giao diện.

## Giới hạn dữ liệu

Kho tài liệu chỉ mô tả mặc định, không xác nhận cấu hình hiện tại sau các lần sửa.
Không đưa file .env, thông tin kết nối, khóa API hoặc dữ liệu giao dịch thật
vào kho tri thức. AI không tự thay cấu hình hoặc sửa số dư/điểm khách.

## Nguồn đối chiếu

- `src/cyberhub_manager/services/management_service.py` — update_loyalty_settings
- `src/cyberhub_manager/domain/loyalty.py`
- `docs/CUSTOMER_PORTAL_PHASE3.md` — Cấu hình quản trị
