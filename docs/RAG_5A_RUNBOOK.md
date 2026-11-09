# RAG 5A — Chạy và kiểm tra bản tích hợp

Bản local trên branch `feat/rag-knowledge-assistant`. Chat chỉ giải thích tài liệu
APPROVED đúng audience; không đọc số dư thật, không chạy SQL, không gọi thao tác
nạp/trừ tiền, mở/đóng phiên hoặc sửa quyền. Hai tài liệu DRAFT vẫn chưa phục vụ.

## Chạy trên máy hiện tại

```bash
cd /media/icnlab/Data/hoanganh/cyberhub-manager-rag
source .venv/bin/activate
python -m scripts.run_rag_local --host 0.0.0.0 --port 8059
```

Giữ terminal mở. Đây là web có đăng nhập và AI chạy thật trên máy này;
`--mode demo` mặc định dùng dữ liệu nghiệp vụ mẫu. Không nhầm với mô hình AI giả:
embedding, tìm tài liệu và sinh câu trả lời đều chạy qua Ollama local.

- Cùng máy: `http://127.0.0.1:8059/`.
- Máy khác qua Tailscale của máy hiện tại: `http://100.110.233.88:8059/`.
- Qua SSH: chuyển tiếp cổng 8059 rồi mở `http://127.0.0.1:8059/` trên máy cá nhân.
- Bản UI mock độc lập vẫn ở cổng **8058**, không gọi API/model thật.

Tài khoản demo nhân viên: `nhanvien01`, quản lý: `quanly01`, admin: `admin01`;
mật khẩu mẫu `demo123`. Khách mở `/customer`, đăng nhập `nguyenvanan` / `demo123`.
Chỉ dùng các tài khoản này trong chế độ demo, không tái sử dụng mật khẩu cho MySQL
hoặc môi trường thật. Sau đăng nhập, bấm **Hỏi CyberHub**; có thể thêm `?assistant=1`
để mở chat ngay sau đăng nhập.

Kiểm tra lần lượt:

1. STAFF hỏi “Cần bao nhiêu số dư để mở phiên?” — trả lời theo đơn giá và quy tắc
   30 phút, không tự gán một số tiền cố định cho mọi máy.
2. Hỏi “Tiền bù và tiền khách đưa khác nhau thế nào?” — tiền bù bằng đúng khoản
   thiếu, tiền thừa trả khách; muốn nạp vào ví phải đi qua luồng nạp riêng.
3. CUSTOMER hỏi điều kiện sửa điện thoại — vẫn phải xác nhận mật khẩu hiện tại;
   không yêu cầu khách gửi mật khẩu qua chat.
4. Bật EN rồi hỏi lại bằng tiếng Anh. Đổi ngôn ngữ không cấp thêm quyền nguồn.
5. Hỏi số dư thật của một khách hoặc yêu cầu nạp tiền ngay — không thực hiện và
   không đưa ra số liệu cá nhân. STAFF không được đọc hướng dẫn cấu hình ADMIN.
6. Bật “Kiểm tra nguồn” để xem tên/path/section/version của nguồn được phép.
   Bình thường đường dẫn và mã `[S1]` được ẩn cho người vận hành.
7. Đăng xuất — chat và dữ liệu hội thoại được xóa khỏi trang. Thử lại bằng role
   khác để kiểm tra quyền; không dùng checkbox xem nguồn để đổi quyền.

Trong demo, chờ model không giữ khóa thao tác của workspace; đăng xuất hoặc đổi
quyền khi đang chờ làm reply cũ bị chặn trước khi trả nội dung.

Hội thoại/đánh giá hữu ích chỉ nằm trong RAM trình duyệt, tối đa 20 lượt. Không
lưu lịch sử chat server hoặc dùng các lượt trước làm ngữ cảnh suy diễn. Không có
endpoint mở file tùy ý. Metadata nguồn không phải thông tin bí mật của role khác.

## Model và runtime

Ứng dụng không tự tải model hoặc chuyển sang dịch vụ cloud khi gặp lỗi.
Runtime/weights nằm ngoài Git tại thư mục ngang hàng:
`/media/icnlab/Data/hoanganh/cyberhub-ai-runtime/`.
Ollama chỉ nghe **127.0.0.1:11435**, `OLLAMA_NO_CLOUD=1`; không mở cổng này ra LAN.
Helper tự khởi động Ollama nếu chưa chạy và binary portable đã có; không dừng
dịch vụ Ollama đang chạy của phiên khác.

Cấu hình model và kết quả kiểm tra thực tế nằm trong
[báo cáo nghiệm thu local](testing/RAG_5A_LOCAL_ACCEPTANCE_2026-11-09.md).
Model sinh câu trả lời mặc định `qwen3:8b` (Q4_K_M); embedding `qwen3-embedding:0.6b`. Dùng `CYBERHUB_LLM_MODEL` để chọn một
tag local đã tải; ngưỡng local hiện 0,53. Thay model/ngưỡng cần chạy lại kiểm tra chất lượng.

