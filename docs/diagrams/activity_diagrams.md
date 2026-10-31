# Activity Diagrams

<!-- Linh: còn bổ sung luồng nạp tiền (LI-04) và checkout (LI-07). -->

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

