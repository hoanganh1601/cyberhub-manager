# Thiết kế RBAC: tách quản trị hệ thống và điều hành kinh doanh

**Trạng thái:** Đang triển khai theo hai bước. Thiết kế ban đầu được khảo sát trên `develop` (`960beb1`); phần mã hiện tại đã thêm vai trò DIRECTOR và chính sách tách quyền tùy chọn. Quyền tài khoản đang hoạt động chưa bị thay đổi tự động.
**Phạm vi:** Web, desktop, demo và MySQL hiện có. Tài liệu này đi cùng [ma trận quyền](RBAC_PERMISSION_MATRIX.md). Không đổi quyền của tài khoản đang hoạt động khi chỉ áp dụng tài liệu này.

## 1. Đầu vào và hiện trạng đã kiểm tra

Yêu cầu RBAC trong phiên làm việc là đầu vào chính. Đặc tả đính kèm về **đăng ký khách tại quầy và kích hoạt email** là đầu vào thứ hai. Các quyền email trong đặc tả là **tương lai**, không được coi là chức năng đã có.

| Phát hiện | Bằng chứng trong mã nguồn | Tác động |
| --- | --- | --- |
| `ADMIN` nhận toàn bộ `_MANAGER_PERMISSIONS`; `MANAGER` lại nhận toàn bộ quyền `STAFF`. `DIRECTOR` chưa tồn tại. | [`domain/p1.py`](../src/cyberhub_manager/domain/p1.py), [`domain/enums.py`](../src/cyberhub_manager/domain/enums.py) | ADMIN có thể vận hành, thu tiền, phê duyệt nghiệp vụ và xem doanh thu dù mục tiêu mới chỉ là quản trị hệ thống. |
| `KITCHEN`, `INVENTORY` là role thật, có quyền riêng; không phải tên hiển thị của `STAFF`. | [`sql/016_pos_roles.sql`](../sql/016_pos_roles.sql), [`domain/p1.py`](../src/cyberhub_manager/domain/p1.py) | Cần chính sách chuyển đổi riêng; không được xóa/hạ quyền hai nhóm này tự động. |
| Quyền được kiểm tra bằng `can()`, tập role cứng, hoặc so sánh trực tiếp `Role.ADMIN`. | [`services/management_service.py`](../src/cyberhub_manager/services/management_service.py), [`services/customer_service.py`](../src/cyberhub_manager/services/customer_service.py), [`services/report_service.py`](../src/cyberhub_manager/services/report_service.py), [`web/application.py`](../src/cyberhub_manager/web/application.py) | Sửa một bảng quyền là chưa đủ; phải đồng bộ cả Service, API, UI, desktop và demo. |
| `ADMIN` được chuyển cơ sở bất kỳ đang hoạt động; phần lớn nghiệp vụ dùng `actor.store_id` làm phạm vi. | [`services/access.py`](../src/cyberhub_manager/services/access.py), [`services/management_service.py`](../src/cyberhub_manager/services/management_service.py) | Quyền chuyển cơ sở phải chuyển sang chính sách nghiệp vụ của DIRECTOR hoặc danh sách cơ sở được giao; không lấy `store_id` từ request làm căn cứ. |
| `employees` gộp hồ sơ nhân sự, tên đăng nhập, `password_hash`, role, status và `store_id` duy nhất. `save_employee` đang cho MANAGER tạo/sửa tài khoản STAFF; chỉ ADMIN được reset mật khẩu người khác. | [`sql/001_initial_schema.sql`](../sql/001_initial_schema.sql), [`sql/020_employee_password_reset.sql`](../sql/020_employee_password_reset.sql), [`services/management_service.py`](../src/cyberhub_manager/services/management_service.py) | Chưa có ranh giới tài khoản/hồ sơ nhân sự; phải tách lệnh nghiệp vụ và quyền ở Service trước khi tách bảng. |
| Tài khoản khách là `customers` + `accounts`; tự đăng ký hiện nhận mật khẩu và đăng nhập ngay. Khách có luồng tự đổi mật khẩu. | [`web/application.py`](../src/cyberhub_manager/web/application.py), [`services/customer_service.py`](../src/cyberhub_manager/services/customer_service.py), [`services/portal_phase2.py`](../src/cyberhub_manager/services/portal_phase2.py), [`sql/001_initial_schema.sql`](../sql/001_initial_schema.sql) | Kích hoạt email, token và quên mật khẩu qua email chưa có trong luồng này; không được đưa vào ma trận quyền **hiện hữu**. |
| Tìm kiếm khách và đọc lịch sử ví dùng `customer_id` toàn cục, không lọc theo cơ sở. | [`repositories/customer_repository.py`](../src/cyberhub_manager/repositories/customer_repository.py), [`services/customer_service.py`](../src/cyberhub_manager/services/customer_service.py), [`services/wallet_service.py`](../src/cyberhub_manager/services/wallet_service.py) | Chưa thể khẳng định dữ liệu khách đã được giới hạn theo cơ sở; cần quyết định mô hình quan hệ khách–cơ sở và che dữ liệu nhạy cảm. |
| Có kiểm tra người đề nghị khác người duyệt ở kiểm kê, hủy/hoàn POS, duyệt ca, đề nghị nhập, nghiệm thu sửa chữa, kích hoạt hợp đồng và đối soát quảng cáo. | [`services/menu_inventory_service.py`](../src/cyberhub_manager/services/menu_inventory_service.py), [`services/menu_order_service.py`](../src/cyberhub_manager/services/menu_order_service.py), [`services/cash_shift_service.py`](../src/cyberhub_manager/services/cash_shift_service.py), [`services/procurement_service.py`](../src/cyberhub_manager/services/procurement_service.py), [`services/maintenance_service.py`](../src/cyberhub_manager/services/maintenance_service.py), [`services/commercial_service.py`](../src/cyberhub_manager/services/commercial_service.py) | Giữ ràng buộc maker–checker ở Service/DB transaction; role cao hơn không được bỏ qua. |
| `SHIFT_REVIEW` hiện cũng cho phép nhập điều chỉnh vào **ca của chính người có quyền review**; `PROCUREMENT_PAY` chưa có bước phê duyệt riêng cho thanh toán công nợ. | [`services/cash_shift_service.py`](../src/cyberhub_manager/services/cash_shift_service.py), [`services/procurement_service.py`](../src/cyberhub_manager/services/procurement_service.py) | Cần chốt quy tắc kiểm soát trước khi cấp DIRECTOR; không mô tả các bước này là đã được bảo vệ đầy đủ. |
| Dự báo và AI analytics nhận `MANAGER`/`ADMIN`; RAG có danh sách audience riêng, không kế thừa role. | [`web/forecasting_routes.py`](../src/cyberhub_manager/web/forecasting_routes.py), [`web/assistant_context.py`](../src/cyberhub_manager/web/assistant_context.py), [`ai/models.py`](../src/cyberhub_manager/ai/models.py) | Bổ sung DIRECTOR vào role, quyền xem dữ liệu và audience tài liệu phải xét riêng, không mở tự động mọi tri thức. |

