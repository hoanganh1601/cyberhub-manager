# Mở rộng và kiểm thử

## Thêm một nghiệp vụ

1. Viết rõ actor, cửa hàng, điều kiện đầu vào, trạng thái, tiền/kho bị tác động và điều kiện rollback trong [luồng nghiệp vụ](../architecture/BUSINESS_FLOWS.md) hoặc tài liệu chuyên sâu phù hợp.
2. Nếu cần dữ liệu mới, thêm migration số tiếp theo trong `sql/`; giữ file cũ và checksum. Cập nhật [mô hình dữ liệu](../architecture/DATA_MODEL.md).
3. Đặt luật nghiệp vụ trong `services/` và quyền trong `domain/p1.py`; repository chỉ làm truy vấn. Nghiệp vụ có nhiều bước ghi phải dùng cùng `database/transaction.py`.
4. Ghép service ở `services/bootstrap.py`; web đăng ký route theo nhóm trong `web/`. Frontend chỉ hiển thị lỗi và trạng thái service trả về.
5. Thêm test cho trường hợp thành công, từ chối quyền, sai trạng thái, rollback và yêu cầu lặp. Với MySQL, kiểm tra cả phạm vi cửa hàng và transaction trên database test.

## Kiểm thử theo phạm vi

```powershell
python -m pytest tests/unit -q
python -m pytest tests/integration -q
```

Integration test dùng **chỉ** `cyberhub_manager_test`; cần MySQL test đang chạy và migration mới nhất. Đọc `tests/conftest.py` trước khi đổi cấu hình test. Test giao diện thủ công theo [checklist](../../tests/manual/CHECKLIST.md); báo cáo nghiệm thu cũ ở [history](../../history/README.md) chỉ là bằng chứng tại thời điểm viết.

Sau khi thay đổi tài liệu, kiểm tra các liên kết Markdown và `git diff --check`. Không chuyển `docs/knowledge-base/` vì loader RAG đọc đường dẫn này. Khi thay đổi nội dung tri thức, kiểm tra phân quyền, nguồn đã duyệt và câu trả lời của trợ lý.
