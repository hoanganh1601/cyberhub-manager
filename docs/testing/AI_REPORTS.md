# Phân loại báo cáo AI

Từ ngày 10/11/2026, source ứng dụng chỉ dùng Gemini API key. Các lệnh chạy/đánh giá cũ
cũng chuyển tiếp sang API; xem [Gemini runbook](../GEMINI_API_RUNBOOK.md).

Các tệp sau là bằng chứng lịch sử của provider trên máy trước khi chuyển đổi:

- `RAG_5A_LOCAL_ACCEPTANCE_2026-11-09.md`.
- `RAG_LOCAL_DEVELOPMENT_2026-11-09.json`.
- `RAG_LOCAL_HOLDOUT_2026-11-09.json`.
- `RAG_LOCAL_VERIFICATION_2026-11-09.json`.

Giữ nguyên tên model, hash, answer và metrics để không biến số đo cũ thành kết quả API chưa từng chạy.
Các báo cáo này không phải hướng dẫn cài đặt hiện tại và không phải kiểm chứng Gemini.

Báo cáo mới do `scripts.evaluate_rag_gemini` tạo có `mode=gemini-api-real-model` và cấu hình
model/embedding tương ứng. Lệnh này tiêu thụ quota thật khi người dùng chủ động chạy.
