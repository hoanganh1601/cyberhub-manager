# P1 desktop/web — kiểm tra ngày 08/11/2026

Nhánh: `feat/p1-desktop-web`; nền `develop` `2424c12`. Không merge 5 PR UI cũ.

## Kết quả tự động

| Bộ kiểm tra | Kết quả |
|---|---:|
| `python -m pytest tests/unit -q` | 1.000 passed |
| `python -m pytest tests/integration -q` | 198 passed |
| Kiểm tra riêng P1 desktop/service/HTTP sau chỉnh giao diện | 26 passed |
| `python -m pip check` | Không có dependency lỗi |
| Python compile, Node syntax cho app.js/p1.js, `git diff --check` | Pass |

Môi trường: Windows, Python 3.13.14, MySQL 8.4 trong container riêng, database
`cyberhub_manager_test` ở cổng 3317. Integration không dùng database vận hành.

Kiểm tra P1 bao gồm: chọn mốc cao nhất, ưu tiên chính sách cơ sở khi bằng mốc,
biên thời gian hiệu lực, không cộng dồn, từ chối khoảng chồng nhau, nạp/thưởng cùng transaction,
hoàn tác khi ghi sổ thưởng thất bại, trừ thưởng trước, chụp khoản thưởng vào hóa đơn,
chống cấp quyền vượt vai trò/khác cơ sở, thu hồi quyền khi khóa nhân viên, rollback thay đổi mật khẩu
khi audit thất bại, bảo vệ Admin, giới hạn cổng khách hàng theo chủ tài khoản,
escaping HTML/CSV, xuất hóa đơn theo cơ sở, bootstrap Admin không nâng quyền nhân viên cũ.

## Kiểm tra giao diện và trình duyệt

Chromium headless ở 1366/1440px và 390px, không có lỗi JavaScript trong các luồng đã chạy:

* Admin đăng nhập, mở Nhân viên/Khuyến mãi/Cơ sở, mở biểu mẫu.
* Tạo cơ sở, chuyển cơ sở, tạo nhân viên STAFF.
* Tạo mốc nạp 100.000 / 10%, xem trước thưởng 10.000 và lưu lần nạp; chi tiết khách hiển thị hai ví.
* Mở hóa đơn ở cửa sổ biên lai HTML để in/lưu PDF.
* Khách đăng nhập cổng riêng, chuyển VI/EN; lịch sử trên điện thoại hiển thị dạng thẻ, không tràn trang.
* Desktop: dựng các màn quản trị, gửi biểu mẫu qua service thật dùng adapter bộ nhớ, cổng khách hàng,
  kiểm tra bản dịch và vị trí modal theo cửa sổ chủ. Icon sidebar vẽ theo cùng hệ outline.

Ảnh đối chiếu:

* [Desktop — Nhân viên](p1-evidence/desktop-employees.png)
* [Web — Nhân viên](p1-evidence/web-employees.png)
* [Web — Khuyến mãi](p1-evidence/web-promotions.png)
* [Web — Cơ sở](p1-evidence/web-stores.png)
* [Cổng khách hàng](p1-evidence/web-customer.png)
* [Cổng khách hàng trên điện thoại](p1-evidence/web-customer-mobile.png)

## Database local

Database `.env` đang trỏ tới `cyberhub_manager` có đủ 8 bảng P0, tất cả đều 0 dòng,
nhưng `schema_migrations` trống. Đã đối chiếu `SHOW CREATE TABLE` của từng bảng với database
tham chiếu tạo mới từ 001+002: khớp hoàn toàn, gồm cột/ràng buộc/index.

Đã lưu backup local không đưa lên Git:
`backups/cyberhub_manager-before-p1-20261108.sql.gz`.
Sau đối chiếu, ghi checksum 001/002 hiện có và chạy migration 003. Không sửa nội dung migration cũ,
không reset bảng, không thêm tài khoản/mật khẩu/chính sách demo vào MySQL.

Database local đã có schema P1 nhưng chưa có cơ sở/nhân viên. Dùng `--mock`/web `demo` để xem UI ngay;
khởi tạo dữ liệu và Admin riêng khi chuyển sang MySQL theo hướng dẫn P1.

## Phạm vi đã kiểm tra

Đã kiểm tra tạo file HTML/CSV, quyền truy cập và mở biên lai; in giấy thực tế cần người dùng kiểm tra
với máy in đang dùng. Bản demo web tách dữ liệu theo phiên đăng nhập; kiểm tra chia sẻ dữ liệu giữa
desktop/web hoặc nhiều máy phải dùng cùng MySQL. Chưa triển khai lại hosting hay push nhánh lên GitHub.

Xem [hướng dẫn vận hành và nghiệm thu](../P1_DESKTOP_WEB.md).
