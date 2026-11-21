# Kế hoạch chuẩn hóa 3NF và củng cố toàn vẹn dữ liệu CyberHub Manager

Ngày rà soát: **21/11/2026**. Nhánh làm việc: `refactor/four-layer-architecture`, sau commit `472958b`.

**Trạng thái: ĐÃ TRIỂN KHAI VÀ NGHIỆM THU CHUẨN HÓA 3NF (`028`–`030`)** — Migration [`028_3nf_derived_and_transitive_cleanup.sql`](../../sql/028_3nf_derived_and_transitive_cleanup.sql), [`029_3nf_hr_identity_and_policy_versions.sql`](../../sql/029_3nf_hr_identity_and_policy_versions.sql), [`030_strict_integrity_checks_and_cross_store_guards.sql`](../../sql/030_strict_integrity_checks_and_cross_store_guards.sql) đã được áp dụng và đối soát không sai lệch trên cả database tạo mới (`cyberhub_manager_test`) lẫn bản sao & database demo thật (`cyberhub_manager`). Toàn bộ 74/74 phiếu chứng minh 3NF được lưu tại [DATABASE_3NF_PROOFS.md](DATABASE_3NF_PROOFS.md).

## 1. Mục tiêu và giới hạn của kết luận

Mục tiêu là có thiết kế quan hệ chứng minh được 3NF, dữ liệu nhất quán, giao dịch an toàn và các quy tắc nghiệp vụ trong phạm vi BTL được kiểm thử. Số lượng bảng không phải tiêu chí đánh giá chuẩn hóa. Không đặt mục tiêu giảm từ 70 bảng xuống một con số tùy ý.

Không thể chứng minh “tuân thủ tất cả nguyên tắc database” hoặc “nghiệp vụ tuyệt đối” chỉ bằng ERD, số lượng khóa ngoại hay một lần chạy test. Thay bằng các điều kiện nghiệm thu cụ thể ở mục 12. Phân biệt ba nội dung trong báo cáo:

- **Chuẩn hóa:** chứng minh dựa trên khóa ứng viên và phụ thuộc hàm của từng quan hệ.
- **Toàn vẹn và giao dịch:** ràng buộc, phân quyền, transaction, chống xử lý lặp và chống tranh chấp.
- **Vận hành:** migration, backup/restore, hiệu năng, theo dõi và tài liệu.

3NF không tự bảo đảm hai nội dung sau. ACID, phân quyền hoặc số bảng lớn cũng không tự chứng minh 3NF.

## 2. Căn cứ và hiện trạng đã xác minh

Nguồn đối chiếu:

- [Migration SQL](../../sql/) từ `001` đến `027`.
- [ERD hiện hành](../diagrams/current_erd.md) và [data dictionary](../diagrams/data_dictionary.md).
- [Repository](../../src/cyberhub_manager/infrastructure/repositories/) và [application services](../../src/cyberhub_manager/application/services/).
- [Integration tests](../../tests/integration/) và [quy định database test](../../tests/conftest.py).

Truy vấn chỉ đọc `INFORMATION_SCHEMA` trước và sau triển khai `028`–`030` xác nhận:

| Chỉ tiêu | Trước chuẩn hóa (`027`) | Sau chuẩn hóa (`030`) |
|---|---:|---:|
| Bảng vật lý (gồm `schema_migrations`) | 71 | **75** |
| Bảng nghiệp vụ cơ sở | 70 | **74** |
| View đọc tương thích (`v_*`) | 0 | **18** |
| Trigger toàn vẹn & chiếm dụng | 0 | **24** |
| Migration được ghi nhận | 27 (`027`) | **30 (`030`)** |
| PRIMARY KEY | 71 | **75** |
| UNIQUE constraint | 62 | **62** |
| FOREIGN KEY constraint | 152 | **149** |
| CHECK constraint | 170 | **186** |
| Cột sinh (GENERATED COLUMN) / Cột JSON trong bảng cơ sở | 4 / 1 | **0 / 0** |

Các con số này mô tả database đang kết nối; chưa thay thế việc đối chiếu toàn bộ DDL với một database sạch và checksum migration. Chưa kiểm tra toàn bộ bản ghi trùng, orphan hoặc số dư trong lượt lập tài liệu này.

Trong phiên refactor ngay trước đó, các nhóm test đã ghi nhận 1.904 unit test pass, 5 test symlink skip trên Windows và 249 integration test pass. Đây là bằng chứng hồi quy cho phiên bản trước chuẩn hóa; phải chạy lại sau migration mới. Test pass không phải chứng minh toán học về 3NF.

## 3. Quy tắc xác định 1NF, 2NF và 3NF

### 3.1. Định nghĩa dùng trong báo cáo

Với quan hệ `R`, xét tập phụ thuộc hàm nghiệp vụ `F` và bao đóng `F+`:

- **Khóa ứng viên:** tập thuộc tính tối thiểu xác định được toàn bộ thuộc tính của `R`.
- **Siêu khóa:** tập thuộc tính xác định được toàn bộ `R`, có thể chưa tối thiểu.
- **Thuộc tính nguyên tố:** thuộc ít nhất một khóa ứng viên.
- **1NF:** không có nhóm lặp; giá trị thuộc miền dữ liệu được định nghĩa cho thuộc tính. Với báo cáo quan hệ cổ điển, biểu diễn các tập/danh sách nghiệp vụ bằng quan hệ chi tiết.
- **2NF:** đạt 1NF; mọi thuộc tính không nguyên tố phụ thuộc đầy đủ vào mọi khóa ứng viên, không phụ thuộc vào một phần thực sự của khóa ứng viên.
- **3NF:** với mọi phụ thuộc hàm không tầm thường `X → A` trong `F+`, `X` là siêu khóa hoặc `A` là thuộc tính nguyên tố.

