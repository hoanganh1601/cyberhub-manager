# Login desktop theo Stitch

Chạy từ thư mục gốc `cyberhub-manager`, với virtual environment đã kích hoạt:

```powershell
python -m cyberhub_manager.app --mock
```

Tài khoản demo: `quanly01 / demo123` (Manager), `nhanvien01 / demo123` (Staff).
Đăng nhập thành công mở App Shell với đầy đủ các màn đã merge trên develop.
Đăng xuất quay về Login và xóa session UI. Demo dùng dữ liệu trong bộ nhớ, không ghi MySQL.

Mở trực tiếp Login hoặc bắt đầu với tiếng Anh:

```powershell
python -m cyberhub_manager.ui.login_view
python -m cyberhub_manager.app --mock --lang en
```

Chạy với backend MySQL thật (cấu hình `.env` và chuẩn bị database theo README):

```powershell
python -m cyberhub_manager.app
```

Tài khoản demo ở trên chỉ dành cho mock. Chế độ thật dùng tài khoản nhân viên trong DB;
mọi service được tiêm `actor_provider` lấy session sau đăng nhập. Lỗi kết nối hiển thị
trên form để thử lại; ứng dụng không tự chuyển sang dữ liệu mẫu khi kết nối thật lỗi.

## Thiết kế

HTML Stitch người dùng cung cấp được giữ tại `ui-reference/login-stitch/code.html`
để đối chiếu. Đây là tài liệu tham chiếu; ứng dụng desktop không chạy HTML này.

Ảnh chụp từ ứng dụng desktop: [VI](screenshots/login-stitch/login-vi.png),
[EN](screenshots/login-stitch/login-en.png),
[lỗi đăng nhập](screenshots/login-stitch/login-auth-error.png),
[1100×650](screenshots/login-stitch/login-1100x650.png).

- Canvas gốc 1280×720, tỷ lệ hai cột 55/45, form rộng 384px. Cho phép co tới 1100×650.
- Nền radial glow, lưới 40px và đường mạch điện được vẽ local; không dùng webview.
- Logo trong suốt dùng `ui/assets/cyberhub_logo_dark.png` có sẵn, hiển thị trực tiếp
  trên nền mạch điện với bề rộng 344px tại kích thước chuẩn; không có khung nền hoặc viền.
- Inter và Space Grotesk được đóng gói trong `ui/assets/fonts`, kèm giấy phép OFL.
- Icon user/lock/eye/arrow/alert/spinner được vẽ bằng Pillow ở độ phân giải cao.
  Không cần tải icon, cài font thủ công hay có Internet khi chạy.
- Token màu/font nằm trong `ui/theme.py`; artwork trong `ui/login_art.py`;
  widget và hành vi form trong `ui/login_view.py`; nối ứng dụng trong `app.py`.

## Kiểm tra bằng tay

1. Ở 1280×720 và 1100×650: không có text, footer hoặc thông báo lỗi bị cắt.
2. Để trống rồi nhấn Đăng nhập: thấy lỗi dưới mỗi trường, không gọi service.
3. Sai mật khẩu: giữ username, xóa và che password, cho phép thử lại.
4. Nhấn icon mắt, Enter để submit, Tab/Shift+Tab để di chuyển focus.
5. Chuyển VI/EN: nội dung và lỗi được dịch, dữ liệu đã nhập vẫn giữ nguyên.
6. Trong khi đăng nhập: có spinner, nút và input bị khóa, không gửi yêu cầu trùng.
7. Đăng nhập Staff: không thấy menu Quản lý máy; đăng xuất quay lại Login trắng mật khẩu.

## Kiểm tra tự động

```powershell
python -m pytest tests/unit/test_login_view.py -q
```

Chụp bốn trạng thái (VI, EN, sai thông tin, cửa sổ nhỏ):

```powershell
python scripts/capture_login_preview.py --output-dir "$env:TEMP\cyberhub-login-preview"
```

Script mở cửa sổ demo trong vài giây, chụp vùng ứng dụng rồi đóng lại.
