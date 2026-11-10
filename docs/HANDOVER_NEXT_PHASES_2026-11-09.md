# Bàn giao công việc tiếp theo — CyberHub Manager

Ngày cập nhật trạng thái: 10/11/2026, giờ Việt Nam.

Phần lịch sử 5A nằm trên **`feat/rag-knowledge-assistant`**. Phần 5B–5C tiếp tục
trên **`feat/ai-phases-5b-5c`**, tạo từ `develop` tại commit `6416bef` sau khi các
Đợt 0–4 và RAG 5A đã được tích hợp. Người nhận cần đọc tài liệu này và
`AI_PHASES_5B_5C.md` trước khi nhận việc.

## 1. Trạng thái hiện tại và phân công

| Hạng mục | Trạng thái | Công việc tiếp theo |
|---|---|---|
| Đợt 0 — Phân quyền | Cốt lõi đã kiểm tra pass | Đồng bộ tài liệu và xác định audit demo |
| Đợt 1 — Menu đồ ăn/đồ uống | Đã tích hợp | Theo dõi lỗi nghiệp vụ/UI sau nghiệm thu |
| Đợt 2 — Voucher | Đã tích hợp | Theo dõi đổi/trừ voucher và audit |
| Đợt 3 — Game/xu | Đã tích hợp | Theo dõi chống lặp và khóa ví xu |
| Đợt 4 — Quảng cáo | Đã tích hợp | Theo dõi callback, hạn mức và thống kê |
| Đợt 5A — RAG tài liệu | Đã nối API, model local và UI đăng nhập | Xem runbook và báo cáo nghiệm thu local; deployment public cần chuẩn bị riêng |
| Đợt 5B — AI phân tích số liệu | Đã triển khai trên branch `feat/ai-phases-5b-5c` | Nghiệm thu model local và biểu đồ/số liệu thực tế |
| Đợt 5C — AI tư vấn dịch vụ mở rộng | Đã triển khai trên branch `feat/ai-phases-5b-5c` | Nghiệm thu chất lượng gợi ý menu/ưu đãi/voucher/game |

“Đợt 1–3” trong tài liệu này là lộ trình menu/voucher/game, khác với các đợt
web khách hàng đã hoàn thành trong `CUSTOMER_PORTAL_PHASE1/2/3.md`.
Không viết lại dashboard, hồ sơ, avatar và thành viên đang có.

Đề nghị người nhận ưu tiên hoàn thiện phần còn lại Đợt 0 rồi thực hiện Đợt 1–4.
Phần AI/RAG do Hoàng Anh phụ trách, có thể làm song song với menu và voucher.

## 2. Đợt 0 — Các việc cần bổ sung

### D0-01. Cập nhật tài liệu phân quyền cũ

Vấn đề: bảng Phân quyền trong `docs/P1_DESKTOP_WEB.md` vẫn gộp xuất/in hóa đơn
và xem doanh thu vào cùng một dòng cho STAFF, không còn đúng sau PR #33.

Cần làm:

- Tách dòng hóa đơn khỏi doanh thu; STAFF giữ quyền hóa đơn theo nghiệp vụ quầy.
- Doanh thu chỉ dành cho MANAGER/ADMIN; MANAGER giới hạn cơ sở được giao.
- Ghi rõ ADMIN hiện xem từng cơ sở qua chức năng đổi cơ sở; không khẳng định
  đã có báo cáo hợp nhất mọi cơ sở cùng lúc.
- Rà lại các hướng dẫn/báo cáo còn mô tả STAFF được xem doanh thu.
- Sau khi người phụ trách xác nhận, cập nhật hai tài liệu RAG
  `docs/knowledge-base/shared/role-policy.md` và
  `docs/knowledge-base/manager/revenue-policy.md` từ DRAFT sang APPROVED,
  tăng version và ngày cập nhật. Không tự duyệt chỉ vì file đã tồn tại.

