# Tài liệu bàn giao nghiệp vụ — Phân quyền, menu, game và AI

Ngày ghi nhận: 09/11/2026  
Dự án: CyberHub Manager

Tài liệu này tổng hợp hai phiên thảo luận nghiệp vụ để bàn giao cho người tiếp tục phân tích và triển khai. Đây là định hướng nghiệp vụ, chưa phải đặc tả kỹ thuật hoàn chỉnh.

Bản cập nhật tiến độ, các việc Đợt 0 còn thiếu, checklist Đợt 1–4 và phần RAG 5A
đã làm/cần tiếp tục nằm tại
[Bàn giao công việc tiếp theo — 09/11/2026](HANDOVER_NEXT_PHASES_2026-11-09.md).

## 1. Phân quyền nhân viên và doanh thu

### Vấn đề cần xử lý

Hiện nhân viên (`STAFF`) không nên mặc định xem được doanh thu của quán. Việc chỉ ẩn menu trên giao diện là chưa đủ; backend cũng phải chặn route và API tương ứng.

### Ma trận quyền đề xuất

| Vai trò | Phạm vi chức năng |
|---|---|
| `STAFF` | Quản lý máy, phiên chơi, khách hàng, hóa đơn và thanh toán trong phạm vi cửa hàng được phân công |
| `MANAGER` | Toàn bộ quyền vận hành của `STAFF`, thêm doanh thu và báo cáo của cửa hàng được phân công |
| `ADMIN` | Toàn hệ thống: doanh thu, báo cáo, cấu hình, phân quyền, cửa hàng và dữ liệu quản trị |

### Yêu cầu bắt buộc

- `STAFF` không thấy mục Doanh thu trên sidebar.
- `STAFF` không truy cập được trang doanh thu bằng URL trực tiếp.
- API doanh thu phải trả lỗi phân quyền nếu tài khoản là `STAFF`.
- `MANAGER` chỉ xem dữ liệu cửa hàng được gán, không xem cửa hàng khác.
- `ADMIN` xem được toàn bộ cửa hàng theo phạm vi hệ thống.
- Các thao tác nhạy cảm phải được ghi audit log.
- Kiểm thử cả giao diện, route trực tiếp và gọi API thủ công.

### Tiêu chí nghiệm thu

1. Đăng nhập bằng `STAFF`: không có menu Doanh thu và không mở được API doanh thu.
2. Đăng nhập bằng `MANAGER`: xem được báo cáo đúng cửa hàng được phân công.
3. Đăng nhập bằng `ADMIN`: xem được dữ liệu toàn hệ thống.
4. Đổi vai trò hoặc cửa hàng được phân công phải có hiệu lực sau khi phiên đăng nhập được xác thực lại.

## 2. Menu đồ ăn dạng sách lật

### Mục tiêu

Tạo một khu menu đồ ăn và đồ uống chuyên nghiệp trên web khách hàng, giúp khách xem món và thúc đẩy gọi món khi đang chơi.

### Cấu trúc menu đề xuất

- Trang 1: món chính, đồ ăn nhanh, món ăn vặt và combo.
- Trang 2: nước ngọt, trà, cà phê và nước tăng lực.
- Phong cách: nền tối, xanh cyan và cam/gold, đồng bộ nhận diện CyberHub.
- Sử dụng hình ảnh và nội dung tự thiết kế, không sao chép logo hoặc watermark của mẫu tham khảo.

### Chức năng giao diện

- Hiệu ứng lật trang trên desktop.
- Nút chuyển trang và hỗ trợ vuốt trên mobile.
- Hiển thị ảnh, tên món, mô tả ngắn, giá và trạng thái còn món.
- Nút “Đặt món” hoặc “Gọi nhân viên”.
- Có thể thay đổi menu theo từng cửa hàng.
- Giao diện vẫn rõ ràng khi không tải được ảnh.

### Quản trị menu

- Thêm, sửa, ẩn món.
- Quản lý nhóm món, giá, ảnh và thứ tự hiển thị.
- Có thể bật/tắt món theo cửa hàng.
- Lưu lịch sử thay đổi giá và trạng thái bán.

## 3. Khu trò chơi và phần thưởng

### Nguyên tắc nghiệp vụ

Tách rõ ba loại giá trị:

```text
Điểm game → Voucher/phần thưởng → Điểm thành viên
```

Không cho đổi trực tiếp điểm game thành tiền mặt. Voucher phải có hạn sử dụng, điều kiện áp dụng và cơ chế sử dụng một lần.