`management_audit` hiện lưu thao tác quản trị; không nên mặc định rằng đã có màn hình/permission xem audit hệ thống. Việc cấu hình kỹ thuật, RBAC động và ngân sách kinh doanh độc lập cũng **chưa thấy là chức năng hiện hữu** trong các route/service đã khảo sát. Các quyền đó là mục tiêu kiến trúc, không được đánh dấu đã triển khai.

## 2. Mô hình đích

| Vai trò | Trách nhiệm và giới hạn |
| --- | --- |
| `ADMIN` | Quản lý tài khoản đăng nhập nhân viên, trạng thái xác thực, cấp/thu hồi role, reset mật khẩu, cấu hình kỹ thuật và audit hệ thống **khi các chức năng đó được xây dựng**. Không mặc định có quyền xem doanh thu, điều hành cửa hàng, thay giá, thu tiền hay duyệt nghiệp vụ. Được xem tối thiểu mã nhân viên, tên và cơ sở để gán tài khoản, không xem dữ liệu nhân sự nhạy cảm ngoài nhu cầu. |
| `DIRECTOR` | Điều hành toàn chuỗi: cơ sở, chính sách giá/khuyến mãi/hạng thành viên, doanh thu, dự báo, nhân sự nghiệp vụ, đối tác và hợp đồng. Không được tạo/khóa/reset thông tin xác thực hoặc tự cấp quyền. Phê duyệt nghiệp vụ chỉ khi không phải người tạo/đề nghị. |
| `MANAGER` | Điều hành cơ sở **được phân công**: máy, ca, menu, kho, nhập hàng, sự cố, khách và báo cáo theo cơ sở. Không quản lý tài khoản đăng nhập/role; không đổi cơ sở ngoài phạm vi được giao. |
| `STAFF` | Thực hiện tác nghiệp theo cơ sở và vị trí làm việc: quầy, bếp, kho. Quyền cụ thể của `KITCHEN` và `INVENTORY` hiện hữu được giữ nguyên đến khi có mapping vị trí được duyệt. |
| Khách hàng | Principal riêng từ `accounts`, chỉ thao tác trên tài khoản của mình. Không phải `Role` nhân viên và không được kế thừa quyền nhân viên. |

