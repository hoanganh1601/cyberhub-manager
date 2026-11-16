# Architecture cleanup

Đợt refactor này chỉ thay đổi ranh giới module, không thay đổi URL, DTO, SQL schema
hay quy tắc nghiệp vụ.

## Domain

`domain/models.py` là facade tương thích. Entity cụ thể nằm trong:

- `model_base.py`: validation dùng chung, `Entity`, `Person`.
- `organization_models.py`: `Store`, `Employee`.
- `account_models.py`: `Account`, `Customer`.
- `machine_models.py`: `Machine`.
- `usage_models.py`: phiên sử dụng và ước tính chi phí.
- `billing_models.py`: giao dịch ví và hóa đơn.

Code cũ vẫn có thể import từ `domain.models`; code mới nên import từ module theo
bounded context khi không cần facade.

## Services và repositories

- `MenuService` là facade ổn định. Catalog/khuyến mãi, kho và vòng đời đơn được
  tách lần lượt sang `menu_catalog_service.py`, `menu_inventory_service.py` và
  `menu_order_service.py`.
- `P1Repository` là facade ổn định ghép các capability quản trị, portal và loyalty.
  SQL helper dùng chung nằm tại `repositories/sql.py`.
- Query hóa đơn khách hàng nằm trong `CustomerInvoiceQueryService`, không nằm
  trong repository facade đa năng.

## Web

- `application.py`: application factory, security hooks, session và auth routes.
- `operations_routes.py`: quản trị, khách hàng, máy, phiên, hóa đơn và doanh thu.
- `feature_routes.py`: POS/kho, voucher, game và quảng cáo.
- `config.py`, `demo.py`, `serialization.py`: cấu hình, workspace demo và JSON projection.

Route registration vẫn diễn ra trong `create_app()`, vì vậy public API và endpoint
không đổi.

## Demo in-memory

`services/mocks` được phân loại qua các namespace:

- `application_services.py`: service doubles.
- `repositories.py`: repository adapters bộ nhớ.
- `demo_data.py`: fixture, scenario và data store.
- `factory.py`: composition root tạo `ServiceBundle`.

MySQL runtime không được import các implementation demo theo tính năng.

## Quy tắc tương thích

Các facade `domain.models`, `MenuService`, `P1Repository` và
`services.mocks.build_mock_services` phải được giữ cho tới khi có migration API
riêng. Mọi lần tách module tiếp theo phải chạy test facade và test nghiệp vụ trước
khi xóa đường import cũ.