### Game phù hợp giai đoạn đầu

- Vòng quay may mắn có giới hạn lượt.
- Quiz kiến thức game.
- Lật thẻ tìm cặp.
- Game phản xạ nhanh.
- Thử thách theo ngày.

### Phần thưởng có thể cung cấp

- Giảm giá đồ ăn.
- Tặng nước hoặc combo.
- Giảm giá giờ chơi.
- Tặng điểm thành viên.

### Chống gian lận

- Kết quả game và phần thưởng phải được xác nhận ở backend.
- Không tin điểm hoặc phần thưởng do trình duyệt gửi lên.
- Giới hạn lượt chơi và phần thưởng mỗi ngày.
- Ghi lịch sử game, quảng cáo và đổi voucher.
- Phát hiện nhiều tài khoản, spam và hành vi tự động hóa.
- Voucher phải có mã, thời hạn, trạng thái và lịch sử đổi.

### Quảng cáo

Có thể cho người chơi xem quảng cáo để mở thêm lượt hoặc nhận phần thưởng, nhưng cần:

- Tuân thủ chính sách của mạng quảng cáo.
- Không ép người dùng xem quảng cáo để sử dụng chức năng cơ bản.
- Chống giả lượt xem và giả sự kiện hoàn thành quảng cáo.
- Không cam kết doanh thu cố định từ quảng cáo.

### Luồng nghiệp vụ đề xuất

```text
Người chơi
  ↓
Chơi game hoặc xem quảng cáo hợp lệ
  ↓
Nhận xu game
  ↓
Đổi phần thưởng theo danh mục
  ↓
Voucher lưu vào tài khoản
  ↓
Nhân viên xác nhận khi khách sử dụng
```

### Nhóm dữ liệu dự kiến

- `games`
- `game_sessions`
- `game_rewards`
- `game_wallets`
- `reward_catalog`
- `customer_vouchers`
- `voucher_redemptions`
- `ad_reward_events`

## 4. Đề xuất áp dụng LLM/AI

AI nên hỗ trợ tư vấn và phân tích, không trực tiếp quyết định nghiệp vụ tài chính.

### Chức năng phù hợp

- Tư vấn món ăn và combo theo ngân sách, thời gian chơi và sở thích.
- Gợi ý ưu đãi cá nhân hóa.
- Trợ lý cho nhân viên tra cứu quy trình.
- Tóm tắt doanh thu và cảnh báo bất thường.
- Tạo nội dung quảng bá món, game và khuyến mãi.
- Phân tích phản hồi khách hàng.
- Cảnh báo hành vi game bất thường.

### Ví dụ

Khách hỏi: “Tôi có 50.000 điểm và đang chơi phòng VIP, nên gọi gì?”  
AI có thể gợi ý combo phù hợp và ưu đãi hiện có, nhưng hệ thống backend vẫn phải kiểm tra số dư, hạng thành viên, giá và điều kiện voucher.

### AI không được tự quyết định

- Cộng hoặc trừ tiền.
- Cấp voucher không giới hạn.
- Xác nhận thanh toán hoặc hoàn tiền.
- Thay đổi hạng thành viên.
- Ghi nhận điểm thưởng mà không qua rule/backend.

## 5. Chia thành các đợt triển khai

### Đợt 0 — Chốt nghiệp vụ và phân quyền nền tảng

Phạm vi:

- Chốt ma trận `STAFF`, `MANAGER`, `ADMIN` ở mục 1.
- Chặn doanh thu ở cả sidebar, route và API.
- Xác định cửa hàng mà từng `MANAGER` được phép xem.
- Bổ sung audit log cho truy cập báo cáo và thay đổi cấu hình.

Tiêu chí nghiệm thu:

- `STAFF` không xem được doanh thu dù truy cập URL/API trực tiếp.
- `MANAGER` chỉ xem đúng cửa hàng được phân công.
- `ADMIN` xem được toàn hệ thống.
- Có test quyền ở backend và test điều hướng ở frontend.

### Đợt 1 — Menu đồ ăn và đồ uống

Phạm vi:

- Tạo menu sách lật gồm một trang đồ ăn và một trang đồ uống.
- Thiết kế theo nhận diện CyberHub, dùng ảnh/nội dung tự xây dựng.
- Responsive desktop/mobile, hỗ trợ nút lật và vuốt trên mobile.
- Hiển thị món, giá, ảnh, trạng thái còn món.
- Trang quản trị thêm/sửa/ẩn món, nhóm món, giá, ảnh và thứ tự.

