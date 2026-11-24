# UML hệ thống CyberHub Manager

Tài liệu này mô tả cấu trúc source bốn tầng và các luồng nghiệp vụ trọng tâm sau migration `032` (75 bảng nghiệp vụ, 18 view đọc, 28 trigger).
ERD đầy đủ nằm tại [current_erd.md](current_erd.md); kiểu cột và ràng buộc vật lý nằm tại
[data_dictionary.md](data_dictionary.md). Các sơ đồ Mermaid có thể xem trực tiếp trên GitHub.

## 1. System context — tác nhân và năng lực hiện có

```mermaid
flowchart LR
    Customer([Khách hàng])
    Staff([Nhân viên])
    Kitchen([Bếp])
    Inventory([Thủ kho])
    Manager([Quản lý cơ sở])
    Director([Giám đốc])
    Admin([Quản trị hệ thống])

    subgraph CyberHub[CyberHub Manager]
        CustomerPortal[Customer Portal]
        Operations[Vận hành máy, hóa đơn, POS]
        BackOffice[Kho, mua hàng, ca tiền, bảo trì]
        Rewards[Voucher, game, quảng cáo nhận thưởng]
        Management[Nhân sự, cơ sở, doanh thu, dự báo]
        Identity[Tài khoản, RBAC, audit]
    end

    Customer --> CustomerPortal
    Customer --> Rewards
    Staff --> Operations
    Staff --> BackOffice
    Kitchen --> Operations
    Inventory --> BackOffice
    Manager --> Operations
    Manager --> BackOffice
    Director --> Management
    Director --> Rewards
    Admin --> Identity
```

Sơ đồ thể hiện **phạm vi năng lực**, không thay thế ma trận quyền. Quyền chi tiết và giới hạn theo cơ sở
nằm tại [RBAC_PERMISSION_MATRIX.md](../RBAC_PERMISSION_MATRIX.md); backend vẫn kiểm tra quyền ở từng use case.

## 2. Domain map — ranh giới nghiệp vụ

```mermaid
flowchart TB
    Identity[Identity & RBAC]
    Organization[Cơ sở & nhân sự]
    Customer[Khách hàng & thành viên]
    Machine[Máy & phiên sử dụng]
    Billing[Hóa đơn, ví & thanh toán]
    POS[Menu & POS]
    Inventory[Kho nguyên liệu]
    Procurement[Nhà cung cấp & mua hàng]
    Shift[Ca làm việc & két tiền]
    Maintenance[Bảo trì & sự cố]
    Reward[Voucher, game & quảng cáo]
    Commercial[Đối tác thương mại]
    Forecast[Phân tích & dự báo]

    Identity -->|định danh actor| Organization
    Organization -->|nhân viên vận hành| Shift
    Organization -->|báo cáo / phân công| Maintenance
    Customer -->|mở phiên| Machine
    Machine -->|kết toán thời gian| Billing
    Customer -->|số dư / hóa đơn| Billing
    Customer -->|đặt món| POS
    POS -->|thanh toán đơn| Billing
    POS -->|giữ và trừ tồn| Inventory
    Procurement -->|nhận hàng| Inventory
    Shift -->|đối chiếu thu chi| Billing
    Reward -->|cấp quyền lợi| Customer
    Commercial -->|chiến dịch tài trợ| Reward
    Forecast -.->|đọc dữ liệu lịch sử| Machine
    Forecast -.->|đọc dữ liệu lịch sử| Billing
    Forecast -.->|đọc dữ liệu lịch sử| POS
```

Mũi tên nét liền là phụ thuộc nghiệp vụ khi thực hiện giao dịch. Mũi tên nét đứt là luồng đọc phục vụ
phân tích; module dự báo không ghi ngược vào dữ liệu giao dịch.

## 3. Component diagram — kiến trúc bốn tầng

