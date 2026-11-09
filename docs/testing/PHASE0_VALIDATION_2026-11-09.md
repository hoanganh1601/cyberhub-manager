# Kiểm tra develop — Đợt 0: phân quyền doanh thu

Ngày kiểm tra: 09/11/2026, giờ Việt Nam.

## Phiên bản và phạm vi

- Branch tại thư mục gốc: `develop`, HEAD `53411629e483b2a5523be9eccabcc161c75c2ffa`.
- Đã fetch GitHub; HEAD trùng `origin/develop` tại thời điểm kiểm tra.
- Bao gồm PR #33, commit triển khai `da5ff78` của Linh.
- Phần RAG bước 1–2 giữ trong commit local `1e15f9a`, branch
  `feat/rag-knowledge-assistant`; không nhập vào develop.
- Không thay mã nghiệp vụ hoặc áp dụng migration trong lần kiểm tra này.

## Kết quả chức năng

| Trường hợp | Kết quả |
|---|---|
| STAFF không thấy menu doanh thu trên desktop/web | PASS |
| STAFF ép điều hướng đến doanh thu ở desktop/web | PASS — bị chặn/quay về tổng quan |
| STAFF gọi trực tiếp `/api/revenue` | PASS — HTTP 403 |
| STAFF giả role qua header/query, chọn store qua query | PASS — không vượt quyền |
| STAFF vẫn truy cập danh sách/xuất hóa đơn theo quyền | PASS |
| MANAGER xem báo cáo và biểu đồ | PASS |
| MANAGER truyền ID cơ sở khác cho ReportService | PASS — PermissionDeniedError |
| MANAGER tự chuyển cơ sở qua API | PASS — HTTP 403 |
| MANAGER truyền store khác qua query doanh thu | PASS — không thay cơ sở backend đang cấp |
| ADMIN xem và chuyển cơ sở vận hành | PASS |
| MySQL ghi `REVENUE_VIEW` đúng người, cơ sở và entity ID | PASS |
| Đổi MANAGER thành STAFF khi phiên web còn mở | PASS — yêu cầu doanh thu kế tiếp bị từ chối |
| Gọi service bằng context MANAGER cũ sau khi hạ quyền | PASS — xác thực lại DB và từ chối |
| Khóa nhân viên khi phiên web còn mở | PASS — yêu cầu kế tiếp HTTP 401 |
| VI/EN trên web với từng vai trò | PASS |

ADMIN xem từng cơ sở qua chức năng đổi cơ sở hiện có. Kết quả này không xác nhận
đã có màn tổng hợp nhiều cơ sở cùng lúc. Kiểm tra trình duyệt dùng Chromium,
viewport 1440×1000; không ghi nhận JavaScript page error trong các luồng đã chạy.

## Kiểm thử tự động

**179 unit/UI tests passed**:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_report_service.py tests/unit/test_web_app.py tests/unit/test_app_shell.py tests/unit/test_ng07_invoices_reports.py tests/unit/test_p1_business.py tests/unit/test_p1_web.py tests/unit/test_p1_desktop.py -q
```

**20 integration tests passed**:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_report_flow.py tests/integration/test_web_mysql.py tests/integration/test_p1_wallet_management.py -q
```

Integration chạy với môi trường process trỏ tới MySQL test riêng
`127.0.0.1:3317`, database `cyberhub_manager_test`. Không dùng database phát triển.
Các chẩn đoán bổ sung audit, hạ quyền, khóa tài khoản và đổi cơ sở dùng fixture
tạo dữ liệu duy nhất và dọn lại sau khi kiểm tra. Không ghi mật khẩu vào báo cáo.

Kiểm tra bổ sung ngoài hai nhóm pytest: API MySQL theo từng trạng thái tài khoản,
Chromium với STAFF/MANAGER/ADMIN và điều hướng trực tiếp bằng cửa sổ desktop.
Đây là kiểm tra tập trung Đợt 0, không phải chạy lại toàn bộ test suite dự án.

## Minh chứng giao diện

- [STAFF xem hóa đơn, không có menu doanh thu](phase0/staff-invoices-no-revenue.png).
- [MANAGER xem doanh thu](phase0/manager-revenue.png).
- [ADMIN xem doanh thu](phase0/admin-revenue.png).

## Hai điểm cần đồng bộ trước khi chốt bàn giao toàn bộ

1. `docs/P1_DESKTOP_WEB.md`, bảng Phân quyền, vẫn ghi STAFF được xem doanh thu.
   Tài liệu này cần cập nhật theo chính sách mới để tránh báo cáo hoặc kho RAG
   sử dụng lại quyền cũ.
2. Audit xem doanh thu đã có ở ReportService dùng MySQL. MockReportService
   trong demo chưa ghi `REVENUE_VIEW`; web demo vẫn chặn STAFF ở API và UI.
   Nếu tiêu chí nghiệm thu yêu cầu demo cũng hiển thị đủ audit truy cập thì cần
   bổ sung vào mock, hoặc quy định rõ kiểm tra audit ở chế độ MySQL.

Kết luận: các yêu cầu cốt lõi về chặn doanh thu STAFF, giới hạn cơ sở MANAGER,
xác thực lại tài khoản và audit doanh thu MySQL đã đạt trong phạm vi kiểm tra.
Hai điểm trên là phần còn lại cần thống nhất; không có bản sửa nghiệp vụ được
tự áp dụng trong lần đánh giá này.

## Người dùng test lại

Web demo ở thư mục gốc, mở `http://127.0.0.1:8000/`, Ctrl+F5 và đăng nhập lại
sau khi server được khởi động lại:

| Vai trò | Username demo | Kỳ vọng |
|---|---|---|
| STAFF | `nhanvien01` | Không có Doanh thu; vẫn có Hóa đơn |
| MANAGER | `quanly01` | Có Doanh thu, chỉ cơ sở được giao |
| ADMIN | `admin01` | Có Doanh thu và đổi cơ sở |

Mật khẩu demo chung `demo123`, không phải tài khoản MySQL thật.
Sau khi STAFF đăng nhập, mở `/api/revenue` ở cùng trình duyệt phải bị từ chối 403.

Desktop, nếu cần kiểm tra bằng dữ liệu mẫu:

```powershell
.\.venv\Scripts\python.exe -m cyberhub_manager.app --mock
```
