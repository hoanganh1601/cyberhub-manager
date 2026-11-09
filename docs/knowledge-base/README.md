# Kho tri thức CyberHub — Đợt 5A, bước 1–11 và 12A–12B

Kho này chứa hướng dẫn nghiệp vụ tĩnh cho trợ lý RAG. Phạm vi hiện tại là tài liệu
Markdown, model Python, loader, chunker, interface/fake provider, chỉ mục cosine,
retriever, bộ tạo prompt và RAG service có kiểm tra nguồn/quyền, audit metadata,
timeout, kiểm thử fake, bộ đánh giá offline và UI chat mock riêng. API dùng phiên
đăng nhập, quota và audit đã có dưới feature flag mặc định tắt (12A–12B).
Chưa có embedding/LLM ngữ nghĩa thật hoặc UI nối API thật.
Model/chunker/provider/retrieval/prompt/service chỉ
dùng thư viện chuẩn; loader dùng PyYAML SafeLoader (được cài cùng dự án). Không
cần API key hoặc MySQL cho các bước này.

## Nội dung và trạng thái

| Tài liệu | Đối tượng | Trạng thái |
|---|---|---|
| [Thuật ngữ](shared/glossary.md) | Tất cả vai trò | APPROVED |
| [Câu hỏi chung](shared/faq.md) | Tất cả vai trò | APPROVED |
| [Chính sách vai trò](shared/role-policy.md) | Nhân sự | DRAFT — chờ Đợt 0 |
| [Tài khoản và avatar](customer/account-guide.md) | Khách hàng | APPROVED |
| [Thành viên](customer/membership-policy.md) | Khách hàng | APPROVED |
| [Ưu đãi cho khách](customer/promotion-policy.md) | Khách hàng | APPROVED |
| [Vận hành máy](staff/machine-operation.md) | Nhân viên, quản lý, admin | APPROVED |
| [Quản lý khách hàng](staff/customer-management.md) | Nhân viên, quản lý, admin | APPROVED |
| [Nạp tiền](staff/top-up-process.md) | Nhân viên, quản lý, admin | APPROVED |
| [Thanh toán](staff/payment-process.md) | Nhân viên, quản lý, admin | APPROVED |
| [Chính sách doanh thu](manager/revenue-policy.md) | Quản lý, admin | DRAFT — chờ Đợt 0 |
| [Quản lý khuyến mãi](manager/promotion-management.md) | Quản lý, admin | APPROVED |
| [Quản lý nhân viên](admin/employee-management.md) | Admin | APPROVED |
| [Cấu hình thành viên](admin/system-configuration.md) | Admin | APPROVED |

`APPROVED` ở bản khởi đầu đánh dấu nội dung đối chiếu được với nghiệp vụ đang có
và quyết định đã chốt, không xác nhận hệ thống RAG đã chạy. Chủ nghiệp vụ cần duyệt
lại khi thay đổi quy trình. Các tài liệu DRAFT giữ lại chính sách đã thống nhất
nhưng chưa nghiệm thu Đợt 0; tuyệt đối không đưa chúng vào chỉ mục phục vụ hỏi đáp.

Không index README này, tài liệu bàn giao tổng thể, toàn bộ thư mục `docs`, mã nguồn,
file cấu hình, thông tin đăng nhập, ảnh bằng chứng hoặc dữ liệu khách hàng thật.
Các đường dẫn tại mục “Nguồn đối chiếu” chỉ để người biên soạn kiểm tra, không phải
chỉ dẫn cho loader tự đọc thêm file ngoài kho tri thức.

## Quy ước tài liệu

Mỗi tài liệu nghiệp vụ có YAML frontmatter:

```yaml
---
id: staff-payment-process
title: Quy trình thanh toán phiên chơi
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - payment
  - invoice
---
```

- `id`: duy nhất toàn kho, chữ thường, số và dấu gạch ngang.
- `audience`: danh sách vai trò được phép đọc, khai báo tường minh; tên thư mục
  chỉ để tổ chức, không thay thế metadata và không tự cấp quyền kế thừa.
- Không có vai trò `SHARED`; nội dung chung liệt kê đủ vai trò cần dùng.
- `status`: `DRAFT`, `APPROVED` hoặc `ARCHIVED`. Loader chỉ trả `APPROVED`.
- `version`: số nguyên dương, tăng khi nội dung hoặc đối tượng được phép đọc đổi.
- `language`: `vi` hoặc `en`. Đợt này biên soạn tiếng Việt; chưa có bản dịch EN.
- `updated_at`: ngày ISO `YYYY-MM-DD`, lịch Việt Nam.
- `tags`: danh sách từ khóa, không dùng làm quyền truy cập.