```mermaid
flowchart LR
    actorCustomer([Khách hàng])
    actorEmployee([Nhân viên / Quản lý])

    subgraph P[Presentation]
        Web[Web routes + JSON API]
        Desktop[Desktop views]
    end

    subgraph A[Application]
        SessionReport[SessionService & ReportService]
        PortalSvc[PortalService + portal_profile]
        GameService[GameService]
        AdService[AdService]
        OtherServices[Services nghiệp vụ khác]
    end

    subgraph D[Domain]
        Entities[Entities + enums]
        Policies[domain/policies.py: RBAC + money]
        BusinessTime[Business time UTC+7]
    end

    subgraph I[Infrastructure]
        CoreRepos[Session / Invoice / Account Repos]
        MgmtRepos[Management / Portal / Loyalty Repos]
        GameRepo[GameRepository]
        AdRepo[AdRepository]
        Tx[Transaction manager]
        MySQL[(MySQL 8.4)]
    end

    actorCustomer --> Web
    actorEmployee --> Web
    actorEmployee --> Desktop
    Web --> SessionReport
    Web --> PortalSvc
    Web --> GameService
    Web --> AdService
    Desktop --> SessionReport
    Desktop --> OtherServices
    SessionReport --> Policies
    PortalSvc --> MgmtRepos
    GameService --> Policies
    AdService --> Policies
    GameService --> BusinessTime
    AdService --> BusinessTime
    SessionReport --> CoreRepos
    GameService --> GameRepo
    AdService --> AdRepo
    AdService --> GameRepo
    OtherServices --> MgmtRepos
    CoreRepos --> Tx
    MgmtRepos --> Tx
    GameRepo --> Tx
    AdRepo --> Tx
    Tx --> MySQL
    SessionReport --> Entities
    GameService --> Entities
    AdService --> Entities
```

Quy tắc phụ thuộc hiện hành: Presentation gọi Application; Application dùng Domain và repository/adapter
Infrastructure; Infrastructure truy cập MySQL và provider kỹ thuật. Domain không phụ thuộc Flask, Tkinter,
Application hay MySQL. Đây là layered architecture bốn tầng của source hiện tại, không mô tả sai thành
Clean Architecture với repository port chưa tồn tại.

## 4. Class diagram — game và quảng cáo nhận thưởng

```mermaid
classDiagram
    direction LR

    class GameService {
        +portal_game(principal)
        +spin(principal)
        +redeem(principal, catalog_id, request_key)
        +manage(actor)
    }
    class AdService {
        +portal_ads(principal)
        +start(principal)
        +complete(principal, token)
        +verify_network_callback(token, txn_id, signature)
    }
    class GameRepository {
        +count_sessions(account_id, game_id, day)
        +insert_session(..., created_at)
        +count_ad_spins(account_id, day)
        +insert_ledger(...)
    }
    class AdRepository {
        +insert_event(..., issued_at)
        +count_events(account_id, day, status)
        +finish_event(event_id, status)
        +daily_stats(since_day, now)
    }
    class BusinessTime {
        +local_day(moment) date
        +utc_day_bounds(day) tuple
    }
    class GameSession {
        +id int
        +account_id int
        +prize_index int
        +prize_label str
        +coins int
        +played_on date
        +created_at datetime
    }
    class AdEvent {
        +id int
        +token str
        +status AdStatus
        +played_on date
        +issued_at datetime
        +expires_at datetime
    }

    GameService --> GameRepository : uses contract
    AdService --> AdRepository : uses contract
    AdService --> GameRepository : credits reward
    GameService --> BusinessTime : local day policy
    AdService --> BusinessTime : local day policy
    GameRepository --> BusinessTime : indexed UTC bounds
    AdRepository --> BusinessTime : indexed UTC bounds
    GameRepository ..> GameSession : maps read model
    AdRepository ..> AdEvent : maps read model
```

`played_on` trong hai read model là dữ liệu trình bày được suy ra. Hai bảng cơ sở chỉ lưu
`created_at` hoặc `issued_at`, vì vậy không còn FD `timestamp → played_on` bên trong quan hệ.

