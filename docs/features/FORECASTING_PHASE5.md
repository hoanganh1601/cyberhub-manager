# Dự báo doanh thu và lượng khách

Module này chạy offline, độc lập với chatbot Gemini và không cần API key. Nó
không phụ thuộc phần đối tác game/quảng cáo nên có thể phát triển và merge trên
nhánh riêng.

## Phạm vi bản đầu

- Dự báo doanh thu, lượng khách và số lượt mở máy trong 7 hoặc 30 ngày.
- Dữ liệu demo 90–365 ngày, mặc định 180 ngày và có `is_simulated: true`.
- Dữ liệu thật được tổng hợp từ MySQL theo ngày, không đọc tên hay số điện thoại.
- Feature ngày trong tuần, cuối tuần, ngày lễ, xu hướng và lag 1/7/14 ngày.
- Chia train/test theo thời gian, không shuffle.
- So sánh seasonal baseline, Linear Regression, Random Forest và Gradient Boosting.
- Báo cáo MAE/MAPE cho từng mô hình và từng mục tiêu.
- Thống kê riêng máy thường, VIP, Couple và Siêu VIP.

## Cài dependency ML

Trong PowerShell tại thư mục dự án:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[forecast]"
```

Dependency ML là tùy chọn nên web chính vẫn có thể cài/chạy mà không cần
scikit-learn.

## Chạy với dữ liệu demo

```powershell
.\.venv\Scripts\python.exe -m scripts.run_forecasting --source demo --history-days 180
```

Kết quả được tạo trong `runtime/forecasting/`:

- `dataset.json`: dữ liệu huấn luyện, luôn ghi rõ `is_simulated`.
- `forecast_model.pkl`: model tốt nhất của từng mục tiêu.
- `evaluation.json`: time split, MAE/MAPE và model được chọn.
- `forecast_7_days.json`: dự báo 7 ngày.
- `forecast_30_days.json`: dự báo 30 ngày.

Thư mục `runtime/` đã nằm trong `.gitignore`; không commit model hoặc dữ liệu
sinh ra vào Git.

## Kiểm tra trên giao diện web

Sau khi đã chạy lệnh tạo dự báo, khởi động web như bình thường:

```powershell
python -m cyberhub_manager.web --port 8000
```

Đăng nhập bằng tài khoản `ADMIN` hoặc `MANAGER`, sau đó chọn **Phân tích & Dự báo** ở
menu bên trái. Trang này cung cấp:

- Chuyển nhanh dự báo 7 ngày và 30 ngày.
- Biểu đồ doanh thu và lượng khách.
- Tổng doanh thu, khách và lượt mở máy dự kiến.
- So sánh Thường, VIP, Couple và Siêu VIP.
- MAE/MAPE của model được chọn.
- Gợi ý mục tiêu doanh thu, ngày tăng cường nhân sự và lượng đồ ăn/uống tham khảo.

`STAFF`, `KITCHEN` và `INVENTORY` không được nhìn thấy menu và API cũng trả
`403` nếu gọi trực tiếp. Web chỉ đọc kết quả đã xuất; việc huấn luyện không chạy
trong HTTP request để tránh làm treo server.

Mặc định web đọc `runtime/forecasting`. Có thể đặt vị trí khác trong `.env`:

```dotenv
CYBERHUB_FORECAST_DIR=D:/private/cyberhub-runtime/forecasting
```

## Chạy với MySQL thật

MySQL phải hoạt động và `.env` phải chứa cấu hình kết nối đúng. Ví dụ dự báo cho
cơ sở có ID `1`:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_forecasting --source mysql --store-id 1 --history-days 180
```

Nếu cơ sở chưa có đủ lịch sử, nên dùng demo cho phần trình bày BTL. Không trộn
dữ liệu mô phỏng vào bảng nghiệp vụ thật. Khi đã có đủ dữ liệu, chạy lại bằng
`--source mysql`; file kết quả sẽ có `is_simulated: false`.

Kết quả MySQL mặc định được tách theo cơ sở tại
`runtime/forecasting/store-<store_id>/`. Khi quản trị viên chuyển cơ sở, API chỉ
đọc bộ dự báo của cơ sở tương ứng. Tham số `--output-dir` vẫn có thể được dùng
để chọn vị trí khác khi cần vận hành riêng.

## Cách đọc chỉ số

- **MAE**: sai lệch tuyệt đối trung bình; càng thấp càng tốt. Với doanh thu, đơn
  vị là VND. Với lượng khách/lượt mở máy, đơn vị là lượt.
- **MAPE**: sai số phần trăm trung bình; càng thấp càng tốt. Ngày có giá trị thực
  bằng 0 được bỏ khỏi MAPE để tránh chia cho 0 nhưng vẫn được tính trong MAE.
- Model tốt nhất được chọn riêng cho từng mục tiêu theo MAE trên tập test cuối
  chuỗi thời gian.

Kết quả từ dữ liệu demo chỉ chứng minh luồng kỹ thuật và cách đánh giá, không
được trình bày như dự báo kinh doanh từ dữ liệu thật.