**Quy tắc:** quyền = `permission` **và** `scope` **và** điều kiện đối tượng/quy trình. Không dùng thứ bậc `ADMIN > DIRECTOR > MANAGER > STAFF`. Mặc định từ chối nếu thiếu quyền, cơ sở không được giao, đối tượng không thuộc phạm vi, hay vi phạm tách nhiệm vụ. Tách `view`, `create/update`, `approve`, `pay`, `credential_manage`; không dùng `MANAGE_EMPLOYEES` để đồng thời sửa hồ sơ, role và mật khẩu. Ma trận chi tiết nằm ở tài liệu kèm theo.

### Tài khoản đăng nhập và hồ sơ nhân sự

Thiết kế logic gồm **EmployeeProfile** (họ tên, cơ sở/vị trí, trạng thái làm việc do DIRECTOR/MANAGER quản lý theo chính sách) và **EmployeeIdentity** (username, hash, trạng thái đăng nhập, auth version, role grants do ADMIN quản lý). Đây là ranh giới Service trước; tách bảng vật lý chỉ sau khi có kế hoạch migration và kiểm tra mọi FK. Trạng thái nghỉ việc **không tự động** đồng nghĩa xóa hồ sơ/lịch sử; phải có quy tắc vô hiệu hóa đăng nhập đồng bộ, có audit và không làm mất chứng từ.

ADMIN tạo hoặc khóa thông tin xác thực của nhân viên dựa trên hồ sơ đã được phê duyệt; DIRECTOR không biết mật khẩu tạm hoặc hash. Nhân viên **tự đổi mật khẩu của mình** bằng mật khẩu hiện tại vẫn được giữ. `reset_employee_password` của ADMIN tiếp tục bắt buộc audit, đổi `auth_version`, yêu cầu đổi mật khẩu sau đăng nhập. ADMIN không được tự reset tài khoản mình qua luồng reset người khác; mất ADMIN cuối cùng phải có quy trình phục hồi riêng.

### Phạm vi cơ sở và dữ liệu khách

Principal lấy từ session đã được kiểm tra lại với DB; `store_id`, `role`, `employee_id` do client gửi không làm thay đổi quyền. `DIRECTOR` có thể chọn cơ sở trong phạm vi toàn chuỗi; `MANAGER` chỉ trong tập cơ sở được giao; STAFF/KITCHEN/INVENTORY chỉ cơ sở đang làm việc. Kiểm tra tại Service và điều kiện truy vấn Repository, gồm cả list, detail, export và mutation. Cơ chế `employees.store_id` hiện chỉ hỗ trợ một cơ sở gốc; nếu duyệt quản lý nhiều cơ sở cần bảng phân công và quy tắc hiệu lực/thời hạn, không ghi đè `store_id` hiện có.

