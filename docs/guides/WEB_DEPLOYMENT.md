# Vận hành web

Để chạy trên máy cá nhân, bắt đầu từ [Quickstart](QUICKSTART.md). File `render.yaml` mô tả bản **demo** trên Render; `railway.json` dùng `Dockerfile.web` để dựng image. Đây là cấu hình trong repository, không phải xác nhận giá, hạn mức hoặc tình trạng gói của nhà cung cấp; kiểm tra lại trước khi triển khai bên ngoài.

## Chế độ và dữ liệu

| Chế độ | Biến | Dữ liệu |
|---|---|---|
| Demo | `CYBERHUB_WEB_MODE=demo` | Trong bộ nhớ, theo phiên, mất khi restart. |
| MySQL | `CYBERHUB_WEB_MODE=mysql` | Dùng kết nối `MYSQL_*` trong `.env`/môi trường; cần migration đã chạy. |

MySQL mode bắt buộc `CYBERHUB_SECRET_KEY` ổn định, ít nhất 32 ký tự. Dùng `CYBERHUB_COOKIE_SECURE=true` khi phục vụ qua HTTPS; nếu sau reverse proxy, cấu hình `CYBERHUB_TRUST_PROXY` phù hợp. Không đưa `.env`, mật khẩu MySQL hoặc API key vào Git.

## Cấu hình deploy hiện có

- `render.yaml`: build `.[web]`, chạy Gunicorn, health check `/healthz`, đặt mode demo và sinh secret cho web.
- `Dockerfile.web`: cài `.[web]`, chạy Gunicorn bằng user không phải root. `railway.json` trỏ Dockerfile này và health check `/healthz`.
- `scripts/init_db.py`: áp dụng migration theo thứ tự; chạy trên MySQL đúng đích trước khi bật mode MySQL. Không tự seed hay chạy migration vào production từ request web.

**Giới hạn cần biết:** image trong `Dockerfile.web` hiện chỉ copy `src/`, `scripts/` và `sql/`, chưa copy `docs/knowledge-base/`. Nếu bật trợ lý RAG trong container, cần đóng gói hoặc mount kho tri thức đã duyệt và đặt `CYBERHUB_KNOWLEDGE_ROOT` tới vị trí đó. Dự báo cũng cần chạy job offline và cung cấp `runtime/forecasting/` hoặc `CYBERHUB_FORECAST_DIR`; web chỉ đọc artifact đã tạo.

Sau deploy, kiểm tra `/healthz`, đăng nhập, một luồng đọc và một luồng ghi phù hợp với mode, rồi xác nhận dữ liệu sau restart. Với MySQL, kiểm tra database đích và quyền người dùng DB trước khi chạy migration/seed.

Hướng dẫn nền tảng chi tiết của đợt trước được giữ tại [tư liệu lịch sử](../../history/docs/guides/WEB_DEPLOYMENT.md); bước trên dashboard, giá và hạn mức có thể thay đổi.