Nghiệm thu: tài liệu, quyền trên UI và kết quả API không mâu thuẫn; các test
metadata và quyền doanh thu vẫn pass.

### D0-02. Thống nhất audit ở chế độ demo

Vấn đề: ReportService thật ghi `REVENUE_VIEW` trong MySQL; MockReportService
trong demo chưa ghi sự kiện này. API/UI demo vẫn chặn STAFF đúng quyền.

Cần làm: thống nhất một trong hai phạm vi nghiệm thu sau trước khi đóng task:

- Bổ sung audit tương ứng trong demo để minh họa được lịch sử truy cập; hoặc
- Ghi rõ kiểm tra audit doanh thu thực hiện ở MySQL, demo chỉ kiểm tra UI/quyền.

Nếu bổ sung mock, dùng danh tính đáng tin từ cấu trúc mock hiện có, không tin
role/employee ID do client tự khai. Truy cập bị từ chối không được tạo sự kiện
xem doanh thu thành công; sự kiện hợp lệ phải đúng nhân viên và cơ sở.

Nghiệm thu: có kiểm thử theo phạm vi đã chọn, không bỏ audit MySQL hoặc mở lại
quyền STAFF để làm demo chạy được.

### Bằng chứng Đợt 0 đã có

- [Báo cáo kiểm tra](testing/PHASE0_VALIDATION_2026-11-09.md).
- 179 unit/UI tests và 20 integration tests pass tại `develop` commit `5341162`.
- Kiểm tra bổ sung MySQL: hạ quyền đang đăng nhập, khóa nhân viên, MANAGER vượt
  cơ sở, ADMIN chuyển cơ sở và ghi audit đều đạt.
- Ảnh minh chứng trong `docs/testing/phase0/`.

Kết quả trên là kiểm tra tập trung Đợt 0, không phải toàn bộ test suite dự án.

## 3. Đợt 1 — Menu đồ ăn và đồ uống

Mục tiêu: khách xem menu đẹp, có giá và tình trạng bán theo cơ sở.

Việc cần làm:

- Một trang đồ ăn và một trang đồ uống, hiệu ứng sách lật trên desktop;
  mobile có nút/vuốt và vẫn đọc được khi không dùng hiệu ứng.
- Mỗi món có mã, tên, nhóm, ảnh, mô tả, giá và trạng thái bán.
- Manager quản trị menu trong phạm vi cơ sở; Admin quản trị theo quyền hệ thống.
- Giá/trạng thái theo cơ sở phải lấy từ backend; món hết hàng không được chọn.
- Hình ảnh thuộc quyền sử dụng của nhóm, không mang watermark đơn vị khác.
- Đồng bộ giao diện dark/cyan, VI/EN và cách báo lỗi đang có.

Điểm phải chốt trước khi triển khai: đợt này chỉ xem menu/gọi nhân viên hay có
đặt món thật. Nếu chỉ xem, không hiển thị nút xác nhận đơn gây hiểu nhầm. Nếu có
đặt món, cần bổ sung vòng đời đơn, người nhận xử lý, giá chụp lúc đặt, trạng thái
món hết, hủy đơn và cách thanh toán. Danh sách menu không tự tạo hóa đơn dịch vụ.

Nghiệm thu: desktop/mobile dễ đọc; hai trang đủ nội dung; đúng giá/cơ sở;
món hết hàng xử lý đúng; backend không cho sửa dữ liệu cơ sở ngoài quyền.

## 4. Đợt 2 — Voucher và phần thưởng

Mục tiêu: phát hành và sử dụng voucher đồ ăn/giờ chơi có kiểm soát.

Việc cần làm:

- Danh mục phần thưởng và voucher của từng khách.
- Mã voucher, thời gian hiệu lực, cơ sở áp dụng, đối tượng, số lượt và trạng thái.
- Chốt giảm theo % hay số tiền, mức giảm tối đa, giá trị đơn tối thiểu,
  giới hạn mỗi khách, quy tắc cộng chồng và xử lý khi hủy đơn/hóa đơn.
