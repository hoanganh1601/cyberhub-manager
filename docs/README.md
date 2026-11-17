# CyberHub Manager — tài liệu hiện hành

Đọc theo thứ tự: [chạy ứng dụng](guides/QUICKSTART.md) → [kiến trúc](architecture/OVERVIEW.md) → [luồng nghiệp vụ](architecture/BUSINESS_FLOWS.md) → [dữ liệu](architecture/DATA_MODEL.md) → [mở rộng và kiểm thử](guides/DEVELOPMENT.md).

| Bạn cần | Tài liệu |
|---|---|
| Xem nhanh web và tài khoản demo | [Quickstart](guides/QUICKSTART.md) |
| Hiểu web, desktop, service, repository và transaction | [Tổng quan kiến trúc](architecture/OVERVIEW.md) |
| Hiểu khách hàng, máy, POS, kho, ca, bảo trì, mua hàng, game và AI | [Luồng nghiệp vụ](architecture/BUSINESS_FLOWS.md) |
| Xem migration, quan hệ và giới hạn của sơ đồ | [Mô hình dữ liệu](architecture/DATA_MODEL.md), [ERD hiện hành](diagrams/current_erd.md) |
| Thêm một nghiệp vụ hoặc kiểm thử thay đổi | [Hướng dẫn phát triển](guides/DEVELOPMENT.md) |
| Cấu hình web/MySQL hoặc Gemini | [Vận hành web](guides/WEB_DEPLOYMENT.md), [Gemini](guides/GEMINI_API_RUNBOOK.md), [RAG](guides/RAG_5A_RUNBOOK.md) |
| Xem quy tắc chuyên sâu | [POS và tồn kho](features/POS_INVENTORY_LIFECYCLE.md), [ca/bảo trì/mua hàng](features/OPERATIONS_PHASE7.md), [đối tác](features/COMMERCIAL_PARTNERS.md), [dự báo](features/FORECASTING_PHASE5.md) |

**Nguồn sự thật:** trạng thái triển khai là mã trong `src/`, migration theo thứ tự trong `sql/` và test trong `tests/`. Tài liệu ở đây mô tả bản hiện tại theo mã nguồn tại ngày 17/11/2026. Sơ đồ [ERD hiện hành](diagrams/current_erd.md) được suy ra từ migration `001`–`024`; chưa xác minh bằng `INFORMATION_SCHEMA` trên MySQL trong lần kiểm kê. [Data dictionary](diagrams/data_dictionary.md) là file sinh từ DB, hiện thiếu 16/63 bảng nghiệp vụ nên không dùng làm danh sách schema đầy đủ.

[Kho tri thức](knowledge-base/README.md) là bộ tài liệu có phân quyền mà chatbot đọc lúc chạy; giữ nguyên đường dẫn này. [Tư liệu lịch sử](../history/README.md) chứa ảnh, phiếu giao việc, báo cáo nghiệm thu và tài liệu P0/đợt cũ. Không dùng những tài liệu đó để suy ra hành vi hiện tại khi mã nguồn đã thay đổi.
