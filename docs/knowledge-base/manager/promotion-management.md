---
id: manager-promotion-management
title: Quản lý chương trình khuyến mãi nạp tiền
audience:
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - promotion
  - management
---

# Quản lý chương trình khuyến mãi nạp tiền

## Phạm vi quyền

Manager quản lý chương trình thuộc cơ sở được giao. Admin quản lý chương trình
theo cơ sở hoặc toàn hệ thống. STAFF không sửa chính sách. Mỗi thao tác phải
xác thực lại ở backend và ghi audit.

## Dữ liệu chương trình

Mã chương trình, tên, cơ sở hoặc toàn hệ thống, mốc nạp, phần trăm thưởng,
bắt đầu/kết thúc, bật/tắt, hạng tối thiểu, điểm tối thiểu và khách hàng riêng nếu có.
Mốc nạp từ 1 đến 100.000.000 VND; thưởng 0–100%; kết thúc phải sau bắt đầu.
Điểm tối thiểu từ 0 đến 1.000.000.000. Khách mục tiêu phải tồn tại.

Không tạo hai chính sách đang bật cùng phạm vi, mốc nạp và đối tượng mà chồng
thời gian. Chương trình khác đối tượng có thể cùng mốc; backend quyết định một
chính sách tại lúc nạp, không cộng chồng.

## Cách vận hành

1. Chọn đúng cơ sở, nhập điều kiện và thời gian.
2. Kiểm tra đối tượng hạng/điểm/khách trên form web.
3. Lưu và kiểm tra chính sách ở danh sách.
4. Xem trước trên một trường hợp minh họa đủ điều kiện, không nạp thử tiền thật.
5. Khi ngừng chương trình, tắt chính sách theo chức năng được cấp.

Giờ nhập ở giao diện theo Việt Nam; quy tắc lưu thời gian của hệ thống là UTC.
Hiệu lực gồm bắt đầu, không gồm kết thúc. Sửa điều kiện đối tượng trên web;
form desktop hiện có giữ nguyên các điều kiện đối tượng đã lưu.

## Giới hạn

Không hứa thưởng cố định chỉ dựa vào ví dụ. Cấu hình thành viên toàn hệ thống
chỉ Admin sửa. AI có thể giải thích điều kiện, không tự bật chương trình hoặc
thay mốc/đối tượng.

## Nguồn đối chiếu

- `src/cyberhub_manager/services/management_service.py` — save_promotion
- `docs/CUSTOMER_PORTAL_PHASE3.md` — Ưu đãi cá nhân hóa
- `docs/P1_DESKTOP_WEB.md` — Phân quyền và thời gian khuyến mãi
