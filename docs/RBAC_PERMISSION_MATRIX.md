# Ma trận quyền RBAC hiện hành (`legacy` vs `separated`)

**Trạng thái:** Đối chiếu trực tiếp với mã nguồn sau migration `025`–`032` ([`domain/policies.py`](../src/cyberhub_manager/domain/policies.py)). Cột **Chế độ `legacy`** là chính sách tương thích mặc định; cột **Chế độ `separated`** là chính sách tách biệt quản trị kỹ thuật (`ADMIN`) và điều hành kinh doanh (`DIRECTOR`/`MANAGER`) được kích hoạt bằng `CYBERHUB_RBAC_POLICY=separated`. Xem chi tiết chuyển đổi tại [RBAC_DESIGN.md](RBAC_DESIGN.md#7-trạng-thái-triển-khai-và-chuyển-đổi).

## Cách đọc

- **Ký hiệu vai trò:** `A` = `ADMIN`, `D` = `DIRECTOR`, `M` = `MANAGER`, `S` = `STAFF`, `K` = `KITCHEN`, `I` = `INVENTORY`, `C` = khách hàng xác thực, `*` = mọi nhân viên đang đăng nhập, `—` = không có quyền.
- `cơ sở` = đúng cơ sở đang thao tác và được giao; `chuỗi` = các cơ sở thuộc chuỗi; `bản thân` = principal của chính người dùng. Dấu `?` đánh dấu điểm cần thống nhất thêm khi mở rộng vận hành thực tế.
- Tên `Permission.*` là hằng số trong [`domain/policies.py`](../src/cyberhub_manager/domain/policies.py). Quyền UI chỉ hỗ trợ trải nghiệm, không thay thế kiểm tra ở Service/API và trigger DB.

## 1. Xác thực, cơ sở, nhân sự

| Chức năng hiện có / điểm kiểm tra | Hiện tại | Đề xuất | Phạm vi và điều kiện |
| --- | --- | --- | --- |
| Đăng nhập/đăng xuất nhân viên; tự đổi mật khẩu | Nhân viên hợp lệ | Nhân viên hợp lệ | Bản thân; đổi mật khẩu cần mật khẩu hiện tại; giữ `auth_version`. [`auth_service.py`](../src/cyberhub_manager/application/services/auth_service.py) |
| Xem danh sách cơ sở | `*` (A xem tất cả) | A: metadata tối thiểu; D: chuỗi; M: được giao; S/K/I: hiện tại | Không để quyền xem danh sách đồng nghĩa quyền vận hành. [`management_service.py`](../src/cyberhub_manager/application/services/management_service.py) |
| Chuyển cơ sở thao tác `SWITCH_STORE` | A | D; M nếu được giao nhiều cơ sở | Kiểm tra phân công còn hiệu lực; S/K/I không chuyển tùy ý. [`access.py`](../src/cyberhub_manager/application/services/access.py) |
| Tạo/sửa/ngừng cơ sở `MANAGE_STORES` | A | D | Chuỗi; chặn ngừng cơ sở còn phiên/chứng từ cần xử lý. Cấu hình kết nối/hạ tầng của cơ sở nếu phát sinh sau này thuộc A, chưa có màn riêng. |
| Xem danh sách hồ sơ nhân viên `MANAGE_EMPLOYEES` | A, M | D, M; A chỉ dữ liệu tối thiểu phục vụ identity | D: chuỗi; M: cơ sở được giao; A không xem hồ sơ kinh doanh nhạy cảm mặc định. |
| Tạo/sửa hồ sơ nhân sự (`save_employee_profile`) | D, M theo phạm vi cơ sở | D, M | Đã tách Service contract và UI Web/Desktop; D/M không được đặt username, password, role hoặc trạng thái khóa đăng nhập. |
| Tạo/sửa/khóa tài khoản nhân viên, gán role (`save_employee`) | A trong chính sách `separated` | A | Tài khoản mới phải gắn hồ sơ nhân sự đang hoạt động và chưa có identity; giữ ít nhất một ADMIN. |
| Reset mật khẩu nhân viên (`reset_employee_password`) | A | A | Không reset chính mình bằng luồng admin; audit, tăng `auth_version`, buộc đổi mật khẩu. |
| Xem audit hệ thống hoặc cấu hình kỹ thuật | Chưa có quyền/API quản trị riêng | A **khi xây dựng** | Không tính là chức năng hiện hữu; chỉ nêu trong thiết kế, không đưa thành grant chạy được. |

Nguồn: [`management_service.py`](../src/cyberhub_manager/application/services/management_service.py), [`operations_routes.py`](../src/cyberhub_manager/presentation/web/operations_routes.py), [`sql/001_initial_schema.sql`](../sql/001_initial_schema.sql).

## 2. Khách hàng, ví, máy, phiên, hóa đơn và báo cáo

| Chức năng hiện có / điểm kiểm tra | Hiện tại | Đề xuất | Phạm vi và điều kiện |
| --- | --- | --- | --- |
| Tìm/xem khách và lịch sử ví (`actor` hợp lệ) | `*`; truy vấn khách toàn cục | D, M, S; K/I chỉ nếu nhiệm vụ cần `?` | Cần chốt chính sách khách đa cơ sở; STAFF chỉ trường tối thiểu cho phục vụ, lịch sử tài chính theo quyền riêng. Đây là **khoảng trống hiện tại**. |
| Tạo khách tại quầy | `CREATE_CUSTOMERS` | M, S theo cơ sở; không A/D mặc định | Trong `separated`: bắt buộc email, tài khoản chờ kích hoạt và nhân viên không biết mật khẩu. Legacy giữ luồng cũ để không làm gián đoạn tài khoản đang dùng. |
| Sửa hồ sơ khách | `*` | M, S theo chính sách `?` | Không cho nhân viên đổi mật khẩu/email đã xác minh của khách. |
| Khóa/mở hồ sơ khách (`LOCK_CUSTOMERS`/role cứng) | A, M | M; D khi xử lý khiếu nại `?` | Audit lý do; không được dùng quyền này để sửa thông tin xác thực nhân viên. |
| Xem trước/nạp tiền ví, đọc giao dịch | `*` | M, S | Cơ sở thu tiền; ca phải mở nếu nghiệp vụ yêu cầu; giữ ledger và audit. |
| Xem máy, phòng, trạng thái | `*` | D xem tổng hợp; M, S xem cơ sở | K/I chỉ khi chức năng liên quan nhiệm vụ. |
| Thêm/sửa giá/phòng/bảo trì/archive máy `MANAGE_MACHINES` hoặc role cứng | A, M | M; D chỉ chính sách giá chuỗi nếu có chức năng riêng `?` | Cơ sở được giao; không sửa máy đang chạy trái quy tắc snapshot. |
| Mở phiên, xem trước checkout, checkout, hủy phiên (`CANCELLED`) | A, M, S | M, S | Đúng cơ sở/máy, tiền và hóa đơn; hủy phiên bị chặn nếu đã có đơn POS; D/A không tác nghiệp quầy mặc định. |
| Xem/xuất hóa đơn `EXPORT_INVOICE` | A, M, S | D, M, S | D: chuỗi; M/S: cơ sở; xuất tài liệu chỉ sau guard xem chính hóa đơn đó. |
| Hủy hóa đơn (`VOID`, `business_manager`) | A, D, M | D, M | Chỉ hủy hóa đơn `PAID` đúng cơ sở, ghi `management_audit_logs`, tự loại khỏi doanh thu và điểm thành viên. |
| Xem báo cáo doanh thu | A, M | D, M | D: chuỗi; M: cơ sở; A không xem dữ liệu doanh thu. |
| Xem phân tích & dự báo | A, M (`manager_only`) | D, M | D: chuỗi; M: cơ sở; file dự báo demo/real phải khớp store scope. |
| Xem/thay đổi chính sách nạp tiền `MANAGE_PROMOTIONS` | A, M | D: chuỗi; M: cơ sở nếu được giao chính sách `?` | Không cho M sửa chính sách toàn chuỗi; giá trị ưu đãi cần audit. |
| Xem/chỉnh cấu hình hạng thành viên (role cứng ADMIN) | A | D | Cấu hình kinh doanh toàn chuỗi; không thuộc cấu hình kỹ thuật. |

Nguồn: [`customer_service.py`](../src/cyberhub_manager/application/services/customer_service.py), [`wallet_service.py`](../src/cyberhub_manager/application/services/wallet_service.py), [`machine_service.py`](../src/cyberhub_manager/application/services/machine_service.py), [`session_service.py`](../src/cyberhub_manager/application/services/session_service.py), [`report_service.py`](../src/cyberhub_manager/application/services/report_service.py), [`forecasting_routes.py`](../src/cyberhub_manager/presentation/web/forecasting_routes.py).

## 3. POS, menu, voucher, game, quảng cáo

| Chức năng hiện có / `Permission` | Hiện tại | Đề xuất | Phạm vi và điều kiện |
| --- | --- | --- | --- |
| Xem đơn/menu quản trị `POS_VIEW_ORDERS` | A, M, S, K | M, S, K; D xem tổng hợp nếu có API phù hợp `?` | Cơ sở; I không đọc đơn khách mặc định. |
| Tạo/sửa nhóm món, món, giá, ảnh `MANAGE_MENU` | A, M | M; D quản lý chính sách giá chuỗi nếu thiết kế riêng `?` | Cơ sở; không cho A thay giá. |
| Đánh dấu món còn/hết `OPERATE` | A, M, S | M, S; K theo yêu cầu vận hành `?` | Cơ sở; hiện K không có `OPERATE` dù xem/chuẩn bị đơn. |
| Chuyển đơn sang PREPARING `POS_PREPARE_ORDERS` | A, M, S, K | M, S, K | Cơ sở, trạng thái hợp lệ. |
| Chuyển đơn sang SERVED `POS_SERVE_ORDERS` | A, M, S, K | M, S, K | Cơ sở, trạng thái hợp lệ. |
| Hủy đơn trước thanh toán `POS_CANCEL_ORDERS` | A, M, S | M, S | Cơ sở, theo vòng đời đơn. |
| Thu tiền POS `POS_COLLECT_PAYMENT` | A, M, S | M, S | Cơ sở, ghi ca/ledger, idempotency. |
| Đề nghị hủy/hoàn sau phục vụ `POS_REQUEST_REVERSAL` | A, M, S | M, S | Lý do và xử lý kho; không tự duyệt. |
| Duyệt hủy/hoàn `POS_APPROVE_REVERSAL` | A, M | M; D nếu được duyệt ngưỡng `?` | Khác người đề nghị; đúng cơ sở, ghi tiền/kho/audit. |
| Cấu hình khuyến mãi POS `MANAGE_MENU` trong Service | A, M | D nếu chính sách chuỗi, M nếu ưu đãi cơ sở `?` | Chỉ áp dụng theo phạm vi của mã khuyến mãi. |
| Danh mục phần thưởng/voucher `MANAGE_REWARDS` | A, M | D toàn chuỗi; M chỉ cơ sở | Tạo voucher toàn chuỗi hiện chỉ A; chuyển quyền chính sách sang D. |
| Phát/thu hồi voucher, xem voucher `OPERATE`/`MANAGE_REWARDS` | A, M; phần xem/đổi có S | D/M quản lý; S thao tác quầy theo quyền hiện có | Cơ sở, quota/đối tượng, audit. |
| Cấu hình vòng quay, ads nội bộ (role cứng ADMIN) | A | D | Chính sách/game/quảng cáo là kinh doanh; không để A kỹ thuật thay xác suất/phần thưởng. |
| Xem Game Center/ads quản trị `OPERATE` | A, M, S | D, M, S theo dữ liệu cần xem | Cơ sở; K/I không được cấp tự động. |
| Khách chơi game/xem ads/đổi thưởng | C | C | Chỉ tài khoản mình, server tính thưởng; không cấp quyền nhân viên. |

Nguồn: [`menu_order_service.py`](../src/cyberhub_manager/application/services/menu_order_service.py), [`menu_catalog_service.py`](../src/cyberhub_manager/application/services/menu_catalog_service.py), [`voucher_service.py`](../src/cyberhub_manager/application/services/voucher_service.py), [`game_service.py`](../src/cyberhub_manager/application/services/game_service.py), [`ad_service.py`](../src/cyberhub_manager/application/services/ad_service.py).

## 4. Kho, ca, bảo trì và mua hàng

| Chức năng hiện có / `Permission` | Hiện tại | Đề xuất | Phạm vi và điều kiện |
| --- | --- | --- | --- |
| Xem kho `INVENTORY_VIEW` | A, M, S, K, I | D: tổng hợp; M, S, K, I: cơ sở | K chỉ dữ liệu nguyên liệu cần chế biến; dữ liệu giá vốn cần quyền riêng `?`. |
| Cấu hình nguyên liệu/công thức `INVENTORY_CONFIGURE` | A, M, I | M, I; D chỉ chính sách chuẩn nếu có `?` | Cơ sở; audit định lượng và ngưỡng. |
| Nhập kho `INVENTORY_RECEIVE` | A, M, I | M, I | Cơ sở, mã chứng từ/idempotency; không đồng nghĩa duyệt phiếu mua. |
| Xuất kho `INVENTORY_ISSUE` | A, M, I | M, I | Cơ sở, lý do và ledger. |
| Lập kiểm kê `INVENTORY_COUNT` | A, M, S, I | M, S, I | Cơ sở, không tự duyệt phiếu đã lập. |
| Duyệt kiểm kê `INVENTORY_APPROVE` | A, M | M; D nếu vượt ngưỡng `?` | Khác người lập; trong transaction, audit. |
| Xem/mở/ghi thu chi/đề nghị đóng ca `SHIFT_VIEW`, `SHIFT_OPERATE` | A, M, S | M, S | Cơ sở và ca của mình; không cho A/D thu tiền tại quầy mặc định. |
| Duyệt chênh lệch/điều chỉnh két `SHIFT_REVIEW` | A, M | M; D nếu vượt ngưỡng `?` | Khác người mở ca; **điều chỉnh ca của chính mình hiện còn khoảng trống kiểm soát**. |
| Xem/báo sự cố máy `MAINTENANCE_VIEW/REPORT` | A, M, S, K, I | D xem tổng hợp; M, S, K, I: cơ sở | Theo máy và cơ sở. |
| Cập nhật xử lý sự cố `MAINTENANCE_UPDATE` | A, M, S | M, S | Người được phân công; K/I hiện không có quyền cập nhật. |
| Phân công/nghiệm thu/hủy sự cố `MAINTENANCE_MANAGE` | A, M | M | Khác người sửa khi nghiệm thu; có thể yêu cầu D nếu chi phí cao `?`. |
| Xem nhà cung cấp/đề nghị/đơn mua/công nợ `PROCUREMENT_VIEW` | A, M, I | D, M, I theo dữ liệu cần xem | I chỉ cơ sở; D toàn chuỗi. |
| Tạo đề nghị nhập `PROCUREMENT_REQUEST` | A, M, I | M, I | Cơ sở; khác người duyệt. |
| Duyệt đề nghị và tạo đơn mua `PROCUREMENT_APPROVE` | A, M | M; D nếu vượt ngưỡng `?` | Không duyệt đề nghị do mình lập; đơn mua dựa trên đề nghị đã duyệt. |
| Nhận hàng `PROCUREMENT_RECEIVE` | A, M, I | M, I | Cơ sở, số lượng/hao hụt và idempotency. |
| Thanh toán công nợ `PROCUREMENT_PAY` | A, M | M; D nếu vượt ngưỡng `?` | Cần ca thu chi; **chưa có người duyệt thanh toán riêng**. |
| Quản lý nhà cung cấp `PROCUREMENT_MANAGE_SUPPLIERS` | A, M | D, M | D cho chính sách toàn chuỗi; M cho NCC cơ sở. |

Nguồn: [`menu_inventory_service.py`](../src/cyberhub_manager/application/services/menu_inventory_service.py), [`cash_shift_service.py`](../src/cyberhub_manager/application/services/cash_shift_service.py), [`maintenance_service.py`](../src/cyberhub_manager/application/services/maintenance_service.py), [`procurement_service.py`](../src/cyberhub_manager/application/services/procurement_service.py).

## 5. Đối tác thương mại, trợ lý và cổng khách hàng

| Chức năng hiện có / `Permission` | Hiện tại | Đề xuất | Phạm vi và điều kiện |
| --- | --- | --- | --- |
| Xem vị trí/chiến dịch thương mại `COMMERCIAL_VIEW` | A, M | D: chuỗi; M: phần cơ sở | Không cho M xem hợp đồng/giá đối tác ngoài phạm vi; cần kiểm tra payload. |
| Tạo/sửa đối tác, hợp đồng, chiến dịch, vị trí `COMMERCIAL_MANAGE` | A | D | Chuỗi, có audit; A kỹ thuật chỉ cấu hình secret reference nếu tách chức năng sau này. |
| Kích hoạt hợp đồng `COMMERCIAL_MANAGE` | A | D | Người kích hoạt khác người tạo hợp đồng. |
| Tạo và duyệt đối soát `COMMERCIAL_RECONCILE` | A | D | Người duyệt khác người tạo đối soát; tránh một tài khoản làm cả hai bước. |
| Hỏi trợ lý ở chế độ tri thức | C và nhân viên xác thực theo audience | Giữ theo audience; D chỉ được thêm vào nguồn đã duyệt | RAG **không kế thừa** audience ADMIN. |
| Hỏi trợ lý analytics và báo cáo tổng hợp | A, M | D, M | D: chuỗi; M: cơ sở; A không xem dữ liệu kinh doanh. |
| Khách xem/sửa hồ sơ của mình, tự đổi mật khẩu, lịch sử, đơn và hóa đơn | C | C | Bản thân; không trộn với role nhân viên. |
| Khách tự đăng ký bằng mật khẩu rồi vào cổng ngay | Khách chưa đăng nhập | Giữ đến khi duyệt chuyển sang email `?` | Hiện chưa xác minh email; không đổi trải nghiệm khách cũ âm thầm. |

Nguồn: [`commercial_service.py`](../src/cyberhub_manager/application/services/commercial_service.py), [`assistant.py`](../src/cyberhub_manager/presentation/web/assistant.py), [`assistant_context.py`](../src/cyberhub_manager/presentation/web/assistant_context.py), [`application.py`](../src/cyberhub_manager/presentation/web/application.py), [`portal_profile.py`](../src/cyberhub_manager/application/services/portal_profile.py).

## 6. Quyền chưa tồn tại trong source: không cấp ở giai đoạn này

Đặc tả đính kèm đề xuất `customer:self_register`, `customer:create_at_counter`, `customer:view`, `customer:update_profile`, `customer:resend_activation`, `customer:change_own_password`, `customer:reset_own_password`, `customer:manage_status`. Các tên permission này chưa được đưa vào enum vì hệ thống đang dùng `Permission` hiện có. Tuy vậy, đăng ký quầy qua email, gửi lại kích hoạt và reset qua email đã có trong `separated`: token chỉ lưu hash, dùng một lần, có hạn, và yêu cầu email không tiết lộ tài khoản có tồn tại.

Khi được phê duyệt, ma trận riêng cho đăng ký email nên là:

| Tác vụ dự kiến | Chủ thể đề xuất | Điều kiện |
| --- | --- | --- |
| Tạo hồ sơ khách tại quầy và yêu cầu gửi kích hoạt | M, S quầy | Đúng cơ sở; không nhập/biết mật khẩu của khách; chống trùng; audit. |
| Gửi lại link kích hoạt | M, S quầy; C tự yêu cầu | Giới hạn tần suất, không tạo hồ sơ mới, không tiết lộ tài khoản/email tồn tại. |
| Kích hoạt/đặt mật khẩu lần đầu; tự đổi/khôi phục mật khẩu | C | Token một lần hoặc mật khẩu hiện tại; chỉ tài khoản mình; không STAFF/MANAGER/DIRECTOR/ADMIN đặt mật khẩu khách. |
| Khóa/mở hồ sơ khách | M; D khi có chính sách khiếu nại | Có lý do/audit, tách trạng thái hồ sơ khỏi trạng thái kích hoạt online. |

Không thêm role `CASHIER` ở giai đoạn này: hiện source chỉ có `STAFF`, `KITCHEN`, `INVENTORY` cho tác nghiệp. Nếu cần quyền thu ngân hẹp hơn, trình phê duyệt vị trí/permission set riêng.

## 7. Kiểm chứng ma trận khi thực thi

Với **mỗi dòng**: kiểm tra role được cho phép, role bị từ chối, cơ sở được giao và không được giao, đối tượng của cơ sở khác, phiên sau khi role bị hạ/khóa, direct API khi UI đã ẩn nút, demo và MySQL. Với dòng có duyệt: thử cùng người lập/người duyệt và hai người khác nhau; thử đồng thời hai yêu cầu. Với thao tác xem dữ liệu: kiểm tra cả list/detail/export và AI context. Chỉ coi migration hoàn tất khi không thay đổi quyền người dùng đang hoạt động ngoài danh sách chuyển đổi được phê duyệt.