Trên máy mới, cài Ollama từ [hướng dẫn chính thức](https://docs.ollama.com/linux),
tải model vào runtime riêng rồi cài package dự án trong venv:

```bash
python -m pip install -e '.[dev]'
OLLAMA_HOST=127.0.0.1:11435 ollama pull qwen3-embedding:0.6b
OLLAMA_HOST=127.0.0.1:11435 ollama pull qwen3:8b
```

Lệnh pull cần daemon tương ứng đang chạy, có thể tốn vài GB và cần kết nối Internet.
Chỉ tải weights; câu hỏi và tài liệu khi chạy bản này không gửi sang nhà cung cấp.
Model được dùng theo giấy phép của nhà phát hành; không commit weights vào repo.

## Cấu hình ứng dụng thật

Mặc định ứng dụng thường **tắt** RAG. Helper ở trên bật bằng môi trường backend:

```bash
export CYBERHUB_ASSISTANT_ENABLED=true
export CYBERHUB_OLLAMA_URL=http://127.0.0.1:11435
export CYBERHUB_ASSISTANT_AUDIT_PATH=/duong-dan-rieng/assistant/audit.sqlite3
```

`CYBERHUB_KNOWLEDGE_ROOT` tùy chọn phải là thư mục tài liệu backend tin cậy.
Không nhận model URL, path tài liệu, role hoặc cơ sở từ request chat.
Muốn dùng DB nghiệp vụ thật, cấu hình `.env` MySQL đúng rồi chạy helper với
`--mode mysql`. Helper không tự migrate, seed, reset hoặc thay schema nghiệp vụ.

Hạn mức mặc định: 10 request/phút/actor, 100/ngày/actor, 1.000/ngày toàn app;
request đã admission kể cả fallback/lỗi vẫn tính. Quota không reset bằng cách
đổi ngôn ngữ, role, cơ sở hoặc hội thoại. 429 có Retry-After; UI không tự gửi lại.
Audit metadata 30 ngày chỉ có danh tính/phạm vi, request/chunk IDs, kết quả và
thời gian; không lưu question/answer/prompt/mật khẩu. SQLite riêng, Linux 0600.

SQLite limiter/audit dùng cho **một host có ổ bền vững**. Nhiều replica/host cần
adapter DB chung và kiểm thử cạnh tranh lại. Không đưa nguyên cấu hình local lên
Render với filesystem tạm; Ollama loopback cũng cần GPU/runtime cùng host hoặc
một phương án provider được review riêng. Môi trường public cần HTTPS và cấu hình
session/cookie của web app hiện có. Bản local không tự trở thành deployment public.

## Kiểm thử và giới hạn

```bash
python -m pytest tests/unit/test_ai_*.py tests/unit/test_*web*.py -q
python -m scripts.evaluate_rag_local --output /tmp/rag-local-evaluation.json
python -m scripts.evaluate_rag_local --questions tests/fixtures/ai/local_holdout_questions.json --output /tmp/rag-local-regression.json
python -m scripts.evaluate_rag_local --questions tests/fixtures/ai/local_verification_questions.json --output /tmp/rag-local-verification.json
```

Ba lệnh đánh giá dùng mô hình thật, không phải unit test offline. Tập 27 câu được dùng
hiệu chỉnh ngưỡng; tập 12 câu bổ sung đã dùng phân tích lỗi nên không còn là kiểm
tra mù độc lập. Tập 6 câu bổ sung cũng được giữ lại làm regression sau đợt kiểm tra. Đọc từng answer cùng nguồn, không coi Hit@3/citation đầy đủ là độ
đúng ngữ nghĩa. Có thể từ chối câu hợp lệ khi điểm thấp hoặc quote không hợp lệ.

Adapter sinh output theo JSON, chỉ nhận ID đoạn đã được backend cấp. Backend
lấy nguyên văn đoạn từ nguồn đúng quyền, kiểm tra số liệu và thực hiện một lượt
kiểm tra nghĩa/phạm vi độc lập trong cùng provider. Model không tự tạo quote. Lượt kiểm
tra này vẫn là mô hình xác suất, không chứng minh mọi câu trả lời đúng. Context local tối đa 32.768 token; kiểm
tra ngân sách byte bảo thủ trước khi gửi để không cắt mất điều kiện cuối nguồn. Câu không
đủ căn cứ được giữ lại; chức năng nghiệp vụ vẫn do backend gốc xác thực/thực hiện.
Một request có một query embedding và tối đa hai lượt inference local, không có
vòng retry sinh câu trả lời. Deadline tổng 40 giây, native call 30 giây, UI 50 giây.

Đối chiếu ảnh, số ca đạt, câu từ chối và phạm vi chưa nghiệm thu trong báo cáo
local; không dùng kết quả RAG/web tập trung để nhận toàn bộ dự án/MySQL đã pass.