`customers` hiện là dữ liệu toàn cục. Trước khi hạn chế truy cập khách theo cơ sở cần chọn một trong các cách: (a) hồ sơ khách dùng chung, nhân viên chỉ xem trường tối thiểu cho giao dịch tại cơ sở, lịch sử đầy đủ theo quyền riêng; hoặc (b) quan hệ khách–cơ sở có chứng cứ phát sinh giao dịch/đăng ký. Không thể chỉ lọc theo cơ sở đăng ký vì khách có thể dùng nhiều cơ sở. Với đăng ký qua email trong đặc tả đính kèm, hồ sơ khách có thể dùng trước kích hoạt nhưng **tài khoản online** phải chờ xác minh; email chưa xác minh không được tự cấp trạng thái ACTIVE.

### Tách nhiệm vụ và audit

- Giữ và kiểm thử `created_by/requested_by/proposed_by != approved_by/reviewed_by` ở từng giao dịch; so sánh **employee ID**, không so sánh role.
- Người mở ca không tự duyệt chênh lệch ca; người kiểm kê không tự duyệt phiếu; người yêu cầu hoàn POS không tự duyệt; người báo/sửa sự cố không tự nghiệm thu theo chính sách được phê duyệt; người tạo hợp đồng/đối soát không tự kích hoạt/duyệt.
- Đề xuất bổ sung kiểm soát điều chỉnh két và thanh toán công nợ: bản ghi lý do, chứng từ, người thực hiện và người duyệt khác nhau. Đây là **điểm cần phê duyệt**, không phải khả năng hiện có.
- Audit bảo toàn actor, role thực tế tại thời điểm thao tác, cơ sở, đối tượng, hành động, kết quả và thời gian; không ghi mật khẩu, token, secret hoặc dữ liệu khách không cần thiết. Quyền xem audit là quyền ADMIN riêng, không suy ra từ quyền thao tác kinh doanh.

## 3. Tác động triển khai khi được duyệt

| Lớp | Công việc dự kiến |
| --- | --- |
| UI Web/Desktop | Thay điều kiện `isManager()`/so sánh role bằng capability nhận từ backend; tách màn hình **Tài khoản & bảo mật** và **Nhân sự**; ẩn nút theo permission/scope; màn hình từ chối quyền rõ ràng. Chỉnh menu, nhãn role, store switch, AI analytics và demo. UI chỉ hỗ trợ trải nghiệm, không là lớp bảo mật. |
| API | Thay `manager_only` và danh sách role cứng bằng guard quyền cụ thể; phân biệt 401/403; validate scope trước khi gọi service; endpoint xem `permissions` phải trả đúng quyền thực tế. Route không tự tin cậy dữ liệu role/store trong body. |
| Service | Tách lệnh hồ sơ nhân sự và tài khoản; bỏ ADMIN khỏi quyền tác nghiệp; bổ sung DIRECTOR có giới hạn nghiệp vụ; rà toàn bộ `Role.ADMIN` trong Management, Report, Customer, Machine, Voucher, Game, Ad, Commercial, Forecast, Assistant; giữ điều kiện maker–checker. |
| Repository | Đưa bộ lọc cơ sở vào truy vấn và kiểm tra lại đối tượng khi update/approve; xử lý danh sách cơ sở được giao; tránh truy vấn khách/hóa đơn toàn cục ngoài quyền; không thay đổi số dư hay lịch sử giao dịch. |
| Database | Migration **mới** cho giá trị `DIRECTOR` trong CHECK role; tùy chính sách được duyệt, bảng phân công cơ sở và bảng identity riêng. Không sửa migration lịch sử `001`/`016`/`020`, không reset dữ liệu, không backfill role bằng suy đoán. |
| AI & tri thức | Rà `AIAccessContext`, audience tài liệu, analytics, snapshot theo store; cấp DIRECTOR rõ ràng theo nguồn; không cho ADMIN đọc tài liệu/doanh thu nghiệp vụ chỉ vì quyền kỹ thuật. |
| Tests | Bảng role × scope × hành động ở Service/API/UI, MySQL và demo; kiểm tra direct API khi nút bị ẩn; kiểm tra hạ quyền/khóa tài khoản khi session còn mở, cùng hồi quy tiền/kho/POS. |

## 4. Migration không đổi quyền âm thầm