Chính sách tiền/điểm trong tài liệu phải ghi rõ mốc mặc định có thể cấu hình.
Hỏi số dư, máy trống, doanh thu hoặc ưu đãi đang có cần API được phân quyền ở bước
sau; tài liệu không phải ảnh chụp dữ liệu hiện tại. Ví dụ số tiền chỉ có tính minh họa.

## Hợp đồng model Python

Module: `src/cyberhub_manager/ai/models.py`. Chỉ dùng thư viện chuẩn Python 3.11+.

| Model | Ý nghĩa |
|---|---|
| `AIAccessContext` | Danh tính và phạm vi được backend xác thực, ngôn ngữ trả lời |
| `KnowledgeDocument` | Metadata và nội dung một tài liệu |
| `KnowledgeChunk` | Một đoạn văn bản có nguồn, đối tượng, ngôn ngữ, phiên bản |
| `Citation` | Nguồn tham khảo gồm document ID, chunk ID, tiêu đề, mục, đường dẫn, phiên bản |
| `AssistantAnswer` | Nội dung trả lời, tuple trích dẫn và cờ `grounded` |

Các model dùng `dataclass(frozen=True)` và tuple, kiểm tra dữ liệu đầu vào bằng
`ValueError`. Không tự đọc file, gọi mạng, truy vấn DB hoặc tự cấp quyền.

Ánh xạ cho loader ở bước 3: frontmatter `id` → `document_id`, `updated_at` →
`datetime.date`, `audience`/`tags` → tuple. `source` lấy từ đường dẫn file thực,
tương đối với thư mục này, dùng `/`, ví dụ `staff/payment-process.md`.
Không nhận đường dẫn nguồn từ người dùng để mở file tùy ý. Kiểm tra symlink và
đường dẫn thực có thuộc knowledge root hay không thuộc trách nhiệm loader bước 3.

`AIAccessContext.actor_id` là `employees.id` cho nhân sự và `accounts.id` cho
`CUSTOMER`. Luôn lưu cùng `role` để tránh nhầm ID ở hai bảng. Khách chỉ đọc hướng
dẫn của khách và nội dung chung; model này không thay thế kiểm tra quyền sở hữu
thông tin cá nhân qua API. `store_ids=()` không cấp quyền xem dữ liệu cửa hàng,
kể cả ADMIN; phạm vi cụ thể phải do backend xác thực. Không nhận role/store từ
payload do trình duyệt tự khai.

`Citation` phải do backend tạo từ chunk đã được phép truy xuất. Model chỉ kiểm tra
cấu trúc, không chứng minh nguồn tồn tại hoặc kết luận LLM đúng. `grounded=True`
phải có trích dẫn; fallback `grounded=False` có tuple trích dẫn rỗng. Kiểm tra độ
đúng của câu trả lời và nguồn thuộc các bước retrieval/evaluation tiếp theo.

Ví dụ tạo context nội bộ (không phải endpoint cấp quyền):

```python
from cyberhub_manager.ai import AIAccessContext, AssistantAnswer

access = AIAccessContext(actor_id=1, role="STAFF", store_ids=(1,))
fallback = AssistantAnswer(
    answer="Chưa tìm thấy thông tin đã được phê duyệt cho câu hỏi này.",
    citations=(),
    grounded=False,
)
```

## Bàn giao cho người làm Đợt 0 và bước tiếp theo

1. Người làm Đợt 0 xác nhận chính sách doanh thu đúng với route, service và UI.
2. Rà soát hai tài liệu DRAFT; khi đạt nghiệm thu mới cập nhật trạng thái,
   ngày và tăng phiên bản.
3. Bước 3–4 đã có loader/chunker: chỉ nhận Markdown nghiệp vụ hợp lệ và APPROVED;
   không coi kiểm tra model hoặc chunking là kiểm tra quyền của người hỏi.
4. Bước 5–11 có interface/fake provider, retrieval, prompt, service, bộ đánh giá
   và UI mock; tiếp theo là xử lý các ca chưa đạt và adapter model thật.
5. Bước 12A–12B đã nối API Flask với context từ session được xác thực lại,
   hạn mức và audit; mặc định chưa bật phục vụ người dùng.

Không viết lại hệ thống xác thực, doanh thu hoặc migration nghiệp vụ.

## Document Loader — bước 3

Module: `src/cyberhub_manager/ai/documents.py`.

```python
from cyberhub_manager.ai.documents import KnowledgeDocumentLoader

documents = KnowledgeDocumentLoader().load()
```

