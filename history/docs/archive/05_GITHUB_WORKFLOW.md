# 5. GitHub Workflow cho nhóm 3 người

Tài liệu này là quy trình Git bắt buộc của dự án **CyberHub Manager**. Mục tiêu là để ba thành viên làm song song mà không ghi đè code, luôn truy ra task Linear và giữ `main` ở trạng thái demo được.

## 5.1. Vai trò trên GitHub

| Thành viên | Ownership chính | Review bắt buộc khi PR thay đổi |
|---|---|---|
| Hoàng Anh | Database, SQL, migration, repository, cấu hình project; Login UI/Auth integration | Schema, SQL, repository contract, transaction, dependency/config; Ngát review Login UI |
| Linh | Domain, service, business rule, automated test | Tính tiền, ví, phiên, checkout, exception/service contract |
| Ngát | UI/UX, theme, view/component, manual E2E | Theme, navigation, layout, wording, trạng thái UI |

Người tạo PR không tự approve PR của mình. Mỗi PR cần ít nhất một review; thay đổi liên quan hai ownership cần cả hai owner liên quan kiểm tra.

## 5.2. Mô hình branch

```text
main                 Bản ổn định, dùng để demo/nộp bài
└── develop          Nhánh tích hợp của cả nhóm
    ├── feature/HA-02-initial-schema
    ├── feature/LI-04-wallet-service
    ├── feature/NG-03-machine-dashboard
    ├── fix/LI-10-checkout-rounding
    └── docs/HA-10-data-dictionary
```

Quy tắc:

- Không commit trực tiếp vào `main` hoặc `develop`.
- Mỗi Linear issue tương ứng một branch và thường là một PR.
- Tạo branch mới từ `develop` mới nhất.
- Feature PR merge vào `develop`; chỉ release PR mới merge `develop` vào `main`.
- Branch sống ngắn, ưu tiên hoàn thành trong 1–3 ngày.
- Không dùng chung một feature branch cho nhiều người.

## 5.3. Thiết lập repository lần đầu — Hoàng Anh

Trên GitHub tạo repository rỗng:

- Repository: `cyberhub-manager`
- Không tạo README, `.gitignore` hoặc license trên GitHub vì tài liệu local đã tồn tại.

Tại thư mục dự án local:

```bash
cd "/media/icnlab/Data/halinh/HoangAnh/BTL Python + SQL/cyberhub-manager"
git init
git branch -M main
git add .
git commit -m "docs: initialize CyberHub Manager specification"
git remote add origin https://github.com/hoanganh1601/cyberhub-manager.git
git push -u origin main

git switch -c develop
git push -u origin develop
```

Đường dẫn chứa khoảng trắng nên **bắt buộc** đặt trong dấu ngoặc kép. Hai lệnh dưới đây tương đương:

```bash
cd "/media/icnlab/Data/halinh/HoangAnh/BTL Python + SQL/cyberhub-manager"
cd /media/icnlab/Data/halinh/HoangAnh/BTL\ Python\ +\ SQL/cyberhub-manager
```

Không dùng lệnh sau vì Bash sẽ tách đường dẫn thành nhiều đối số:

```bash
# Sai
cd /media/icnlab/Data/halinh/HoangAnh/BTL Python + SQL/cyberhub-manager
```

### Đẩy khung code sau khi đã đẩy docs

Git không hiển thị thư mục rỗng. Repository đã chuẩn bị các file placeholder trong `scripts/`, `sql/`, `src/` và `tests/` để mọi người clone về thấy toàn bộ module và owner/task. Các file này chỉ có comment/docstring, chưa có implementation.

Tạo branch riêng và đẩy skeleton:

```bash
git switch develop
git pull --rebase origin develop
git switch -c chore/HA-01-project-skeleton

git add .gitignore .env.example requirements.txt pyproject.toml docker-compose.yml
git add scripts sql src tests docs
git status
git commit -m "chore: add project code skeleton"
git push -u origin chore/HA-01-project-skeleton
```

Trên GitHub, tạo Pull Request:

```text
base: develop
compare: chore/HA-01-project-skeleton
title: [HA-01] Add project code skeleton
```

Sau khi PR được merge, Linh và Ngát chạy:

```bash
git switch develop
git pull --rebase origin develop
```

Lúc đó toàn bộ khung `src/cyberhub_manager`, `sql`, `scripts` và `tests` sẽ xuất hiện trên máy của mọi người.

