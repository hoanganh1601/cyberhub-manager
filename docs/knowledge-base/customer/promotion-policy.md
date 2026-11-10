---
id: customer-promotion-policy
title: Ưu đãi nạp tiền dành cho khách hàng
audience:
  - CUSTOMER
status: APPROVED
version: 2
language: vi
updated_at: 2026-11-10
tags:
  - promotion
  - top-up
---

# Ưu đãi nạp tiền dành cho khách hàng

## Phương thức nạp tiền

CyberHub hỗ trợ nạp tiền bằng tiền mặt (`CASH`) hoặc chuyển khoản (`TRANSFER`). Nhân viên xác nhận
khoản nạp tại quầy sau khi đã nhận đủ tiền; khách hàng không tự thực hiện giao dịch qua trợ lý AI.
Xem trước quyền lợi chỉ là phép tính dự kiến, không làm tăng số dư và không xác nhận đã nhận tiền.

## Điều kiện áp dụng

Ưu đãi phải đang bật, trong thời gian hiệu lực, đúng cơ sở hoặc toàn hệ thống,
và đủ mốc nạp. Các điều kiện hạng, điểm tối thiểu và khách hàng mục tiêu phải
đồng thời đúng nếu chương trình có đặt. Màn Ưu đãi chỉ hiện chính sách phù hợp
với tài khoản và cơ sở được chọn; tài liệu không liệt kê ưu đãi đang mở.

## Cách tính thưởng

Một lần nạp chỉ áp dụng một chính sách, không cộng chồng mốc. Chọn mốc cao nhất
đủ điều kiện; nếu cùng mốc, ưu tiên chính sách cơ sở, rồi chính sách riêng khách,
hạng cao hơn, điểm cao hơn và ID mới hơn. Thưởng làm tròn xuống đến VND.
Những lần nạp riêng không cộng dồn để đạt mốc.

Ví dụ giả định có chính sách 100.000 VND tặng 10%: nạp 150.000 VND được
15.000 VND thưởng nếu còn đủ điều kiện lúc xác nhận. Ví dụ này không xác nhận
chính sách đang tồn tại hoặc được giữ lại cho khách.

## Xem trước và xác nhận

“Xem quyền lợi” chỉ tính thử, không tạo giao dịch, không tăng số dư và không giữ
ưu đãi. Nhân viên xác nhận khoản nạp tại quầy; backend tính lại điều kiện lúc lưu.
Tiền bù thiếu khi kết thúc phiên không được xem là nạp tiền hưởng khuyến mãi.
Tiền thưởng dùng trước cho phí chơi, không đổi tiền mặt.

## Nguồn đối chiếu

- `docs/CUSTOMER_PORTAL_PHASE1.md` — Nghiệp vụ được áp dụng
- `docs/CUSTOMER_PORTAL_PHASE3.md` — Ưu đãi cá nhân hóa
- `src/cyberhub_manager/domain/p1.py` — quote_top_up
