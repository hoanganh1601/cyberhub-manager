# 1. Yêu cầu sản phẩm — CyberHub Manager

## 1.1. Mục tiêu

Xây dựng ứng dụng desktop giúp một hoặc nhiều cửa hàng net đã đăng ký trong hệ thống quản lý tập trung khách hàng, tài khoản, máy tính, phiên sử dụng, nạp tiền, hóa đơn và doanh thu. Sản phẩm phải giảm thao tác thủ công, ngăn mở trùng máy và bảo đảm số dư không sai lệch khi có lỗi.

## 1.2. Người dùng

| Vai trò | Quyền trong MVP |
|---|---|
| Nhân viên | Đăng nhập; tìm/tạo/cập nhật khách; nạp tiền; xem máy; mở và checkout phiên; xem hóa đơn vừa tạo |
| Quản lý | Toàn bộ quyền nhân viên; thêm/sửa máy; bật/tắt bảo trì; xem lịch sử hóa đơn và doanh thu |
| Admin | Quản lý toàn hệ thống ở P1; MVP có tài khoản seed để demo và kiểm tra phân quyền |
| Khách hàng | Sử dụng máy, nạp tiền và xem số dư thông qua nhân viên; chức năng tự đăng nhập/self-service thuộc P1 |

Khách hàng không trực tiếp dùng ứng dụng desktop trong MVP.

## 1.3. Phạm vi ưu tiên

### P0 — bắt buộc để nghiệm thu MVP

- Đăng nhập nhân viên và lưu nhân viên đang thao tác.
- Tạo, cập nhật, tìm kiếm và xem số dư khách hàng.
- Xem danh sách máy theo cửa hàng và trạng thái trực quan.
- Nạp tiền và lưu lịch sử giao dịch.
- Mở phiên, ước tính thời gian chơi, checkout và tính phí.
- Cho phép số dư tạm âm trong phiên; yêu cầu bù đủ trước khi hoàn tất checkout.
- Tạo hóa đơn, xem lịch sử hóa đơn và doanh thu theo ngày.
- Transaction/rollback cho tất cả luồng thay đổi tiền hoặc nhiều bảng.

### P1 — làm sau khi P0 ổn định

- Tự động cộng tiền khuyến mãi theo mốc nạp.
- Tách số dư chính và số dư khuyến mãi; ưu tiên trừ số dư khuyến mãi và không cho quy đổi thành tiền mặt.
- Phân quyền nút/chức năng chi tiết theo `STAFF`, `MANAGER`, `ADMIN`.
- Quản lý nhiều cửa hàng đầy đủ.
- Quản lý nhân viên và chức năng khách hàng tự đăng nhập/xem số dư.
- Xuất hóa đơn ra file hoặc in.

### P2 — tùy chọn nếu còn thời gian

- Quản lý sản phẩm/dịch vụ cơ bản; không bao gồm quản lý kho phức tạp.

### Out of scope

- Đặt máy online, website/app khách hàng.
- AI, quản lý kho phức tạp, membership nhiều hạng.
- Thanh toán qua cổng ngân hàng thật.

## 1.4. Yêu cầu chức năng

### AUTH — Đăng nhập nhân viên

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| AUTH-01 | Đăng nhập bằng username/password | Đúng thông tin và tài khoản `ACTIVE` thì vào dashboard; sai thì báo lỗi chung, không nói sai username hay password |
| AUTH-02 | Ghi nhận phiên làm việc | Sau đăng nhập, mọi thao tác nạp tiền/mở phiên/checkout/hóa đơn đều gắn `employee_id` |
| AUTH-03 | Đăng xuất | Xóa thông tin phiên UI và quay về màn hình login |

### CUS — Khách hàng và tài khoản

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| CUS-01 | Tạo khách hàng và tài khoản trong cùng transaction | Có mã khách/mã tài khoản tự sinh; mỗi khách có đúng một tài khoản; phone và username không trùng; lỗi ở bước nào thì không lưu dữ liệu dở dang |
| CUS-02 | Tìm kiếm | Tìm gần đúng theo mã khách, họ tên, số điện thoại hoặc username; phản hồi dưới 2 giây với dữ liệu demo |
| CUS-03 | Cập nhật thông tin | Cho sửa họ tên, số điện thoại; không cho sửa trực tiếp số dư |
| CUS-04 | Xem số dư | Hiển thị VND có phân cách hàng nghìn; số dư âm hiển thị đỏ |
| CUS-05 | Khóa tài khoản | Tài khoản `LOCKED` không mở được phiên mới |

