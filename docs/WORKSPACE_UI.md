# Quản lý máy, Hóa đơn và Doanh thu

Chạy từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m cyberhub_manager.app --mock
```

Manager: `quanly01 / demo123`; Staff: `nhanvien01 / demo123`.
Để dùng MySQL đã cấu hình, bỏ `--mock`. Các UI nhận cùng service/DTO như trước.

## Tiếng Anh và vị trí hộp thoại

- Nhấn **EN** ở thanh trên để đổi cả nội dung màn đang mở và các màn tiếp theo.
- Tiêu đề, bảng, KPI, bộ lọc, trạng thái, biểu đồ, tooltip và các form nghiệp vụ đều có bản EN.
- Tên cơ sở, nhân viên, khách hàng, tên máy và mã định danh là dữ liệu nên giữ nguyên.
- EN dùng dấu phẩy phân cách hàng nghìn, thời lượng `hr / min`; ngày vẫn theo `dd/mm/yyyy` và giờ Việt Nam.
- Hộp thoại căn giữa cửa sổ chính, kể cả khi được mở từ một frame con. Vị trí tính theo scale Windows và vùng làm việc của màn hình chứa ứng dụng.
- Form sửa khách hàng rộng 620 px, tạo khách hàng 660 px (kích thước logic, trước scale Windows).
- Form tự điều chỉnh khi xuất hiện lỗi nhập liệu hoặc thay đổi nội dung; giữ các nút xác nhận trong vùng làm việc.

Mở trực tiếp bản EN với dữ liệu mẫu:

```powershell
.\.venv\Scripts\python.exe -m cyberhub_manager.app --mock --lang en
```

Kiểm tra riêng việc đổi ngôn ngữ và căn giữa:

```powershell
python -m pytest tests/unit/test_desktop_localization.py -q
```

Ảnh đối chiếu VI/EN nằm trong `docs/screenshots/localization-refresh/`.

## Quản lý máy

- Header, KPI, bộ lọc và bảng theo cùng một hệ thống thiết kế.
- Thẻ trạng thái hiển thị số lượng và tỷ lệ so với tổng máy.
- Icon sửa/bảo trì/lưu trữ có tooltip khi rê chuột.
- Máy đang sử dụng vẫn chặn bảo trì và lưu trữ; các thao tác cần xác nhận giữ nguyên.
- Bảng cuộn trong trang, không cắt mất dòng ở màn hình thấp; vẫn phân trang 7 máy.

## Hóa đơn

- KPI phân biệt tổng hóa đơn, doanh thu đã thanh toán và hóa đơn hủy.
- Bộ lọc ngày, từ khóa, trạng thái có khoảng cách thống nhất và lỗi ngay tại ô ngày.
- Bảng xen kẽ màu; ngày/giờ tách hai dòng, tên được xuống dòng khi cần.
- Ở cửa sổ hẹp, cột Thu ngân chuyển sang panel chi tiết để giữ đủ chỗ cho số tiền và trạng thái.
- Panel chi tiết ưu tiên giá trị hóa đơn ngay trên đầu, có nút sao chép mã.
- Chi tiết dài có thể cuộn; hóa đơn hủy có màu cảnh báo và không cộng vào doanh thu.

## Doanh thu và biểu đồ

1. Chọn ngày rồi nhấn **Áp dụng**, hoặc dùng **7 ngày / 30 ngày / Tháng này**.
2. Dùng **Ngày / Tuần / Tháng** để tổng hợp. Tuần bắt đầu thứ Hai; tháng theo lịch.
3. Dùng **Đường / Cột** để đổi cách hiển thị xu hướng doanh thu.
4. Biểu đồ bên cạnh thể hiện **số hóa đơn** trong cùng khoảng.
5. Rê chuột để xem doanh thu, số hóa đơn và ngày của một điểm/cột.
6. Nhấn điểm/cột để lọc bảng và phân tích khoảng đó; vùng cuộn tự chuyển tới chi tiết.
7. Nhấn **Xem toàn kỳ** để bỏ chọn. KPI phía trên luôn là số liệu toàn kỳ đang áp dụng.
8. Có thể Tab tới biểu đồ, dùng phím trái/phải và Enter để chọn.

Số liệu lấy từ `ReportService.daily_revenue`, chỉ gồm hóa đơn PAID.
Ngày không phát sinh được hiển thị bằng 0. Không tạo dữ liệu mẫu bổ sung cho biểu đồ.
Khoảng dài tự gộp các kỳ liền nhau để tối đa 60 điểm; tooltip thể hiện đúng hai đầu khoảng.

**Trung bình/ngày lịch** chia cho đủ số ngày của khoảng đã chọn.
**Trung bình/ngày có thu** chỉ chia cho các ngày service trả dữ liệu.
Giá trị trung bình/hóa đơn tính từ tổng doanh thu chia tổng số hóa đơn, không lấy
trung bình của các trung bình ngày. Đây là thống kê hiển thị, không thay đổi cách tính tiền.

Loading, lỗi và kỳ rỗng có trạng thái riêng; lỗi tải sẽ xóa số liệu biểu đồ cũ để tránh
hiểu nhầm là số liệu của bộ lọc mới. Nhấn Làm mới / Retry để thử lại.

## Kiểm tra

```powershell
python -m pytest tests/unit/test_revenue_analysis.py tests/unit/test_ng07_invoices_reports.py tests/unit/test_ng03_machines.py -q
```

Test bao gồm tổng hợp không mất tiền/số hóa đơn, ngày nhuận, tuần/tháng giao nhau,
khoảng ngày rất dài, ngày 0, lọc từ biểu đồ bằng chuột và lỗi dịch vụ.
Ảnh giao diện trong `docs/screenshots/workspace-refresh/`.

Biểu đồ dùng Canvas native của Tk; không cần cài thư viện chart hay tải thêm icon.
