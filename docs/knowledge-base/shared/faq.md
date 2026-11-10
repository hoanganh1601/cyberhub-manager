---
id: shared-faq
title: Câu hỏi thường gặp về CyberHub
audience:
  - CUSTOMER
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 3
language: vi
updated_at: 2026-11-10
tags:
  - faq
  - availability
  - scope
---

# Câu hỏi thường gặp về CyberHub

## Cần bao nhiêu số dư để mở phiên?

Số dư tối thiểu để mở phiên phải đủ 30 phút theo đơn giá của máy được chọn, làm tròn lên
đến VND. Số tiền yêu cầu phụ thuộc đơn giá máy, không phải một mức tiền cố định cho mọi máy.
Đây là điều kiện mở phiên, không phải thu trước phí 30 phút hoặc tự dừng máy sau 30 phút.

## Xem số máy trống có đồng nghĩa đã đặt máy không?

Không. Cổng khách hàng chỉ thông báo số máy còn trống theo cơ sở và loại máy thường,
VIP, Couple, Siêu VIP; không đếm số phòng vật lý còn trống.
Số liệu tự cập nhật mỗi 5 phút, có thời điểm lấy dữ liệu và không giữ chỗ.
Máy được sắp xếp tại quầy khi khách tới. Tài liệu này không cung cấp số máy hiện tại.

## Vì sao số dư hiện tại khác số dư sau thanh toán dự kiến?

Phí của phiên đang chơi chưa được trừ vào ví. Số dư sau thanh toán dự kiến có tính
phí đang phát sinh; thời gian còn lại là ước tính và không tự ngắt máy.

## Nạp tiền hoặc xem trước ưu đãi có tạo điểm thành viên không?

Không. Điểm được ghi từ phí chơi hợp lệ trên hóa đơn đã thanh toán. Xem trước
ưu đãi không tạo giao dịch, không cộng tiền và không giữ ưu đãi đến lúc nạp thật.

## Trợ lý có thể trả lời mọi câu hỏi về tài khoản không?

Trợ lý tài liệu chỉ giải thích chính sách đã được duyệt. Muốn xem số dư, điểm,
hóa đơn hoặc ưu đãi cá nhân đang có, khách mở các màn tương ứng sau khi đăng nhập.
Trợ lý không được yêu cầu khách cung cấp mật khẩu, mã phiên hoặc bí mật hệ thống.

## Menu đồ ăn, game nhận xu và AI giao dịch đã có chưa?

Menu sách lật, voucher, game và quảng cáo nhận thưởng thuộc kế hoạch bàn giao,
chưa được mô tả là tính năng đang hoạt động trong kho này. Đợt 5A chỉ xây trợ lý
đọc tài liệu; AI không tự nạp tiền, thanh toán hoặc cấp voucher.

## Nguồn đối chiếu

- `src/cyberhub_manager/domain/models.py` — minimum_balance, MINIMUM_SESSION_MINUTES
- `docs/CUSTOMER_PORTAL_PHASE1.md`
- `docs/CUSTOMER_PORTAL_PHASE2.md`
- `docs/HANDOVER_BUSINESS_DISCUSSION.md`