Tiêu chí nghiệm thu:

- Khách xem menu tốt trên desktop và điện thoại.
- Món hết hàng không thể được chọn.
- Menu có thể thay đổi theo cửa hàng.
- Không làm ảnh hưởng luồng đăng nhập, hồ sơ và thanh toán hiện tại.

### Đợt 2 — Voucher và phần thưởng cơ bản

Phạm vi:

- Tạo danh mục phần thưởng: giảm đồ ăn, tặng nước, giảm giờ chơi, tặng điểm.
- Voucher có mã, hạn sử dụng, điều kiện, trạng thái và lịch sử sử dụng.
- Khách xem voucher trong tài khoản.
- Nhân viên xác nhận voucher khi khách sử dụng.
- Không quy đổi phần thưởng thành tiền mặt.

Tiêu chí nghiệm thu:

- Voucher chỉ dùng được đúng đối tượng và điều kiện.
- Voucher đã dùng không thể dùng lại.
- Hết hạn hoặc bị khóa phải bị từ chối.
- Mọi lần phát hành và sử dụng đều có audit log.

### Đợt 3 — Game đầu tiên và xu game

Phạm vi:

- Bắt đầu bằng một game đơn giản, ưu tiên vòng quay hoặc quiz.
- Giới hạn lượt chơi theo tài khoản và theo ngày.
- Kết quả được xác nhận ở backend.
- Xu game là đơn vị riêng, không phải tiền và không phải điểm thành viên.
- Cho đổi xu game sang voucher theo danh mục đã cấu hình.

Tiêu chí nghiệm thu:

- Không thể tự sửa điểm bằng request từ trình duyệt.
- Có lịch sử phiên chơi, kết quả, xu nhận và xu đã đổi.
- Không thể đổi vượt số dư hoặc đổi trùng giao dịch.
- Có cơ chế khóa tài khoản/game khi phát hiện bất thường.

### Đợt 4 — Quảng cáo nhận thưởng

Phạm vi:

- Cho phép xem quảng cáo hợp lệ để mở thêm lượt hoặc nhận phần thưởng.
- Tích hợp server-side verification nếu nền tảng quảng cáo hỗ trợ.
- Giới hạn tần suất và phần thưởng mỗi ngày.
- Ghi nhận sự kiện quảng cáo độc lập với kết quả game.

Tiêu chí nghiệm thu:

- Không cộng thưởng chỉ dựa vào tín hiệu không đáng tin từ client.
- Chống gửi lại cùng một sự kiện quảng cáo.
- Có thống kê lượt xem, lượt hợp lệ và phần thưởng đã cấp.
- Nội dung và cách hiển thị tuân thủ chính sách mạng quảng cáo.

### Đợt 5 — AI hỗ trợ khách hàng và nhân viên

Phạm vi:

- AI tư vấn món, combo và ưu đãi phù hợp.
- AI trả lời quy trình cho nhân viên dựa trên tài liệu nội bộ.
- AI tóm tắt doanh thu, phản hồi và cảnh báo bất thường.
- Có log truy vấn và cơ chế giới hạn dữ liệu nhạy cảm.

Giới hạn bắt buộc:

- AI không tự cộng/trừ tiền, cấp voucher, đổi hạng hoặc xác nhận thanh toán.
- Mọi kết quả liên quan tiền, điểm và voucher phải được backend kiểm tra lại.
- Có câu trả lời dự phòng khi AI không chắc chắn.

### Thứ tự ưu tiên bàn giao

```text
Đợt 0: Phân quyền
   ↓
Đợt 1: Menu
   ↓
Đợt 2: Voucher
   ↓
Đợt 3: Game và xu game
   ↓
Đợt 4: Quảng cáo nhận thưởng
   ↓
Đợt 5C: AI kết nối menu/voucher/game đã hoàn thiện
```

Quảng cáo nhận thưởng cần game/voucher, audit và cơ chế chống gian lận ổn định.
Riêng **Đợt 5A (RAG hỏi đáp tài liệu)** do Hoàng Anh phụ trách, được làm song song
với Đợt 1–4; bước 1–2 đã có trên branch `feat/rag-knowledge-assistant`.
Đợt 5B phân tích số liệu cần quyền và API báo cáo, còn 5C tư vấn dịch vụ cần các
module tương ứng. Người nhận có thể ưu tiên Đợt 1–4 theo checklist bàn giao mới.