Mặc định chỉ đọc `docs/knowledge-base` của checkout này. Có thể truyền đường dẫn
đó vào `load(root_path)`; truyền thư mục khác bị từ chối. Với bản đóng gói hoặc
kiểm thử, cấu hình `KnowledgeDocumentLoader(knowledge_root=...)` ở backend bằng
đường dẫn đáng tin cậy; không lấy cấu hình này từ request của người dùng.

- Duyệt `.md` theo thứ tự đường dẫn; bỏ `README.md` (không phân biệt hoa/thường).
- Không đọc liên kết Markdown trong nội dung, không nạp file ngoài kho. Từ chối
  mọi symlink, kể cả symlink nội bộ, thư mục và liên kết hỏng.
- Giới hạn mặc định 256 KiB/file (tính theo byte UTF-8), 16 KiB/frontmatter.
  File vượt giới hạn gây lỗi thay vì âm thầm bỏ sót; chỉ đọc file thông thường.
- Frontmatter yêu cầu đúng tám trường trên. YAML an toàn, không chấp nhận key
  trùng, alias/anchor, tag tường minh hoặc collection lồng sâu. Version phải là
  số nguyên dương; audience phải là danh sách role hợp lệ, không trùng.
- Kiểm tra cả tài liệu DRAFT/ARCHIVED và ID trùng trên toàn kho, sau đó chỉ trả
  APPROVED. Hai tài liệu chờ duyệt hiện vẫn được loại khỏi kết quả.
- Lỗi công khai trong `ai/errors.py`: `InvalidMetadataError`,
  `DuplicateDocumentError`, `KnowledgePathError`, `DocumentTooLargeError`,
  `KnowledgeReadError`; tất cả kế thừa `KnowledgeError`.

Mỗi lần `load()` đọc lại toàn bộ, không cache hoặc cộng dồn kết quả. Pipeline
index ở bước sau phải **thay thế toàn bộ snapshot sau lần nạp thành công** để
thu hồi tài liệu đã xóa/đổi quyền/đổi trạng thái. Khi nạp lỗi, không được tiếp tục
phục vụ chỉ mục cũ như thể đã kiểm tra quyền mới. Bước này chưa có index nên chưa
triển khai thao tác thay thế đó. Kho phải do quản trị viên kiểm soát và không cho
người dùng không tin cậy sửa đồng thời trong lúc nạp.

Kiểm tra loader cùng model và corpus, không gọi mạng/AI/MySQL:

```bash
python -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py tests/unit/test_ai_documents.py -q
```

## Markdown Chunker — bước 4

Module: `src/cyberhub_manager/ai/chunking.py`.

```python
from cyberhub_manager.ai.chunking import MarkdownChunker
from cyberhub_manager.ai.documents import KnowledgeDocumentLoader

chunker = MarkdownChunker(target_words=500, max_words=700, overlap_words=75)
chunks = [
    chunk
    for document in KnowledgeDocumentLoader().load()
    for chunk in chunker.split(document)
]
```

- Mỗi lần `split(document)` chỉ xử lý một tài liệu APPROVED. Gọi trực tiếp với
  DRAFT/ARCHIVED bị từ chối bằng `ChunkingError`, kể cả khi bỏ qua loader.
- Tách theo tiêu đề ATX (`#`–`######`) và Setext (`===`/`---` dưới tiêu đề một
  dòng); giữ tiêu đề tài liệu và các tiêu đề cha trong nội dung từng chunk.
  `section` chứa đường dẫn mục, ví dụ `Thanh toán > Tiền bù > Ngoại lệ`.
- Không coi tiêu đề trong khối code fenced/indent là mục nghiệp vụ. Không ghép
  các mục khác nhau hoặc tài liệu khác nhau để đạt đủ số từ; mục ngắn giữ nguyên.
- Mục dài ưu tiên giữ đoạn văn/danh sách. Đoạn vượt giới hạn được chia theo ranh
  giới câu/dòng khi có thể, cuối cùng theo từ, không bỏ phần nội dung còn lại.
- Mặc định mục tiêu 500 từ, tối đa 700 **bao gồm tiêu đề lặp lại**; overlap tối đa
  75 từ nội dung trong cùng mục. Overlap có thể ít hơn để giữ giới hạn hoặc giữ
  nguyên khối code. Đếm theo khoảng trắng, không phải tokenizer của mô hình AI.
- Code fenced là khối nguyên vẹn. Code quá dài, tiêu đề chiếm hết giới hạn hoặc
  fence chưa đóng gây `ChunkingError`; sửa tài liệu hoặc cấu hình rồi nạp lại.
  Tài liệu chỉ có tiêu đề, không có nội dung, trả danh sách chunk rỗng.