## 5. Sequence diagram — quay thưởng an toàn

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Khách hàng
    participant API as Web API
    participant Service as GameService
    participant Repo as GameRepository
    participant DB as MySQL

    Customer->>API: POST /game/spin
    API->>Service: spin(principal)
    Service->>Repo: wallet(account_id, lock=True)
    Repo->>DB: SELECT ... FOR UPDATE
    Service->>Service: local_day(now UTC)
    Service->>Repo: count_sessions(account, game, day)
    Repo->>DB: WHERE created_at >= startUTC AND < endUTC
    Service->>Repo: count_ad_spins(account, day)
    Repo->>DB: SUM reward trong cùng khoảng UTC
    alt Hết lượt hoặc thao tác quá nhanh
        Service->>Repo: ghi bộ đếm nghi vấn / khóa ví nếu cần
        Service-->>API: ConflictError
    else Hợp lệ
        Service->>Service: bốc thăm phía máy chủ
        Service->>Repo: insert_session(created_at=now)
        Service->>Repo: cập nhật ví + append coin ledger
        Repo->>DB: COMMIT nguyên tử
        Service-->>API: giải thưởng và số dư
        API-->>Customer: kết quả
    end
```

## 6. Sequence và state diagram — quảng cáo nhận thưởng

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Khách hàng
    participant API as Web API
    participant Service as AdService
    participant Ads as AdRepository
    participant Games as GameRepository
    participant DB as MySQL

    Customer->>API: Bắt đầu xem quảng cáo
    API->>Service: start(principal)
    Service->>Games: khóa ví theo account
    Service->>Ads: count_events(account, localDay)
    Ads->>DB: lọc issued_at theo khoảng UTC có index
    Service->>Ads: insert_event(issued_at, min_complete_at, expires_at)
    Ads->>DB: INSERT status=ISSUED
    DB-->>Customer: token + nội dung quảng cáo
    Customer->>API: Hoàn thành(token)
    API->>Service: complete(principal, token)
    Service->>Ads: get_event(token, lock=True)
    Ads->>DB: SELECT ... FOR UPDATE
    alt Quá sớm, hết hạn, vượt hạn mức hoặc ví bị khóa
        Service->>Ads: finish_event(REJECTED, reason)
    else Hợp lệ
        Service->>Ads: finish_event(COMPLETED)
        Service->>Games: cộng xu hoặc cấp lượt quay
        Games->>DB: append ledger + cập nhật ví
    end
    Service->>DB: COMMIT nguyên tử
```

```mermaid
stateDiagram-v2
    [*] --> ISSUED: start
    ISSUED --> COMPLETED: xác minh hợp lệ
    ISSUED --> REJECTED: quá sớm / hết hạn / vượt hạn mức
    ISSUED --> REJECTED: token cũ bị thay thế
    COMPLETED --> [*]
    REJECTED --> [*]
```

## 7. Quy tắc dữ liệu sau migration `031`–`032`

- Timestamp trong bảng cơ sở là nguồn sự thật và được lưu theo UTC (`031`); ngày nghiệp vụ là `DATE(timestamp + INTERVAL 7 HOUR)` trong read model và truy vấn đếm theo ngày dùng khoảng UTC nửa mở có index.
- Sổ cái ví `account_transactions` luôn gắn `store_id NOT NULL` và tách liên kết phiên tùy chọn sang bảng 1–1 `session_transactions(transaction_id PK, session_id)` (`032`), loại bỏ cột `session_id` nullable/thưa trên sổ cái.
- Hai bảng sổ cái cốt lõi (`account_transactions`, `inventory_movements`) được bảo vệ bất biến (append-only) ở mức trigger MySQL (`BEFORE UPDATE` / `BEFORE DELETE` phát `SQLSTATE '45000'`).
- Giới hạn lượt, cập nhật ví, hủy phiên (`CANCELLED`), hủy hóa đơn (`VOID`) và ghi ledger đều chạy trong cùng transaction có khóa hàng `FOR UPDATE`.