Validation: họ tên 2–100 ký tự; số điện thoại gồm 10 chữ số và bắt đầu bằng `0`; username 4–30 ký tự gồm chữ, số, `_`, `.`; mật khẩu tối thiểu 6 ký tự.

### MAC — Máy tính

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| MAC-01 | Xem sơ đồ máy theo cửa hàng | Mỗi máy hiện tên, trạng thái, đơn giá; màu đúng theme |
| MAC-02 | Quản lý trạng thái | Ba trạng thái: `AVAILABLE`, `IN_USE`, `MAINTENANCE` |
| MAC-03 | Thêm/sửa máy | Mã máy là duy nhất; đơn giá/giờ là số nguyên dương |
| MAC-04 | Bảo trì | Chỉ quản lý/admin được đổi; không chuyển máy đang `IN_USE` sang bảo trì |
| MAC-05 | Phạm vi cửa hàng | Nhân viên chỉ thao tác máy thuộc cửa hàng của mình |
| MAC-06 | Xóa/ngừng sử dụng máy | Máy chưa có lịch sử có thể xóa theo quyền; máy đã có phiên chỉ được archive/đổi trạng thái để giữ lịch sử |

Không xóa cứng máy đã phát sinh phiên; dùng trạng thái/bảo trì để giữ lịch sử.

### WAL — Ví và nạp tiền

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| WAL-01 | Nạp tiền | Số tiền nguyên, lớn hơn 0, tối đa 100.000.000 VND/lần |
| WAL-02 | Cập nhật số dư và lịch sử | Cộng số dư + tạo giao dịch trong cùng transaction; lỗi thì rollback cả hai |
| WAL-03 | Phương thức | MVP hỗ trợ `CASH` và `TRANSFER` dạng ghi nhận, không tích hợp cổng thật |
| WAL-04 | Khuyến mãi P1 | Áp dụng đúng một chính sách đang hiệu lực có mốc cao nhất; ghi giao dịch bonus riêng |
| WAL-05 | Lịch sử | Hiển thị thời gian, loại, số tiền, nhân viên, phương thức và ghi chú |
| WAL-06 | Hai loại số dư P1 | Tách số dư chính/khuyến mãi; trừ khuyến mãi trước; số dư khuyến mãi không rút hoặc hoàn tiền mặt |

### SES — Phiên sử dụng

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| SES-01 | Mở phiên | Chỉ máy `AVAILABLE`, khách `ACTIVE`, không có phiên khác và đủ số dư tối thiểu 30 phút |
| SES-02 | Snapshot đơn giá | Lưu đơn giá máy vào phiên lúc mở; đổi giá máy sau đó không làm đổi phiên đang chạy |
| SES-03 | Chống mở trùng | Một máy và một khách chỉ có tối đa một phiên `ACTIVE`; chặn cả ở UI lẫn DB |
| SES-04 | Ước tính thời gian | Khi mở, hiển thị `floor(số dư × 60 / đơn giá giờ)` phút |
| SES-05 | Theo dõi phiên | Dashboard hiển thị khách, giờ bắt đầu, thời lượng và số dư ước tính theo thời gian thực |
| SES-06 | Cảnh báo âm | Khi `số dư hiện tại - chi phí tạm tính < 0`, card máy hiển thị cảnh báo đỏ; không tự tắt máy |
| SES-07 | Tính phí checkout | `phút = ceil((kết thúc - bắt đầu) / 60 giây)`, tối thiểu 1 phút; `phí = ceil(phút × đơn giá giờ / 60)` |
| SES-08 | Bù nợ khi checkout | Nếu số dư sau trừ phí âm, hiển thị số cần thu; chỉ hoàn tất khi tiền bù làm số dư `>= 0` |
| SES-09 | Kết thúc nguyên tử | Trừ tiền, ghi giao dịch, đóng phiên, trả máy `AVAILABLE`, tạo hóa đơn trong một transaction |

Luồng checkout phải có bước **xem trước**. Nếu cần bù nợ, UI hỏi số tiền/phương thức rồi mới gọi lệnh hoàn tất; không đóng phiên trước khi bù đủ.

### INV — Hóa đơn và doanh thu