- Mỗi chunk sao chép `document_id`, `title`, `source`, `audience`, `version`,
  `language`; không tự cấp quyền theo tên thư mục hoặc vai trò kế thừa.
- ID là SHA256 của mảng JSON `[document_id, version, section, content]` mã hóa
  UTF-8. Cùng đầu vào/cấu hình cho cùng ID; sửa nội dung/mục/version đổi ID.
  Sửa một mục không làm đổi ID các mục khác nếu version tài liệu vẫn giữ nguyên.
  Chunk trùng hệt trong cùng tài liệu được gộp theo ID.

Quyền nằm trong metadata được sao chép, không suy ra từ ID. Khi đổi audience phải
tăng version và thay thế snapshot theo quy tắc bước 3. Bước retrieval sau vẫn
phải lọc quyền của người hỏi và kiểm tra lại trước khi xây prompt.

Kiểm tra ngày 09/11/2026: **40 tests chunking**, tổng nhóm bước 1–4 **138 tests
pass**. Kho thật: **12 tài liệu APPROVED → 61 chunk**, ID không trùng, chunk lớn
nhất 127 từ. Hai tài liệu DRAFT chưa được duyệt và không sinh chunk phục vụ.

```bash
python -m pytest tests/unit/test_ai_chunking.py -q
python -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py tests/unit/test_ai_documents.py tests/unit/test_ai_chunking.py -q
```

## Provider độc lập — bước 5

- `ai/providers.py`: `EmbeddingProvider` và `LLMProvider` là Python Protocol,
  không phụ thuộc SDK, Flask, DB hoặc khóa API. Adapter local/cloud chỉ cần cung
  cấp đúng các phương thức; không bắt buộc kế thừa một class của nhà cung cấp.
- Embedding: `embed_documents(texts)` trả vector cùng thứ tự/số lượng đầu vào;
  `embed_query(text)` dùng cùng mô hình/số chiều. Batch rỗng trả `[]`. Khi đổi mô
  hình hoặc cấu hình vector phải xây lại index, không trộn với vector cũ.
- LLM: `generate(*, system_prompt, user_prompt)` nhận hai prompt tách biệt, trả
  text không rỗng. Adapter thật chịu trách nhiệm timeout hữu hạn, giới hạn output
  và cấu hình mô hình/credential ở backend; bước này chưa có adapter gọi AI thật.
- `validate_embedding`, `validate_embedding_batch`, `validate_generation` kiểm
  tra đầu ra ở ranh giới provider. Kiểm tra số vector, số chiều, kiểu dữ liệu,
  tọa độ hữu hạn và vector khác zero; trả bản sao để tránh bị sửa từ bên ngoài.
  Retriever/service ở bước sau phải gọi các helper này sau khi nhận output từ
  adapter. Chỉ khớp Protocol không chứng minh output hợp lệ hoặc câu trả lời đúng.
- Lỗi công khai: `ProviderError`, `ProviderUnavailableError`,
  `ProviderTimeoutError` và `InvalidProviderResponseError`. Timeout là một loại
  unavailable; không nhúng API key, prompt hoặc output gốc vào thông báo lỗi.
  Service ở bước sau quyết định fallback/retry có hạn mức; fake không tự retry.
- `ai/fakes.py`: `FakeEmbeddingProvider`, `FakeLLMProvider` không gọi mạng, không
  cần API key. Có thể truyền lỗi để mô phỏng timeout/mất dịch vụ/output lỗi.
  Lịch sử gọi chỉ giữ trong bộ nhớ cho test, không dùng làm audit production.

Ví dụ fixture có vector xác định, không phải embedding có chất lượng ngữ nghĩa:

```python
from cyberhub_manager.ai.fakes import FakeEmbeddingProvider, FakeLLMProvider
from cyberhub_manager.ai.providers import (
    EmbeddingProvider, LLMProvider, validate_embedding_batch,
)

embedding: EmbeddingProvider = FakeEmbeddingProvider(vectors={
    "Quy trình nạp tiền": [1.0, 0.0],
    "Nạp tiền thế nào?": [1.0, 0.0],
})
vectors = validate_embedding_batch(
    embedding.embed_documents(["Quy trình nạp tiền"]),
    expected_count=1,
    expected_dimensions=2,
)
query_vector = embedding.embed_query("Nạp tiền thế nào?")
llm: LLMProvider = FakeLLMProvider(response="Câu trả lời cố định cho kiểm thử.")
```

Khi cung cấp mapping, fake embedding từ chối text chưa được cấu hình. Khi không
cung cấp mapping, mọi text nhận cùng vector `[1.0, 0.0]` mặc định: chỉ thử luồng
dữ liệu, **không dùng để đo retrieval Hit@3 hoặc chất lượng trả lời**. Fake LLM
trả text cố định, không thực hiện giao dịch hoặc xác nhận tính đúng của nội dung.

