# Trợ lý CyberHub với Gemini API (RAG & Phân tích)

Ứng dụng sử dụng Google Gemini API cho cả embedding, sinh câu trả lời và kiểm chứng nguồn — không cần tải model cục bộ hay GPU. Mọi lớp kiểm tra phân quyền, phạm vi cơ sở, lọc nguồn `APPROVED` và audit đều chạy ở backend.

## 1. Khởi động nhanh

1. Tạo API key tại [Google AI Studio](https://aistudio.google.com/api-keys) và thêm vào `.env` (không commit `.env`):

   ```dotenv
   GEMINI_API_KEY=key_cua_ban
   ```

2. Chạy ứng dụng web kèm trợ lý Gemini:

   ```powershell
   python -m scripts.run_rag_gemini --port 8059
   ```

3. Chờ thông báo `Gemini RAG ready`, mở `http://127.0.0.1:8059`, đăng nhập và bấm **Hỏi CyberHub** (thêm `?assistant=1` để mở khung chat ngay).
   - Mặc định helper chạy chế độ `demo` (`quanly01`, `nhanvien01`, `admin01`, `nguyenvanan` / `demo123`).
   - Thêm `--mode mysql` để chạy với cơ sở dữ liệu MySQL thật.
   - Thêm `--runtime-dir <thư_mục>` để đổi nơi lưu audit SQLite (không đặt trong `static/` hay `assets/`).

## 2. Chế độ hoạt động & Quyền dữ liệu

- **Tài liệu (RAG):** Chỉ nạp và giải thích nguồn có `status: APPROVED` trong `docs/knowledge-base/` đúng với `audience` của vai trò đang đăng nhập. Các tài liệu `DRAFT` (như `manager/revenue-policy.md`) không được lập chỉ mục.
- **Phân tích & Gợi ý:** Backend lọc sẵn snapshot doanh thu/máy theo vai trò và cơ sở (cho `DIRECTOR`/`MANAGER`, hoặc `ADMIN` ở `legacy`) hoặc gợi ý menu/ưu đãi/voucher/game cho chính khách hàng đang đăng nhập trước khi gửi lên model.
- **Giới hạn an toàn:** Trợ lý chỉ đọc — không thực hiện nạp tiền, checkout, hủy đơn, thay đổi tồn kho, sinh SQL hay thay đổi quyền. Không nhận key, model URL, đường dẫn tài liệu hoặc role từ request client.

## 3. Model, hạn mức và cấu hình triển khai

- Mặc định: `GEMINI_MODEL=gemini-3.1-flash-lite`, `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`, ngưỡng tương đồng `CYBERHUB_GEMINI_MIN_SIMILARITY=0.6`.
- Mỗi lượt hỏi sử dụng tối đa 1 request embedding và 2 request LLM (sinh câu trả lời + kiểm chứng). Timeout mỗi API call: 30s; deadline toàn lượt: 60s.
- Hạn mức nội bộ mặc định: 10 request/phút/actor, 100/ngày/actor, 1.000/ngày toàn ứng dụng. Khi hết quota từ Google, backend trả mã `429`.
- Audit được ghi vào SQLite riêng (`runtime/assistant/audit.sqlite3` hoặc `CYBERHUB_ASSISTANT_AUDIT_PATH`), **không** lưu câu hỏi, prompt, câu trả lời hay API key.
- Khi chạy qua WSGI/production: cấu hình `CYBERHUB_ASSISTANT_ENABLED=true`, `CYBERHUB_ASSISTANT_PROVIDER=gemini`, `GEMINI_API_KEY`, và `CYBERHUB_ASSISTANT_AUDIT_PATH` (đường dẫn tuyệt đối).

> **Lưu ý dữ liệu gửi ra ngoài:** Toàn bộ tài liệu `APPROVED` được gửi tới Google để tạo embedding; câu hỏi và snapshot đã lọc theo quyền được gửi khi trả lời. Kiểm tra chính sách gói API trước khi bật trên dữ liệu thật.

## 4. Kiểm thử và đánh giá

Chạy kiểm thử tự động (không gọi API thật, không tốn quota):

```powershell
$aiTests = Get-ChildItem tests/unit/test_ai_*.py | Select-Object -ExpandProperty FullName
python -m pytest @aiTests -q
```

Đánh giá retrieval offline:

```powershell
python -m scripts.evaluate_rag --output "$env:TEMP\rag-offline.json"
```

Đánh giá với Gemini API thật (có tiêu thụ quota):

```powershell
python -m scripts.evaluate_rag_gemini --limit 3 --output "$env:TEMP\rag-gemini-check.json"
python -m scripts.evaluate_rag_gemini --retrieve-only --limit 3 --output "$env:TEMP\rag-gemini-retrieval.json"
```

## 5. Checklist xác minh nhanh trên giao diện

1. Hỏi *"Cần bao nhiêu số dư để mở phiên?"* → giải thích quy tắc đủ 30 phút theo đơn giá máy.
2. Hỏi *"Nạp tiền hỗ trợ phương thức nào?"* → `CASH` hoặc `TRANSFER`.
3. Hỏi *"Tiền bù và tiền khách đưa khác nhau thế nào?"* → tiền bù đúng khoản thiếu, tiền dư trả lại.
4. Khách hàng hỏi cách sửa điện thoại → nhắc yêu cầu xác nhận mật khẩu hiện tại.
5. Bật **Xem nguồn** để kiểm tra citation (`path`, `section`, `version`) đúng phạm vi vai trò.
6. Đăng xuất/đổi vai trò khi đang chờ trả lời → phản hồi cũ bị chặn và xóa khung chat.
