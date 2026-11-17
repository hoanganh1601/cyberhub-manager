---
id: customer-membership-policy
title: Chính sách điểm và hạng thành viên
audience:
  - CUSTOMER
status: APPROVED
version: 2
language: vi
updated_at: 2026-11-15
tags:
  - loyalty
  - points
  - membership
---

# Chính sách điểm và hạng thành viên

## Tích điểm

Mặc định mỗi 10.000 VND phí chơi hợp lệ trên từng hóa đơn PAID được 1 điểm,
làm tròn xuống riêng từng hóa đơn. Không cộng phần lẻ giữa các hóa đơn.
Phí hợp lệ = phí chơi trừ phần dùng từ số dư khuyến mãi.
Tiền chính và tiền bù trong phí chơi được tính, không cộng tiền bù lần thứ hai.
Nạp tiền chưa phải chi tiêu chơi nên không tự tạo điểm.

Ví dụ minh họa với mức mặc định: phí chơi 25.000 VND, đã dùng thưởng 5.000 VND,
phí hợp lệ 20.000 VND, nhận 2 điểm. Đây không phải số liệu tài khoản hiện tại.

## Hạng thành viên

Hạng dựa trên tổng chi tiêu hợp lệ của các hóa đơn PAID tại toàn bộ cửa hàng:

| Hạng | Chi tiêu hợp lệ tối thiểu mặc định |
|---|---:|
| Đồng | 0 VND |
| Bạc | 1.000.000 VND |
| Vàng | 3.000.000 VND |
| Kim cương | 5.000.000 VND |

Các mốc và tỷ lệ tích điểm có thể do Admin thay đổi. Muốn biết hạng, điểm và mốc
đang áp dụng, xem màn Thành viên của tài khoản. Mã nội bộ Kim cương là PLATINUM.

## Hóa đơn hủy và thay đổi cấu hình

Hóa đơn VOID không tạo điểm hiệu lực hoặc chi tiêu xét hạng; hủy hóa đơn có thể
làm giảm điểm, hạng và quyền nhận ưu đãi. Đổi tỷ lệ không tính lại điểm hóa đơn cũ.
Đổi mốc hạng có thể thay đổi hạng theo tổng chi tiêu hợp lệ hiện có.
Tạm dừng tích điểm mới không xóa điểm cũ, chi tiêu hợp lệ vẫn được tính cho hạng.

## Điểm có đổi tiền hay hết hạn không?

Điểm không phải tiền ví, không đổi tiền mặt và hiện không có thời hạn điểm/hạng.
Xem ưu đãi không tự trừ điểm. Xu game cũng là đơn vị riêng, không phải điểm thành
viên và không chuyển thẳng thành tiền hoặc điểm. Khách có thể dùng xu đổi một
voucher loại `MEMBER_POINTS` nếu phần thưởng đó đang hoạt động; điểm chỉ được cộng
khi voucher được xác nhận sử dụng theo nghiệp vụ voucher. Giá xu và số điểm nằm
trong ảnh chụp danh mục tại thời điểm xem, không phải tỷ lệ quy đổi cố định.

## Nguồn đối chiếu

- `docs/features/CUSTOMER_PORTAL_PHASE3.md` — Chính sách được người dùng phê duyệt
- `src/cyberhub_manager/domain/loyalty.py`
- `src/cyberhub_manager/services/game_service.py`
- `src/cyberhub_manager/services/voucher_service.py`
