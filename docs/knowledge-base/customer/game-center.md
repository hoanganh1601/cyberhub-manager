---
id: customer-game-center
title: Game Center, xu và phần thưởng
audience:
  - CUSTOMER
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-15
tags:
  - game
  - coins
  - rewards
  - ads
---

# Game Center, xu và phần thưởng

## Trò chơi hiện có

Game Center trong cổng khách có vòng quay may mắn, Cyber 2048, Snake Arena và
Puzzle ký ức. Bubble Blast và Candy Match là vị trí game tài trợ đang ở trạng
thái chưa mở. Danh mục và trạng thái hoạt động do backend công bố.

Cyber 2048 hoàn thành khi đạt ô 128; Snake Arena hoàn thành khi ăn đủ 5 mục tiêu;
Puzzle ký ức hoàn thành khi ghép đủ 6 cặp. Điểm số và thao tác game chạy trên
trình duyệt chỉ phục vụ trải nghiệm, không được dùng làm số xu tin cậy.

## Lượt chơi và nhận xu

Hoàn thành mini-game mở nút nhận thưởng. Backend tự chọn kết quả, ghi phiên chơi
và cộng xu trong cùng giao dịch; trình duyệt không gửi số xu hoặc ô trúng. Lượt
nhận thưởng dùng chung hạn mức trong ngày với vòng quay. Mức mặc định của demo là
3 lượt/ngày theo giờ Việt Nam nhưng Admin có thể cấu hình khác. Xem hết quảng cáo
nhận thưởng hợp lệ có thể cấp thêm lượt. Thao tác quá nhanh hoặc lặp bất thường
có thể làm ví game bị khóa để nhân viên kiểm tra.

## Đổi phần thưởng

Xu game tách biệt với tiền ví và điểm thành viên, không đổi thành tiền mặt. Khách
dùng xu để đổi các mục đang hoạt động trong cửa hàng phần thưởng. Mỗi lần đổi tạo
voucher cho chính tài khoản; gửi lại cùng khóa yêu cầu không bị trừ xu hai lần.
Voucher có thể là thời gian chơi, giảm giá đồ ăn hoặc điểm thành viên. Với voucher
điểm, điểm không được cộng trực tiếp lúc chơi game mà chỉ cộng khi voucher được
xác nhận sử dụng theo quy trình voucher.

## Quảng cáo và game tài trợ

Xem quảng cáo là tự nguyện. Quảng cáo nội bộ có thời lượng tối thiểu và hạn mức
theo ngày; chỉ sự kiện hoàn thành hợp lệ mới cấp thưởng. Các vị trí game đối tác
chưa mở không tạo lượt chơi hoặc phần thưởng. Trợ lý AI không thể chơi, hoàn thành
quảng cáo, cộng xu hay đổi voucher thay khách.

## Nguồn đối chiếu

- `history/docs/features/GAME_CENTER_PHASE6.md` — Phạm vi Game Center và mô hình tài trợ
- `src/cyberhub_manager/application/services/game_service.py` — Lượt chơi, ví xu và đổi thưởng
- `src/cyberhub_manager/application/services/ad_service.py` — Quảng cáo nhận thưởng