1. **Kiểm kê chỉ đọc:** sao lưu và xuất danh sách tài khoản, role, cơ sở, trạng thái; đối chiếu permission hiện có với ma trận. Không đưa mật khẩu/hash ra báo cáo. Lập bảng mapping **từng nhân viên** và người phê duyệt.
2. **Mở rộng tương thích:** migration thêm `DIRECTOR` vào CHECK, cập nhật enum/parser và chính sách mới ở trạng thái chưa áp dụng cho tài khoản hiện hữu. Không tự gán `DIRECTOR`; không tự loại `KITCHEN`/`INVENTORY`. Có bản rollback schema tương thích.
3. **Tách interface:** dựng kiểm tra permission/scope ở Service, API và UI, chạy shadow audit/so sánh quyết định cũ–mới trên dữ liệu kiểm thử. Cảnh báo các ca bị mất hoặc thừa quyền; không âm thầm đổi hành vi production.
4. **Duyệt chuyển đổi từng tài khoản:** owner phê duyệt danh sách ADMIN kỹ thuật, DIRECTOR kinh doanh, MANAGER được giao cơ sở và vị trí STAFF; kiểm tra còn ít nhất một ADMIN và một người phê duyệt nghiệp vụ độc lập. Nếu người đang dùng ADMIN cần cả hai chức năng, cấp **hai tài khoản tách biệt** sau phê duyệt, không kế thừa quyền trong một session.
5. **Cutover có giám sát:** triển khai theo cơ sở/nhóm, revoke phiên khi đổi role hoặc phạm vi, kiểm tra 403 và SoD, audit thay đổi; lưu snapshot quyền trước cutover để đối chiếu. Rollback bằng mapping được duyệt và migration bổ sung, không rollback bằng cách bật lại quyền rộng vô điều kiện.

## 5. Quyết định cần phê duyệt trước triển khai

1. Danh sách **cụ thể** tài khoản ADMIN nào sẽ ở lại ADMIN kỹ thuật, ai trở thành DIRECTOR/MANAGER; người đang mang ADMIN cần tài khoản kinh doanh riêng hay không.
2. DIRECTOR có quyền trực tiếp tác nghiệp thu tiền/POS/kho hay chỉ xem, cấu hình và phê duyệt? Đề xuất: **không tác nghiệp hằng ngày**, chỉ phê duyệt đúng nghiệp vụ và khác người lập.
3. MANAGER được phân công nhiều cơ sở hay chỉ một; ai cấp/thu hồi phân công, hiệu lực từ ngày nào.
4. Xử lý `KITCHEN`/`INVENTORY`: giữ role chuyên trách tương thích lâu dài hay chuyển thành vị trí STAFF + permission set sau khi xác nhận từng người.
5. Chính sách hồ sơ khách dùng chung và mức dữ liệu STAFF/MANAGER được xem; đặc biệt lịch sử giao dịch, điện thoại và tài khoản khách liên cơ sở.
6. Quyền tạo/sửa hồ sơ nhân sự của MANAGER: chỉ nhân viên tại cơ sở hay DIRECTOR duyệt trước; ai cho phép thay đổi trạng thái nghỉ việc.
7. Phạm vi duyệt ngân sách/giá, hợp đồng quảng cáo và thanh toán công nợ; ngưỡng tiền và người phê duyệt thứ hai nếu cần. **Chưa có module ngân sách riêng** trong mã hiện tại.
8. Thời điểm và chính sách bật đăng ký tại quầy qua email: khách cũ giữ đăng nhập thế nào, khi nào nhân viên được xem email, thời hạn token, nhà cung cấp email. Đây là **giai đoạn chức năng khác**, chưa triển khai trong RBAC này.

## 6. Tiêu chí kiểm thử khi triển khai

