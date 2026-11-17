# 3. Theme và quy chuẩn Frontend

Tên hiển thị chính thức trên giao diện: **CyberHub Manager**. Tagline chỉ dùng tại màn hình đăng nhập: **“Vận hành thông minh — Quản lý tập trung”**.

## 3.1. Hướng thiết kế

Tên theme: **Cyber Ops Dark**. Giao diện tối, tương phản cao, tập trung giúp nhân viên nhận biết trạng thái máy nhanh. Dùng `CustomTkinter` và chỉ định nghĩa token tại `ui/theme.py`; không hard-code màu/font trong từng view.

**Quy chuẩn ngôn ngữ hiển thị:**

- App Shell cung cấp lựa chọn ngôn ngữ `VI/EN`; mặc định là `VI`.
- Khi chọn `VI`, toàn bộ điều hướng, nhãn trường, nút, trạng thái, toast, dialog, lỗi nghiệp vụ, lỗi từng trường và nội dung trợ giúp phải hiển thị bằng tiếng Việt.
- Khi chọn `EN`, toàn bộ nội dung tương ứng phải lấy từ cùng khóa dịch và hiển thị bằng tiếng Anh; không trộn hai ngôn ngữ trong một màn hình.
- Không hard-code chuỗi vận hành trực tiếp trong view; view lấy nội dung qua lớp message/i18n dùng chung.
- Code, tên biến và tài liệu kỹ thuật sử dụng tiếng Anh.

## 3.2. Design tokens

### Màu

| Token | Hex | Sử dụng |
|---|---|---|
| `BG_APP` | `#0B1120` | Nền toàn ứng dụng |
| `BG_SIDEBAR` | `#111827` | Sidebar |
| `BG_SURFACE` | `#172033` | Card, panel, dialog |
| `BG_SURFACE_HOVER` | `#22304A` | Hover/selected surface |
| `BG_TOPBAR` | `#0D1626` | Thanh điều hướng trên cùng |
| `BG_CONTENT` | `#080F1E` | Nền khu vực nội dung App Shell |
| `BG_CARD` | `#111B2C` | Card trong Dashboard và các view |
| `BG_CARD_HOVER` | `#162238` | Card khi hover |
| `BG_INPUT` | `#0E1728` | Input và ô tìm kiếm |
| `BG_OVERLAY` | `#050A14` | Lớp nền tối phía sau dialog |
| `BG_NAV_ACTIVE` | `#083344` | Menu sidebar đang được chọn |
| `BG_NAV_HOVER` | `#12233A` | Menu sidebar khi hover |
| `BRAND_PRIMARY` | `#06B6D4` | Accent cyan chính của App Shell |
| `BRAND_PRIMARY_HOVER` | `#0891B2` | Accent cyan khi hover |
| `NAV_TEXT` | `#94A3B8` | Chữ menu mặc định |
| `NAV_TEXT_ACTIVE` | `#67E8F9` | Chữ menu đang được chọn |
| `BORDER` | `#334155` | Viền, divider |
| `TEXT_PRIMARY` | `#F8FAFC` | Tiêu đề/nội dung chính |
| `TEXT_SECONDARY` | `#94A3B8` | Mô tả/metadata |
| `ACCENT` | `#3B82F6` | Primary button, link, focus |
| `ACCENT_HOVER` | `#2563EB` | Hover primary |
| `SUCCESS` | `#22C55E` | Máy trống, thao tác thành công |
| `DANGER` | `#EF4444` | Máy đang dùng/cảnh báo âm/lỗi |
| `WARNING` | `#F59E0B` | Bảo trì/cảnh báo chưa chặn |
| `INFO` | `#06B6D4` | Thông tin, badge phụ |
| `DISABLED` | `#64748B` | Control bị khóa |

Trạng thái không chỉ dùng màu: luôn có icon + label “Trống”, “Đang dùng”, “Bảo trì”.

### Typography

Font mặc định: `Segoe UI`; fallback `Arial`.

App Shell và các màn nghiệp vụ dùng thống nhất Segoe UI: menu 13 px Regular,
mục đang chọn 13 px Segoe UI Semibold, tiêu đề trang 18 px Semibold.
Header logo và topbar cùng cao 64 px; sidebar dùng logo gốc trong suốt đầy đủ,
giữ tỷ lệ và không cắt biểu tượng rồi ghép chữ. Login có bộ font riêng theo Stitch.

| Style | Size/weight | Dùng cho |
|---|---|---|
| `TITLE_XL` | 28 / Bold | Tên màn hình login |
| `TITLE_LG` | 22 / Bold | Tiêu đề trang |
| `TITLE_MD` | 18 / Semibold | Dialog/card section |
| `BODY` | 14 / Regular | Nội dung/form/table |
| `BODY_STRONG` | 14 / Semibold | Nút, số liệu chính |
| `CAPTION` | 12 / Regular | Hint, thời gian, metadata |
| `MONEY` | 16 / Bold | Số dư và tổng tiền |

