# Các lựa chọn API miễn phí — kiểm tra ngày 10/11/2026

CyberHub hiện dùng Gemini API cho cả embedding và LLM. Các dịch vụ bên dưới là gợi ý
khi cần dự phòng; key của chúng không thay trực tiếp cho `GEMINI_API_KEY`.

| Dịch vụ | Hình thức miễn phí | Lưu ý cho CyberHub |
|---|---|---|
| [Gemini / Google AI Studio](https://ai.google.dev/gemini-api/docs/pricing) | Free tier cho một số model, gồm model mặc định hiện tại | Đã tích hợp cả embedding và sinh/kiểm chứng; quota cụ thể xem trong project AI Studio. |
| [GroqCloud](https://console.groq.com/docs/rate-limits) | Free Plan, giới hạn theo model và tổ chức | Ưu tiên cân nhắc làm LLM dự phòng. Cần adapter và model hỗ trợ structured output; kiểm tra cả giới hạn token/phút. |
| [OpenRouter](https://openrouter.ai/collections/free-models) | Các model có ID kết thúc `:free` | Không cần mua credit cho các biến thể `:free`; giới hạn thông thường 20 request/phút, 50 request/ngày khi chưa mua credit. Năng lực/quota phụ thuộc model và nhà cung cấp phía sau. |

## Khi Gemini hết hạn mức

Key là thông tin xác thực, không phải một gói lượt hỏi riêng. Theo
[tài liệu Google](https://ai.google.dev/gemini-api/docs/rate-limits), quota áp dụng theo project,
không theo từng key: tạo key khác trong cùng project không tăng quota.
Nếu chạm giới hạn theo phút, chờ rồi thử lại; giới hạn theo ngày phải chờ reset hoặc kiểm tra tier.

Nếu chuyển LLM sang Groq/OpenRouter, còn cần xử lý phần embedding riêng: chỉ đổi LLM không
giải quyết được trường hợp Gemini embedding cũng hết quota. Không trộn vector từ model embedding
khác vào index hiện có; cần tạo lại index bằng một cấu hình embedding nhất quán.

Chatbot thực hiện tối đa hai request LLM cho một câu trả lời (sinh và kiểm chứng), nên 50 request
không tương đương 50 lượt hỏi. Dịch vụ miễn phí có thể thay đổi model/hạn mức; kiểm tra dashboard
và chính sách dữ liệu của dịch vụ trước khi dùng thông tin khách hàng thật.

Không tự chuyển API key giữa các dịch vụ, không tự bật billing hay tự gửi dữ liệu sang nhà cung cấp
khác. Cấu hình nhà cung cấp mới cần được triển khai và kiểm thử riêng.
