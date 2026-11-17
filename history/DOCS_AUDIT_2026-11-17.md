# Kiểm kê tài liệu ngày 17/11/2026

## Kết luận và cách xử lý

Trước lượt này, `docs/` có **213 file**. Sau khi xem đường dẫn được code, script, test và README sử dụng, **184 file** có tính lịch sử được chuyển sang `history/docs/`; `docs/` còn **36 file** (21 file trong `knowledge-base/` và 15 file hướng dẫn/thiết kế/nghiệp vụ). Không xóa nội dung hay migration.

| Nhóm được chuyển | Số file | Lý do |
|---|---:|---|
| Ảnh nghiệm thu và báo cáo test theo ngày | 142 | Bằng chứng tại thời điểm test, không phải quy trình hiện hành. |
| ERD P0, ảnh sơ đồ và tài liệu UI cũ | 10 | Mô tả 8 bảng ban đầu; migration hiện có 63 bảng nghiệp vụ. |
| Backlog/handover, phiếu giao việc, yêu cầu/contract P0 | 15 | Kế hoạch và phân quyền của giai đoạn cũ. |
| Các tài liệu theo đợt, demo và API free | 11 | Trùng luồng hiện tại hoặc dựa trên thời điểm phát hành. |
| Báo cáo architecture/schema cũ, CSV Linear, HTML tham chiếu, README RAG cũ và hướng dẫn web cũ | 6 | Dùng để đối chiếu lịch sử; trang hiện hành đã tóm tắt giới hạn cần biết. |

Phần còn lại trong `docs/`: [mục lục hiện hành](../docs/README.md), kiến trúc/luồng/dữ liệu, Quickstart/hướng dẫn phát triển/vận hành, 4 quy tắc nghiệp vụ chuyên sâu, ERD hiện hành, data dictionary do script sinh, và `knowledge-base/` mà RAG đọc theo vai trò.

## Những điểm cũ hoặc chưa xác minh

- ERD P0 và các báo cáo nghiệm thu tháng 11/2026 không mô tả toàn bộ tính năng hiện tại; đã đưa ra khỏi `docs/`.
- Data dictionary sinh từ MySQL đang thiếu 16/63 bảng theo kiểm kê migration. Chưa chạy đối chiếu `INFORMATION_SCHEMA` trên DB thật trong lượt này; chưa sửa generator để tránh sinh tài liệu sai từ DB không xác định.
- Guide triển khai cũ có mô tả P0 và bước theo nhà cung cấp có thể thay đổi; [guide hiện hành](../docs/guides/WEB_DEPLOYMENT.md) chỉ nêu cấu hình có trong repo và giới hạn đã thấy trong `Dockerfile.web`.
- Kho tri thức còn một file `DRAFT` (`manager/revenue-policy.md`) và 19 file `APPROVED`; giữ nguyên nội dung/phân quyền thay vì tự duyệt lại. README cũ của kho tri thức được giữ tại `history/docs/knowledge-base/README.md`.
- Các tài liệu được lưu trong `history/` có thể chứa quyết định cũ; chỉ dùng để giải thích lịch sử và đối chiếu Git.

## Xác minh sau khi sắp xếp

- Kiểm tra 254 liên kết Markdown nội bộ: 0 đường dẫn thiếu. Chưa kiểm tra anchor tự sinh hoặc URL ngoài.
- Unit test loader/RAG: 77 pass, 4 skip vì symlink không khả dụng trên Windows.
- `git diff --check` không báo lỗi whitespace. Chưa chạy lại toàn bộ test hoặc integration MySQL; thay đổi chính là tài liệu và đường dẫn mặc định của script chụp ảnh.