Kiểm tra ngày 09/11/2026: **65 tests provider pass**, tổng nhóm bước 1–5 **203
tests pass**. Nhóm provider chặn socket kết nối mạng; không dùng API key/MySQL.

```bash
python -m pytest tests/unit/test_ai_providers.py -q
python -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py tests/unit/test_ai_documents.py tests/unit/test_ai_chunking.py tests/unit/test_ai_providers.py -q
```

## Vector index và Retriever — bước 6

Module: `ai/retrieval.py`; không cần FAISS, Chroma hoặc dịch vụ vector bên ngoài
cho kho nhỏ hiện tại.

- `CosineKnowledgeIndex`: chỉ mục trong bộ nhớ, chuẩn hóa vector và xếp hạng
  cosine; xử lý tọa độ rất lớn/nhỏ để tránh tràn số. Điểm bằng nhau sắp theo ID
  chunk để kết quả ổn định. Điểm cosine không phải xác suất hoặc bằng chứng đúng.
- `KnowledgeRetriever.rebuild(documents)` chunk và embed toàn bộ tài liệu APPROVED;
  `refresh(loader)` đọc lại kho thông qua loader bước 3. Không append lên chỉ mục cũ.
- `search(question=..., access=..., limit=5)` trả chunk; `search_scored(...)` trả
  `RetrievalMatch(chunk, score)` cho service bước 8 áp dụng ngưỡng căn cứ.
- Lọc audience **trước khi embed query/chấm điểm/top-k**, không để tài liệu cấm
  đẩy tài liệu hợp lệ khỏi kết quả. Không có mục được phép thì trả `[]`, không
  gọi embedding query. ADMIN không tự được đọc tài liệu chỉ dành cho CUSTOMER.
- Context phải do backend xác thực. Không nhận dictionary role/store từ client.
  Đây là tài liệu tĩnh, không có số dư/doanh thu hiện tại hoặc scope dữ liệu cơ
  sở. `store_ids=()` vẫn có thể đọc tài liệu hướng dẫn đúng role, không cấp quyền
  xem dữ liệu thật. Tài liệu VI có thể làm căn cứ cho câu trả lời EN.
- Câu hỏi tối đa 2.000 ký tự, không rỗng; `limit` là số nguyên 1–20.
  Query embedding được kiểm tra số chiều và giá trị theo snapshot đang dùng.
- Hai lần rebuild đồng thời được tuần tự hóa. Trong khi reload và khi reload
  lỗi, chỉ mục không khả dụng (`KnowledgeIndexUnavailableError`), không phục vụ
  bản APPROVED cũ có thể đã bị thu hồi. Reload thành công với kho rỗng trả `[]`.
- Nạp lại xóa tài liệu đã xóa/đổi trạng thái, thay quyền/phiên bản mới. Kết quả
  truy xuất đang chạy bị từ chối nếu snapshot thay đổi trước khi trả kết quả.
  Nếu đổi instance embedding provider phải rebuild; cấu hình/model của adapter
  đang dùng cũng phải cố định, thay mô hình phải xây lại index.

Chỉ mục chưa tự theo dõi thay đổi trên đĩa: pipeline/backend phải gọi `refresh`
khi cập nhật tri thức. Việc tạo index dùng toàn bộ tài liệu đã duyệt ở backend;
adapter embedding thực tế được lựa chọn sau phải phù hợp với quyền xử lý kho đó.
Không đưa tài liệu/role do request tự khai vào thao tác rebuild.

## Prompt có kiểm tra quyền — bước 7

Module: `ai/prompts.py`; `RAGPromptBuilder` dùng **cùng retriever** để kiểm tra lại
ngữ cảnh trước và sau khi định dạng prompt.

```python
from cyberhub_manager.ai import AIAccessContext
from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.fakes import FakeEmbeddingProvider
from cyberhub_manager.ai.prompts import RAGPromptBuilder
from cyberhub_manager.ai.retrieval import KnowledgeRetriever

retriever = KnowledgeRetriever(FakeEmbeddingProvider())
retriever.refresh(KnowledgeDocumentLoader())
# Fixture nội bộ; adapter thật phải lấy từ session được backend xác thực lại.
access = AIAccessContext(actor_id=1, role="STAFF", store_ids=(1,), language="vi")
question = "Tiền bù khi thanh toán được tính thế nào?"
chunks = retriever.search(question=question, access=access)
if chunks:
    prompt = RAGPromptBuilder(retriever).build(
        question=question, access=access, chunks=chunks,
    )
    # Bước 8 mới gọi LLM bằng hai tham số system_prompt/user_prompt tách biệt.
```

