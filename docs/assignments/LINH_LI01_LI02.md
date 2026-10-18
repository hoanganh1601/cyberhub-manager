# Phiếu giao việc — Linh — LI-01 và LI-02

## Mục tiêu

Bàn giao dữ liệu và interface thống nhất để Ngát làm UI không cần chờ MySQL/service thật. Làm LI-01 trước, bàn giao sớm, rồi làm LI-02. Dùng chính xác `../07_DTO_UI_HANDOFF.md` v1 và requirements/theme hiện có.

## Đầu vào

- HA-02 đã có trên develop: 8 bảng, 11 index.
- `01_REQUIREMENTS.md`, `02_CODEBASE_SKELETON.md`, Logical ERD và bản DTO/UI v1.
- Quyết định dùng dataclass DTO, enum theo entity, Protocol và exception có field_errors đã có trong bản v1; không cần Ngát tự thiết kế lại.

## LI-01 — Phạm vi

1. `src/cyberhub_manager/domain/enums.py`: enum theo mục 3 bản v1.
2. `src/cyberhub_manager/domain/models.py`: entity theo schema/skeleton, các kiểu nullable rõ ràng; không đưa hash mật khẩu vào model công khai trả UI.
3. Thêm `src/cyberhub_manager/domain/dtos.py`: DTO và kiểu theo mục 4 bản v1.
4. `src/cyberhub_manager/domain/exceptions.py`: hierarchy và payload theo mục 6.
5. `docs/diagrams/class_diagram.md`: entity, DTO và service interface; thể hiện quan hệ customer-account, machine-active session, checkout-invoice.
6. Cập nhật `docs/02_CODEBASE_SKELETON.md` phần DTO/contract theo những điểm đã liệt kê ở mục 12 bản v1. Phần SQL/schema không thuộc task này.

Bàn giao sớm đầu tiên: EmployeeSession, CustomerSummary, SessionSummary, ActiveSessionSummary, MachineSummary; enum và business exceptions đi kèm. Các DTO còn lại hoàn thiện trong LI-01 trước khi đóng task.

## LI-02 — Phạm vi

1. Thêm `src/cyberhub_manager/services/contracts.py`: 6 Protocol và ServiceBundle theo mục 5 bản v1.
2. Thêm package `src/cyberhub_manager/services/mocks/`, gồm factory `build_mock_services`, MockScenario và sáu mock cùng một kho dữ liệu trong bộ nhớ.
3. Thêm README trong package mock: cách tạo bundle, tài khoản demo giả, kịch bản/operation bị tác động, cách reset và điều khiển clock.
4. Fixture và scenario theo mục 9: ba trạng thái máy, cảnh báo âm, customer inactive/account locked, success/empty/validation/conflict/unavailable.
5. Các mock dùng đúng Protocol, DTO và exception; hỗ trợ demo stateful cơ bản (tạo/sửa khách, nạp tiền/lịch sử, mở/checkout phiên) bằng bộ dữ liệu nhất quán, không triển khai SQL/locking/transaction DB.
6. Kiểm tra factory tạo dữ liệu độc lập giữa hai bundle; top-up trong một bundle phản ánh ở search/history; đường lỗi không thay đổi dữ liệu demo dở dang. Không viết test kiểm tra lại từng field dataclass.

## Phối hợp

- Thông báo Ngát tên DTO/module và đưa một fixture dùng được ngay sau lần bàn giao tối thiểu.
- Ngát chỉ import DTO chung; không duy trì một kiểu CustomerSummary/MachineSummary riêng ở UI.
- Helper hash/verify đã chốt tại `cyberhub_manager/security.py` do Hoàng Anh triển khai (mục 1 bản v1); auth thật dùng helper chung, không tự làm helper thứ hai trong UI hoặc mock. Mock không dùng mật khẩu database thật.
- Chưa nhận auth/customer/wallet/session service thật, repository hay UI vào LI-01/LI-02.

## Nghiệm thu

- Domain/contract import được khi không có Docker hoặc `.env`; không phụ thuộc UI/mysql connector.
- Hai trạng thái customer/account không bị nhập thành một status.
- Không có password/hash trong DTO trả UI.
- Mock dựng được dữ liệu hiển thị đúng số liệu tại mục 9; cùng API với service thật dự kiến.
- Empty trả []; không tìm thấy đối tượng trả NotFoundError; lỗi field có tên ổn định.
- Ngát chạy được gallery bằng factory chung và không phải đổi field DTO.
- Bàn giao danh sách file, hướng dẫn dùng mock và kết quả kiểm tra hành vi quan trọng; Class Diagram/contract khớp code.

Nhánh gợi ý: `feature/LI-01-domain-contracts`, sau đó `feature/LI-02-service-mocks` từ develop đã có LI-01.
