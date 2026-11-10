# RAG 5A — Chạy và kiểm tra bằng Gemini API

Ứng dụng hiện dùng API key cho cả embedding, trả lời và kiểm chứng.
Tài liệu chính: [Gemini API runbook](GEMINI_API_RUNBOOK.md).
Các chế độ Phân tích/Gợi ý được mô tả tại [AI_PHASES_5B_5C.md](AI_PHASES_5B_5C.md).

## Chạy trong Terminal VS Code

Thêm key của bạn vào `.env`:

```dotenv
GEMINI_API_KEY=key_cua_ban
```

Dừng web cũ bằng Ctrl+C rồi chạy trong venv:

```powershell
python -m scripts.run_rag_gemini --port 8059
```

Đợi `Gemini RAG ready` rồi mở `http://127.0.0.1:8059/`.
Helper mặc định dùng dữ liệu demo; `--mode mysql` dùng cấu hình dịch vụ nghiệp vụ thật.
Lệnh cũ `scripts.run_rag_local` cũng chuyển tiếp sang Gemini API.

Tài khoản demo: nhân viên `nhanvien01`, quản lý `quanly01`, admin `admin01`;
mật khẩu `demo123`. Khách mở `/customer`, đăng nhập `nguyenvanan / demo123`.
Sau đăng nhập, bấm **Hỏi CyberHub**; thêm `?assistant=1` để mở chat ngay.

## Kiểm tra chức năng

1. Hỏi “Cần bao nhiêu số dư để mở phiên?”: giải thích quy tắc đủ 30 phút theo đơn giá máy.
2. Hỏi “Nạp tiền hỗ trợ phương thức nào?”: tiền mặt CASH hoặc chuyển khoản TRANSFER.
3. Hỏi “Tiền bù và tiền khách đưa khác nhau thế nào?”: tiền bù đúng khoản thiếu, tiền dư trả lại.
4. CUSTOMER hỏi cách sửa điện thoại: vẫn phải xác nhận mật khẩu trong form bảo mật.
5. Bật EN để kiểm tra ngôn ngữ; đổi ngôn ngữ không cấp thêm quyền nguồn.
6. Bật **Xem nguồn** để xem tên/path/section/version của tài liệu đúng quyền.
7. Kiểm tra đăng xuất/đổi vai trò khi đang chờ: trả lời cũ phải bị chặn, chat được xóa.

Chế độ Tài liệu chỉ giải thích nguồn APPROVED. Snapshot cho Phân tích/Gợi ý được backend
lọc theo vai trò, cơ sở và chính khách hàng trước khi gửi AI. AI không thực hiện giao dịch,
không sinh SQL hoặc thay đổi quyền. Các tài liệu DRAFT không được phục vụ.

## Runtime và hạn mức

Provider mặc định là Gemini. Model lấy từ `GEMINI_MODEL`; embedding lấy từ
`GEMINI_EMBEDDING_MODEL`. Xem giá trị mặc định và free tier trong runbook Gemini.
Không nhận key, model URL, path tài liệu hoặc vai trò từ request chat.

API call có timeout 30 giây; deadline lượt hỏi là 60 giây.
Prompt bị giới hạn theo ngân sách, không cắt âm thầm điều kiện cuối tài liệu.
Mỗi lượt hỏi có một query embedding và tối đa hai lần gọi LLM (sinh/kiểm chứng).
Thiếu nguồn trả thông báo chưa đủ căn cứ; hết quota trả 429; key/quyền sai có mã cấu hình riêng.

Hạn mức nội bộ mặc định: 10 request/phút/actor, 100/ngày/actor, 1.000/ngày toàn app.
Quota nhà cung cấp độc lập với quota nội bộ. Đăng xuất, đổi key trong cùng project hoặc
mở hội thoại mới không tạo thêm quota của Google.

Audit dùng SQLite riêng ở `cyberhub-ai-runtime/assistant/audit.sqlite3` mặc định.
Không lưu câu hỏi, prompt, câu trả lời hay key trong audit. UI giữ hội thoại trong RAM
trình duyệt, tối đa 20 lượt. Nhiều host cần adapter limiter/audit dùng chung.

## Quyền dữ liệu và triển khai

Embedding gửi toàn bộ kho APPROVED tới Google. Prompt trả lời chỉ nhận nguồn đúng quyền.
Câu hỏi và snapshot Phân tích/Gợi ý cũng gửi tới Google; kiểm tra chính sách free tier
trước khi dùng dữ liệu thật. Key chỉ nằm ở backend, không đưa vào JavaScript.

App thường/WSGI cần `CYBERHUB_ASSISTANT_ENABLED=true`, API key và audit path tuyệt đối.
Helper tự cấu hình cờ bật và nơi lưu audit. Triển khai public dùng HTTPS, secret key bền vững
và ổ lưu audit bền vững. Helper không migrate, seed hoặc reset database nghiệp vụ.

## Kiểm thử và đánh giá

Kiểm thử không gọi API thật:

```powershell
$aiTests = Get-ChildItem tests/unit/test_ai_*.py | Select-Object -ExpandProperty FullName
python -m pytest @aiTests -q
```

Đánh giá thật có tiêu thụ quota; bắt đầu với vài câu:

```powershell
python -m scripts.evaluate_rag_gemini --limit 3 --output "$env:TEMP\rag-gemini-check.json"
python -m scripts.evaluate_rag_gemini --retrieve-only --limit 3 --output "$env:TEMP\rag-gemini-retrieval.json"
```

Bỏ `--limit` để chạy toàn bộ fixture; dùng `--questions` để chọn bộ regression khác.
Đọc câu trả lời cùng nguồn: retrieval Hit@3 và citation hợp lệ không chứng minh đúng ngữ nghĩa.
Đợt kiểm chứng bằng model vẫn là xác suất, không thay cho kiểm tra nghiệp vụ.

Các báo cáo ngày 09/11/2026 trong `docs/testing/RAG_LOCAL_*.json` và
[báo cáo nghiệm thu cũ](testing/RAG_5A_LOCAL_ACCEPTANCE_2026-11-09.md)
là lịch sử của provider trước đây. Các số đo đó không phải kết quả Gemini.
