# Bàn giao công việc tiếp theo — CyberHub Manager

Ngày cập nhật: 09/11/2026, giờ Việt Nam.

Branch bàn giao: **`feat/rag-knowledge-assistant`**. Branch đã tích hợp `develop`
đến commit `5341162` (PR #33 của Linh, phân quyền doanh thu), cùng phần RAG 5A
bước 1–2 tại commit `1e15f9a`. Người nhận cần đọc tài liệu này trước khi nhận việc.

## 1. Trạng thái hiện tại và phân công

| Hạng mục | Trạng thái | Công việc tiếp theo |
|---|---|---|
| Đợt 0 — Phân quyền | Cốt lõi đã kiểm tra pass | Đồng bộ tài liệu và xác định audit demo |
| Đợt 1 — Menu đồ ăn/đồ uống | Chưa triển khai | Người nhận làm menu và quản trị món |
| Đợt 2 — Voucher | Chưa triển khai | Làm sau khi chốt nghiệp vụ sử dụng voucher |
| Đợt 3 — Game/xu | Chưa triển khai | Dùng nền voucher và sổ giao dịch xu |
| Đợt 4 — Quảng cáo | Chưa triển khai | Làm khi game/voucher và xác minh thưởng ổn định |
| Đợt 5A — RAG tài liệu | Đã làm bước 1–2 | Hoàng Anh tiếp tục loader, chunking và các bước sau |
| Đợt 5B — AI phân tích số liệu | Chưa triển khai | Cần API dữ liệu đúng quyền và phạm vi cơ sở |
| Đợt 5C — AI tư vấn dịch vụ mở rộng | Chưa triển khai | Kết nối menu/voucher/game sau khi có dữ liệu |

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
- Chưa có loader, embedding, chỉ mục vector, LLM, API chat hoặc UI chat.

Sau khi đồng bộ `develop` vào branch bàn giao, đã chạy lại nhóm RAG và
ReportService: **122 tests pass** (09/11/2026):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py tests/unit/test_report_service.py -q
```

### Bước 3 — Loader và kiểm tra tài liệu

- Chỉ đọc Markdown nghiệp vụ trong knowledge root; bỏ README và bản chưa duyệt.
- Parse metadata an toàn; chặn ID trùng, audience không hợp lệ, version sai.
- Kiểm tra đường dẫn thực, không đi qua symlink ra ngoài thư mục cho phép.
- Ánh xạ metadata vào KnowledgeDocument đúng hợp đồng trong README của kho.
- Khi tài liệu đổi audience/status/version, pipeline sau phải thay thế hoặc
  thu hồi các chunk cũ; không giữ bản APPROVED cũ khi bản mới bị thu hồi.

Nghiệm thu: file không hợp lệ báo lỗi rõ; chỉ APPROVED được đưa tiếp vào pipeline;
test đường dẫn thoát thư mục, duplicate ID, DRAFT/ARCHIVED không được phục vụ.

### Bước 4 — Chunking có giữ ngữ nghĩa

- Chia theo tiêu đề/mục, giữ ngữ cảnh; giới hạn độ dài có thể cấu hình.
- ID ổn định từ tài liệu, version, section và content.
- Giữ document ID, source, section, audience, language, version.
- Không ghép nội dung có đối tượng được đọc khác nhau.

Nghiệm thu: cùng đầu vào cho cùng chunk ID; sửa nội dung/version đổi ID tương
ứng; giữ nguồn truy vết; không làm mất điều kiện hoặc ngoại lệ quan trọng.

### Các bước tiếp theo sau 3–4

1. Provider embedding và LLM độc lập, fake provider cho unit test.
2. Retrieval lọc quyền trước khi đưa nội dung vào prompt, kiểm tra lại khi tạo context.
3. RAG service trả lời có nguồn, fallback khi thiếu căn cứ, timeout và giới hạn chi phí.
4. Bộ câu hỏi đánh giá retrieval, grounded answer và từ chối ngoài quyền.
5. UI chat mock, sau đó nối Flask/session theo quyền Đợt 0.
6. Integration/security tests; danh tính, role và cơ sở phải do backend cấp.

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
