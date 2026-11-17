# Tài liệu CyberHub Manager

Điểm bắt đầu cho bản hiện tại (migration `001`–`024`):

| Cần làm gì | Tài liệu |
|---|---|
| Chạy ứng dụng và chuẩn bị môi trường | [README dự án](../README.md), [web/MySQL](guides/WEB_DEPLOYMENT.md) |
| Trình diễn không cần MySQL | [Hướng dẫn demo](demo/README.md) |
| Kiểm thử | [Chiến lược và phạm vi test](testing/TEST_COVERAGE_AUDIT.md), [checklist thủ công](../tests/manual/CHECKLIST.md) |
| Đọc sơ đồ dữ liệu | [Tổng quan ERD](diagrams/erd.md), [kiểm kê schema](architecture/DATABASE_SCHEMA_AUDIT.md) |
| Nghiệp vụ hiện hành | [Ca/két, bảo trì, nhập hàng](features/OPERATIONS_PHASE7.md), [đối tác game/quảng cáo](features/COMMERCIAL_PARTNERS.md), [dự báo](features/FORECASTING_PHASE5.md) |

## Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| [`guides/`](guides/) | Hướng dẫn chạy web, đăng nhập, Gemini và RAG. |
| [`features/`](features/) | Quy trình và ghi chú theo nghiệp vụ: khách hàng, POS, kho, game, dự báo và vận hành. |
| [`reference/`](reference/) | Yêu cầu, cấu trúc ban đầu, giao diện và phân quyền P1. |
| [`architecture/`](architecture/) | Báo cáo cấu trúc mã nguồn và kiểm kê schema. |
| [`diagrams/`](diagrams/README.md) | ERD và sơ đồ thiết kế. |
| [`testing/`](testing/) | Báo cáo kiểm thử, nghiệm thu và kiểm kê test. |
| [`demo/`](demo/README.md) | Hướng dẫn trình diễn và ảnh demo. |
| [`archive/`](archive/README.md) | Handover, backlog và checklist theo giai đoạn cũ. |
| [`knowledge-base/`](knowledge-base/README.md) | Tri thức được duyệt để trợ lý sử dụng theo vai trò. |

`linear_import.csv` là dữ liệu nhập Linear, giữ ở gốc `docs/` để tiện tìm. Các file trong `archive/` và nhiều file có tên `PHASE`, `VALIDATION`, `REPORT` hoặc mã task phản ánh **thời điểm viết**; hãy đối chiếu với mã nguồn và hướng dẫn hiện hành trước khi dùng làm quy trình vận hành. Ảnh và báo cáo nghiệm thu được giữ để tra cứu lịch sử.

[Kho tri thức RAG](knowledge-base/README.md) là nội dung mà trợ lý đọc theo quyền; không dùng tài liệu vận hành nội bộ làm nguồn cho khách hàng nếu chưa được phê duyệt.
