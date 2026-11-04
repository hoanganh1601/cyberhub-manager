# Activity Diagrams

<!-- Linh: còn bổ sung luồng nạp tiền (LI-04). -->

## 1. Mở phiên sử dụng máy (LI-06)

Căn cứ: SES-01 đến SES-06 trong `docs/01_REQUIREMENTS.md`, `SessionServiceProtocol`
trong `services/contracts.py`. Preview chỉ đọc; mở phiên khóa dữ liệu bằng
`SELECT ... FOR UPDATE` và chạy trọn trong một transaction.

```mermaid
flowchart TD
    START(("Bắt đầu")) --> A["Nhân viên bấm 'Mở máy' trên card máy AVAILABLE"]
    A --> B["Chọn khách hàng"]
    B --> P1

    subgraph PREVIEW ["preview_open: chỉ đọc, không khóa, không ghi"]
        P1["Đọc lại actor từ DB<br>(actor_provider + AuthRepository)"]
        P1 --> P2{"Employee và store ACTIVE,<br>khớp employee_id, store_id, role?"}
        P2 -- "Có" --> P3{"Máy cùng store, active, AVAILABLE;<br>khách và account ACTIVE;<br>không có phiên ACTIVE?"}
        P3 -- "Có" --> P4["Tính minimum_balance = ceil(30 x đơn giá / 60)<br>estimated_minutes = floor(số dư x 60 / đơn giá)"]
    end

    P4 --> D1{"can_open?<br>số dư >= minimum_balance"}
    D1 -- "Không" --> TOPUP["Hiện số tiền cần nạp;<br>nhân viên nạp tiền cho khách (LI-04)"]
    TOPUP --> P1
    D1 -- "Có" --> C["Nhân viên xác nhận mở phiên"]
    C --> T1

    subgraph TX ["open_session: một transaction"]
        T1["BEGIN; đọc lại actor từ DB"]
        T1 --> T2["SELECT máy FOR UPDATE"]
        T2 --> T3{"Máy cùng store,<br>active, AVAILABLE?"}
        T3 -- "Có" --> T4["Đọc khách;<br>SELECT account FOR UPDATE"]
        T4 --> T5{"Khách ACTIVE,<br>account ACTIVE?"}
        T5 -- "Có" --> T6["SELECT phiên ACTIVE theo máy<br>và theo khách FOR UPDATE"]
        T6 --> T7{"Không có<br>phiên ACTIVE?"}
        T7 -- "Có" --> T8{"Số dư >=<br>minimum_balance?"}
        T8 -- "Có" --> T9["INSERT usage_sessions<br>hourly_rate = snapshot đơn giá máy (SES-02)"]
        T9 --> T10{"mark_in_use:<br>máy AVAILABLE -> IN_USE?"}
        T10 -- "Có" --> T11["COMMIT<br>(không trừ tiền, không tạo hóa đơn)"]
    end

    P2 -- "Không" --> DENY["PermissionDeniedError"]
    T1 -- "Actor không hợp lệ" --> DENY
    P3 -- "Không" --> REJECT["ConflictError / NotFoundError /<br>PermissionDeniedError (khác store)"]
    T3 -- "Không" --> RB["ROLLBACK<br>ConflictError / PermissionDeniedError"]
    T5 -- "Không" --> RB
    T7 -- "Không" --> RB
    T10 -- "Không" --> RB
    T9 -.->|"Trùng unique index<br>(hai request cùng lúc)"| RB
    T8 -- "Không" --> RBI["ROLLBACK<br>InsufficientBalanceError (required_top_up)"]

    DENY --> ERR["UI hiển thị lỗi thân thiện,<br>dữ liệu không thay đổi"]
    REJECT --> ERR
    RB --> ERR
    RBI --> ERR
    T11 --> OK["Trả SessionSummary;<br>card máy chuyển IN_USE"]
    OK --> END1(("Kết thúc"))
    ERR --> END1
```

**Điểm chính**

| Điểm | Cách đảm bảo |
|---|---|
| Không tin role/store từ UI | Mỗi lần gọi đều đọc lại actor bằng `AuthRepository.get_active_session_by_id`; role, store khai báo khác DB thì bị từ chối |
| Preview không ghi | `preview_open` dùng `lock=False`, không gọi `create` hay `mark_in_use` |
| Chống mở trùng (SES-03) | Khóa theo thứ tự máy -> account -> phiên; request sau phải chờ rồi đọc thấy máy `IN_USE`. Unique index `uq_usage_sessions_active_machine/customer` là lưới an toàn cuối |
| Insert phiên và đổi máy cùng thành công hoặc cùng thất bại | Mọi lỗi sau `INSERT` thoát khỏi `with transaction()` nên rollback cả phiên |
| Snapshot đơn giá (SES-02) | `usage_sessions.hourly_rate` chép từ máy lúc mở; đổi giá máy sau đó không ảnh hưởng |

## 2. Live estimate trên dashboard (SES-05, SES-06)

Không thêm method vào `SessionServiceProtocol`; dashboard lấy qua
`MachineService.list_machines()`, dùng chung `estimate_live_usage()` ở domain với
công thức tính phí checkout (SES-07).

```mermaid
flowchart TD
    S(("Mỗi lần refresh dashboard")) --> L1["MachineService.list_machines(store_id)"]
    L1 --> L2["Với mỗi máy IN_USE: lấy phiên ACTIVE<br>và số dư hiện tại của khách"]
    L2 --> L3["estimate_live_usage(session, balance, now)<br>at = max(now, started_at), theo UTC"]
    L3 --> L4["elapsed_seconds; estimated_cost theo đơn giá snapshot;<br>projected_balance = số dư - estimated_cost"]
    L4 --> L5{"projected_balance < 0?"}
    L5 -- "Có" --> W["Card máy cảnh báo đỏ (SES-06),<br>không tự tắt máy"]
    L5 -- "Không" --> N["Card hiển thị bình thường"]
    W --> E(("Hết lượt refresh"))
    N --> E
```

