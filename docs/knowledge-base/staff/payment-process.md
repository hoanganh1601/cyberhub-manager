---
id: staff-payment-process
title: Quy trình thanh toán phiên chơi
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - payment
  - invoice
  - session
---

# Quy trình thanh toán phiên chơi

## Điều kiện và xem trước

Nhân viên có quyền vận hành đúng cơ sở, máy còn phiên ACTIVE và chưa checkout.
Mở xem trước để kiểm tra khách, thời lượng, đơn giá chụp khi mở phiên, phí,
số dư và khoản thiếu. Kết quả xem trước có thể đổi theo thời gian hoặc giao dịch ví.

Thời gian tính phí làm tròn lên đến phút, tối thiểu 1 phút. Phí bằng số phút
tính tiền × đơn giá giờ / 60, làm tròn lên đến VND. Không nhầm với biểu đồ sử dụng
của khách tính theo giây thực tế.

## Trừ ví và tiền bù

Hệ thống ưu tiên trừ khuyến mãi rồi đến số dư chính. Nếu thiếu, khoản bù phải
bằng đúng khoản thiếu backend tính lại khi checkout; nhận bằng CASH hoặc TRANSFER.
Nếu không thiếu, không nhập phương thức bù hoặc khoản bù dương.

Ví dụ minh họa: phí 20.000 VND, ví tổng 12.000 VND gồm 2.000 thưởng và 10.000
tiền chính; cần bù 8.000 VND. Không ghi 8.000 này thành tiền nạp hưởng khuyến mãi.
Phí hóa đơn vẫn 20.000 VND, không cộng tiền bù thành 28.000 VND.

## Luồng xác nhận

1. Xem trước, xác nhận khoản phải thu tại quầy.
2. Backend xác thực nhân viên, khóa dữ liệu và tính lại phí/số dư.
3. Nếu khoản thiếu thay đổi, dừng xác nhận và xem lại dữ liệu.
4. Ghi tiền bù nếu cần, trừ ví, hoàn tất phiên và ghi hóa đơn trong transaction.
5. Khi thành công, máy về AVAILABLE, phiên COMPLETED, hóa đơn PAID.
6. Kiểm tra hóa đơn và kết quả trước khi thao tác tiếp.

Mỗi phiên tối đa một hóa đơn. Gửi lại yêu cầu đã xử lý không được tạo thanh toán
lần hai. Lỗi giao dịch không được xử lý bằng cách tự sửa số dư trong database.

## Điểm thành viên và hóa đơn hủy

Chi tiêu tích điểm bằng phí chơi trừ thưởng đã dùng. Mặc định làm tròn xuống
từng 10.000 VND = 1 điểm. Chụp cấu hình và số điểm cùng lúc lập hóa đơn;
Admin có thể thay tỷ lệ cho hóa đơn mới. Tiền bù đã nằm trong phí nên không cộng lại.

Chỉ hóa đơn PAID được tính vào doanh thu và thành viên. VOID không tạo điểm
hiệu lực hoặc chi tiêu xét hạng. Không suy diễn hủy hóa đơn đồng nghĩa ví tự
được hoàn tiền; cần quy trình hoàn tiền được duyệt riêng trước khi trả tiền.

## Giới hạn trợ lý

Trợ lý giải thích quy trình; không xác nhận thu tiền, đóng phiên, hủy hóa đơn
hoặc hoàn tiền thay nhân viên. Không cần cung cấp dữ liệu khách thật cho AI.

## Nguồn đối chiếu

- `src/cyberhub_manager/services/session_service.py`
- `docs/P1_DESKTOP_WEB.md` — Checkout và tiền bù
- `docs/CUSTOMER_PORTAL_PHASE3.md` — Chính sách thành viên