Ví dụ dùng fake hằng chỉ để thử luồng, không chứng minh tài liệu tìm được liên
quan. Chưa được tự coi `chunks != []` là đủ căn cứ để trả lời: ngưỡng/fallback
và kiểm tra câu trả lời thuộc bước 8/evaluation.

- Kiểm tra role lần hai và so sánh **toàn bộ chunk** với snapshot hiện tại: ID,
  nội dung, nguồn, audience, version... Context giả mạo, không được phép hoặc đã
  thay đổi gây `KnowledgeAccessError`, không tạo prompt chứa phần hợp lệ một nửa.
- `system_prompt` có bản VI/EN, chỉ trả lời từ context, yêu cầu nguồn, cấm suy
  đoán số liệu hiện tại và thực hiện/xác nhận giao dịch. Câu hỏi/tài liệu là dữ
  liệu không đáng tin, không được thay chỉ dẫn hệ thống.
- `user_prompt` là XML: question tách khỏi authorized_context. Escape nội dung và
  metadata để không thể đóng giả thẻ document/system. Ký tự không biểu diễn được
  trong XML gây `InvalidContextError`, không âm thầm sửa nội dung đã duyệt.
- Mỗi document có ref `S1`, `S2`... và định danh nguồn/version/section/chunk.
  `RAGPrompt.citations` do backend tạo từ chính context đã gửi, theo thứ tự ref;
  đây là các nguồn ứng viên, chưa chứng minh LLM dùng đúng hoặc kết luận đúng.
- Mặc định tối đa 5 chunk, 20.000 ký tự context **sau serialize**, gồm metadata
  và escape; không cắt mất điều kiện/ngoại lệ để vừa giới hạn. Vượt giới hạn gây
  `ContextBudgetError`. Không có context gây `InsufficientContextError`.
- Chỉ escape và tách prompt không bảo đảm LLM thật chống mọi prompt injection.
  Bước 8–10 phải kiểm tra nguồn/kết luận, ngưỡng, fallback và đánh giá mô hình.

Kiểm tra ngày 09/11/2026: bước 6–7 **83 tests pass**, toàn bộ nhóm bước 1–7
**286 tests pass**, không gọi API/MySQL. Có test lọc role trước chấm điểm, bốn vai
trò, context giả mạo, thu hồi quyền/tài liệu, rebuild đồng thời/lỗi và delimiter
injection. Chưa triển khai gọi LLM, audit hỏi đáp, API hoặc UI chat.

```bash
python -m pytest tests/unit/test_ai_retrieval.py tests/unit/test_ai_prompts.py -q
python -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py tests/unit/test_ai_documents.py tests/unit/test_ai_chunking.py tests/unit/test_ai_providers.py tests/unit/test_ai_retrieval.py tests/unit/test_ai_prompts.py -q
```

## RAG service và kiểm thử fake — bước 8–9

`ai/service.py` cung cấp `RAGAssistantService(retriever, llm, ...)` và
`ask(question=..., access=...) -> AssistantAnswer`. Service chỉ đọc tri thức,
không gọi SQL, service giao dịch hoặc thao tác cấp quyền.

- Chuẩn hóa/giới hạn câu hỏi, retrieval đúng role, lọc điểm cosine từ 0,7 mặc
  định. Không có context hoặc dưới ngưỡng trả fallback VI/EN, `grounded=False`,
  không gọi LLM và không trả citation. Ngưỡng này chưa được hiệu chỉnh cho mô
  hình thật; bước 10 phải đánh giá lại, không coi điểm là xác suất chính xác.
- Mỗi request tối đa một query embedding và một generation, không tự retry.
  Kiểm tra lại context trước/sau LLM; nguồn thu hồi trong khi chờ không được
  dùng để trả câu trả lời.
- Câu trả lời phải có nguồn hợp lệ `[S1]`... ở cuối từng dòng có nội dung. Sai
  nguồn/thiếu nguồn, HTML/link ngoài, text rỗng hoặc vượt 4.000 ký tự đều trả
  fallback an toàn. Chỉ trả các nguồn thực sự được tham chiếu, đánh lại số ref
  theo thứ tự xuất hiện. Không bịa citation từ text do LLM tự khai.
- `grounded=True` chỉ xác nhận căn cứ đúng quyền/đủ điểm và cấu trúc ref hợp lệ,
  **không chứng minh mọi kết luận được nguồn hỗ trợ**. Fake và kiểm tra cú pháp
  không thay thế đánh giá ngữ nghĩa hoặc kiểm thử prompt injection trên LLM thật.
