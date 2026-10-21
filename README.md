# CyberHub Manager — Hệ thống quản lý quán Net

**Tên sản phẩm:** CyberHub Manager  
**Tên đề tài:** Xây dựng hệ thống quản lý quán Net  
**Tagline:** Vận hành thông minh — Quản lý tập trung

Tên “CyberHub” thể hiện một trung tâm kết nối máy tính, khách hàng và hoạt động vận hành. Tên đủ ngắn để dùng trên logo, màn hình đăng nhập, repository, slide và video demo.

Thư mục này **không chứa code implementation**. Đây là bộ tài liệu thống nhất để ba thành viên tự triển khai bài tập lớn Python + SQL về hệ thống quản lý quán net.

## Quyết định chung đã chốt

- Tên repository/thư mục dự án: `cyberhub-manager`.
- Tên Python package/import: `cyberhub_manager` — Python không dùng dấu gạch ngang trong tên package.
- Sản phẩm: ứng dụng desktop cho nhân viên/quản lý quán net.
- Python: 3.11 trở lên.
- Frontend: `CustomTkinter` (giao diện desktop, thống nhất theme tại tài liệu UI).
- Database: MySQL 8.4 LTS; storage engine `InnoDB`; Python kết nối bằng `mysql-connector-python`.
- Kiến trúc: Layered Architecture, chiều phụ thuộc `UI -> Service -> Repository -> Database`.
- Tiền tệ: lưu bằng `BIGINT` có dấu theo đơn vị VND, không dùng `FLOAT`/`DOUBLE`.
- Đồng thời: khóa bản ghi bằng `SELECT ... FOR UPDATE` trong luồng nạp tiền, mở phiên và checkout.
- Mật khẩu: chỉ lưu password hash, không lưu plain text.
- Phạm vi bắt buộc: đăng nhập nhân viên, khách hàng/tài khoản, máy, nạp tiền, mở/đóng phiên, hóa đơn và doanh thu ngày.
- Phạm vi sau MVP: khuyến mãi, phân quyền chi tiết, quản lý dịch vụ/sản phẩm.

## Tài liệu bàn giao

1. [Yêu cầu sản phẩm](docs/01_REQUIREMENTS.md)
2. [Khung code và hợp đồng module](docs/02_CODEBASE_SKELETON.md)
3. [Theme và quy chuẩn frontend](docs/03_UI_THEME.md)
4. [Phân công 3 thành viên và backlog Linear](docs/04_LINEAR_BACKLOG.md)
5. [GitHub workflow cho nhóm 3 người](docs/05_GITHUB_WORKFLOW.md)
6. [Checklist kickoff trước khi code](docs/06_KICKOFF_CHECKLIST.md)
7. [CSV để nhập task vào Linear](docs/linear_import.csv)

## Thứ tự nhóm nên thực hiện

1. Cả nhóm review và khóa các tài liệu trong thư mục `docs/`.
2. Hoàng Anh tạo repository, skeleton folder và schema SQL.
3. Linh triển khai domain/service dựa trên contract đã chốt.
4. Ngát dựng UI bằng mock data ngay từ đầu, sau đó thay mock bằng service thật.
5. Tích hợp theo từng vertical slice: Login → Khách hàng → Nạp tiền → Mở phiên → Checkout → Báo cáo.

Mọi thay đổi tên bảng, field, hàm service hoặc màu theme phải được cập nhật vào tài liệu tương ứng trước khi merge code.