- Test bảng quyền từng dòng của [ma trận](RBAC_PERMISSION_MATRIX.md) ở Service và HTTP: được phép đúng scope, bị từ chối ngoài scope, không sinh side effect khi bị từ chối.
- Test UI: menu/nút không có quyền bị ẩn; gọi URL/API trực tiếp vẫn trả 403. Test desktop và demo cùng chính sách; không dựa vào ảnh chụp UI làm chứng cứ an toàn.
- Test nâng quyền: sửa role/store/employee ID trong request hoặc session cũ; đổi role/khóa tài khoản khi đã đăng nhập; race condition giữa đọc và phê duyệt; tự phê duyệt ở cùng/khác cơ sở.
- Test dữ liệu: `ADMIN` không xem doanh thu/đơn/kho; `DIRECTOR` không reset mật khẩu nhân viên; `MANAGER` không xem dữ liệu cơ sở chưa giao; STAFF không đọc hồ sơ khách toàn chuỗi theo chính sách được duyệt.
- Test migration trên bản sao DB: kiểm đếm tài khoản/role/permissions trước–sau, giữ hash/số dư/hóa đơn/lịch sử, xác nhận rollback và đăng nhập bằng các tài khoản cũ trước cutover.

| Principal | Ca được phép phải kiểm tra | Ca bị từ chối phải kiểm tra ở **cả UI và API** |
| --- | --- | --- |
| ADMIN | Reset mật khẩu nhân viên khác, khóa tài khoản, xem audit khi có màn/API tương ứng | Doanh thu, dự báo, thanh toán POS, duyệt kiểm kê, sửa chính sách khuyến mãi và hợp đồng; tự reset bằng endpoint quản trị. |
| DIRECTOR | Xem doanh thu chuỗi, chính sách/hợp đồng được giao, quản lý hồ sơ nhân sự nghiệp vụ | Tạo/khóa/reset tài khoản nhân viên, tự duyệt hợp đồng/đối soát do mình lập, thu tiền tại quầy nếu chưa được phê duyệt. |
| MANAGER | Vận hành và phê duyệt nghiệp vụ đúng cơ sở; xem doanh thu cơ sở | Dữ liệu/đơn/khách ngoài phạm vi được giao, cấp role, reset mật khẩu nhân viên, tự duyệt phiếu của mình. |
| STAFF | Tạo khách tại quầy theo chính sách, mở phiên, thu tiền, tác nghiệp ca/POS | Phê duyệt hủy/hoàn, sửa role hoặc chính sách chuỗi, xem toàn bộ doanh thu, truy vấn khách liên cơ sở không có quyền. |
| KITCHEN | Xem/chuẩn bị/phục vụ đơn và xem nguyên liệu cần chế biến | Thu tiền POS, duyệt kho, đọc công nợ nhà cung cấp, đổi trạng thái nhân viên. |
| INVENTORY | Xem/nhập/xuất/kiểm kê kho, tạo đề nghị và nhận hàng | Tự duyệt kiểm kê/đề nghị nhập, thu tiền POS, xem doanh thu, sửa tài khoản nhân viên. |
| Khách hàng | Xem/sửa thông tin và đổi mật khẩu của chính mình, đặt món/chơi game theo chính sách | Truy cập `/api/employees`, `/api/revenue`, tài khoản khách khác hoặc các API nghiệp vụ nhân viên. |

## 7. Trạng thái triển khai và chuyển đổi