Sau khi push:

1. Mời Linh và Ngát làm collaborator.
2. Đặt `main` làm default branch nếu dùng cho người xem; nhóm vẫn tạo feature từ `develop`.
3. Bật branch protection cho `main` và `develop`:
   - Require a pull request before merging.
   - Require ít nhất 1 approval.
   - Require conversation resolution.
   - Không cho force push hoặc delete branch.
4. Bật tự động xóa head branch sau khi merge.

## 5.4. Đưa dự án sang máy cá nhân

### Cách 1 — Qua GitHub, khuyến nghị cho source code

Sau khi Hoàng Anh hoàn thành bước push ở mục 5.3, trên máy cá nhân mở Terminal/PowerShell tại nơi muốn lưu project.

Linux/macOS:

```bash
cd "$HOME/Documents"
git clone https://github.com/hoanganh1601/cyberhub-manager.git
cd cyberhub-manager
git switch develop
```

Windows PowerShell:

```powershell
cd "$HOME\Documents"
git clone https://github.com/hoanganh1601/cyberhub-manager.git
cd cyberhub-manager
git switch develop
```

Đây là cách nên dùng hằng ngày: máy lab `git push`, máy cá nhân `git pull`; không chép đè cả thư mục qua lại.

### Cách 2 — Chuyển toàn bộ thư mục môn học

Cách này dùng khi cần mang cả các file Word gốc trong `BTL Python + SQL`, không chỉ repository CyberHub Manager.

Trên máy lab, tạo một file nén tại `/tmp`:

```bash
cd "/media/icnlab/Data/halinh/HoangAnh"
tar -czf "/tmp/BTL_Python_SQL.tar.gz" "BTL Python + SQL"
```

Sau đó chọn một trong các cách chuyển file `BTL_Python_SQL.tar.gz`:

- chép vào USB hoặc ổ lưu trữ cá nhân;
- tải qua công cụ quản lý file của máy lab;
- hoặc dùng `scp` từ máy cá nhân nếu máy lab cho phép SSH.

Ví dụ chạy trên máy cá nhân; thay `<username>` và `<lab-host>` bằng tài khoản/địa chỉ thật:

```bash
scp "<username>@<lab-host>:/tmp/BTL_Python_SQL.tar.gz" .
tar -xzf BTL_Python_SQL.tar.gz
```

PowerShell trên Windows cũng có thể dùng `scp` và `tar` nếu OpenSSH Client đã được cài:

```powershell
scp "<username>@<lab-host>:/tmp/BTL_Python_SQL.tar.gz" .
tar -xzf .\BTL_Python_SQL.tar.gz
```

Sau khi kiểm tra bản sao trên máy cá nhân mở được đầy đủ, có thể xóa file nén tạm trên máy lab:

```bash
rm "/tmp/BTL_Python_SQL.tar.gz"
```

Không đưa `.env`, MySQL credential, database dump thật hoặc virtual environment lên GitHub/USB/Drive. Trên máy cá nhân tạo `.env` mới từ `.env.example`.

## 5.5. Thiết lập lần đầu — Linh và Ngát

```bash
git clone https://github.com/hoanganh1601/cyberhub-manager.git
cd cyberhub-manager
git fetch origin
git switch develop
git pull --rebase origin develop
```

Mỗi người cấu hình đúng danh tính commit trên máy của mình:

```bash
git config user.name "Tên thành viên"
git config user.email "email-github@example.com"
```

Chỉ cấu hình trong repository, không thêm `--global` nếu máy được dùng chung.

## 5.6. Workflow hằng ngày

### Bước 1 — Nhận task

Trên Linear:

1. Chuyển issue từ `Backlog` sang `In Progress`.
2. Đọc dependency và acceptance criteria.
3. Nếu cần đổi schema/service contract/theme, báo owner trước khi code.

### Bước 2 — Cập nhật `develop` và tạo branch

```bash
git switch develop
git pull --rebase origin develop
git switch -c feature/LI-04-wallet-service
```

Định dạng branch:

- Tính năng: `feature/<LINEAR-ID>-<ten-ngan>`
- Sửa lỗi: `fix/<LINEAR-ID>-<ten-loi>`
- Tài liệu: `docs/<LINEAR-ID>-<ten-tai-lieu>`
- Việc kỹ thuật: `chore/<LINEAR-ID>-<ten-cong-viec>`

