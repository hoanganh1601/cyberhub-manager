# Audit và sắp xếp tài liệu, test

Lần kiểm kê 17/11/2026. Trước thay đổi: nhánh `feat/ui-ux-polish`, SHA `04978194b37d3990d74d9278397eb31f56c1d881`, working tree sạch. Nhánh riêng `refactor/docs-tests-db-audit` được tạo từ `origin/develop` tại `960beb1a0a0ffa4b4e517f6cc75f9e1ef1b6300f` (working tree sạch). Đã kiểm tra `README.md`, `pyproject.toml`, toàn bộ cây `docs/`, `tests/`, migration `sql/`, runner `scripts/`, repository/domain/service trong `src/cyberhub_manager/` và CI (không có thư mục `.github` trong checkout).

## Kiểm kê có bằng chứng

| File/nhóm | Mục đích | Status | Bằng chứng | Action | Rủi ro |
|---|---|---|---|---|---|
| `README.md`, `docs/guides/WEB_DEPLOYMENT.md` | Lệnh chạy web, MySQL, demo | CURRENT | Có lệnh demo/MySQL, chỉ rõ DB test | KEEP; liên kết từ `docs/README.md` | Thấp |
| `history/docs/demo/NG09_DEMO_UI.md` | Kịch bản/ảnh nghiệm thu desktop P0 | HISTORICAL | `scripts/capture_ui_screens.py` vẫn tham chiếu file và 18 tên ảnh; kịch bản chỉ bao phủ P0 | KEEP; giới thiệu phạm vi trong `history/docs/demo/README.md` | Thấp |
| `history/docs/archive/NG01_SCREENSHOT_EVIDENCE.md` | Dấu vết dự kiến cho ảnh | UNKNOWN | File tracked dài 0 byte; chưa tìm thấy bằng chứng sử dụng | INVESTIGATE; không xóa | Thấp |
| `history/docs/diagrams/erd.md`, `conceptual_erd.md`, `logical_erd.md`, `physical_erd.md`, PNG | Thiết kế P0 | HISTORICAL | Mô tả 8 bảng, migration `001`; SQL hiện tạo 63 bảng | KEEP, ghi chú P0; UPDATE trang tổng để trỏ ERD hiện hành | Thấp |
| `docs/diagrams/data_dictionary.md`, `scripts/gen_data_dictionary.py` | Sinh tài liệu schema từ MySQL | OUTDATED | `TABLES` có 47 tên, migration có 63; thiếu 16 bảng | INVESTIGATE/UPDATE khi MySQL test hoạt động; không sửa file sinh tay | Trung bình |
| `history/docs/testing/*_VALIDATION*`, `RAG_*`, `LI09_TEST_REPORT.md`, `HA09_DB_REVIEW.md` | Bằng chứng kiểm thử từng giai đoạn | HISTORICAL | Báo cáo lưu commit/ngày/test/ảnh riêng | KEEP; phân biệt với baseline hiện tại | Thấp |
| `history/docs/reference/01_REQUIREMENTS.md`, `history/docs/reference/07_DTO_UI_HANDOFF.md` | Contract ban đầu | HISTORICAL | Chỉ liệt kê 3 role; `history/docs/reference/02_CODEBASE_SKELETON.md` và code có 5 role | KEEP; khi cần cập nhật thì giữ bối cảnh P0 | Trung bình |
| `docs/features/OPERATIONS_PHASE7.md`, `COMMERCIAL_PARTNERS.md`, `FORECASTING_PHASE5.md` | Runbook nghiệp vụ mới | CURRENT | Khớp migration `021`–`024` và các service hiện có | KEEP, liên kết từ index | Thấp |
| `tests/unit/*.py` | 1.892 case được collect/run (gồm 5 skip) | CURRENT | 1.887 passed, 5 skipped; ba tên test lặp nhưng khác hành vi | KEEP; thêm index, chưa xóa/di chuyển | Thấp |
| `tests/conftest.py`, `tests/integration/*.py` | Fixture, DB test bảo vệ và test SQL | CURRENT | `SELECT DATABASE()`, chỉ cho `cyberhub_manager_test` | KEEP; chờ chạy khi Docker sẵn sàng | Thấp |
| `sql/001_*.sql`–`sql/024_*.sql`, `scripts/init_db.py` | Lịch sử schema và checksum | CURRENT | Runner đọc theo thứ tự tên và từ chối checksum khác | KEEP, không sửa | Cao nếu chạm |
| `src/cyberhub_manager/` | Nghiệp vụ, repo, UI | CURRENT | Repository có query tới 16 bảng bị thiếu trong dictionary | Chỉ cập nhật các dẫn chiếu đường dẫn tài liệu trong chú thích/docstring | Thấp |

