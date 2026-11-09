# RAG 5A — Bản tích hợp local để nghiệm thu

Ngày 09/11/2026, branch `feat/rag-knowledge-assistant`. Chưa commit/push trong
đợt này. Phạm vi: hoàn thiện luồng 5A đọc tài liệu tĩnh, API có đăng nhập và UI
web đã duyệt. Không triển khai 5B/5C, không nhận là deployment public đã hoàn tất.

## Bản chạy

[Lệnh chạy và hướng dẫn kiểm tra](../RAG_5A_RUNBOOK.md).

- `http://127.0.0.1:8059/` hoặc Tailscale `http://100.110.233.88:8059/`.
- Cổng 8059: đăng nhập thật qua web app, AI local thật; nghiệp vụ mặc định demo.
- Cổng 8058: mock UI độc lập, không kết nối AI/API. Giữ để so sánh giao diện.
- Ollama `127.0.0.1:11435`, cloud disabled. Không mở endpoint model ra LAN.
- Chat dùng Inter cho nội dung và Space Grotesk cho tiêu đề, thống nhất với `develop`.
- Helper không tự tải model, migrate, seed, reset hoặc thay schema DB nghiệp vụ.

## Cấu hình đã kiểm tra

| Thành phần | Cấu hình |
|---|---|
| Runtime | Ollama portable v0.40.15, Linux x86_64, RTX A4000 15 GB |
| Sinh câu trả lời | `qwen3:8b`, Q4_K_M, temperature 0, seed 7, thinking off |
| Embedding | `qwen3-embedding:0.6b`, Q8_0, vector 1024 chiều |
| Kho | 12 APPROVED, 2 DRAFT không phục vụ; 62 chunk |
| Retrieval | cosine, ngưỡng 0,53; tìm top 4 sau lọc quyền |
| Context | tối đa hai tài liệu cha đã chọn, 16 chunk/14.000 ký tự; prompt 18.000 ký tự |
| Model budget | 32.768 token context, kiểm tra UTF-8 byte bảo thủ; output 768 token |
| Xác minh | tối đa một lượt kiểm tra nghĩa/phạm vi, output 1.024 token |
| Deadline | service 40 giây, native call 30 giây; UI abort 50 giây |
| Capacity | runner tối đa hai worker; Ollama một inference song song |
| Hạn mức | 10/phút/actor, 100/ngày/actor, 1.000/ngày toàn app; cửa sổ UTC |

Model tags có thể đổi theo registry. Manifest digest ghi nhận trên máy này:

- `qwen3:8b`: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- `qwen3-embedding:0.6b`: `ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`.
- Archive Ollama SHA256: `628c018404a4206493efd38e46251c154ede5141b8b8dc85c659b3b027c47379`.

Weights/runtime nằm ngoài Git ở `../cyberhub-ai-runtime/`. Không có API key cloud
hoặc câu hỏi/tài liệu gửi ra nhà cung cấp trong chế độ này. Tải weights là bước
riêng có dùng Internet; model chạy local sau khi tải.

## Những việc đã hoàn thiện

- Loader safe YAML, chặn path/symlink/ID trùng, chỉ APPROVED; chunk ổn định và
  giữ audience/version/source. Không kế thừa quyền ADMIN ngầm.
- Embedding query có instruction, cosine lọc audience trước xếp hạng. Mở rộng
  tài liệu cha để không mất ngoại lệ ở heading khác; kiểm tra lại nguồn sau LLM.
- Đổi câu trả lời sang JSON chọn passage ID do backend cấp. Backend lấy nguyên
  văn đoạn đã được phép, không tin quote hoặc URL tự tạo từ model. Kiểm tra ref,
  số liệu, ngôn ngữ và một lượt kiểm tra nghĩa/phạm vi trước khi trả answer.
- Lỗi mô hình, thiếu căn cứ, điểm thấp hoặc nguồn bị thu hồi không trả nội dung
  chưa hợp lệ. `grounded=true` chỉ biểu thị đã qua các gate, không phải xác suất
  đúng hoặc bằng chứng mọi kết luận đều chính xác.