Dùng chữ thường, dấu gạch ngang, không dùng tiếng Việt có dấu hoặc khoảng trắng.

### Bước 3 — Commit nhỏ và rõ nghĩa

Trước khi commit:

```bash
git status
git diff
```

Chỉ stage file thuộc task:

```bash
git add src/cyberhub_manager/services/wallet_service.py
git add tests/unit/test_wallet_service.py
git commit -m "feat(wallet): add atomic top-up flow"
```

Không dùng `git add .` theo thói quen khi workspace có file không liên quan.

Quy ước commit:

| Prefix | Khi dùng | Ví dụ |
|---|---|---|
| `feat` | Thêm chức năng | `feat(session): add checkout preview` |
| `fix` | Sửa bug | `fix(wallet): reject zero top-up amount` |
| `test` | Thêm/sửa test | `test(session): cover 61-second billing` |
| `docs` | Chỉ đổi tài liệu | `docs(db): update data dictionary` |
| `refactor` | Đổi cấu trúc, không đổi hành vi | `refactor(ui): extract machine card` |
| `style` | Format/code style | `style: format repository modules` |
| `chore` | Cấu hình/công cụ | `chore: configure pytest` |

Commit message dùng tiếng Anh ngắn gọn; nội dung UI và tài liệu vẫn dùng tiếng Việt.

### Bước 4 — Đồng bộ trước khi mở PR

```bash
git fetch origin
git merge origin/develop
```

Nếu có conflict, xử lý ngay trên feature branch, chạy lại test rồi commit merge. Không sửa conflict trực tiếp trên GitHub nếu chưa chạy test local.

### Bước 5 — Push branch

```bash
git push -u origin feature/LI-04-wallet-service
```

Các lần sau chỉ cần:

```bash
git push
```

### Bước 6 — Tạo Pull Request

- Base: `develop`.
- Compare: feature branch của task.
- Tiêu đề: `[LI-04] Implement atomic wallet top-up`.
- Gắn link Linear issue.
- Chọn reviewer theo ownership.
- Không merge khi PR còn Draft, conflict hoặc test fail.

PR description dùng mẫu:

```markdown
## Linear

LI-04 — link issue

## Thay đổi

- ...
- ...

## Cách kiểm tra

1. ...
2. ...

## Evidence

- Test result:
- Screenshot/video nếu có UI:

## Checklist

- [ ] Đúng acceptance criteria
- [ ] Đã chạy test liên quan
- [ ] Không commit secret, database hoặc log
- [ ] Đã cập nhật tài liệu nếu contract thay đổi
```

### Bước 7 — Review và merge

Reviewer kiểm tra:

- Code có đúng scope issue không.
- Business rule/schema/theme có đúng tài liệu không.
- Có validation, error path và test phù hợp không.
- Có SQL injection, commit secret hoặc query UI trực tiếp không.
- Có làm hỏng module của thành viên khác không.

Tác giả xử lý từng comment và bấm `Resolve conversation` sau khi reviewer đồng ý. Dùng **Squash and merge** để mỗi issue tạo một commit rõ ràng trên `develop`, sau đó xóa feature branch.

### Bước 8 — Cập nhật local sau merge

```bash
git switch develop
git pull --rebase origin develop
git branch -d feature/LI-04-wallet-service
```

Chuyển Linear issue sang `Done` và đính kèm link PR.

## 5.7. Quy tắc tránh conflict giữa 3 người

1. Mỗi file có owner; cần sửa file của người khác phải báo trong Linear hoặc nhóm chat.
2. Không vừa rename vừa sửa lớn một file trong cùng PR nếu không cần thiết.
3. Chia PR theo vertical slice nhưng không trộn database, service và toàn bộ UI vào một PR khổng lồ.
4. `requirements.txt`, `pyproject.toml`, config, enum và DTO là file dùng chung; báo nhóm trước khi sửa.
5. Pull `develop` mỗi đầu ngày và trước khi mở PR.
6. Không format toàn project trong feature PR nhỏ vì sẽ tạo conflict không cần thiết.

Nếu hai người cần cùng một contract:

1. Linh chốt DTO/service interface trong một PR nhỏ.
2. Merge contract vào `develop` trước.
3. Ngát và Hoàng Anh cùng cập nhật branch của mình từ `develop`.
4. Hai bên triển khai độc lập theo contract đã merge.

## 5.8. Xử lý merge conflict

Trên feature branch:

```bash
git fetch origin
git merge origin/develop
git status
```