- Khách xem voucher của mình; nhân viên xác nhận sử dụng đúng phạm vi.
- Phát hành, dùng và thu hồi có lịch sử, thực hiện trong transaction phù hợp.
- Chặn sử dụng hai lần khi có yêu cầu đồng thời hoặc gửi lại.

Điểm cần lưu ý: hóa đơn hiện tại gắn với phiên chơi. Voucher giờ chơi phải chốt
cách lưu giảm giá và tính doanh thu, không sửa tùy tiện `usage_cost` để qua ràng
buộc. Voucher đồ ăn cần luồng bán hàng/đơn đồ ăn nếu muốn thanh toán trong app.

Chưa có tính năng tiêu điểm thành viên. Nếu bổ sung đổi điểm, phải có chính sách
và sổ biến động điểm riêng được duyệt; không trừ trực tiếp tổng điểm suy ra từ hóa đơn.

Nghiệm thu: đúng chủ tài khoản/cơ sở/điều kiện; hết hạn bị từ chối; không dùng
trùng; số tiền giảm và doanh thu có thể đối chiếu; không quy đổi voucher tiền mặt.

## 5. Đợt 3 — Game đầu tiên và xu game

Mục tiêu: một game đơn giản tạo tương tác, có xu riêng và đổi phần thưởng.

Việc cần làm:

- Chọn một game đầu tiên; quiz hoặc lật thẻ giúp bắt đầu với luật rõ ràng.
- Giới hạn lượt, thời gian phiên và mức thưởng/ngày bằng cấu hình.
- Backend xác minh phiên/kết quả; không tin điểm do trình duyệt tự báo.
- Ví xu tách biệt tiền chính, tiền khuyến mãi và điểm thành viên.
- Sổ giao dịch xu có nguồn nhận/đổi, mã chống xử lý lặp và thời điểm.
- Đổi xu sang voucher qua danh mục Đợt 2, kiểm tra số dư và tồn phần thưởng
  trong transaction; gửi lại không cộng/trừ hoặc cấp voucher thêm lần nữa.
- Không xây thao tác mua lượt bằng tiền hoặc rút xu thành tiền trong phạm vi này.

Nếu muốn đổi xu sang điểm thành viên, dừng ở mức cấu hình đề xuất cho tới khi
chốt cách ghi nhận điểm ngoài hóa đơn; backend hiện tại chưa hỗ trợ nguồn điểm đó.

Nghiệm thu: không tự cộng xu bằng request, không đổi vượt số dư, không cấp trùng
phần thưởng; có lịch sử đối chiếu; cơ chế giới hạn hoạt động khi gửi đồng thời.

## 6. Đợt 4 — Quảng cáo nhận thưởng

Mục tiêu: thưởng cho lượt quảng cáo hợp lệ sau khi game/xu/voucher ổn định.

Việc cần làm:

- Chọn nền tảng có hình thức quảng cáo thưởng phù hợp và cơ chế xác minh.
- Mỗi sự kiện có ID duy nhất, trạng thái chờ/xác minh/thưởng/từ chối.
- Callback phải kiểm tra tính xác thực và liên kết đúng người/phiên.
- Hạn mức thưởng và số lần xem được kiểm tra ở server.
- Không cộng thưởng chỉ dựa vào nút hoặc sự kiện JavaScript “đã xem xong”.
- Nếu chỉ có bản mô phỏng, gắn nhãn demo, không ghi nhận là doanh thu quảng cáo thật.
- Tách khoản tiền quảng cáo khỏi doanh thu phí chơi hiện có và xác định nguồn
  đối soát trước khi đưa vào báo cáo tài chính.