### Spacing và kích thước

- Grid cơ sở: 4 px; spacing hợp lệ: 4, 8, 12, 16, 24, 32.
- Border radius: input/button 8 px; card 12 px; dialog 16 px.
- Input/button cao 40 px; primary action cao 44 px.
- Component legacy vẫn giữ token `WIDTH_SIDEBAR=224` và `HEIGHT_HEADER=64` để tương thích.
- Unified App Shell dùng sidebar 208 px, topbar 56 px, status bar 28 px.
- Unified App Shell dùng content padding 16 px và card gap 12 px.
- App tối thiểu 1280×720; dialog form 480–560 px.

## 3.3. App shell

### Sidebar

Thứ tự menu cố định:

1. Tổng quan
2. Khách hàng
3. Hóa đơn
4. Doanh thu
5. Quản lý máy — chỉ Manager/Admin
6. Đăng xuất ở cuối

Item đang chọn dùng nền `BG_NAV_ACTIVE`, icon và text `NAV_TEXT_ACTIVE`. Item hover dùng `BG_NAV_HOVER`; item thường dùng `NAV_TEXT`. Không đổi vị trí menu giữa các màn.

### Header

- Topbar cao 56 px và giữ nguyên trên mọi màn hình.
- Bên trái: logo CyberHub, tên cửa hàng và ca làm việc hiện tại.
- Chính giữa: ô tìm kiếm hoặc tra cứu nhanh theo ngữ cảnh.
- Bên phải: lựa chọn `VI/EN`, tên nhân viên, role badge/avatar và đăng xuất.
- Tiêu đề màn hình và action chính đặt trong content area, không đặt lẫn vào topbar.
- Sidebar, topbar và status bar phải giữ nguyên hình học khi điều hướng giữa các view.

## 3.4. Component chuẩn

### Button

| Loại | Style | Ví dụ |
|---|---|---|
| Primary | nền `ACCENT`, chữ trắng | Tạo khách hàng, Xác nhận nạp |
| Secondary | nền surface, viền `BORDER` | Hủy, Làm mới |
| Success | nền `SUCCESS` | Mở phiên |
| Danger | nền `DANGER` | Checkout, xác nhận thao tác nguy hiểm |
| Ghost | không nền, hover surface | Xem chi tiết |

Mỗi dialog chỉ có một primary action. Khi đang xử lý: disable action và hiện “Đang xử lý…”, ngăn double click.

### Input

- Label ở trên; placeholder không thay cho label.
- Field lỗi dùng viền `DANGER` và message 12 px ngay bên dưới.
- Số tiền có hậu tố `VND`, chỉ nhận chữ số; hiển thị format sau khi mất focus.
- Password có nút hiện/ẩn.

### Data table

- Header nền `#1E293B`; row cao tối thiểu 40 px; zebra rất nhẹ hoặc hover.
- Empty state phải ghi rõ “No matching data found”.
- Loading state dùng skeleton/text, không để bảng trống gây hiểu nhầm.
- Cột tiền căn phải; tên/mô tả căn trái; trạng thái dùng badge.

### Dialog và feedback

- **Info / Success**: Không dùng popup modal nếu Toast đã đủ rõ nghĩa (tránh làm gián đoạn thao tác).
- **Validation**: Lỗi nhập liệu hiển thị trực tiếp viền đỏ và thông báo ngay tại field tương ứng.
- **Lỗi nghiệp vụ và xung đột**: Lỗi có `field_errors` được đánh dấu tại trường và hiển thị một Toast tiếng Anh. Tranh chấp máy/phiên hoặc lỗi chặn luồng dùng `ConfirmDialog.alert()`; sau khi đóng dialog, tải lại dữ liệu liên quan. Không hiển thị cả dialog và Toast cho cùng một lỗi.
- **Xác nhận thao tác**: Bắt buộc dùng `ConfirmDialog.ask()` cho các thao tác nguy hiểm hoặc ảnh hưởng tiền/dữ liệu (checkout, kết thúc/bật bảo trì, đăng xuất, khóa tài khoản).
- **Toast**: Hiển thị góc trên bên phải, tự đóng sau 3–5 giây cho các thông báo nền, cập nhật trạng thái nhanh.

## 3.5. Machine card — component quan trọng nhất

Mỗi card kích thước tối thiểu 220×150, gồm:

- Hàng 1: tên máy + status badge.
- Hàng 2: khách đang dùng hoặc “Sẵn sàng”.
- Hàng 3: thời gian đã chơi; đơn giá/giờ.
- Hàng 4: số dư ước tính nếu đang dùng.
- Footer: action chính theo trạng thái.