Mở từng file conflict, chọn nội dung đúng và xóa các marker:

```text
<<<<<<< HEAD
=======
>>>>>>> origin/develop
```

Sau đó:

```bash
git add <file-da-xu-ly>
git commit
git push
```

Nếu không chắc phần nào đúng, dừng và gọi owner của file review. Không dùng `git checkout --theirs`, `--ours` hoặc xóa file hàng loạt khi chưa hiểu thay đổi.

## 5.9. Workflow riêng cho Database

- Không sửa migration đã merge và đã được người khác chạy.
- Mỗi thay đổi schema tạo migration mới: `002_add_promotions.sql`, `003_add_invoice_indexes.sql`.
- Migration phải chạy theo thứ tự và có mô tả ảnh hưởng dữ liệu.
- Repository PR phụ thuộc migration phải ghi rõ trong description.
- Không commit `.env`, MySQL credential hoặc database dump chứa dữ liệu thật.
- Cả nhóm dùng MySQL 8.4 LTS; cấu hình local thống nhất bằng image `mysql:8.4` trong `docker-compose.yml`.
- Schema/migration dùng `InnoDB`, `utf8mb4`; tiền VND dùng `BIGINT` có dấu.
- Transaction cạnh tranh phải review `SELECT ... FOR UPDATE` và thứ tự khóa để hạn chế deadlock.
- Seed không chứa mật khẩu plain text hoặc dữ liệu cá nhân thật.
- Hoàng Anh review mọi SQL/schema PR; Linh review nếu thay đổi ảnh hưởng business rule.

## 5.10. Workflow riêng cho UI và service contract

- Ngát dựng UI bằng mock theo DTO từ LI-02; không tự đổi tên field trong UI.
- Khi service thật sẵn sàng, chỉ thay data source, không viết SQL trong event handler.
- Thay đổi public service operation phải cập nhật `02_CODEBASE_SKELETON.md` và báo Ngát.
- Thay đổi màu/font/component token phải cập nhật `03_UI_THEME.md` và được Ngát review.
- PR UI phải kèm screenshot hoặc video cho success và error state chính.

## 5.11. Release từ `develop` sang `main`

Cuối cycle hoặc trước demo:

1. Không còn issue blocker.
2. Automated test pass.
3. Manual checklist pass trên seed mới.
4. Hoàng Anh tạo PR `develop -> main` với tiêu đề `Release v0.1.0`.
5. Linh xác nhận business flow; Ngát xác nhận UI/demo; Hoàng Anh xác nhận DB/migration.
6. Merge PR, tạo tag và GitHub Release.

```bash
git switch main
git pull --rebase origin main
git tag -a v0.1.0 -m "CyberHub Manager MVP"
git push origin v0.1.0
```

Phiên bản gợi ý:

- `v0.1.0`: foundation/login.
- `v0.2.0`: customer/wallet.
- `v0.3.0`: session/checkout.
- `v1.0.0`: bản MVP dùng để nộp và demo.

## 5.12. Hotfix

Chỉ dùng khi lỗi nghiêm trọng đã có trên `main`:

```bash
git switch main
git pull --rebase origin main
git switch -c fix/BUG-ID-short-description
```

PR hotfix vào `main`, sau đó merge/cherry-pick cùng thay đổi về `develop` để hai branch không lệch nhau. Bug thông thường vẫn sửa từ `develop`.

## 5.13. Tuyệt đối không làm

- Không push trực tiếp `main`/`develop`.
- Không dùng `git push --force` trên branch dùng chung.
- Không commit `.env`, MySQL credential, database dump thật, password, API key, log hoặc virtual environment.
- Không dùng `git reset --hard` hoặc xóa branch của người khác để giải quyết conflict.
- Không merge PR đang fail test hoặc chưa resolve review.
- Không gộp nhiều Linear issue không liên quan trong một PR.
- Không thay đổi schema, service contract hoặc theme mà không báo owner.

## 5.14. Checklist nhanh mỗi ngày

```text
[ ] Linear issue đang In Progress
[ ] Branch tạo từ develop mới nhất
[ ] Chỉ sửa file trong scope
[ ] Commit nhỏ, message đúng convention
[ ] Đã merge develop mới nhất trước PR
[ ] Test local pass
[ ] PR có Linear link và evidence
[ ] Có reviewer đúng ownership
[ ] Sau merge đã cập nhật develop và đóng issue
```