| ID | Yêu cầu | Acceptance criteria |
|---|---|---|
| INV-01 | Tạo hóa đơn | Một phiên chỉ có một hóa đơn; lưu mã hóa đơn, khách, nhân viên checkout, cửa hàng, tổng phí, tiền bù, trạng thái và thời gian |
| INV-02 | Bảo toàn lịch sử | Hóa đơn `PAID` không được xóa cứng; nếu cần sửa dùng trạng thái `VOID` ở bản sau |
| INV-03 | Lịch sử | Lọc/xem hóa đơn theo ngày, khách hoặc mã hóa đơn |
| INV-04 | Doanh thu ngày | Tổng doanh thu là tổng `usage_cost` của hóa đơn `PAID` trong ngày tại cửa hàng |
| INV-05 | Biên lai | Sau checkout hiển thị mã hóa đơn, máy, khách, thời gian, số phút, phí và số dư còn lại |

## 1.5. Business rules bắt buộc

1. Một máy có tối đa một phiên `ACTIVE`.
2. Một khách có tối đa một phiên `ACTIVE` trên toàn hệ thống.
3. Chỉ máy `AVAILABLE` mới mở phiên; mở thành công chuyển `IN_USE`.
4. Checkout thành công trả máy về `AVAILABLE`.
5. Số dư có thể âm trong lúc chơi nhưng khách có số dư âm không được mở phiên mới.
6. Chỉ hoàn tất checkout khi số dư sau phí và tiền bù lớn hơn hoặc bằng 0.
7. Mọi lệnh thay đổi tiền phải có audit transaction và nhân viên thực hiện.
8. Nhân viên không thao tác tài nguyên của cửa hàng khác.
9. Hóa đơn và lịch sử giao dịch không xóa cứng.
10. UI không truy vấn SQL trực tiếp.
11. Mỗi khách hàng có đúng một tài khoản; một khách có thể có nhiều phiên và nhiều hóa đơn.
12. Mỗi phiên thuộc đúng một khách hàng và đúng một máy.
13. Nhân viên mở phiên và nhân viên checkout phải là tài khoản đang đăng nhập; hệ thống lưu riêng `opened_by` và `closed_by`.

## 1.6. Dữ liệu chính

| Bảng | Trường tối thiểu | Ràng buộc chính |
|---|---|---|
| `stores` | id, code, name, address, status | code unique |
| `employees` | id, code, store_id, full_name, username, password_hash, role, status | username unique; FK store |
| `customers` | id, code, full_name, phone, status, created_at | code/phone unique |
| `accounts` | id, code, customer_id, username, password_hash, balance, status; P1 thêm cash_balance, bonus_balance | 1–1 customer; code/username unique |
| `machines` | id, code, store_id, name, status, hourly_rate | code unique; rate > 0 |
| `usage_sessions` | id, code, customer_id, machine_id, opened_by, closed_by, start/end, hourly_rate, cost, status | code unique; generated column + unique index cho phiên active theo machine/customer |
| `account_transactions` | id, code, account_id, employee_id, session_id, type, amount, method, created_at | code unique; amount khác 0; đủ FK |
| `invoices` | id, code, session_id, customer_id, employee_id, store_id, usage_cost, settlement, total_amount, status, created_at | session unique; code unique |
| `promotions` (P1) | id, code, name, minimum_amount, bonus_percent, start/end, status | code unique; mốc > 0; % từ 0–100 |

Quy ước MySQL:

- Dùng `InnoDB`, charset `utf8mb4`, collation thống nhất cho toàn schema.
- ID dùng `BIGINT UNSIGNED AUTO_INCREMENT`; tiền VND dùng `BIGINT` có dấu vì số dư có thể âm.
- Thời gian lưu bằng `DATETIME` theo UTC; UI chuyển sang múi giờ `Asia/Ho_Chi_Minh` khi hiển thị.
- Foreign key dùng `ON DELETE RESTRICT` cho dữ liệu lịch sử; không cascade-delete hóa đơn/giao dịch.
- MySQL không hỗ trợ partial unique index với mệnh đề `WHERE`. Tạo generated column trả về `machine_id`/`customer_id` khi phiên là `ACTIVE`, trả về `NULL` ở trạng thái khác, rồi đặt unique index trên generated column.
- Luồng nạp tiền, mở phiên và checkout phải khóa account/machine/session liên quan bằng `SELECT ... FOR UPDATE` trong transaction.
- Index các trường search/filter; migration và seed tách riêng; SQL luôn parameterized.

