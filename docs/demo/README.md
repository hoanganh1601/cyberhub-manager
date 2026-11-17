# Chạy demo CyberHub

Từ thư mục gốc, cài dependency web nếu chưa có: `python -m pip install -e ".[web]"`.

## Web demo (không cần MySQL)

```powershell
$env:CYBERHUB_WEB_MODE="demo"
python -m cyberhub_manager.web --port 8000
```

Mở `http://127.0.0.1:8000`. Đăng nhập nhân viên: `admin01`, `quanly01`, `nhanvien01`, `bep01`, `thukho01` với mật khẩu demo `demo123`; khách dùng `http://127.0.0.1:8000/customer` và `nguyenvanan / demo123`. Dữ liệu demo lưu trong bộ nhớ và mất khi khởi động lại server. Kho demo được mô phỏng; nghiệm thu ledger/transaction kho cần MySQL thật.

## Demo trên MySQL

Xem [chuẩn bị schema và seed](../../README.md#chuẩn-bị-database-ứng-dụng-lần-đầu) và [cấu hình web MySQL](../guides/WEB_DEPLOYMENT.md). `demo.manager`, `demo.staff01`, `demo.kitchen`, `demo.inventory` dùng **mật khẩu do người chạy nhập lúc seed**, không dùng mật khẩu MySQL và không mặc định là `demo123`.

## Kịch bản và giới hạn

- [NG-09: kịch bản desktop P0 và ảnh bằng chứng](NG09_DEMO_UI.md) là tài liệu nghiệm thu lịch sử; script [chụp ảnh desktop](../../scripts/capture_ui_screens.py) vẫn tham chiếu tên file này.
- [Vận hành ca/két, bảo trì, nhập hàng](../features/OPERATIONS_PHASE7.md) chỉ chạy trên MySQL.
- [Đối tác game và quảng cáo](../features/COMMERCIAL_PARTNERS.md) có quy tắc đối soát riêng.
- [Dự báo](../features/FORECASTING_PHASE5.md) dùng dữ liệu mô phỏng có gắn `is_simulated=true` khi demo.

Không dùng tài khoản demo/mật khẩu demo cho triển khai thật. Kịch bản NG-09 không bao gồm các tính năng được thêm sau P0.