Định nghĩa 3NF phải xét **mọi khóa ứng viên**, không chỉ PK. Nguồn lý thuyết: [bài giảng chuẩn hóa, Purdue University](https://www.cs.purdue.edu/homes/cs541/other_handouts/normalization.pdf).

Không kết luận một phụ thuộc hàm chỉ vì dữ liệu mẫu đang có giá trị giống nhau. Phải xác định quy tắc đúng với mọi trạng thái hợp lệ của nghiệp vụ. `UNIQUE` có cột nullable trong MySQL cũng không tự tương đương khóa ứng viên của mô hình quan hệ cổ điển.

### 3.2. Những nhận định trước cần hiệu chỉnh

| Nhận định quá rộng | Cách đánh giá đúng |
|---|---|
| Có `balance` và ledger thì chắc chắn sai 3NF | Đây là khả năng dư thừa giữa các quan hệ. Phải kiểm tra FD trong từng quan hệ và cơ chế đồng bộ; không tự kết luận vi phạm 3NF. |
| Lưu tổng header và tổng các dòng luôn sai 3NF | Tổng qua nhiều bảng là ràng buộc liên quan nhiều quan hệ; không tự tạo FD không khóa bên trong header. Tuy nhiên có rủi ro lệch tổng. |
| Snapshot giá/tên luôn sai 2NF | Giá/tên tại thời điểm đặt có thể phụ thuộc vào cả `(order_id, item_id)`. Cần phân biệt với giá/tên hiện tại của món. |
| Hai bảng có `full_name` thì cả hai đều sai 3NF | Trùng dữ liệu giữa hai bảng là vấn đề nguồn sự thật; từng bảng vẫn cần phân tích FD riêng. |
| Có JSON thì chắc chắn không đạt 1NF | Cần quy định miền dữ liệu và cách sử dụng. Với yêu cầu BTL quan hệ cổ điển, các sự kiện giá/ưu đãi phải có bảng cấu trúc; không dùng JSON làm nguồn duy nhất. |
| Xóa mọi số dư là đủ đạt 3NF | Còn phải xét phụ thuộc bắc cầu, các khóa ứng viên, quy tắc version và phạm vi cơ sở. |

### 3.3. Hồ sơ chứng minh bắt buộc cho từng bảng

Mỗi bảng phải có một phiếu theo mẫu sau, đặt trong phụ lục báo cáo hoặc data dictionary bổ sung:

```text
Tên quan hệ và ý nghĩa của một dòng:
Các thuộc tính, miền giá trị, ngữ nghĩa NULL:
Tập FD nghiệp vụ và nguồn xác nhận từng FD:
Phủ tối thiểu của F:
Mọi khóa ứng viên; chứng minh bằng bao đóng X+ và tính tối thiểu:
Thuộc tính nguyên tố / không nguyên tố:
Kiểm tra 1NF, 2NF, 3NF trên tập FD suy ra:
Phép phân rã đề xuất, nếu có:
Chứng minh nối không mất mát và bảo toàn phụ thuộc:
PK / UNIQUE / FK / CHECK hiện thực hóa thiết kế:
Quy tắc cần transaction hoặc service hỗ trợ:
Test và bằng chứng dữ liệu:
Kết luận, người rà soát, ngày rà soát:
```

Thêm `id AUTO_INCREMENT` không loại bỏ các FD giữa thuộc tính không khóa. Không tách máy móc mỗi cột dẫn xuất thành một bảng 1–1: bảng mới vẫn có thể giữ nguyên FD vi phạm.

## 4. Danh sách vấn đề chuẩn hóa cần xử lý

Quy ước: **P0** phải chốt trước nghiệm thu; **P1** phải xử lý/giải trình để tuyên bố 3NF; **P2** cải thiện vận hành. Các thiết kế dưới đây là phương án cần hiện thực hóa và kiểm chứng, chưa phải DDL đã áp dụng.

### NF-01 — Giá trị lặp hoặc công thức trong cùng một quan hệ — P1

| Quan hệ | Căn cứ | FD cần đánh giá | Hướng xử lý cho mô hình logic 3NF |
|---|---|---|---|
| `invoices` | `001`, CHECK buộc `total_amount = usage_cost` | `usage_cost → total_amount`; tiền không xác định duy nhất hóa đơn | Giữ một giá trị gốc; cung cấp tên `total_amount` qua view/read model. |
| `accounts` | `003`, `cash_balance` là generated column | `(balance, bonus_balance) → cash_balance` | Nếu yêu cầu cả quan hệ SQL hiển thị không chứa FD này, đưa `cash_balance` vào view; ghi rõ generated column là lựa chọn vật lý khi giải thích thiết kế hiện tại. |
| `commercial_settlements` | `024`, CHECK `net_amount = gross_amount + adjustment_amount` | `(gross_amount, adjustment_amount) → net_amount` | Tính `net_amount` tại view/query, giữ dữ kiện gốc cần thiết. |
| `cash_shifts` | Service tính `variance = counted_cash - expected_cash` | `(counted_cash, expected_cash) → variance` nếu đây là quy tắc bắt buộc | Giữ số kiểm đếm và căn cứ chốt sổ; tính chênh lệch. Không làm thay đổi kết quả ca đã duyệt khi ledger phát sinh muộn. |
| `commercial_settlement_lines` | Repository lưu `units`, `unit_rate`, `amount` | `(units, unit_rate) → amount` chỉ khi công thức của từng loại doanh thu xác định hoàn toàn số tiền | Chốt công thức `FIXED` và theo lượt; bỏ cột tính toán hoặc định nghĩa riêng khoản điều chỉnh thực tế. |
| `invoices` | `006`, các trường điểm và phần chi hợp lệ | Kiểm tra FD của `usage_cost`, `bonus_used`, `loyalty_unit`, version và điểm theo chính sách | Tách chính sách bất biến theo version; quyết định điểm là phép tính hay một khoản cấp điểm độc lập có căn cứ. |

`cash_shifts.active_employee_id`, `usage_sessions.active_machine_id`, `usage_sessions.active_customer_id` là generated column phục vụ uniqueness có điều kiện. Cần mô tả riêng ở mô hình vật lý. Nếu hội đồng yêu cầu kiểm tra 3NF trên cả tập cột vật lý, thiết kế quan hệ chiếm dụng đang hoạt động với khóa duy nhất thay cho các cột dẫn xuất; cập nhật trong cùng transaction với phiên/ca. Không xóa các cơ chế chống mở trùng trước khi có cơ chế thay thế.

### NF-02 — Phụ thuộc bắc cầu do lặp thông tin cha — P1

| Quan hệ | FD theo mô hình cha/con | Vấn đề và lựa chọn |
|---|---|---|
| `cash_shift_entries` | `shift_id → store_id` vì một ca thuộc một cơ sở | `shift_id` không phải siêu khóa của entries; ưu tiên lấy cơ sở qua ca và JOIN/view. Người ghi entry không mặc định là chủ ca: không tự xóa `employee_id`. |
| `commercial_events` | `placement_id → campaign_id` vì vị trí thuộc một chiến dịch | Không giữ hai định danh cùng biểu diễn quan hệ hiện tại; lấy campaign qua placement. Nếu cần chiến dịch lịch sử, tạo placement version bất biến. |
| `menu_items` | `category_id → store_id` nếu món bắt buộc cùng cơ sở với nhóm | Chọn category làm nguồn xác định cơ sở hoặc thiết kế lại danh mục dùng chung/assignment. Không giữ hai nguồn current-state trái nhau. |
| `inventory_movements`, `inventory_counts` | `ingredient_id → store_id` nếu nguyên liệu có ID toàn cục và chỉ thuộc một cơ sở | Lấy cơ sở từ nguyên liệu hoặc tách danh mục nguyên liệu toàn chuỗi khỏi đối tượng tồn theo cơ sở. Composite FK hiện có tăng toàn vẹn nhưng không tự loại FD bắc cầu. |
| `menu_orders` | `session_id → machine_id` khi một phiên gắn cố định một máy | Bỏ machine lặp nếu cùng nghĩa. Nếu hỗ trợ chuyển máy, phải mô hình hóa phân đoạn phiên/vị trí phục vụ và chứng minh lại FD. |
| `machine_incidents` | `machine_id → store_id` nếu đó là cơ sở hiện tại và máy không được chuyển | Nếu `store_id` là nơi phát sinh sự cố lịch sử thì không đồng nghĩa vị trí hiện tại; cần mô hình lịch sử điều chuyển hoặc snapshot có ý nghĩa rõ ràng. |
| `goods_receipts` | `order_id → store_id` nếu một đơn mua thuộc một cơ sở | Nhiều phiếu nhận của một đơn không cần lặp cơ sở cùng nghĩa. |
| `purchase_orders`, `supplier_payables` | `supplier_id → store_id` nếu supplier là bản ghi riêng theo cơ sở và các chứng từ bắt buộc cùng cơ sở | Phân tích theo ngữ nghĩa supplier hiện tại; lấy cơ sở qua chủ sở hữu chuẩn hoặc chuyển supplier thành danh mục toàn chuỗi với bảng quan hệ. |
| `commercial_reward_grants` | Kiểm tra `event_id → account_id` và chủ sở hữu phiên | `event_id` hiện UNIQUE NOT NULL nên là khóa ứng viên của grants; phụ thuộc từ `event_id` không tự vi phạm 3NF. Vẫn cần chống cấp thưởng sai người khi các FK riêng lẻ cùng hợp lệ. |

Không kết luận `store_id` thừa trong mọi chứng từ. Một cơ sở lịch sử tại thời điểm phát sinh khác với cơ sở hiện tại của nhân viên hoặc máy. Phải chốt ý nghĩa và quy tắc thay đổi của đối tượng cha trước khi phân rã.

### NF-03 — Hồ sơ nhân sự và tài khoản đăng nhập có hai nguồn sự thật — P0

Căn cứ: `026` sao chép mã/tên/cơ sở từ `employees` sang `employee_profiles`. `ManagementRepositoryMixin.update_employee_profile()` cập nhật ngược tên và cơ sở vào `employees`.

Cần thực hiện:

- Chốt bảng sở hữu mã nhân sự, tên, cơ sở chính và trạng thái việc làm.
- Chốt bảng sở hữu username, hash, trạng thái đăng nhập, role, auth version và yêu cầu đổi mật khẩu.
- Phân biệt trạng thái nghỉ việc với khóa credential; không mặc định hai trạng thái là một thuộc tính.
- Nhân sự có thể chưa có tài khoản; giữ tính tùy chọn của quan hệ đó.
- Giữ ID nhân viên hoặc bảng ánh xạ cho mọi FK lịch sử. Không làm mất người lập/duyệt chứng từ khi đổi cấu trúc.
- Chuyển repository sang JOIN từ nguồn chuẩn rồi mới bỏ đồng bộ hai chiều và cột cùng nghĩa.

Có thể giữ tên bảng hiện tại và chuyển vai trò của chúng, hoặc dùng `employee_credentials`. Không bắt buộc đổi tên để đạt 3NF. Điểm phải giải quyết là ngữ nghĩa thuộc tính và nguồn sở hữu dữ liệu.

### NF-04 — Version chính sách và snapshot lịch sử — P1

Căn cứ: `menu_order_pricing` giữ `promotion_id`, code/kind và JSON; voucher chụp điều kiện lúc phát; invoice giữ version/unit tính điểm. Các snapshot không được tùy ý thay bằng giá trị hiện tại khi JOIN.

Phương án:

1. Mô hình chính sách có danh tính ổn định và các version bất biến, dùng khóa `(policy_id, version)` hoặc `policy_version_id` duy nhất; không dùng một con số version không có phạm vi rõ ràng.
2. Đơn tham chiếu đúng version đã áp dụng. Không sửa/xóa version đã được chứng từ tham chiếu.
3. Khi tên/giá món phải bảo toàn lịch sử, chọn version món/giá hoặc thuộc tính snapshot của dòng giao dịch. Nếu snapshot phụ thuộc cả order và item thì không quy sai thành phụ thuộc một phần theo item.
4. Chuyển dữ kiện cần tính tiền/hoàn tiền/đối soát khỏi `snapshot_json` sang bảng có cột và khóa rõ ràng. JSON chỉ còn payload bổ trợ nếu phạm vi báo cáo cho phép.
5. Backfill version từ chứng từ cũ. Nếu chứng từ cũ chỉ biết kết quả, lưu kết quả lịch sử với nguồn gốc tương ứng; không bịa chính sách đã áp dụng.

Nếu version quyết định `promotion_code`, `promotion_kind`, `unit_amount` thì các bảng giao dịch không tiếp tục lặp các thuộc tính cùng nghĩa đó. Giá trị thực tế sau một quyết định điều chỉnh phải được mô hình hóa thành sự kiện/adjustment riêng có người và lý do.

### NF-05 — Số dư, tổng tiền và giá trị tổng hợp giữa các bảng — P0 về toàn vẹn

Các cặp cần đối soát: `accounts`/`account_transactions`, `game_wallets`/`game_coin_ledger`, `inventory_ingredients`/`inventory_movements`, header/lines POS và mua hàng, ca/entries, incident/parts, công nợ/thanh toán.

Không bắt buộc xóa hết các số dư chỉ để chứng minh 3NF. Với mục tiêu một nguồn sự thật, có thể chọn ledger gốc và view; với thiết kế vật lý có số dư lưu sẵn, phải công bố phần lưu tổng hợp và quy tắc đồng bộ, không gọi toàn bộ nó là mô hình logic 3NF đã chứng minh.

Trước khi chuyển sang ledger-only:

- Chứng minh ledger đủ dữ liệu tái lập số dư tiền gốc/khuyến mãi, xu, tồn thực và giữ tồn.
- Có opening entry hoặc mốc chuyển đổi được phê duyệt cho lịch sử thiếu; không tự coi số dư không khớp là 0.
- Không cộng cả số dư hiện tại lẫn toàn bộ ledger như hai nguồn độc lập.
- Khóa một bản ghi gốc ổn định theo tài khoản/nguyên liệu/ca trước khi kiểm tra và ghi; `SUM()` đơn thuần không ngăn hai giao dịch cùng tiêu số dư.
- Ledger bất biến theo quyền tài khoản DB; sửa sai bằng bút toán đảo có liên kết.
- Đo hiệu năng truy vấn và lập index thích hợp trước khi bỏ cột tổng hợp.

## 5. Toàn vẹn dữ liệu và quy tắc database cần củng cố

### INT-01 — Quan hệ cùng cơ sở và đúng chủ sở hữu — P0

FK riêng lẻ chỉ chứng minh mỗi ID tồn tại. Ví dụ `menu_items.store_id` và `category_id` có thể đều tồn tại nhưng thuộc hai cơ sở khác nhau nếu ghi ngoài service.

Phải kiểm tra các đường quan hệ:

- Món → nhóm món; công thức → nguyên liệu cùng cơ sở.
- Đơn POS → phiên → khách/account → máy → cơ sở phục vụ.
- Đề nghị mua → đơn mua → supplier → nguyên liệu → phiếu nhận → công nợ.
- Sự cố → máy và cơ sở phát sinh; ca → entry.
- Chiến dịch → vị trí → phiên chơi → sự kiện → người nhận thưởng.
- Bảng cấp điểm → voucher → đúng khách sở hữu tài khoản.

Ưu tiên loại thuộc tính cùng nghĩa bị lặp trong mô hình 3NF. Nếu mô hình vật lý giữ chúng, dùng composite FK trỏ vào candidate/UNIQUE key phù hợp hoặc trigger có kiểm chứng. FK ghép là công cụ toàn vẹn, không phải bằng chứng quan hệ đã đạt 3NF. Quan hệ phức tạp vẫn cần service và transaction.

### INT-02 — NULL, CHECK và vòng đời trạng thái — P0

MySQL chấp nhận CHECK có kết quả `TRUE` hoặc `UNKNOWN`; một phép so sánh với NULL có thể không bị từ chối. Các cột bắt buộc theo trạng thái phải được kiểm tra `IS NOT NULL` tường minh. Xem [MySQL CHECK](https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html).

Cần rà và thêm test trực tiếp SQL cho:

- POS `PAID`/`REFUNDED`: phương thức, thời điểm, người thu/hoàn, chứng từ và số tiền hợp lệ. Ví dụ CHECK hiện tại dùng `payment_method IN (...)`: NULL có thể làm cả biểu thức thành UNKNOWN, dù hai cột khác đã có giá trị.
- `inventory_counts`: trạng thái quyết định phải khớp `decided_by/decided_at`; người quyết định khác người đề nghị.
- `supplier_payables`: `PAID` phải khớp số đã thanh toán và metadata thanh toán; CHECK hiện chỉ kiểm tra từng miền chưa chứng minh toàn bộ tổ hợp trạng thái.
- `machine_incidents`: người được phân công, mốc bắt đầu/hoàn thành/xác nhận khớp trạng thái và thứ tự thời gian.
- `cash_shifts`: đóng ca phải có dữ kiện chốt, người duyệt khi cần và lý do chênh lệch.
- `commercial_settlements`: duyệt/thanh toán phải có mốc và người hợp lệ.
- Voucher: các cột `used_*` khi chưa dùng phải đồng nhất; chỉ ràng buộc `used_store_id` theo quy tắc đã chốt.
- Email activation/reset: một token chỉ dùng một lần, đúng purpose, còn hạn, đúng account; email thay đổi không được giữ xác minh cũ ngoài ý muốn.

CHECK hiện tại có thể đã chặn một phần các trường hợp trên; đây là danh sách kiểm chứng và bổ sung phần thiếu, không phải khẳng định tất cả đang lỗi.

### INT-03 — Miền dữ liệu, khóa và chống trùng — P0/P1

- Tiền VND dùng số nguyên theo phạm vi đã chốt; không dùng FLOAT cho hạch toán. Tính phần trăm phải có quy tắc làm tròn xác định và giới hạn overflow.
- Số lượng có đơn vị g/ml/cái; không trộn đơn vị trong recipe, phiếu nhận, tồn và hao hụt. Tách quy đổi đơn vị nếu nghiệp vụ phát sinh.
- Mã, username, email có quy tắc trim/case/collation; định nghĩa duy nhất toàn chuỗi hay theo cơ sở.
- Mọi FK đúng kiểu, độ rộng và signedness. Tham chiếu candidate/UNIQUE key rõ ràng; không dựa vào nonstandard FK tới nonunique index.
- UNIQUE nullable không chặn nhiều dòng NULL. Điều kiện duy nhất theo trạng thái cần một thiết kế riêng có kiểm tra đồng thời.
- Kiểm tra thêm các key nghiệp vụ: một invoice/phiên, một reversal/đơn, một khoản cấp thưởng/sự kiện, một xử lý/request key. Không suy diễn “một nhân viên chỉ có một ca” thành “một cơ sở chỉ có một ca” nếu chưa chốt số két.
- `source_type/source_id` ở `cash_shift_entries`, `entity_id` ở `management_audit` không có FK đến từng loại chứng từ. Giữ nguyên như reference đa hình phải công bố giới hạn; nếu yêu cầu tham chiếu chặt ở DB, thiết kế supertype chứng từ hoặc các quan hệ nguồn có FK thật.

### INT-04 — Engine, charset, index và lịch sử — P1/P2

`015`, `018`, `019` có bốn CREATE TABLE không ghi tường minh engine/charset/collation. Database đang rà xác nhận cả bốn hiện là `InnoDB`, `utf8mb4_0900_ai_ci`; chưa có lỗi engine thực tế. Migration mới nên làm rõ cấu hình để triển khai không phụ thuộc defaults.

Index phải dựa vào WHERE/JOIN/ORDER BY thực tế và EXPLAIN; kiểm tra index trùng/bao hàm trước khi thêm. Index không thay thế chứng minh khóa ứng viên.

Không xóa dây chuyền hóa đơn, ledger, phiếu nhận và audit khi khóa tài khoản hoặc ngừng bán. `CASCADE` chỉ áp dụng cho dữ liệu phụ thuộc có thể xóa theo chính sách, chẳng hạn ảnh; cần giữ retention rõ ràng cho token/outbox/log, đồng thời bảo toàn chứng từ được báo cáo tham chiếu.

## 6. Giao dịch, đồng thời và phân quyền

### TX-01 — ACID và chống xử lý lặp — P0

| Luồng | Thao tác phải nguyên tử | Tranh chấp bắt buộc kiểm thử |
|---|---|---|
| Nạp ví | Giao dịch tiền, số dư/read model, entry ca, audit | Retry cùng yêu cầu không nạp hai lần; phân biệt hai lần nạp thật. |
| Mở/kết thúc phiên | Chiếm dụng máy/khách, phiên, thu tiền, invoice, điểm, ca | Hai nhân viên cùng mở máy; hai yêu cầu cùng checkout. |
| Đặt/thanh toán POS | Đơn/dòng hàng, snapshot/version, giữ/trừ tồn, tiền, voucher, ca, notification | Hai đơn tranh phần tồn cuối; pay/cancel/refund tranh nhau. |
| Hết hạn giữ tồn | Trạng thái đơn và release ledger | Worker chạy lại không release lần hai; không hủy đơn đã PREPARING. |
| Nhập/kiểm kê | Phiếu nhận/count, ledger, trạng thái mua, công nợ | Retry receipt; approve count khi tồn đã thay đổi. |
| Hoàn đơn | Phê duyệt, reversal tiền, restock/hao hụt, điểm và notification | Hai phê duyệt đồng thời; hoàn quá số đã thu. |
| Thưởng game/quảng cáo | Sự kiện xác thực, grant, xu/voucher/lượt | Callback trùng, sai người, sai chữ ký hoặc replay. |
| Chốt ca/đối soát | Dữ kiện đóng, duyệt, audit | Entry mới đến trong lúc đóng; hai người duyệt cùng chứng từ. |

Service mở transaction; các repository dùng cùng connection; lỗi rollback cả use case. Retry deadlock phải chạy lại đơn vị giao dịch với idempotency key ổn định. Khóa theo thứ tự thống nhất để giảm deadlock. Gửi email/HTTP provider ngoài transaction ghi nghiệp vụ; ghi outbox cùng transaction rồi worker xử lý.

### SEC-01 — RBAC, tách nhiệm vụ và quyền DB — P0

- ADMIN quản lý credential/RBAC; DIRECTOR điều hành chuỗi; MANAGER đúng các cơ sở được giao; STAFF/KITCHEN/INVENTORY theo permission đã triển khai.
- Backend xác thực lại actor và cơ sở cho mỗi yêu cầu nhạy cảm; không tin role hoặc `store_id` do client tự gửi.
- Chặn tự phê duyệt khi nghiệp vụ yêu cầu: kiểm kê, hoàn/hủy sau phục vụ, mua hàng, chênh lệch ca và đối soát.
- Bảo vệ cả UI lẫn API; kiểm thử đoán ID và truy cập chéo khách/cơ sở.
- Tài khoản runtime DB có quyền tối thiểu; migration dùng credential riêng. Nếu còn dùng tài khoản có quyền rộng để chạy demo, ghi rõ giới hạn đó.
- Chỉ lưu hash mật khẩu; không log secret/token thô; reset credential thu hồi phiên cũ. Mã token phải được kiểm tra hết hạn, mục đích và tính dùng một lần trong transaction.
- Audit phải chứa actor, hành động, đối tượng đủ định danh, thời điểm, request/correlation ID và lý do đối với thao tác điều chỉnh. Không gọi audit “bất biến tuyệt đối” nếu tài khoản DB vẫn được phép UPDATE/DELETE.

## 7. Quyết định nghiệp vụ phải chốt trước khi viết migration

| Mã | Câu hỏi cần chốt | Vì sao ảnh hưởng thiết kế |
|---|---|---|
| B01 | Máy có được điều chuyển cơ sở và khách có được đổi máy giữa phiên không? | Quyết định FD vị trí và cách bảo toàn lịch sử. |
| B02 | VIP/Couple/Siêu VIP là loại máy hay một phòng được thuê độc quyền? | `machine_room_types` hiện phân loại máy; không tự chứng minh đặt cả phòng 2/4–5 máy. Có nghiệp vụ phòng thật mới thêm room/occupancy/rate phù hợp. |
| B03 | Giá tính theo máy/giờ hay phòng/giờ; quy tắc làm tròn phút và giá có hiệu lực? | Cần đơn vị tính, version giá và snapshot chứng từ chính xác. |
| B04 | Supplier dùng chung toàn chuỗi hay hồ sơ riêng theo cơ sở? | Quyết định chuẩn hóa supplier/store, phạm vi công nợ và FK. |
| B05 | Cho thanh toán công nợ một lần hay nhiều lần? | Hiện trạng đơn giản không được mô tả thành hỗ trợ trả góp. Cần bảng payment khi có nhiều khoản độc lập. |
| B06 | Một đề nghị mua có được chia nhiều PO, nhiều supplier không? | `purchase_orders.request_id` hiện UNIQUE; muốn khác phải đổi cardinality có chủ đích. |
| B07 | Một đơn có được nhiều ưu đãi hoặc hoàn từng món không? | Hiện luồng một ưu đãi xác định và hoàn toàn đơn; không tự mở rộng chỉ để thêm bảng. |
| B08 | Tiền nạp, tiền tiêu, tiền thưởng, công nợ, doanh thu và cashflow được phân biệt thế nào? | Tránh cộng trùng nạp ví với doanh thu tiêu dùng và thu ca. |
| B09 | Điểm/hạng dựa vào chi tiêu nào; hoàn tiền có đảo điểm/hạng không? | Chốt policy version và bút toán đảo, không suy ra hạng từ tiền nạp. |
| B10 | Mỗi cơ sở có bao nhiêu két, ai được cùng sử dụng? | Chốt chủ thể cần khóa và điều kiện ca đang mở. |

Nếu BTL chưa triển khai một khả năng, ghi phạm vi và giới hạn thay vì thêm bảng rồi tuyên bố nghiệp vụ đã hoàn thiện.

## 8. Phạm vi 70 bảng cần có phiếu chứng minh

Danh sách dưới đây là danh mục bắt buộc rà, **không phải danh sách đã chứng minh đạt 3NF**. Mỗi tên bảng phải có đủ phiếu ở mục 3.3 trước khi nghiệm thu.

| Nhóm | Số bảng | Danh sách |
|---|---:|---|
| Nền tảng và giao dịch máy | 14 | `stores`, `employees`, `customers`, `accounts`, `machines`, `usage_sessions`, `account_transactions`, `invoices`, `promotions`, `management_audit`, `customer_notification_reads`, `machine_room_types`, `loyalty_settings`, `customer_avatars` |
| POS và kho | 15 | `menu_categories`, `menu_items`, `menu_item_images`, `menu_item_changes`, `menu_orders`, `menu_order_items`, `inventory_ingredients`, `menu_item_recipes`, `menu_order_recipe_snapshots`, `inventory_movements`, `inventory_counts`, `customer_notification_events`, `pos_order_reversals`, `menu_promotions`, `menu_order_pricing` |
| Voucher, game và quảng cáo | 12 | `reward_catalog`, `customer_vouchers`, `voucher_events`, `loyalty_point_grants`, `games`, `game_prizes`, `game_wallets`, `game_sessions`, `game_coin_ledger`, `ad_settings`, `ad_creatives`, `ad_reward_events` |
| Ca, bảo trì và mua hàng | 13 | `cash_shifts`, `cash_shift_entries`, `machine_incidents`, `machine_incident_parts`, `machine_incident_events`, `suppliers`, `purchase_requests`, `purchase_request_lines`, `purchase_orders`, `purchase_order_lines`, `goods_receipts`, `goods_receipt_lines`, `supplier_payables` |
| Đối tác thương mại | 9 | `commercial_partners`, `commercial_contracts`, `commercial_campaigns`, `commercial_placements`, `commercial_play_sessions`, `commercial_events`, `commercial_reward_grants`, `commercial_settlements`, `commercial_settlement_lines` |
| RBAC và email | 7 | `employee_profiles`, `employee_store_assignments`, `customer_store_links`, `supplier_payable_approvals`, `customer_email_tokens`, `customer_mail_outbox`, `customer_security_audit` |

`schema_migrations` được rà riêng như metadata vận hành; không tính vào 70 bảng nghiệp vụ. Các bảng ảnh, bảng header/detail, quan hệ nhiều–nhiều, ledger và audit có lý do tồn tại riêng; không xóa chỉ vì có quan hệ 1–1 hoặc đang ít dữ liệu.

## 9. Kế hoạch triển khai theo kiến trúc 4 tầng

| Đợt | Công việc | Sản phẩm phải review |
|---|---|---|
| A | Chốt B01–B10; lập FD, mọi khóa ứng viên và mô hình logic cho 70 quan hệ | Phụ lục chứng minh, ERD đích, bảng ánh xạ cũ/mới, danh sách phạm vi chưa hỗ trợ. |
| B | Chỉnh các FD vi phạm đã chứng minh: NF-01/NF-02 | DDL đề xuất, chứng minh lossless/dependency preservation, view giữ hợp đồng UI. |
| C | Hợp nhất nguồn nhân sự, chính sách có version, dữ kiện giá cấu trúc | Quy tắc lịch sử, script backfill và kiểm tra credential/quyền không đổi ngoài kế hoạch. |
| D | Củng cố INT-01–INT-04, TX-01, SEC-01 | Constraint, transaction, idempotency, index và test thất bại có chủ đích. |
| E | Đối soát dữ liệu cũ, chuyển repository và nghiệm thu | Báo cáo trước/sau, rollback/recovery drill, kết quả test và tài liệu cuối. |

Phân công code:

- **Domain:** trạng thái, quy tắc tiền/điểm, kiểu dữ liệu và invariant thuần.
- **Application:** quyền, điều phối workflow, transaction và idempotency; không chứa SQL.
- **Infrastructure:** migration, repository, truy vấn/view, mapping DB và adapter lưu trữ.
- **Presentation:** giữ hợp đồng trường hiển thị như `balance`, `total_amount`, `variance` dù giá trị được tính từ nguồn mới; không tự tính lại hạch toán.

Mỗi đợt làm một thay đổi có thể kiểm chứng. Không đổi schema, quy tắc tính tiền và toàn bộ UI trong cùng một bước không có đối soát.

## 10. Migration, đối soát và phục hồi

1. Xác định database đích, backup và thử restore thành công sang database riêng. Export schema, migration version/checksum và số dòng trước chuyển đổi.
2. Dựng database sạch từ migrations hiện hành; đối chiếu DDL với database đang dùng. Lập biên bản cho mọi drift trước khi backfill.
3. Thêm migration số tiếp theo sau version thực tế mới nhất; không sửa `001–027`. Chốt lịch chạy với người đang phát triển nhánh khác.
4. Tạo cấu trúc mới, khóa và view; chưa drop cột đang được bản app cũ đọc.
5. Backfill theo lô có checkpoint/idempotency và mapping ID. Nêu cách xử lý dữ liệu thiếu/không khớp; đưa vào danh sách cần xác nhận thay vì tự suy đoán.
6. Chuyển sang một nguồn ghi được chọn rõ ràng. Nếu có giai đoạn dual-write, phải cùng transaction và có ngày kết thúc; tránh hai hệ ghi độc lập.
7. Đối soát: số dòng và quan hệ, ID chứng từ, tổng theo cơ sở/ngày, tiền gốc/bonus, tồn/giữ, điểm, voucher, công nợ, số lần cấp thưởng và ca đã đóng.
8. Test cả trên bản sao có dữ liệu cũ và database tạo mới. Database rỗng chạy được chưa đủ chứng minh nâng cấp an toàn.
9. Chỉ drop cột/bảng đã được thay thế khi không còn consumer, dữ liệu đối soát đúng và phương án quay lại đã thử. Không xóa lịch sử để làm đẹp schema.
10. Cập nhật ERD, data dictionary, phiếu FD và script vận hành theo schema cuối.

MySQL có các DDL gây implicit commit; transaction Python không bảo đảm rollback toàn bộ một file migration DDL. Phải có expand/contract, checkpoint và phương án restore hoặc forward-fix. Tham khảo [MySQL implicit commit](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html).

## 11. Bộ kiểm thử cần bổ sung

| Nhóm | Ca kiểm thử | Điều kiện đạt |
|---|---|---|
| Cấu trúc | PK/FK/UNIQUE/CHECK, kiểu cột, engine/collation | Khớp migration và dictionary, không có drift chưa giải trình. |
| Khóa | Trùng mã, username, email; key ghép và NULL | Dữ liệu sai bị từ chối theo đúng chính sách duy nhất. |
| Quan hệ | ID tồn tại nhưng sai cơ sở/chủ sở hữu | Cả API và đường ghi DB theo chính sách đều bảo vệ invariant. |
| Trạng thái | PAID thiếu phương thức, approved thiếu người, mốc thời gian ngược | Bị chặn; test bao gồm NULL khiến CHECK thành UNKNOWN. |
| Đồng thời | Hai connection và barrier thật cùng đặt/pay/approve/redeem | Chỉ kết quả hợp lệ được commit; không tồn âm, trùng invoice hoặc cấp thưởng đôi. |
| Lặp yêu cầu | Cùng key cùng payload; cùng key khác payload | Lặp hợp lệ trả cùng kết quả, payload khác bị phát hiện. |
| Rollback | Chèn lỗi sau khi đã ghi một phần | Không có khoản tiền, tồn, điểm, ca hoặc notification mồ côi. |
| Lịch sử | Đổi giá, policy, tên món, nhân sự và vị trí máy | Chứng từ cũ giữ đúng ý nghĩa; JOIN không làm đổi số liệu quá khứ. |
| Đối soát | Ledger/read model/header-detail | Không có sai lệch chưa được phê duyệt và giải trình. |
| Phân quyền | ADMIN/DIRECTOR/MANAGER/STAFF/KITCHEN/INVENTORY/CUSTOMER | Đúng quyền và phạm vi; chặn tự duyệt theo quy trình. |
| Migration | DB mới, DB có lịch sử, dừng giữa backfill, chạy tiếp | Không mất dữ liệu; tái chạy không nhân đôi. |
| Vận hành | Backup/restore, worker dừng sau commit, retry outbox | Khôi phục được; không gửi/cấp thưởng/hạch toán trùng. |
| Hiệu năng | EXPLAIN và dữ liệu mô phỏng có quy mô công bố | Đạt ngưỡng thời gian đã chốt; dữ liệu mô phỏng ghi nhãn rõ. |

Integration test chỉ ghi vào `cyberhub_manager_test` hoặc database thử nghiệm được chỉ định rõ; không reset/seed database trình diễn. Báo cáo ghi commit, cấu hình RBAC, schema version, bộ dữ liệu, số test pass/fail/skip và ngày chạy. Chỉ chạy toàn bộ suite ở bước kiểm chứng cuối sau các test theo phạm vi.

## 12. Điều kiện nghiệm thu để đưa vào BTL

- [x] Có phạm vi nghiệp vụ và quyết định B01–B10 đã được xác nhận — [DATABASE_3NF_PROOFS.md §2](DATABASE_3NF_PROOFS.md).
- [x] Mỗi quan hệ logic (74/74 bảng nghiệp vụ) có đầy đủ FD, mọi candidate key và phân tích 1NF/2NF/3NF; đã rà các FD suy diễn trong `F+` — [DATABASE_3NF_PROOFS.md §4](DATABASE_3NF_PROOFS.md).
- [x] Mọi phân rã (`028`, `029`) có bằng chứng nối không mất mát (Định lý Heath) và bảo toàn phụ thuộc; ngoại lệ lịch sử/phạm vi được nêu rõ — [DATABASE_3NF_PROOFS.md §3](DATABASE_3NF_PROOFS.md).
- [x] Phân biệt rõ mô hình logic 3NF (0 generated column, 0 JSON trên 74 bảng cơ sở, 18 view `v_*`) với các số dư tổng hợp liên bảng NF-05 được công bố tường minh — [DATABASE_3NF_PROOFS.md §1](DATABASE_3NF_PROOFS.md).
- [x] Mỗi thuộc tính có một ngữ nghĩa và nguồn sở hữu duy nhất (`employee_profiles` vs `employees` tại `029`); snapshot chính sách có phiên bản bất biến (`loyalty_policy_versions`, `menu_promotion_versions`) — [`028`](../../sql/028_3nf_derived_and_transitive_cleanup.sql), [`029`](../../sql/029_3nf_hr_identity_and_policy_versions.sql).
- [x] Không có dữ liệu sai cơ sở, sai chủ, trùng nghiệp vụ, orphan hoặc lệch tổng chưa giải trình — kiểm chứng qua 11 trigger INT-01 tại [`030`](../../sql/030_strict_integrity_checks_and_cross_store_guards.sql) và đối soát clone `cyberhub_manager` đạt 0 sai lệch trên 402 hóa đơn, 11 ví, 254 đơn POS, 10 ca, 2 kỳ đối soát.
- [x] Các tổ hợp NULL/trạng thái được kiểm tra đúng (chống lỗ hổng `UNKNOWN` của MySQL CHECK) và tách nhiệm vụ SoD ở cả DB lẫn backend — [`test_3nf_and_integrity.py`](../../tests/integration/test_3nf_and_integrity.py).
- [x] Dòng tiền, doanh thu, tiền nạp, bonus, điểm và xu được phân biệt, không cộng trùng — xác minh bằng đối soát số liệu trước/sau migration và B08/B09.
- [x] Luồng tiền/kho/chứng từ/điểm/notification nguyên tử và idempotent; có test concurrent bằng nhiều connection — `test_wallet_flow.py`, `test_open_session_flow.py`, `test_inventory_order_lifecycle.py`, `test_3nf_and_integrity.py`.
- [x] Quyền và tách nhiệm vụ được kiểm tra tại backend và ràng buộc DB; đã thử truy cập trái phép — `test_rbac_followup_mysql.py`, `test_3nf_and_integrity.py` (lưu ý: tách user DB runtime chỉ-INSERT cho audit/ledger vẫn là giới hạn môi trường demo đã công bố).
- [x] Migration dữ liệu cũ (backup `mysqldump` 443.395 byte → restore vào `cyberhub_manager_migration_test` → áp `028`–`030` → đối soát 0 sai lệch → áp `cyberhub_manager`) và tạo DB mới (`cyberhub_manager_test` từ `001`–`030`) đều qua nghiệm thu.
- [x] ERD ([`current_erd.md`](../diagrams/current_erd.md)), data dictionary ([`data_dictionary.md`](../diagrams/data_dictionary.md)), source (`src/`, `scripts/`), migrations (`001`–`030`, giữ nguyên `001`–`027`) và kết quả test khớp cùng một phiên bản.
- [x] Các khả năng chưa triển khai và giới hạn demo được công bố trung thực — [DATABASE_3NF_PROOFS.md §1](DATABASE_3NF_PROOFS.md).

## 13. Cách trình bày báo cáo

Phần chính nên trình bày phạm vi nghiệp vụ, các FD tiêu biểu, phép phân rã có chứng minh, ERD chia theo phân hệ, các transaction quan trọng và kết quả kiểm thử. Đưa toàn bộ danh sách 74 quan hệ, candidate key, FD và dictionary vào phụ lục ([DATABASE_3NF_PROOFS.md](DATABASE_3NF_PROOFS.md) và [data_dictionary.md](../diagrams/data_dictionary.md)).

**Mô tả chuẩn mực để đưa trực tiếp vào báo cáo BTL (đã điền số liệu thật và giới hạn):**

> Mô hình quan hệ gồm **74 bảng nghiệp vụ cơ sở** (cùng 1 bảng kỹ thuật `schema_migrations`, 18 view đọc `v_*` và 24 trigger toàn vẹn) ở phiên bản migration `001`–`030` (MySQL 8.4, 100% InnoDB, `utf8mb4_0900_ai_ci`) đã được kiểm tra và chứng minh đạt **chuẩn 3NF nghiêm ngặt** theo tập phụ thuộc hàm nghiệp vụ và quyết định B01–B10 tại phụ lục `DATABASE_3NF_PROOFS.md`. Toàn bộ cột dẫn xuất/công thức (NF-01), phụ thuộc bắc cầu từ khóa ngoại cha (NF-02), hai nguồn sự thật nhân sự (NF-03) và cột JSON bán cấu trúc (NF-04) đã được loại bỏ khỏi bảng cơ sở (0 cột sinh, 0 cột JSON) kèm chứng minh nối không mất mát và bảo toàn phụ thuộc. Các trường số dư/tổng tổng hợp liên bảng (NF-05) được công bố rõ ràng là projection đồng bộ nguyên tử với sổ cái dưới khóa hàng `FOR UPDATE`. Phiên bản sau chuẩn hóa vượt qua **1.904 unit test** (5 skip symlink Windows) và **258 integration test** trên MySQL 8.4 thật (gồm bộ kiểm thử riêng cho 3NF, CHECK chống `NULL/UNKNOWN`, SoD và trigger chéo cơ sở), đồng thời vượt qua diễn tập sao lưu/phục hồi và nâng cấp dữ liệu thật với **0 sai lệch đối soát**. Các giới hạn phạm vi (tham chiếu đa hình `source_type/source_id`, `entity_id`; tài khoản DB demo dùng chung; 2 hợp đồng seed lịch sử trước `030`) được công bố minh bạch tại mục 1 của phụ lục.

## 14. Tài liệu tham khảo

- [Purdue University — Normalization](https://www.cs.purdue.edu/homes/cs541/other_handouts/normalization.pdf): định nghĩa và chứng minh chuẩn hóa.
- [MySQL 8.4 — CHECK constraints](https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html): xử lý biểu thức TRUE/UNKNOWN.
- [MySQL 8.4 — FOREIGN KEY constraints](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html): khóa tham chiếu, index và hành vi FK.
- [MySQL 8.4 — implicit commit](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html): giới hạn transaction với DDL.
- [Mô hình dữ liệu của dự án](DATA_MODEL.md), [luồng nghiệp vụ](BUSINESS_FLOWS.md), [kiến trúc bốn tầng](OVERVIEW.md), [thiết kế RBAC](../RBAC_DESIGN.md).