- Deadline mặc định 15 giây dùng chung retrieval/generation, prompt tối đa
  24.000 ký tự tổng và 20.000 ký tự context. `ai/runner.py` giới hạn mặc định hai
  provider call đang chạy; quá hạn trả fallback, hết slot từ chối ngay.
  Thread quá hạn giữ slot tới khi xong; Python không hủy cưỡng bức thread.
- Giới hạn request/ký tự không phải quota tiền/tokens thực tế. Adapter thật vẫn
  phải có timeout network/inference và max output tokens. Chưa chọn/gọi adapter
  cloud, chưa phát sinh chi phí API ở giai đoạn này.
- `ai/audit.py` ghi request ID, actor/role/store/ngôn ngữ, chunk IDs, mã kết quả,
  latency và thời điểm UTC. Không ghi câu hỏi, prompt, answer hoặc lỗi SDK gốc.
  Sink lỗi thì không trả grounded answer. Sink logging mặc định cần handler
  INFO/retention do ứng dụng cấu hình; chưa có audit MySQL bền vững.
- `ai/fakes.py` có `InMemoryAssistantAuditSink` cho test. Lịch sử fake không
  được dùng thay kho audit production. Backend cần tái sử dụng service/runner
  để giới hạn worker có hiệu lực chung, không tạo service mới cho mỗi request.

Ví dụ kiểm thử một tài liệu, không gọi mạng:

```python
from cyberhub_manager.ai import AIAccessContext
from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.fakes import (
    FakeEmbeddingProvider, FakeLLMProvider, InMemoryAssistantAuditSink,
)
from cyberhub_manager.ai.retrieval import KnowledgeRetriever
from cyberhub_manager.ai.service import RAGAssistantService

payment = next(doc for doc in KnowledgeDocumentLoader().load()
               if doc.source == "staff/payment-process.md")
retriever = KnowledgeRetriever(FakeEmbeddingProvider())
retriever.rebuild([payment])
audit = InMemoryAssistantAuditSink()
assistant = RAGAssistantService(
    retriever,
    FakeLLMProvider(response="Câu trả lời cố định cho kiểm thử. [S1]"),
    audit=audit,
)
answer = assistant.ask(
    question="Giải thích quy trình thanh toán.",
    access=AIAccessContext(actor_id=1, role="STAFF", store_ids=(1,)),
)
```

Ví dụ chỉ minh họa kết nối interface: fake hằng không chứng minh nguồn `[S1]`
được chọn liên quan hoặc câu trả lời cố định đúng. Context thật ở API sau này
phải lấy từ session backend được xác thực lại, không nhận role/store từ client.

Ngày 09/11/2026: **101 tests mới** service/runner, toàn nhóm bước 1–9 **387 tests
pass**. Chi tiết và phạm vi còn lại trong
[báo cáo bước 8–9](../testing/RAG_STEPS_8_9_2026-11-09.md).

```bash
python -m pytest tests/unit/test_ai_service.py tests/unit/test_ai_runner.py -q
```

## Bộ đánh giá và UI mock — bước 10–11

Bộ câu hỏi tại `tests/fixtures/ai/evaluation_questions.json` có **27 ca**, bốn
vai trò, VI/EN, truy vấn không dấu, câu hỏi ngoài phạm vi và nguồn sai quyền/
chưa duyệt. `scripts/evaluate_rag.py` chạy loader, chunker, retrieval và service.

Baseline `LexicalEmbeddingProvider` là TF-IDF offline học từ nội dung kho, không
đọc nhãn đáp án để xếp hạng. `ExtractiveEvaluationLLM` chỉ trích đoạn đầu của
nguồn tìm được để đo luồng citation/fallback, không phải LLM thật hoặc bản dịch.
Không dùng fake embedding hằng hay vector đặt theo đáp án để công bố Hit@3.

```bash
python -m scripts.evaluate_rag --output /tmp/rag-evaluation.json
```

Với ngưỡng lexical 0,2: raw Hit@3 100%, nguồn kỳ vọng đủ ngưỡng trong top 3 **70%**,
độ phủ citation của câu có trả lời 100%, từ chối đúng **6/7 ca**, rò rỉ nguồn sai
quyền **0**. Không coi raw Hit@3 là độ chính xác trả lời. Còn một ca STAFF hỏi đổi
cấu hình thành viên nhận trích đoạn glossary không đủ để đáp ứng câu hỏi; EN và
một số câu hợp lệ còn bị từ chối vì điểm thấp. **Chưa đạt để bật AI thật.**
Ngưỡng mặc định 0,7 của service không bị sửa bởi đánh giá này.