- `sql/025_director_role.sql` chỉ mở rộng CHECK của `employees.role`; không sửa role, mật khẩu hay dữ liệu người dùng hiện có. Chạy `scripts/init_db.py` sau khi sao lưu cơ sở dữ liệu và kiểm tra thứ tự migration.
- Mặc định `CYBERHUB_RBAC_POLICY=legacy`: ADMIN hiện tại vẫn dùng quyền cũ. `CYBERHUB_RBAC_POLICY=separated` giới hạn ADMIN vào quản trị thông tin xác thực nhân viên; DIRECTOR quản lý chính sách kinh doanh và xem báo cáo. Cả web, Service, demo và desktop dùng chung ma trận `permissions_for()`.
- Quy trình chuyển đổi: kiểm kê tài khoản ADMIN hiện tại; phê duyệt người giữ vai trò ADMIN kỹ thuật và người cần tài khoản DIRECTOR; tạo tài khoản DIRECTOR riêng sau migration; xác minh đăng nhập và quyền API; sau đó mới bật `separated` và khởi động lại web. Không đổi role hàng loạt hoặc bật chính sách mới trước khi có tài khoản điều hành độc lập.
- `employees` hiện vẫn là một bảng chứa cả hồ sơ và thông tin xác thực. Service đã chặn DIRECTOR/MANAGER sửa username, role, trạng thái đăng nhập và mật khẩu trong chính sách mới; ADMIN không được sửa hồ sơ nhân sự của tài khoản đã tồn tại. Đổi username, role, trạng thái hoặc cơ sở làm tăng `auth_version` và vô hiệu phiên cũ. Tạo hồ sơ mới hoàn toàn độc lập tài khoản vẫn cần migration tách bảng và quy trình phê duyệt riêng.
- Quan hệ khách hàng với cơ sở, MANAGER nhiều cơ sở và phân tách trạng thái nghỉ việc với khóa đăng nhập chưa có mô hình dữ liệu. Không coi các phạm vi đó là đã giải quyết; cần chốt chính sách và migration trước khi dùng dữ liệu thực nhiều cơ sở.
- Kiểm thử: `tests/unit/test_rbac_separation.py` kiểm tra quyền, API, chống leo thang và chuyển cơ sở ở demo. Cần kiểm tra migration và quy trình đăng nhập trên bản sao MySQL trước khi cutover.

### Bàn giao triển khai hiện tại

Các phần sau đã có code, migration và kiểm thử MySQL trên database `cyberhub_manager_test`:

- `025`: bổ sung vai trò `DIRECTOR`, giữ `CYBERHUB_RBAC_POLICY=legacy` là mặc định để không hạ quyền tài khoản đang hoạt động.
- `026`: tách hồ sơ nhân sự (`employee_profiles`) khỏi tài khoản đăng nhập theo luồng nghiệp vụ; ADMIN cấp thông tin xác thực, DIRECTOR/MANAGER quản lý hồ sơ. Thêm `employee_store_assignments` cho MANAGER đa cơ sở và `customer_store_links` cho phạm vi khách theo chứng cứ giao dịch/đăng ký.
- `026`: ca có điều chỉnh tiền phải chuyển sang chờ duyệt khi đóng; công nợ nhà cung cấp ở chính sách `separated` cần người duyệt và người thanh toán khác nhau.
- `027`: đăng ký khách tại quầy bằng email, kích hoạt/đặt lại mật khẩu qua token dùng một lần có hạn, transactional outbox và worker SMTP. Tài khoản khách hiện có vẫn đăng nhập được; chỉ tài khoản mới theo luồng quầy phải kích hoạt.
- `scripts/rbac_cutover.py`: dry-run mặc định; chỉ áp dụng mapping từng tài khoản đã có `approval_reference`, vẫn phải còn ADMIN kỹ thuật và DIRECTOR kinh doanh trước khi bật `separated`.

Các phần cần hoàn thiện hoặc quyết định trước khi đưa vào vận hành thật:

1. Lập và phê duyệt file mapping tài khoản thật, chạy `rbac_cutover.py` trên bản sao trước; không bật `CYBERHUB_RBAC_POLICY=separated` chỉ bằng suy đoán role hiện tại.
2. Cấu hình SMTP, `CYBERHUB_EMAIL_TOKEN_SECRET` và `CYBERHUB_PUBLIC_URL` HTTPS; chạy worker outbox riêng. Chưa có cơ chế scheduler/service manager để tự khởi động worker khi deploy.
3. UI Desktop mới phản ánh quyền tách ở mức menu/guard hiện có, nhưng chưa có màn hình riêng cho hồ sơ nhân sự, cấp tài khoản và phân công đa cơ sở như Web MySQL.
4. Liên kết khách–cơ sở được backfill từ hóa đơn/phiên và được nhân viên xác minh bằng mã khách + số điện thoại. Cần thống nhất chính sách hiển thị dữ liệu tối thiểu cho khách liên cơ sở trước khi mở rộng sang báo cáo hoặc export toàn chuỗi.
5. Chính sách duyệt chi mới chưa có hạn mức tiền, đính kèm chứng từ, hoặc luồng duyệt nhiều cấp. Đây là bước tiếp theo nếu dùng với công nợ thật.
