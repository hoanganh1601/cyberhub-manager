# Đối tác game, quảng cáo và đối soát doanh thu

Migration `024_commercial_partners.sql` bổ sung lớp thương mại cho P1 mà không
thay thế các game/quảng cáo nội bộ đã có. Mọi thao tác ghi chạy trong transaction
và mọi API quản trị đều kiểm tra permission ở service, không tin việc ẩn nút ở UI.

## Phạm vi dữ liệu

- `commercial_partners`: hồ sơ đối tác. Chỉ lưu **tên biến môi trường** chứa bí
  mật callback, không lưu bí mật trong database hoặc response.
- `commercial_contracts`: snapshot mô hình doanh thu `CPM/CPC/CPA/FIXED`, đơn
  giá và kỳ hiệu lực. Người tạo không được tự kích hoạt hợp đồng.
- `commercial_campaigns`: lịch chạy, ngân sách và cấu hình phần thưởng.
- `commercial_placements`: vị trí banner/rewarded-ad/game theo cửa hàng hoặc
  toàn hệ thống.
- `commercial_events`: ledger bất biến, có khóa idempotency của CyberHub và mã
  sự kiện duy nhất của đối tác.
- `commercial_reward_grants`: outbox phần thưởng. Callback hợp lệ chỉ tạo bản
  ghi `PENDING`; worker nội bộ mới được áp dụng xu/voucher rồi chuyển `APPLIED`.
- `commercial_settlements` và `commercial_settlement_lines`: kỳ đối soát cùng
  snapshot số lượng, đơn giá và thành tiền. Điều chỉnh khác 0 bắt buộc có lý do.

## Vòng đời và quyền

1. `ADMIN` tạo đối tác và hợp đồng ở trạng thái `DRAFT`.
2. Một `ADMIN` khác kích hoạt hợp đồng (maker-checker).
3. `ADMIN` tạo chiến dịch/vị trí và cấu hình URL game HTTPS.
4. `MANAGER` chỉ xem vị trí áp dụng cho cửa hàng hiện tại; không xem hợp đồng,
   bí mật callback hoặc đối soát toàn hệ thống.
5. `ADMIN` tạo đối soát từ event đã xác minh; người tạo không được tự duyệt.

Permission được cấp tường minh trong `domain/p1.py`. Việc thêm permission mới
không tự động trao quyền cho `MANAGER` hoặc `ADMIN`.

## Ranh giới an toàn của game ngoài

Iframe phải được render bằng đúng dữ liệu launch do server trả về:

```html
<iframe
  sandbox="allow-scripts allow-pointer-lock"
  referrerpolicy="no-referrer"
  src="https://game.example/launch/...">
</iframe>
```

- Không thêm `allow-same-origin`, `allow-forms`, `allow-popups` hoặc quyền điều
  hướng top-level nếu chưa có một review bảo mật riêng.
- CSP `frame-src` phải giới hạn theo `allowed_origin` của placement; kiểm tra
  origin chính xác khi nhận `postMessage`.
- Không đưa session đăng nhập CyberHub, callback secret, dữ liệu khách hoặc API
  token vào URL iframe hay `postMessage`.
- JavaScript đối tác chỉ có thể gửi `IMPRESSION`, `START`, `CLICK`. Các event
  `CLIENT` không được tính doanh thu. Event được tính doanh thu phải đến từ
  callback server đã ký tại `POST /commercial/callback/event`.
- `COMPLETE` chỉ hợp lệ khi server đối tác gọi endpoint SSV và ký HMAC SHA-256.
  Token launch chỉ lưu dưới dạng SHA-256 trong database và hết hạn sau 15 phút.
- Đối tác không có endpoint trực tiếp để cộng xu hay phát voucher. Reward outbox
  phải được worker nội bộ xử lý idempotently theo unique `event_id`.

## Đối soát

- CPM/CPC/CPA chỉ đếm event `accepted=TRUE` có `verification_method` là
  `SERVER` hoặc `SSV`; event trình duyệt không tạo doanh thu.
- `FIXED` ghi một đơn vị và chỉ được đối soát đúng một lần cho toàn bộ ngày
  bắt đầu–kết thúc của hợp đồng. Nếu cần thu cố định theo tháng/quý, phải bổ
  sung `billing_frequency` bằng migration riêng; không tự chia kỳ để tránh tính
  cùng khoản phí nhiều lần.
- Hợp đồng `FIXED` phải có ít nhất một placement để dòng đối soát luôn truy vết
  được nguồn thương mại. Chiến dịch `ENDED` là trạng thái cuối; muốn chạy đợt
  mới phải tạo chiến dịch mới thay vì kích hoạt lại lịch sử cũ.
- `budget_amount` là trần ngân sách vận hành để theo dõi/cảnh báo, không phải
  số tiền được phép âm thầm cắt khỏi đối soát. Event đối tác đã được server xác
  minh vẫn phải xuất hiện trong ledger; muốn chặn nhận event khi hết ngân sách
  cần một chính sách admission riêng và phải báo rõ cho đối tác trước khi chạy.
- Các kỳ không được chồng lấn. `net_amount = gross_amount + adjustment_amount`.
- Điều chỉnh khác 0 cần lý do tối thiểu 5 ký tự và tổng ròng không được âm.
- Người tạo đối soát không được tự duyệt; thanh toán thực tế là bước vận hành
  riêng sau khi đối soát đã `APPROVED`.

## Bí mật callback

Ví dụ đối tác có `callback_secret_ref=CYBERHUB_PARTNER_ACME_SECRET`, môi trường
chạy backend phải khai báo biến cùng tên. Mọi loại đối tác đều phải cấu hình
secret này; database không lưu giá trị bí mật.

Callback hoàn thành game ký HMAC-SHA256 của chuỗi:

```text
<launch_token>\n<provider_event_id>\ncomplete
```

Callback impression/start/click đã xác minh ký một namespace riêng để chữ ký
không thể phát lại chéo giữa hai endpoint:

```text
commercial-event\n<placement_code>\n<provider_event_id>\n<event_type>
```

Không ghi giá trị secret, launch token thô hoặc payload nhạy cảm vào log.