| Trạng thái | Viền trái/icon | Action | Nội dung |
|---|---|---|---|
| `AVAILABLE` | `SUCCESS` | “Mở máy” | đơn giá, sẵn sàng |
| `IN_USE` | `DANGER` | “Checkout” | khách, giờ bắt đầu, thời lượng, số dư live |
| `MAINTENANCE` | `WARNING` | “Bật lại” nếu có quyền | lý do/trạng thái bảo trì |

Nếu số dư ước tính âm: nền cảnh báo đỏ nhạt, icon `!`, text “Âm X VND”; không nhấp nháy liên tục.

## 3.6. Đặc tả từng màn hình

### Login

- Owner implementation: Hoàng Anh; owner theme/UI review: Ngát; business review: Linh.
- Card giữa màn hình, logo/tên sản phẩm, username, password, nút Đăng nhập.
- Enter để submit; lỗi không làm xóa username; password được xóa sau login sai.
- Không có đăng ký nhân viên ở màn này.

### Dashboard máy

- Summary bar: tổng máy, trống, đang dùng, bảo trì, tài khoản âm.
- Filter trạng thái + ô tìm tên máy.
- Grid card 4 cột ở 1280 px, co còn 3/2 cột khi cửa sổ nhỏ.
- Refresh định kỳ 15 giây và refresh ngay sau thao tác.

### Khách hàng

- Search debounce 300 ms; bảng: mã, họ tên, SĐT, username, số dư, trạng thái.
- Action: tạo khách; chọn row để xem/sửa/nạp tiền/lịch sử.
- Manager/Admin có action khóa/mở khóa; nhân viên chỉ xem trạng thái.
- Số dư âm dùng `DANGER`; không có nút sửa số dư.

### Quản lý máy — Manager/Admin

- Bảng gồm mã máy, tên, cửa hàng, trạng thái, đơn giá/giờ và lần cập nhật cuối.
- Action chính: thêm máy; action theo row: sửa, bật/tắt bảo trì, archive/xóa.
- Nhân viên `STAFF` không thấy menu; service vẫn phải kiểm tra quyền nếu bị gọi ngoài UI.
- Không cho sửa mã máy sau khi đã phát sinh phiên; không cho bảo trì/archive máy `IN_USE`.
- Khi archive máy có lịch sử, dialog phải nói rõ máy chỉ được ngừng sử dụng chứ không xóa dữ liệu.
- Sau thao tác thành công phải refresh cả màn quản lý máy và dashboard.

### Open session dialog

- Hiển thị máy đã chọn; search/chọn khách.
- Preview: số dư, số dư tối thiểu, thời gian ước tính.
- Không đủ tiền: disable “Mở phiên”, hiện CTA “Nạp tiền”.

### Checkout dialog

- Bước 1 preview: khách, máy, bắt đầu/kết thúc, số phút, phí, số dư dự kiến.
- Nếu dự kiến âm, hiện block đỏ và field “Tiền khách bù”, phương thức.
- Chỉ enable hoàn tất khi tiền bù đủ; sau thành công hiển thị receipt summary.

### Hóa đơn và doanh thu

- Quản lý máy, Hóa đơn và Doanh thu dùng chung PageHeader, MetricTile, bo góc 12 px,
  khoảng cách 12 px; bảng có hàng xen kẽ, vùng cuộn và icon thao tác có chú thích.
- Hóa đơn: bộ lọc ngày/từ khóa/trạng thái; giá trị hóa đơn được nhấn mạnh trên đầu
  panel chi tiết, panel cuộn để không mất nội dung khi cửa sổ thấp.
- Doanh thu: biểu đồ đường/cột doanh thu và biểu đồ số hóa đơn, tổng hợp ngày/tuần/tháng;
  chọn điểm/cột để lọc bảng chi tiết. Ngày không phát sinh được điền 0; chỉ cộng hóa đơn PAID.
- Phân tích phân biệt trung bình theo ngày lịch và theo ngày có doanh thu; không suy diễn
  chi phí, lợi nhuận hay cơ cấu phương thức thanh toán từ dữ liệu không có trong DTO.
- Cách chạy và kiểm tra: [Workspace UI](WORKSPACE_UI.md).

## 3.7. Quy tắc nội dung

- Dùng “Máy đang được sử dụng”, không dùng message kỹ thuật “IntegrityError”.
- Format tiền: `25.000 VND`; thời gian: `HH:mm dd/MM/yyyy`; duration: `1 giờ 12 phút`.
- Nút dùng động từ rõ: “Mở phiên”, “Xác nhận nạp”, “Hoàn tất checkout”; tránh “OK”.
- Lỗi phải nói được người dùng cần làm gì tiếp theo.

## 3.8. Checklist review UI

- Không có màu/font hard-code ngoài `theme.py`.
- Có hover, focus, loading, disabled, empty và error state.
- Double click không tạo hai giao dịch.
- Keyboard Tab/Enter hoạt động ở form chính.
- Status có chữ/icon bên cạnh màu.
- Screenshot ở 1280×720 không vỡ layout, không cắt action.