- API dùng session/CSRF hiện có; client không chọn role/store/actor/context.
  CUSTOMER chỉ đọc corpus đúng audience, không được gọi thêm API nhân viên.
- Trong demo, inference không giữ workspace lock làm chặn logout/checkout.
  Sau model phải xác thực lại workspace/danh tính; logout hoặc đổi role/cơ sở
  khi đang chờ thì reply bị giữ lại và audit chuyển `ACCESS_CHANGED`.
- Quota admission/audit SQLite riêng, nguyên tử, fail closed và tồn tại qua
  restart. Chỉ metadata 30 ngày, không lưu question/answer/prompt/mật khẩu.
- UI có VI/EN, nguồn ẩn mặc định, retry có chủ đích, xử lý 429/503, hội thoại
  mới và bỏ reply đến muộn; logout/đổi danh tính xóa nội dung trên trang.

Một số lỗi được tìm ra trong quá trình kiểm tra và đã xử lý ở mức chặn output:
model nhỏ từng đảo ngược điều kiện mật khẩu; model tự chép quote sai; bản dịch
trả tiếng Việt khi chọn EN; prompt dài có nguy cơ mất điều kiện cuối nguồn.
Các output vi phạm bị chặn, không dùng kết quả fake để nhận là model thật đã đạt.

`staff/payment-process.md` và `shared/glossary.md` tăng version lên 2 để giải
thích tiền khách đưa/tiền thừa theo SES-08 và DTO handoff đã có. Đây là đồng bộ
định nghĩa, không đổi nghiệp vụ checkout. Hai bản DRAFT giữ nguyên.

## Kết quả tự động

Kiểm thử tập trung: **568 passed trong 28,20 giây**:

```bash
python -m pytest tests/unit/test_ai_*.py tests/unit/test_*web*.py -q
```

Bao gồm auth/CSRF, bốn role, quyền đổi giữa request, logout đồng thời khi model
đang chờ, nguồn bị thu hồi, quota cạnh tranh/restart, audit lỗi, timeout và output
không hợp lệ. Test môi trường offline không gọi model/network. `git diff --check`
và kiểm tra whitespace các file text mới đều sạch.

Chrome headless: **1280×720 và 390×844**, font Inter/Space Grotesk, chat nằm trong viewport,
VI/EN, nguồn ẩn/mở review, error/retry, 429 cooldown, XSS hiển thị text, reset khi
đang chờ và logout đều kiểm tra bằng script trong `tests/browser/`.
Kết quả JSON và ảnh đi kèm bên dưới.


Số đo cuối cùng nằm trong phần tổng hợp phía dưới và các JSON đi kèm. Các tập
27, 12 và 6 câu đã được dùng phân tích lỗi/hiệu chỉnh nên được coi là regression;
không công bố là benchmark mù độc lập. Nhãn mong đợi chỉ dùng tính điểm, không
đưa vào embedding, prompt hoặc provider. JSON có corpus hash và cờ `complete`
để phân biệt một lần chạy bị ngắt với kết quả đầy đủ.

Các unit/HTTP dùng provider giả kiểm tra ranh giới và lỗi; đánh giá local dùng
embedding + LLM thật. Kiểm tra Chrome gọi API/model thật ở lượt trả lời thông
thường. Các lỗi 503/429/late-reply được chèn chỉ để kiểm tra state UI, không tính
là khả năng sinh câu trả lời của mô hình.

## Giới hạn còn lại

- Một số câu hợp lệ vẫn bị giữ lại do điểm thấp, sai schema/số liệu/ngôn ngữ hoặc
  semantic gate. Không hạ kiểm tra quyền hay bỏ gate để tăng tỷ lệ trả lời.
- Lượt kiểm tra nghĩa vẫn là mô hình xác suất, có thể từ chối nhầm hoặc bỏ sót.
  Chưa có người phụ trách nghiệp vụ ký xác nhận mọi câu/biến thể diễn đạt.