Nghiệm thu: chống callback giả/lặp, một sự kiện chỉ nhận một thưởng, lỗi mạng
không tạo thưởng trùng và không cản chức năng cơ bản. Nếu nền tảng không cung cấp
xác minh đủ tin cậy, chưa bật đổi thưởng có giá trị thật.

## 7. Đợt 5A — RAG: đã làm gì, tiếp tục từ đâu?

### Đã hoàn thành bước 1 và 2

- 14 tài liệu nghiệp vụ và README tại `docs/knowledge-base/`.
- 12 tài liệu APPROVED, hai DRAFT liên quan Đợt 0 chờ duyệt lại.
- Model thuần Python tại `src/cyberhub_manager/ai/models.py`:
  `AIAccessContext`, `KnowledgeDocument`, `KnowledgeChunk`, `Citation`, `AssistantAnswer`.
- Model bất biến, metadata/đường dẫn tương đối/định danh/trích dẫn được kiểm tra.
- 48 tests model và cấu trúc kho tài liệu pass tại commit `1e15f9a`.
- Tại mốc bước 1–2 chưa có loader/chunking. Checkout hiện đã bổ sung bước 3–11
  bên dưới; adapter/model local và chat có session được bổ sung ở bước 12C–12D.

Sau khi đồng bộ `develop` vào branch bàn giao, đã chạy lại nhóm RAG và
ReportService: **122 tests pass** (09/11/2026):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py tests/unit/test_report_service.py -q
```

### Bước 3 — Loader và kiểm tra tài liệu

**Đã triển khai trên checkout RAG ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
`ai/documents.py`, `ai/errors.py` và `test_ai_documents.py`; nhóm model/corpus/loader
đạt **98 tests**. Chi tiết giới hạn, lỗi và lệnh chạy tại
[README kho tri thức](knowledge-base/README.md#document-loader--bước-3).
Chưa triển khai chunking/index và chưa tự duyệt hai tài liệu DRAFT.

- Chỉ đọc Markdown nghiệp vụ trong knowledge root; bỏ README và bản chưa duyệt.
- Parse metadata an toàn; chặn ID trùng, audience không hợp lệ, version sai.
- Kiểm tra đường dẫn thực, không đi qua symlink ra ngoài thư mục cho phép.
- Ánh xạ metadata vào KnowledgeDocument đúng hợp đồng trong README của kho.
- Khi tài liệu đổi audience/status/version, pipeline sau phải thay thế hoặc
  thu hồi các chunk cũ; không giữ bản APPROVED cũ khi bản mới bị thu hồi.

Nghiệm thu: file không hợp lệ báo lỗi rõ; chỉ APPROVED được đưa tiếp vào pipeline;
test đường dẫn thoát thư mục, duplicate ID, DRAFT/ARCHIVED không được phục vụ.

### Bước 4 — Chunking có giữ ngữ nghĩa

**Đã triển khai trên checkout RAG ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
`ai/chunking.py` cung cấp `MarkdownChunker.split(document)`; **40 tests chunking
pass**, tổng nhóm bước 1–4 đạt **138 tests**. Chạy loader và chunker trên kho thật:
12 tài liệu APPROVED tạo 61 chunk, ID duy nhất, giữ nguồn/quyền/phiên bản.
Chi tiết cấu hình, giới hạn và lệnh kiểm tra tại
[README kho tri thức](knowledge-base/README.md#markdown-chunker--bước-4).
Chưa nối embedding/retrieval/LLM/API/UI; không tự duyệt tài liệu DRAFT.

- Chia theo tiêu đề/mục, giữ ngữ cảnh; giới hạn độ dài có thể cấu hình.
- ID ổn định từ tài liệu, version, section và content.
- Giữ document ID, source, section, audience, language, version.
- Không ghép nội dung có đối tượng được đọc khác nhau.

Nghiệm thu: cùng đầu vào cho cùng chunk ID; sửa nội dung/version đổi ID tương
ứng; giữ nguồn truy vết; không làm mất điều kiện hoặc ngoại lệ quan trọng.

### Bước 5 — Interface embedding/LLM và fake provider

**Đã triển khai trên checkout RAG ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
`ai/providers.py` định nghĩa hai Protocol và kiểm tra output; `ai/fakes.py` cung
cấp fake xác định/mô phỏng lỗi, không gọi mạng hoặc yêu cầu API key. Lỗi provider
được tách trong `ai/errors.py`; chưa gắn SDK hoặc mô hình AI cụ thể.
**65 tests provider pass**, tổng nhóm bước 1–5 **203 tests**. Chi tiết hợp đồng,
giới hạn của fake, lỗi và lệnh kiểm tra tại
[README kho tri thức](knowledge-base/README.md#provider-độc-lập--bước-5).

### Bước 6 — Vector index và Retriever lọc quyền

**Đã triển khai trên checkout RAG ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
`ai/retrieval.py` có chỉ mục cosine trong bộ nhớ, `KnowledgeRetriever.search` và
`search_scored`. Lọc audience trước scoring/top-k, xác thực vector đầu ra, rebuild
toàn bộ snapshot và từ chối phục vụ chỉ mục cũ khi reload lỗi/đang chạy.
Không mở quyền kế thừa ADMIN và không truy vấn số dư/doanh thu thật.

### Bước 7 — Tạo prompt từ context được phép

**Đã triển khai trên checkout RAG ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
`ai/prompts.py` tạo system prompt VI/EN và user prompt XML có escape. Trước/sau
định dạng kiểm tra lại quyền và toàn bộ chunk so với chỉ mục hiện tại; context
giả mạo/thu hồi bị chặn. Có nguồn ứng viên và giới hạn context, chưa gọi LLM.

Bước 6–7 đạt **83 tests**, toàn nhóm bước 1–7 **286 tests pass**, không gọi mạng
hoặc MySQL. Bao gồm kiểm thử phân quyền, reload đồng thời/lỗi, stale/forged chunk,
ngôn ngữ và delimiter injection; không khẳng định LLM thật đã chống injection.
Chi tiết/lệnh chạy tại [README kho tri thức](knowledge-base/README.md#vector-index-và-retriever--bước-6).

### Bước 8 — RAG service điều phối

**Đã triển khai trên checkout RAG ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
`ai/service.py` kiểm tra câu hỏi, ngưỡng cosine, quyền/context, prompt, gọi LLM tối
đa một lần và kiểm tra ref trong response. Thiếu căn cứ/provider lỗi trả fallback
không citation. Context được kiểm tra lại sau LLM để chặn nguồn vừa bị thu hồi.
`ai/runner.py` có deadline và số worker hữu hạn; `ai/audit.py` chỉ ghi metadata.
Adapter thật vẫn phải có timeout native và giới hạn output; chưa tích hợp AI cloud.

### Bước 9 — Kiểm thử fake và các đường lỗi

**Đã triển khai trên checkout RAG ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
Tái sử dụng fake bước 5, thêm audit in-memory và **101 tests service/runner**.
Toàn nhóm bước 1–9 **387 tests pass**, không gọi API/MySQL. Có test bốn vai trò,
score thấp, citation giả/thiếu, timeout thực, worker bận, audit lỗi, context bị thu
hồi trong khi LLM chạy và pipeline từ kho Markdown thật đến answer envelope.
`grounded=True` chưa chứng minh kết luận đúng ngữ nghĩa; đánh giá mô hình thật và
ngưỡng thuộc bước 10. Audit logging cần cấu hình handler; chưa tạo schema AI.
Chi tiết/lệnh chạy: [báo cáo bước 8–9](testing/RAG_STEPS_8_9_2026-11-09.md).

### Bước 10 — Bộ câu hỏi và đánh giá offline

**Đã có công cụ/bộ đánh giá trên checkout ngày 09/11/2026, chất lượng chưa đạt để bật AI thật.**
27 câu hỏi tại `tests/fixtures/ai/evaluation_questions.json`, CLI
`python -m scripts.evaluate_rag`. TF-IDF chỉ học từ nội dung tài liệu, không từ
expected_source/keywords. Trả lời trích đoạn chỉ để đo luồng nguồn, không giả là LLM.
Raw Hit@3 100%, nguồn kỳ vọng đủ ngưỡng 70%, citation của câu trả lời 100%, từ chối
đúng 6/7, nguồn sai quyền bị trả về 0. Còn ca STAFF hỏi đổi cấu hình nhận đoạn
glossary không đủ căn cứ; EN và một số ca hợp lệ bị từ chối vì baseline lexical.

### Bước 11 — Chat UI mock riêng

**Đã triển khai trên checkout ngày 09/11/2026, chờ Hoàng Anh kiểm tra.**
`python -m cyberhub_manager.ai.preview --port 8058` mở app preview riêng dùng
theme/font/logo hiện tại. Chat có nguồn, loading, fallback, lỗi/thử lại, VI/EN,
feedback và hội thoại mới; chỉ lưu trong RAM trình duyệt, không gửi câu hỏi,
role/store đến backend. Chưa sửa auth hoặc API của app vận hành.

Bước 10–11 có 32 tests mới; 419 tests RAG + 40 web regression = **459 pass**.
Browser kiểm tra 1280×720 và 390×844, không lỗi JS hoặc request API. Bằng chứng và
ca chưa đạt: [báo cáo bước 10–11](testing/RAG_STEPS_10_11_2026-11-09.md).

### Bước 12A–12B — API/session và hạn mức/audit

**Đã triển khai local, chưa bật AI thật.** `web/assistant.py` cung cấp
`POST /api/assistant/messages` dựa trên auth/CSRF hiện có; identity/scope từ
backend và kiểm tra lại sau generation. `ai/policy_store.py` admission quota và
audit metadata bền vững trên SQLite riêng cho một host; không lưu nội dung chat.
Mặc định feature tắt, chỉ bật với service factory và audit path do backend cấu
hình. Không tự đưa baseline lexical lên phục vụ người dùng.

Nhóm tập trung service/policy/HTTP đạt **138 tests**. Chi tiết cách kiểm tra,
giới hạn triển khai và việc chưa làm:
[báo cáo 12A–12B](testing/RAG_STEP_12AB_2026-11-09.md).

### Bước 12C–12D — Model local và UI có đăng nhập

> Mốc lịch sử ngày 09/11/2026. Runtime hiện tại đã chuyển sang Gemini API vào 10/11/2026;
> dùng [runbook Gemini](GEMINI_API_RUNBOOK.md) để chạy. Mô tả/số đo provider cũ bên dưới được giữ để đối chiếu.

Đã bổ sung adapter Ollama loopback: `qwen3-embedding:0.6b` và `qwen3:8b`, ngưỡng
cosine 0,53 trên tập development. Context mở rộng theo tài liệu cha đã được phép
để giữ điều kiện/ngoại lệ; không mở rộng sang nguồn sai audience. Tài liệu thay
đổi hoặc bị thu hồi thì answer đang chờ bị chặn, request sau mới rebuild index.

Model trả JSON chọn ID đoạn nguồn do backend cấp; không tin quote tự tạo.
Backend phân giải đoạn nguồn nguyên văn, kiểm tra số liệu và một lượt kiểm
tra nghĩa/phạm vi trước khi trả nội dung. Đây vẫn là mô hình xác suất, không phải
chứng minh mọi câu trả lời đúng. Giữ fallback cho ca chưa đủ căn cứ.

Chat tích hợp dùng Inter/Space Grotesk như `develop`, hỗ trợ VI/EN, ẩn path/ref mặc định, dùng cookie/CSRF hiện có;
429/503 không tự retry, đổi danh tính/đăng xuất xóa lịch sử trên trang. 8058 vẫn là
mock; 8059 là bản AI local thật với dữ liệu nghiệp vụ demo mặc định.

Đã làm rõ tiền khách đưa/tiền thừa theo SES-08 và DTO handoff trong
`staff/payment-process.md` và `shared/glossary.md`, tăng version lên 2. Không
chuyển hai tài liệu DRAFT sang APPROVED hoặc thay đổi quy tắc tiền của backend.

- [Lệnh chạy và cách kiểm tra](RAG_5A_RUNBOOK.md).
- [Kết quả nghiệm thu và các giới hạn còn lại](testing/RAG_5A_LOCAL_ACCEPTANCE_2026-11-09.md).

Lịch sử/feedback server, quota/audit nhiều host và triển khai public là phần mở
rộng; chưa áp schema AI/history vào DB nghiệp vụ. Deployment cần ổ bền vững,
HTTPS và mô hình provider/GPU phù hợp, không dùng nguyên SQLite local cho nhiều
replica. Hai tài liệu DRAFT vẫn chờ người phụ trách duyệt nghiệp vụ.

5A giải thích tài liệu tĩnh, không đọc doanh thu thật hoặc thao tác tài chính.
5B mới tích hợp dữ liệu báo cáo theo quyền; 5C chờ các module menu/voucher/game
tương ứng. Không cần chuyển Flask sang FastAPI để tiếp tục phần này.

## 8. Kéo về máy khác

Nếu đã có repository và không có thay đổi chưa lưu:

```powershell
git status
git fetch origin
git switch --track origin/feat/rag-knowledge-assistant
```

Nếu branch local đã tồn tại:

```powershell
git switch feat/rag-knowledge-assistant
git pull --ff-only origin feat/rag-knowledge-assistant
```

Nếu máy chưa có repository:

```powershell
git clone --branch feat/rag-knowledge-assistant https://github.com/hoanganh1601/cyberhub-manager.git
cd cyberhub-manager
```

Không ghi đè thay đổi đang làm dở. Nếu `git status` còn thay đổi, lưu chúng vào
branch riêng trước khi đổi branch hoặc pull.

Chuẩn bị môi trường trên máy mới:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[web,dev]"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py -q
```