## 1.7. Yêu cầu phi chức năng

| ID | Yêu cầu |
|---|---|
| NFR-01 | Thao tác thông thường phản hồi trong khoảng 2 giây với dữ liệu demo |
| NFR-02 | Tách UI, service, repository và database; không import ngược chiều |
| NFR-03 | Dùng transaction và rollback cho luồng nhiều bảng/tiền |
| NFR-04 | Hash mật khẩu; không log mật khẩu hoặc dữ liệu nhạy cảm |
| NFR-05 | Thông báo lỗi thân thiện; lỗi kỹ thuật ghi log, không làm crash ứng dụng |
| NFR-06 | Giao diện tối thiểu 1280×720, trạng thái máy nhận biết bằng cả màu và chữ |
| NFR-07 | Có test tự động cho tính tiền, mở trùng, rollback nạp tiền và checkout bù nợ |
| NFR-08 | Có seed: 1 cửa hàng, 1 quản lý, 2 nhân viên, 20 máy và 5 khách mẫu |
| NFR-09 | MySQL dùng `InnoDB`, `utf8mb4`; cấu hình kết nối lấy từ environment và không commit credential |

## 1.8. Use case chuẩn — Mở phiên sử dụng

**Actor:** Nhân viên đang đăng nhập.

**Precondition:**

- Nhân viên thuộc đúng cửa hàng của máy.
- Khách hàng/tài khoản tồn tại và đang `ACTIVE`.
- Máy đang `AVAILABLE`.
- Khách không có phiên `ACTIVE` khác và đủ số dư tối thiểu.

**Main flow:**

1. Nhân viên chọn khách hàng.
2. Nhân viên chọn máy.
3. Hệ thống khóa và kiểm tra lại tài khoản, máy và phiên active trong transaction.
4. Hệ thống hiển thị mã khách, mã máy, đơn giá snapshot và thời gian chơi ước tính.
5. Nhân viên xác nhận.
6. Hệ thống tạo phiên, lưu thời gian bắt đầu và `opened_by`.
7. Hệ thống chuyển máy sang `IN_USE` và commit.
8. Dashboard hiển thị phiên vừa mở.

**Alternative flow:**

- Máy vừa được người khác mở: rollback và báo “Máy đang được sử dụng”.
- Khách đang có phiên khác: rollback và báo phiên hiện tại.
- Không đủ số dư tối thiểu: không tạo phiên, hiển thị số tiền cần nạp.
- Lỗi database: rollback toàn bộ, máy và phiên giữ nguyên trạng thái trước thao tác.

**Postcondition:** Một phiên `ACTIVE` duy nhất được tạo cho máy và khách; máy ở trạng thái `IN_USE`.

## 1.9. Điều kiện nghiệm thu MVP

MVP chỉ được coi là xong khi demo liền mạch được kịch bản: đăng nhập → tạo/tìm khách → nạp tiền → mở máy → dashboard đổi trạng thái → checkout → hóa đơn → doanh thu ngày; đồng thời test được ba nhánh lỗi: mở máy đang bận, khách thiếu số dư tối thiểu, checkout cần bù nợ.

## 1.10. Ma trận truy vết với tài liệu gốc

### Yêu cầu chức năng C-01 đến C-22

| Mã gốc | Yêu cầu tương ứng trong tài liệu này | Trạng thái/phạm vi |
|---|---|---|
| C-01 | CUS-01 | P0 |
| C-02 | CUS-02 | P0 |
| C-03 | CUS-03 | P0 |
| C-04 | CUS-04 | P0 |
| C-05 | WAL-05 | P0 |
| C-06 | MAC-01 | P0 |
| C-07 | MAC-02 | P0 |
| C-08 | MAC-02, MAC-06 | P0; xóa cứng bị giới hạn để giữ lịch sử |
| C-09 | MAC-03, MAC-04, MAC-06 | P0 |
| C-10 | SES-01, SES-09 | P0 |
| C-11 | SES-01, SES-02 và use case 1.8 | P0 |
| C-12 | SES-05, SES-07 | P0 |
| C-13 | SES-07, SES-09 | P0 |
| C-14 | SES-07 | P0 |
| C-14.1 | SES-04 | P0 |
| C-15 | WAL-01; WAL-04 cho bonus | Nạp tiền P0; bonus P1 theo phần “nếu còn thời gian” của tài liệu gốc |
| C-16 | WAL-02 | P0 |
| C-17 | WAL-02, WAL-05 | P0 |
| C-18 | SES-06 đến SES-09 | P0 |
| C-19 | INV-01, INV-05 | P0 |
| C-20 | INV-01 | P0 |
| C-21 | INV-03 | P0 |
| C-22 | INV-04 | P0 |

