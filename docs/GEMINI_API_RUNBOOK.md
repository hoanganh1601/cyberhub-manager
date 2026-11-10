# CyberHub với Gemini API

Ứng dụng chạy cả embedding và sinh câu trả lời qua Google API, không tải model và không cần GPU.
Bộ kiểm tra nguồn, phân quyền và audit của ứng dụng vẫn áp dụng.

## Khởi động trong Terminal VS Code

1. Tạo key cho project của bạn tại [Google AI Studio](https://aistudio.google.com/api-keys).
2. Trong `.env` ở thư mục project, thêm:

   ```dotenv
   GEMINI_API_KEY=key_cua_ban
   ```

3. Dừng web cũ bằng Ctrl+C rồi chạy trong venv:

   ```powershell
   python -m scripts.run_rag_gemini --port 8059
   ```

4. Đợi `Gemini RAG ready`, mở `http://127.0.0.1:8059`, đăng nhập và chọn Hỏi CyberHub.
   Helper mặc định dùng dữ liệu demo. Có thể đóng phần mềm chạy model cũ để giải phóng RAM/VRAM.

Không cần cài SDK Google. Không gửi key trong chat, JavaScript hoặc commit `.env` vào Git.

## Model và free tier

Mặc định `GEMINI_MODEL=gemini-3.1-flash-lite` và `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`.
Theo [bảng giá Google](https://ai.google.dev/gemini-api/docs/pricing), các model này có free tier
tại thời điểm cập nhật hướng dẫn (10/11/2026). Khả năng truy cập và quota phụ thuộc project/tài khoản;
key không đảm bảo mọi request đều miễn phí hoặc luôn có quota. Kiểm tra tier/quota của project
trong AI Studio; ứng dụng không tự bật billing, đổi model hay chuyển sang nhà cung cấp khác.

Mỗi lượt trả lời thường dùng một request embedding và hai request sinh/kiểm chứng.
Khởi động tạo index từ các chunk tài liệu bằng embedding theo lô. Cache trong RAM tái sử dụng
chunk không đổi khi tài liệu được cập nhật, nhưng khởi động lại sẽ tạo cache mới.

Ngưỡng truy xuất Gemini mặc định `0.6`, có thể cấu hình qua
`CYBERHUB_GEMINI_MIN_SIMILARITY`. Đây là ngưỡng ban đầu, chưa được hiệu chỉnh bằng API key thật;
cần chạy bộ đánh giá trước khi kết luận chất lượng với model/tài khoản cụ thể.

## Dữ liệu gửi tới Google

Toàn bộ tài liệu APPROVED được gửi để tạo embedding. Khi hỏi, chỉ các nguồn đúng quyền mới
được đưa vào prompt trả lời. Câu hỏi, các đoạn nguồn và phần kiểm chứng được gửi tới Google.
Chế độ Phân tích/Gợi ý cho tôi cũng gửi snapshot đã được backend lọc theo quyền.
Free tier có thể dùng nội dung để cải thiện sản phẩm theo chính sách của Google; ưu tiên dữ liệu demo.
Backend audit chỉ lưu metadata, không lưu key hoặc nội dung hội thoại.

## Cấu hình khác và xử lý lỗi

- `--mode mysql`: dùng dịch vụ nghiệp vụ thật, yêu cầu cấu hình MySQL và secret key hiện có.
- `--runtime-dir <thư_mục>`: đổi nơi lưu audit. Không đặt audit trong thư mục web/static/assets.
- Web thường/WSGI: đặt `CYBERHUB_ASSISTANT_ENABLED=true`,
  `CYBERHUB_ASSISTANT_PROVIDER=gemini`, `GEMINI_API_KEY` và
  `CYBERHUB_ASSISTANT_AUDIT_PATH` là đường dẫn tuyệt đối tới file audit riêng.
- Thiếu key: helper dừng trước khi tạo app và hướng dẫn đặt `GEMINI_API_KEY`.
- Key/quyền không hợp lệ: kiểm tra key và API/project trong AI Studio; thông tin lỗi thô không đưa ra UI.
- Hết quota: backend trả 429, UI thông báo hạn mức và chờ ít nhất 60 giây trước khi thử lại.
  Quota theo ngày cần chờ lâu hơn hoặc kiểm tra dashboard; retry không tự tạo thêm quota.
- Timeout/mất mạng: kiểm tra kết nối; ứng dụng không tự khởi động model trên máy hoặc đổi nhà cung cấp.

Các lệnh cũ `scripts.run_rag_local` và `scripts.evaluate_rag_local` hiện chuyển tiếp sang Gemini API.
Adapter model trên máy đã được gỡ khỏi source; giữ các lệnh chuyển tiếp để tránh đứt workflow cũ.

## Đánh giá bằng API thật

Các lệnh sau tiêu thụ quota Gemini, chỉ chạy khi đã có key và muốn đánh giá:

```powershell
python -m scripts.evaluate_rag_gemini --limit 3 --output "$env:TEMP\rag-gemini-check.json"
python -m scripts.evaluate_rag_gemini --retrieve-only --limit 3 --output "$env:TEMP\rag-gemini-retrieval.json"
```

Báo cáo ghi rõ `gemini-api-real-model`; kết quả cũ trong `docs/testing/RAG_LOCAL_*.json`
là số đo lịch sử của model trước đây và không chứng minh Gemini đã được nghiệm thu.
Xem [các lựa chọn API miễn phí](FREE_API_OPTIONS.md) khi cần nhà cung cấp dự phòng.