Chạy demo web để đối chiếu quyền, không cần database thật:

```powershell
$env:CYBERHUB_WEB_MODE="demo"
.\.venv\Scripts\python.exe -m cyberhub_manager.web --port 8000
```

Mở `http://127.0.0.1:8000/`. STAFF `nhanvien01`, MANAGER `quanly01`, ADMIN `admin01`;
mật khẩu demo chung `demo123`. Desktop demo dùng `python -m cyberhub_manager.app --mock`.
`.env`, database thật và bí mật không đi theo Git; cấu hình riêng nếu cần chế độ MySQL.

## 9. Nhận task và tạo PR

- Việc RAG tiếp tục trên nhánh bàn giao hoặc branch con thống nhất với Hoàng Anh.
- Với Đợt 1–4, tạo branch riêng từ `develop` mới nhất sau khi đã lưu thay đổi local;
  không cần gộp mã RAG chỉ để làm menu hoặc voucher.
- Một PR tập trung một đợt hoặc một nhóm nghiệp vụ; ghi rõ đã làm, chưa làm,
  migration, cách chạy và kết quả kiểm thử.
- Mỗi thay đổi tài chính/quyền phải có unit và integration test tương ứng.
- Không chỉnh migration đã áp dụng; tạo migration mới và thống nhất số thứ tự
  với người làm song song trước khi thêm SQL.
- Không cần chạy lại migration chỉ để đọc tài liệu bàn giao này.
- Hướng dẫn gốc từng đợt: [HANDOVER_BUSINESS_DISCUSSION.md](HANDOVER_BUSINESS_DISCUSSION.md).
