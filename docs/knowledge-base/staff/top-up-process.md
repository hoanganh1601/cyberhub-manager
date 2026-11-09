---
id: staff-top-up-process
title: Quy trình nạp tiền và áp dụng khuyến mãi
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - top-up
  - wallet
  - promotion
---

# Quy trình nạp tiền và áp dụng khuyến mãi

## Nhận và xác nhận tiền

1. Chọn đúng khách hàng, kiểm tra cơ sở đang vận hành.
2. Nhập số tiền nguyên từ 1 đến 100.000.000 VND và phương thức CASH hoặc TRANSFER.
3. Xem trước số tiền chính và thưởng dự kiến.
4. Chỉ xác nhận sau khi nhận tiền theo quy trình quầy.
5. Kiểm tra kết quả, số dư và lịch sử giao dịch sau khi lưu thành công.

AI không xác nhận đã nhận tiền hoặc thực hiện nạp thay nhân viên.

## Chính sách thưởng

Backend chọn một chính sách thỏa đồng thời: đang bật, đúng thời gian, đúng cơ sở
hoặc toàn hệ thống, đủ mốc nạp và đủ điều kiện hạng/điểm/khách hàng mục tiêu.
Ưu tiên mốc cao nhất, rồi cơ sở, khách riêng, hạng, điểm và ID mới hơn.
Không cộng chồng thưởng, không gộp các lần nạp riêng để đạt mốc.

Thưởng = phần nguyên của số tiền nạp × phần trăm / 100. Khoảng hiệu lực gồm
thời điểm bắt đầu, không gồm thời điểm kết thúc. Xem trước không giữ chính sách;
khi xác nhận hệ thống đọc lại điều kiện và số dư trong transaction.

## Giao dịch ví

Tiền chính ghi TOP_UP; tiền thưởng ghi PROMOTION riêng nếu có. Cả hai được lưu
cùng transaction với cập nhật ví, tránh trạng thái chỉ cộng một phần.
Số dư tổng = chính + thưởng; thưởng dùng trước cho phí chơi, không đổi tiền mặt.
Nạp tiền không tự tạo điểm thành viên.

## Tài khoản bị khóa và tiền bù

Nghiệp vụ hiện có cho phép nhân viên nạp để trả nợ dù tài khoản khóa hoặc khách
ngừng hoạt động; điều này không tự mở khóa hay cho mở phiên mới.
Trong trường hợp khách/tài khoản không hoạt động, chỉ xét ưu đãi công khai,
không dùng ưu đãi cá nhân hóa.

Khoản DEBT_SETTLEMENT khi checkout là tiền bù thiếu, không phải TOP_UP;
không áp dụng thưởng nạp tiền và không cộng lần thứ hai vào phí chơi.

## Nguồn đối chiếu

- `src/cyberhub_manager/services/wallet_service.py`
- `src/cyberhub_manager/domain/p1.py` — quote_top_up
- `docs/P1_DESKTOP_WEB.md` — Quy tắc nghiệp vụ
- `docs/CUSTOMER_PORTAL_PHASE3.md` — Ưu đãi cá nhân hóa
