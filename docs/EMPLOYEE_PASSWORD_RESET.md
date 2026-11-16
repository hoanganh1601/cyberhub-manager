# Đặt lại mật khẩu nhân viên

## Luồng nghiệp vụ

1. Chỉ `ADMIN` mở **Nhân viên** và chọn **Đặt lại mật khẩu** cho tài khoản khác.
2. Admin nhập mật khẩu tạm hoặc dùng nút tạo ngẫu nhiên, rồi xác nhận.
3. Backend bcrypt mật khẩu, tăng `auth_version`, đánh dấu `must_change_password` và ghi audit `EMPLOYEE_PASSWORD_RESET` trong cùng transaction.
4. Mọi phiên đăng nhập cũ của tài khoản đích hết hiệu lực.
5. Người dùng đăng nhập bằng mật khẩu tạm và bắt buộc đổi mật khẩu trước khi dùng chức năng khác.
6. Đổi thành công ghi audit `EMPLOYEE_PASSWORD_CHANGE`, tăng lại `auth_version` và bỏ trạng thái mật khẩu tạm.

Mật khẩu rõ không được lưu trong database, response, log hay audit. Admin không thể xem lại mật khẩu cũ.

## Cập nhật MySQL

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe -c "from scripts.seed_db import run_seed; run_seed(expected_database='cyberhub_manager')"
```

Lệnh seed bổ sung hai tài khoản nếu chưa tồn tại:

- `demo.kitchen` — role `KITCHEN`
- `demo.inventory` — role `INVENTORY`

Hai tài khoản dùng mật khẩu demo bạn nhập khi chạy seed. Seed chạy lại không đổi mật khẩu của tài khoản đã tồn tại.

Ở chế độ demo web, có thể dùng `bep01` và `thukho01`, mật khẩu `demo123`.

## Quên mật khẩu Admin duy nhất

Nếu không còn Admin nào đăng nhập được, chạy tại máy chủ ứng dụng:

```powershell
.\.venv\Scripts\python.exe scripts/reset_admin_password.py --database cyberhub_manager --username admin01
```

Lệnh chỉ khôi phục tài khoản đang là `ADMIN` và `ACTIVE`; không tạo Admin mới,
không nâng quyền tài khoản thường. Mật khẩu được nhập ẩn, mọi phiên cũ bị thu hồi,
người dùng phải đổi mật khẩu tạm sau khi đăng nhập và sự kiện được ghi audit.
