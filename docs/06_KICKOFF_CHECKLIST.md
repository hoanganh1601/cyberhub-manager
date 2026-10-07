# 6. Checklist kickoff trước khi code

Checklist này là cổng vào Cycle 0. Nhóm chỉ bắt đầu code tính năng khi phần “Gate bắt buộc” được hoàn thành và có bằng chứng trên GitHub/Linear.

## 6.1. Quyết định đã khóa

| Hạng mục | Quyết định |
|---|---|
| Tên sản phẩm | CyberHub Manager |
| GitHub repository | `cyberhub-manager` |
| Python package | `cyberhub_manager` |
| Python | 3.11 trở lên; cả nhóm dùng cùng minor version nếu có thể |
| Frontend | CustomTkinter; theme Cyber Ops Dark |
| Database | MySQL 8.4 LTS, InnoDB, utf8mb4 |
| MySQL local | Docker image `mysql:8.4` qua `docker-compose.yml` |
| Driver | `mysql-connector-python` |
| Kiến trúc | UI → Service → Repository → Database |
| Tiền tệ | `BIGINT` có dấu, đơn vị VND; không dùng float/double |
| Timezone | DB lưu UTC; UI hiển thị Asia/Ho_Chi_Minh |
| Branch | `main`, `develop`, feature branch theo Linear ID |
| Merge strategy | Feature → develop bằng Squash and merge; release → main |

## 6.2. Gate bắt buộc trước khi chia code

### Repository — Hoàng Anh

- [ ] Repository GitHub rỗng đã được tạo đúng tên.
- [ ] Thư mục dự án được `git init` độc lập, không dùng nhầm repository cha.
- [ ] `main` và `develop` đã push.
- [ ] Linh và Ngát đã được mời làm collaborator.
- [ ] Branch protection được bật cho `main` và `develop`.
- [ ] `.gitignore` loại `.env`, virtual environment, log, cache và database dump thật.

### Môi trường — Hoàng Anh, cả nhóm xác nhận

- [ ] `pyproject.toml`/`requirements.txt` có dependency đã thống nhất.
- [ ] `.env.example` chỉ chứa tên biến, không chứa credential thật.
- [ ] `docker-compose.yml` pin `mysql:8.4` và có healthcheck.
- [ ] Có một lệnh khởi động MySQL và một lệnh chạy test trong README.
- [ ] Cả ba máy kết nối được MySQL và dùng cùng charset/timezone.

Biến môi trường tối thiểu:

```text
MYSQL_HOST
MYSQL_PORT
MYSQL_DATABASE
MYSQL_USER
MYSQL_PASSWORD
LOG_LEVEL
```

### Contract — Linh chủ trì, cả nhóm duyệt

- [ ] DTO/model/enum ban đầu đã được chốt.
- [ ] Public service contract trong `02_CODEBASE_SKELETON.md` được giữ nguyên hoặc cập nhật qua PR.
- [ ] Contract có đủ khóa/mở khóa khách; thêm/sửa/bảo trì/archive máy.
- [ ] Mock service có success, empty, validation, conflict và permission error.
- [ ] Ngát xác nhận DTO đủ dữ liệu cho mọi màn P0.
- [ ] Hoàng Anh xác nhận repository có thể cung cấp dữ liệu theo contract.

### Database design — Hoàng Anh chủ trì

- [ ] ERD đủ 8 bảng P0 và cardinality.
- [ ] Data dictionary có type, nullable, default, PK/FK/index.
- [ ] Generated columns + unique indexes cho active machine/customer đã được thử trên MySQL 8.4.
- [ ] Quy tắc `ON DELETE RESTRICT`, archive máy và bảo toàn lịch sử được chốt.
- [ ] Thứ tự khóa `SELECT ... FOR UPDATE` của top-up/open/checkout được ghi lại để tránh deadlock.
- [ ] Migration và seed strategy được cả nhóm hiểu.

### UI foundation — Ngát chủ trì

- [ ] Theme token được đặt duy nhất tại `ui/theme.py`.
- [ ] Có wireframe/login/app shell/machine card/customer table/dialog chính.
- [ ] Có màn quản lý máy cho Manager/Admin.
- [ ] Loading, empty, disabled, success và error state đã được thiết kế.
- [ ] Screenshot 1280×720 không vỡ layout.

### Linear — Hoàng Anh/PO

- [ ] Import đủ 30 issue từ `linear_import.csv`.
- [ ] Assignee khớp tài khoản thật của Hoàng Anh, Linh, Ngát.
- [ ] Tạo 5 cycle một tuần hoặc điều chỉnh theo deadline thực tế.
- [ ] Mỗi issue có priority, estimate, labels, dependency và acceptance criteria.
- [ ] Chỉ issue đạt Definition of Ready mới chuyển sang `In Progress`.

## 6.3. Diagram deliverables

| Diagram | Owner | Reviewer | Hạn tương đối |
|---|---|---|---|
| ERD + cardinality | Hoàng Anh | Linh | Trước HA-06/HA-07 |
| Class Diagram domain/service | Linh | Hoàng Anh, Ngát | Trước LI-03 |
| Activity Diagram nạp tiền | Linh | Hoàng Anh | Trước LI-04 |
| Activity Diagram mở phiên | Linh | Hoàng Anh, Ngát | Trước LI-06/NG-05 |
| Activity Diagram checkout | Linh | Hoàng Anh, Ngát | Trước LI-07/NG-06 |
| UI navigation/wireflow | Ngát | Linh | Trước NG-02 |

Diagram phải khớp requirement và code hiện tại; khi contract/schema thay đổi, diagram được cập nhật trong cùng PR.

## 6.4. Thứ tự công việc Cycle 0

1. Hoàng Anh thực hiện HA-01, sau đó HA-02 và HA-04; HA-03 bắt đầu khi schema được duyệt.
2. Linh thực hiện LI-01, chốt Class Diagram/DTO, sau đó LI-02 tạo mock contract.
3. Ngát thực hiện NG-01 bằng mock DTO đã thống nhất, không chờ database hoàn thành.
4. Cả nhóm tổ chức contract review: schema ↔ DTO ↔ UI state.
5. Merge các PR foundation vào `develop` và chạy smoke test trên máy của cả ba người.

HA-11 thuộc Cycle 1, nhưng Hoàng Anh có thể dựng Login bằng mock ngay sau khi NG-01 và LI-02 được merge. Việc này không làm thay đổi dependency/gate của Cycle 0.

Không bắt đầu LI-03, NG-02 hoặc repository feature khi contract review chưa pass.

## 6.5. Tiêu chí kết thúc Cycle 0

- [ ] Clone repository trên máy sạch thành công.
- [ ] MySQL healthcheck pass và migration/seed chạy được.
- [ ] Project import/start được dù màn hình còn placeholder.
- [ ] Login mock/app shell render đúng theme.
- [ ] ERD, Class Diagram, DTO và service contract được approve.
- [ ] Automated test command chạy được và có ít nhất một smoke test.
- [ ] Không có secret, dump thật hoặc file môi trường bị commit.
- [ ] Không còn quyết định kỹ thuật P0 chưa có owner.

Khi tất cả mục trên pass, dự án ở trạng thái **GO cho Cycle 1**.
