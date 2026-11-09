---
id: staff-machine-operation
title: Quy trình vận hành máy và mở phiên
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - machine
  - session
  - operation
---

# Quy trình vận hành máy và mở phiên

## Điều kiện mở phiên

Nhân viên đang hoạt động, có quyền vận hành tại cơ sở của máy. Máy phải còn phục vụ,
trạng thái AVAILABLE, không bảo trì, không có phiên ACTIVE. Khách và tài khoản
phải đang hoạt động; khách chưa có phiên ACTIVE khác.

Số dư tối thiểu đủ 30 phút theo đơn giá máy; mức yêu cầu được làm tròn lên đến VND.
Ví dụ đơn giá 10.000 VND/giờ cần tối thiểu 5.000 VND. Đây là quy tắc mở phiên,
không phải thu trước phí 30 phút hoặc tự dừng máy sau 30 phút.

## Luồng mở phiên

1. Chọn đúng máy và khách hàng tại màn Tổng quan.
2. Xem thông tin và kết quả kiểm tra trước khi mở phiên.
3. Xác nhận mở; backend kiểm tra lại quyền, trạng thái, số dư và trùng phiên.
4. Ghi nhận thời điểm bắt đầu và đơn giá tại thời điểm mở.
5. Máy chuyển sang IN_USE khi giao dịch thành công.

Một máy hoặc một khách không được có hai phiên ACTIVE đồng thời. Nếu dữ liệu
thay đổi trong lúc thao tác, xem lại trạng thái rồi thực hiện theo kết quả backend.
Không cố mở bằng cách sửa request hoặc ghi SQL trực tiếp.

## Bảo trì và phân loại phòng

STAFF vận hành phiên, không mặc định có quyền thêm/sửa máy hoặc chuyển bảo trì.
Các thao tác quản lý máy và phân phòng thuộc Manager/Admin theo cơ sở vận hành.
Máy đang có phiên phải kết thúc phiên trước khi đổi phòng. Đổi STANDARD/VIP
không tự thay đổi giá giờ hoặc trạng thái sử dụng.

## Kết thúc phiên

Dùng luồng thanh toán để kết thúc phiên, xử lý khoản thiếu chính xác trước khi
xác nhận. Không chuyển tay máy về AVAILABLE để bỏ qua thanh toán. Nếu hệ thống
báo đã checkout, đối chiếu hóa đơn và trạng thái mới trước khi thao tác tiếp.

## Nguồn đối chiếu

- `src/cyberhub_manager/services/session_service.py`
- `src/cyberhub_manager/domain/models.py` — minimum_balance, UsageSession
- `docs/P1_DESKTOP_WEB.md` — Phân quyền
- `docs/CUSTOMER_PORTAL_PHASE2.md` — Quản lý phân loại phòng