- Không lưu hội thoại/feedback server, không có dữ liệu cá nhân hoặc phân tích
  số liệu realtime. 5A không phải chatbot tự thao tác giao dịch.
- SQLite quota/audit là một host có ổ bền vững; nhiều host cần adapter DB chung.
  Không deploy nguyên cấu hình này lên hosting filesystem tạm hoặc thiếu GPU.
- API đã có kiểm thử phiên/quyền demo; không nhận MySQL nghiệp vụ/deployment
  public đã nghiệm thu trong đợt này. Chưa tự bật feature trên develop/production.
- Đã thử mở rộng toàn bộ unit suite: nhóm Tk desktop cần DISPLAY và lỗi vì môi
  trường headless không có X server. Không nhận toàn bộ dự án pass từ nhóm RAG/web.

Đây là bản local có thể bàn giao kiểm tra 5A. Trước mở public cần review nghiệp
vụ các câu bị giữ lại, kiểm tra MySQL/deployment, HTTPS/session và quota đa host.

## Tổng hợp lần chạy cuối

| Bộ câu hỏi | Tổng | Câu hợp lệ được trả lời | Câu ngoài phạm vi/sai quyền bị giữ lại | Rò rỉ nguồn sai quyền |
|---|---:|---:|---:|---:|
| development | 27 | 19/20 | 7/7 | 0 |
| holdout | 12 | 4/8 | 4/4 | 0 |
| verification | 6 | 4/4 | 2/2 | 0 |

Tổng **45 câu**: **27/32 câu hợp lệ có trả lời**, **13/13 câu ngoài phạm vi/sai quyền không trả nội dung**, **0 rò rỉ nguồn sai audience**.
Mọi câu được trả lời có citation hợp lệ; đây là coverage, không phải điểm chính xác
ngữ nghĩa 100%. Một số ca bị giữ lại bằng HTTP 503 (INVALID_RESPONSE), không tính
chúng là lời từ chối nghiệp vụ trơn tru. Tập hợp lệ còn bị giữ lại gồm:

- `unaccented-open-session`: `INVALID_RESPONSE`.
- `holdout-stop-after-minimum`: `INVALID_RESPONSE`.
- `holdout-room-price`: `LOW_RELEVANCE`.
- `holdout-name-password`: `NO_CONTEXT`.
- `holdout-settlement-en`: `INVALID_RESPONSE`.

Độ trễ service các câu có trả lời: trung bình **8.26s**,
cao nhất **19.18s** trên máy này; đây là phép đo local,
có thể chịu tải kiểm tra trình duyệt đồng thời, không phải SLA production.
Corpus SHA256: `d5f5053d88bee8190f202874d70322a2b0847863ece91ecc37319024eb666357`.

- [Development 27 câu](RAG_LOCAL_DEVELOPMENT_2026-11-09.json).
- [Regression bổ sung 12 câu](RAG_LOCAL_HOLDOUT_2026-11-09.json). Tên file lịch sử
  dùng HOLDOUT, nhưng tập này đã dùng tìm lỗi nên không coi là đánh giá mù.
- [Verification 6 câu](RAG_LOCAL_VERIFICATION_2026-11-09.json).
- [Chrome với API/model thật](RAG_LIVE_BROWSER_2026-11-09.json).
- [Chrome với UI mock](RAG_UI_BROWSER_2026-11-09.json).
- [Ảnh chat desktop](../screenshots/rag-live/live-chat-1280.png),
  [mobile](../screenshots/rag-live/live-chat-390.png).

Đã rà các answer được trả lời cùng nguồn trong các JSON, gồm điều kiện mật khẩu,
trừ khuyến mãi trước, tiền bù/tiền thừa và giới hạn role. Chưa thay thế review của
người phụ trách nghiệp vụ; một số câu trả lời còn ngắn và chưa bao phủ mọi ý hỏi.
