# AI Đợt 5B–5C — Phân tích vận hành và gợi ý cá nhân

Ngày cập nhật: 10/11/2026 (Asia/Ho_Chi_Minh).

## Phạm vi đã triển khai

### Đợt 5B — phân tích dữ liệu

- Tổng hợp doanh thu 7, 30 hoặc 90 ngày và so sánh với kỳ liền trước.
- Liệt kê ngày thấp hơn 60% doanh thu trung bình kỳ.
- Tổng hợp máy theo số phiên, số phút tính phí và doanh thu.
- Tổng hợp khung giờ tạo doanh thu để hỗ trợ chọn thời điểm khuyến mãi.
- `STAFF` và `CUSTOMER` không được dùng chế độ này.
- `MANAGER` chỉ nhận dữ liệu cơ sở đang phụ trách.
- `ADMIN` nhận snapshot hợp nhất của tất cả cơ sở đang hoạt động.

### Đợt 5C — gợi ý dịch vụ cá nhân

- Chỉ dành cho khách hàng đang đăng nhập.
- Gợi ý từ hạng/điểm, chi tiêu 30 ngày, ưu đãi đủ điều kiện, menu còn phục vụ,
  voucher đang hoạt động, ví xu, lượt quay và quảng cáo nhận thưởng.
- Không gửi số điện thoại, mật khẩu, tên đăng nhập, mã voucher hoặc dữ liệu khách
  khác sang model.
- AI chỉ tư vấn; không tự đặt món, đổi xu, dùng voucher hoặc cộng thưởng.

## Luồng bảo mật

```text
Người dùng chọn chế độ và đặt câu hỏi
→ Flask xác thực session + CSRF
→ Backend tải lại vai trò/cơ sở hoặc customer principal
→ Service nghiệp vụ kiểm tra quyền và truy vấn dữ liệu
→ Backend tạo snapshot tổng hợp, loại dữ liệu nhận dạng
→ Prompt builder kiểm tra audience và store scope
→ Model chỉ nhận snapshot đã lọc
→ Backend kiểm tra lại danh tính sau khi model trả lời
→ Câu trả lời có nguồn runtime và audit metadata
```

Model không nhận connection, repository, SQL, API thao tác hoặc quyền gọi tool.

## API

`POST /api/assistant/messages`

```json
{
  "question": "Tóm tắt doanh thu và ngày thấp bất thường",
  "language": "vi",
  "mode": "analytics",
  "days": 30
}
```

Các mode:

- `knowledge`: RAG tài liệu 5A.
- `analytics`: 5B, chỉ `MANAGER`/`ADMIN`.
- `personalized`: 5C, chỉ `CUSTOMER`; có thể gửi `store_id` hợp lệ.

Client không được gửi `role`, `store_ids`, `actor_id`, context hoặc dữ liệu tự dựng.

## Chạy web với API key

Giống 5A:

```powershell
python -m scripts.run_rag_gemini --port 8059
```

Thêm `GEMINI_API_KEY` vào `.env` trước khi chạy. Sau khi đăng nhập, mở **Hỏi CyberHub**
và chọn chế độ trong thanh công cụ. Embedding, trả lời và kiểm chứng dùng Gemini API;
snapshot Phân tích/Gợi ý đã lọc theo quyền cũng được gửi tới Google.

Tài khoản demo:

- Manager: `quanly01 / demo123` — thấy Tài liệu và Phân tích.
- Admin: `admin01 / demo123` — Phân tích nhiều cơ sở.
- Staff: `nhanvien01 / demo123` — chỉ Tài liệu.
- Customer: `nguyenvanan / demo123` tại `/customer` — thấy Tài liệu và Gợi ý cho tôi.

## Kiểm thử

```powershell
python -m pytest tests/unit/test_ai_phases_5b_5c.py -q
python -m pytest tests/integration/test_report_flow.py -q
node --check src/cyberhub_manager/web/static/assistant_live.js
```

Các test bao gồm chống vượt vai trò/cơ sở, snapshot MySQL thật, không rò số điện
thoại/mã voucher, nguồn động ngoài scope bị từ chối trước khi gọi model và kiểm tra
audit `AI_REVENUE_ANALYSIS`.

## Giới hạn có chủ đích

- Phân tích là hỗ trợ quyết định, không phải dự báo tài chính bảo đảm chính xác.
- Ngày doanh thu thấp dùng ngưỡng kỹ thuật 60% trung bình kỳ; quản lý phải đối
  chiếu ngày nghỉ, sự cố và sự kiện trước khi chạy khuyến mãi.
- Tình trạng món/voucher/lượt thưởng có thể thay đổi sau thời điểm snapshot; người
  dùng phải xác nhận lại trên màn hình chức năng trước khi thao tác.