### Business rules B-01 đến B-16

| Mã gốc | Vị trí bao phủ |
|---|---|
| B-01 | Rule 1; SES-03 |
| B-02 | Rule 3; SES-01 |
| B-03 | Rule 3; SES-09 |
| B-04 | Rule 4; SES-09 |
| B-05 | WAL-01 |
| B-06 mới | Rule 5; SES-06, SES-08 |
| B-07, B-08 | Rule 12 và foreign key `usage_sessions` |
| B-09, B-10 | Rule 11 và quan hệ dữ liệu |
| B-11 | Rule 9; INV-02 |
| B-12 | Rule 7, Rule 13; AUTH-02 |
| B-13 | Rule 8; MAC-05 |
| B-14 | SES-01, SES-04 |
| B-15 | Rule 6; SES-08 |
| B-16 | Rule 5; SES-01 |

### Yêu cầu dữ liệu và phi chức năng

| Mã gốc | Vị trí bao phủ |
|---|---|
| D-01 | `customers` tại mục 1.6 |
| D-02 | `accounts`; CUS-01, CUS-04 và WAL-06 |
| D-03 | `machines`; MAC-01 đến MAC-06 |
| D-04 | `usage_sessions`; SES-01 đến SES-09 |
| D-05 | `invoices`; INV-01 đến INV-05 |
| D-06 | `stores` và phạm vi cửa hàng tại MAC-05 |
| D-07 | `account_transactions`; WAL-02, WAL-05 và SES-09 |
| D-08 | `employees`; AUTH-01, AUTH-02 và Rule 13 |
| D-09 | `promotions`, WAL-04 và WAL-06 — P1 |
| N-01 | NFR-01 |
| N-02 | NFR-02 |
| N-03 và N-05 trùng nhau | NFR-03 |
| N-04 | NFR-06 và tài liệu UI theme |
| N-06 | NFR-04 |

## 1.11. Quyết định xử lý điểm mâu thuẫn trong tài liệu gốc

1. **B-06 và B-15:** B-06 cho phép số dư âm trong khi chơi hoặc còn nợ sau phiên, nhưng B-15 yêu cầu bù đủ trước khi hoàn tất checkout. MVP ưu tiên B-15: số dư có thể âm khi phiên còn `ACTIVE`; khi checkout phải bù đủ rồi mới hoàn tất phiên/hóa đơn.
2. **C-08/C-09 và bảo toàn lịch sử:** “Xóa máy” được hiểu là xóa cứng chỉ khi chưa có lịch sử. Máy đã phát sinh phiên phải archive/ngừng sử dụng để không làm mất dữ liệu.
3. **Khuyến mãi:** C-15 nhắc tự động cộng thưởng, trong khi scope và D-09 đều ghi “nếu còn thời gian”. Vì vậy nạp tiền là P0, chính sách thưởng và hai loại số dư là P1.
4. **Khách hàng đăng nhập:** Tài liệu gốc nêu ý tưởng khách có thể đăng nhập, nhưng không có use case frontend khách hàng và app online nằm ngoài phạm vi. MVP vẫn tạo username/password cho tài khoản; màn hình self-service khách hàng thuộc P1.
5. **Quyền xóa/sửa máy:** C-08 ghi nhân viên có thể xóa/sửa trạng thái, còn C-09 giao quản lý quyền thêm/xóa/bảo trì. MVP áp dụng nguyên tắc quyền tối thiểu: nhân viên xem và vận hành phiên; Manager/Admin mới được thêm, sửa, archive hoặc chuyển bảo trì.
6. **Khóa ngoại cửa hàng của máy:** D-03 trong tài liệu gốc ghi “Mã cửa hàng (D-08)”, nhưng D-08 là Nhân viên và D-06 mới là Cửa hàng. Thiết kế chuẩn hóa `machines.store_id` tham chiếu `stores.id` của D-06.