UI mock tách khỏi ứng dụng vận hành; không sửa login, dashboard hoặc Flask API
hiện tại. Chỉ phục vụ trang/asset ở một app preview riêng:

```bash
python -m cyberhub_manager.ai.preview --host 127.0.0.1 --port 8058
```

Mở `http://127.0.0.1:8058/`. Có drawer chat, nguồn mẫu ở chế độ review, VI/EN, loading, fallback,
lỗi/thử lại, phản hồi hữu ích và hội thoại mới có xác nhận. Nút hội thoại mới hủy
reply mẫu đang chờ; Enter gửi, Shift+Enter xuống dòng. Tối đa 20 lượt trong bộ nhớ.
Không có fetch hỏi đáp, cookie, localStorage, feedback backend, dữ liệu tài khoản
hoặc role/store gửi từ client. CSP chặn kết nối API; app preview riêng không có
`/api/assistant/messages`. API bước 12 nằm trong ứng dụng Flask vận hành và
mặc định tắt. Nguồn trên UI là trích đoạn mẫu của ba quy trình, không mở toàn kho.
Giao diện mặc định ẩn mã `[S1]`, thẻ nguồn và đường dẫn Markdown; chỉ hiện câu
trả lời cho người vận hành. Muốn kiểm tra nguồn, bật checkbox trên trang preview
hoặc mở `/?review=1`. Đây chỉ là tùy chọn hiển thị trong app mock, không phải cơ
chế phân quyền. Metadata/citation và kiểm tra quyền ở RAG core vẫn giữ nguyên.

**32 tests mới** cho evaluation/preview; nhóm RAG **419 tests pass**, thêm 40
web regression = **459 tests pass**. Chrome headless kiểm tra thực tế 1280×720 và
390×844, không có request API hoặc lỗi JavaScript. Không thay thế kiểm tra thiết
bị thật/Windows DPI hoặc đánh giá LLM.

[Báo cáo, ảnh và giới hạn bước 10–11](../testing/RAG_STEPS_10_11_2026-11-09.md).

## API/session, hạn mức và audit — bước 12A–12B

`web/assistant.py` bổ sung endpoint opt-in `POST /api/assistant/messages`, dùng
auth/CSRF hiện có. Từ chối role/store/context do client gửi; lấy danh tính backend
và kiểm tra lại sau khi model trả lời. Không cho khách gọi thêm API nhân viên.

`ai/policy_store.py` dùng SQLite riêng cho hạn mức/audit metadata một host, không
lưu câu hỏi, prompt hoặc câu trả lời. Admission và quota trong cùng transaction;
provider/audit lỗi không trả nội dung. Hạn mức mặc định 10/phút/actor,
100/ngày/actor, 1.000/ngày toàn app; dùng cửa sổ UTC, không reset theo cơ sở/role.

Mặc định tắt, chưa cấu hình model thật, chưa nối UI hoặc lưu hội thoại/feedback.
Nhiều host cần adapter DB chung; không dùng mỗi replica một SQLite file.
**530 tests RAG/web pass**, trong đó nhóm tập trung service/policy/HTTP 138 pass.
Không phải integration MySQL hoặc đánh giá chất lượng LLM thật.

[Contract/cách kiểm tra/việc còn lại](../testing/RAG_STEP_12AB_2026-11-09.md).

```bash
python -m pytest tests/unit/test_ai_evaluation.py tests/unit/test_ai_preview.py -q
```

Kiểm tra model và cấu trúc kho tài liệu:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py -q
```

## Bản tích hợp model local — bước 12C–12D

Xem [runbook RAG 5A](../RAG_5A_RUNBOOK.md) để chạy web có đăng nhập tại cổng 8059,
và [báo cáo local](../testing/RAG_5A_LOCAL_ACCEPTANCE_2026-11-09.md) để xem kết quả
mô hình thật. Các số đo bước 10–11 và 12A–12B ở trên là mốc lịch sử, không phải
kết quả model local mới. Corpus hiện có 12 tài liệu APPROVED, 62 chunk; tài liệu
thanh toán và glossary version 2 đã giải thích tiền khách đưa/tiền thừa đúng SES-08.
Hai DRAFT giữ nguyên. Mặc định RAG vẫn tắt trong app thường; helper mới bật local.

Runtime dùng Qwen embedding và LLM local, có passage-ID/numeric gate và lượt kiểm tra
nghĩa; không gửi tài liệu ra cloud, không thực hiện giao dịch. Ngưỡng 0,53 chỉ được
hiệu chỉnh cho bộ model/corpus trong báo cáo, không dùng như xác suất đúng 53%.
