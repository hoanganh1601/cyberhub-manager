# Game Center khách hàng

## Phạm vi đã triển khai

Game Center trong cổng khách hàng hiện có bốn trải nghiệm hoạt động:

- Vòng quay may mắn do máy chủ quyết định kết quả.
- Cyber 2048, hoàn thành khi đạt ô 128.
- Snake Arena, hoàn thành khi ăn đủ 5 mục tiêu.
- Puzzle ký ức, hoàn thành khi ghép đủ 6 cặp.

Bubble Blast và Candy Match là hai vị trí mẫu dành cho game tài trợ, hiện ở trạng thái
chưa mở. Danh mục và trạng thái hoạt động được backend công bố; trình duyệt chỉ dựng
giao diện và chạy engine game nội bộ.

Khi khách hoàn thành mini-game, frontend chỉ yêu cầu một lượt nhận thưởng. Backend tự
chọn kết quả, áp giới hạn lượt/ngày, khoảng cách giữa hai lượt và khóa ví khi có hành vi
bất thường. Điểm số trong trình duyệt không được dùng để tính số xu. Xu game tách biệt
với tiền trong tài khoản và điểm thành viên; khách dùng xu tại cửa hàng phần thưởng để
đổi voucher, thời gian chơi hoặc voucher cộng điểm.

Quảng cáo nhận thưởng hiện dùng luồng quảng cáo nội bộ sẵn có. Việc xem quảng cáo hoàn
thành có thể cấp lượt quay bổ sung; quảng cáo không tự cộng tiền hoặc điểm từ dữ liệu do
trình duyệt gửi lên.

## Mô hình doanh thu đề xuất

1. Quảng cáo nhận thưởng: tính phí theo lượt xem hợp lệ hoặc chiến dịch cố định.
2. Game tài trợ: đối tác thuê vị trí trong danh mục và gắn nhận diện thương hiệu.
3. Chiến dịch đồng tài trợ: đối tác tài trợ voucher/giải thưởng, CyberHub cung cấp lượt
   chơi và báo cáo tương tác.
4. Game ngoài hệ thống: chỉ tích hợp qua manifest được quản trị duyệt; không cho mã của
   đối tác truy cập cookie, API nội bộ hoặc tự cộng thưởng.

## Bước tiếp theo để cho đối tác thuê game thật

- Thêm bảng đối tác, hợp đồng, game manifest, chiến dịch, ngân sách và thống kê impression,
  start, complete, reward, click.
- Chạy game đối tác trong iframe có `sandbox`, CSP và allowlist domain; giao tiếp bằng
  `postMessage` với schema và chữ ký phiên do backend cấp.
- Dùng play ticket một lần, thời hạn ngắn và transactional ledger để cấp thưởng idempotent.
- Có trạng thái duyệt `DRAFT → REVIEW → ACTIVE → PAUSED → EXPIRED`, audit mọi lần đổi
  cấu hình và nút dừng khẩn cấp.
- Không lấy điểm số client làm căn cứ tiền thưởng. Nếu giải đấu cần xếp hạng, backend phải
  xác minh replay/sự kiện hoặc dùng engine chạy phía máy chủ.