77 file Markdown và 119 ảnh PNG trong `docs/`; 142 liên kết Markdown nội bộ và 2 ảnh liên kết đã kiểm tra đều tồn tại. Không có hai file tài liệu nào trùng SHA-256. Kiểm tra liên kết này chưa kiểm chứng URL bên ngoài, anchor tự động của Markdown hoặc mọi path viết trong code block; các yếu tố đó là `UNKNOWN`.

## Cấu trúc trước/sau

| Trước | Sau lượt tài liệu này |
|---|---|
| `docs/` không có trang điều hướng; 30 file Markdown ở gốc | `docs/README.md` là file Markdown duy nhất ở gốc; thêm mục lục theo thư mục |
| Tài liệu nghiệp vụ, hướng dẫn, baseline và handover lẫn ở gốc | Chuyển 29 file sang `features/`, `guides/`, `reference/`, `architecture/` và `archive/`; giữ nguyên nội dung nghiệp vụ, cập nhật các dẫn chiếu |
| `history/docs/demo/` chỉ có NG-09 P0 | Thêm `history/docs/demo/README.md`; giữ nguyên NG-09 và ảnh |
| `docs/diagrams/` chỉ có ERD P0 và dictionary 47 bảng | Thêm `current_erd.md`; trang `erd.md` và `README.md` phân biệt phạm vi |
| `tests/unit/` gồm 83 file `.py`, không có hướng dẫn riêng | Thêm `tests/unit/README.md`; không di chuyển, đổi tên, xóa test |
| `history/docs/testing/` có nhiều báo cáo theo đợt | Thêm audit hiện tại và ma trận test; báo cáo cũ giữ nguyên |

Không gộp hoặc loại bỏ tài liệu. File gốc đã được chuyển, kể cả file NG-01 rỗng, để giảm số file ở `docs/`; Git sẽ ghi nhận các thao tác này là đổi chỗ khi xem rename detection. `docs/knowledge-base/` là nguồn RAG đã duyệt: giữ nguyên vị trí và nội dung nghiệp vụ, chỉ sửa dẫn chiếu đến tài liệu đã chuyển.

## Xác minh và các việc còn lại

- Baseline unit: `1887 passed, 5 skipped` trong 493,52 giây, Python 3.13.14.
- Baseline full: `1887 passed, 5 skipped, 247 errors` trong 524,55 giây; MySQL test không kết nối được. Docker daemon tắt. Chi tiết tại [TEST_COVERAGE_AUDIT.md](TEST_COVERAGE_AUDIT.md).
- Schema thực tế và generator dictionary: **NOT VERIFIED**; xem [DATABASE_SCHEMA_AUDIT.md](../architecture/DATABASE_SCHEMA_AUDIT.md).
- Sau thay đổi: unit `1887 passed, 5 skipped` / 367,14 giây; full `1887 passed, 5 skipped, 247 errors` / 379,50 giây. 181/181 liên kết Markdown nội bộ tồn tại; `git diff --check` sạch. Kiểm tra tĩnh ERD thấy đủ 63 tên bảng và 90 cạnh FK có chứng cứ trong SQL (FK `account_transactions.promotion_id` nằm ở `ALTER TABLE`). Không có Mermaid CLI cục bộ, nên **render/syntax trong trình xem: NOT VERIFIED**. Integration giữ `NOT VERIFIED`.
- Sau khi sắp xếp thư mục và thêm mục lục: 227/227 liên kết Markdown nội bộ tồn tại; `git diff --check` sạch. Vì phần bổ sung chỉ chuyển Markdown và sửa đường dẫn trong tài liệu/chú thích, không chạy lại bộ unit/full vốn đã chạy ở bước trước.
- Các thay đổi có rủi ro trung bình (nâng generator/test dictionary, đổi chỗ test hoặc tái sinh PNG) cần cơ sở MySQL test và đối chiếu riêng; không làm trong lượt tài liệu này.

Trạng thái nghiệm thu: **PARTIALLY VERIFIED** cho đến khi full suite và `INFORMATION_SCHEMA` chạy được trên `cyberhub_manager_test`.