## 3. Checkout và tạo hóa đơn (LI-07)

Căn cứ: SES-07 đến SES-09 và INV-01 trong `docs/01_REQUIREMENTS.md`. Preview chỉ
đọc. Hoàn tất checkout tính lại phí bằng giờ server và số dư đã khóa; trừ số dư,
ghi giao dịch, đóng phiên, trả máy và tạo hóa đơn cùng commit hoặc cùng rollback.

```mermaid
flowchart TD
    START(("Bắt đầu")) --> A["Nhân viên bấm 'Checkout' trên card máy IN_USE"]
    A --> P1

    subgraph PREVIEW ["preview_checkout: chỉ đọc, không khóa, không ghi"]
        P1["Đọc lại actor từ DB<br>(actor_provider + AuthRepository)"]
        P1 --> P2{"Actor hợp lệ,<br>máy cùng store,<br>có phiên ACTIVE?"}
        P2 -- "Có" --> P3["Tính phí theo usage_sessions.hourly_rate (SES-07)<br>phút = max(1, ceil(giây / 60))<br>phí = ceil(phút x đơn giá / 60)"]
        P3 --> P4["projected_balance = số dư - phí<br>settlement_required = max(0, -projected_balance)"]
    end

    P4 --> D1{"settlement_required > 0?"}
    D1 -- "Không" --> C0["Xác nhận: settlement_amount = 0, method = None"]
    D1 -- "Có" --> C1["Thu tiền bằng CASH / TRANSFER<br>settlement_amount = settlement_required;<br>tiền khách đưa và tiền thừa chỉ thuộc UI"]
    C0 --> T1
    C1 --> T1

    subgraph TX ["complete_checkout: một transaction"]
        T1["BEGIN; đọc lại actor từ DB"]
        T1 --> T2["SELECT máy FOR UPDATE<br>-> SELECT account FOR UPDATE<br>-> SELECT phiên ACTIVE FOR UPDATE"]
        T2 --> T3{"Máy cùng store, IN_USE,<br>vẫn đúng phiên đã đọc?"}
        T3 -- "Có" --> T4["Tính lại phí bằng giờ server<br>và số dư đã khóa"]
        T4 --> T5{"Tiền bù bằng đúng<br>settlement_required?"}
        T5 -- "Có" --> T6["Có tiền bù: cộng số dư<br>+ ghi DEBT_SETTLEMENT"]
        T6 --> T7["Trừ phí (balance >= phí)<br>+ ghi USAGE_PAYMENT"]
        T7 --> T8["usage_sessions -> COMPLETED<br>(closed_by, ended_at, cost)"]
        T8 --> T9["machines IN_USE -> AVAILABLE"]
        T9 --> T10["INSERT invoices (PAID)<br>một phiên một hóa đơn"]
        T10 --> T11["COMMIT"]
    end

    P2 -- "Không" --> REJECT["PermissionDeniedError / NotFoundError /<br>ConflictError (không có phiên)"]
    T1 -- "Actor không hợp lệ" --> RB
    T3 -- "Không" --> RB["ROLLBACK<br>ConflictError / PermissionDeniedError"]
    T5 -- "Thiếu tiền bù" --> RBS["ROLLBACK<br>SettlementRequiredError (settlement_required)"]
    T5 -- "Lớn hơn số tiền còn thiếu" --> RBV["ROLLBACK<br>ValidationError"]
    T7 -.->|"Lỗi ở bất kỳ bước ghi nào"| RBA["ROLLBACK toàn bộ<br>số dư, giao dịch, phiên, máy, hóa đơn"]
    T10 -.->|"Trùng uq_invoices_session<br>(double-click)"| RB

    RBS --> C1
    REJECT --> ERR["UI hiển thị lỗi thân thiện,<br>dữ liệu không thay đổi"]
    RB --> ERR
    RBV --> ERR
    RBA --> ERR
    T11 --> OK["Trả CheckoutResult: InvoiceDetail + balance_after;<br>card máy về AVAILABLE"]
    OK --> END1(("Kết thúc"))
    ERR --> END1
```

**Điểm chính**

| Điểm | Cách đảm bảo |
|---|---|
| Không tin số liệu từ UI | Contract không nhận phí, thời lượng hay số dư; `ended_at` lấy từ đồng hồ server, số dư đọc sau khi khóa |
| Preview không ghi | `preview_checkout` đọc không khóa, không gọi repository ghi |
| Số dư không âm | Cộng tiền bù trước, `debit_balance` có `WHERE balance >= amount` |
| Một phiên một hóa đơn, chống double-click | Request sau chờ khóa máy rồi thấy máy `AVAILABLE`; `UPDATE ... WHERE status = 'ACTIVE'`; unique `uq_invoices_session` là lưới an toàn cuối |
| Nguyên tử (SES-09) | Mọi lệnh ghi nằm trong `with transaction()`; repository trả `False` hoặc ném lỗi đều làm rollback cả năm nhóm dữ liệu |
| Thứ tự khóa | Máy -> account -> phiên, giống mở phiên, để hai thao tác không khóa chéo nhau |
| Tiền bù không phải tiền khách đưa | `settlement_amount` phải bằng đúng `settlement_required`; tiền khách đưa và tiền thừa chỉ được UI dùng để hiển thị, phần dư muốn nạp vào ví phải gọi luồng `top_up` riêng |

