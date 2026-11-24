# Phạm vi unit test

Chạy từ gốc repository: `python -m pytest tests/unit -q`. Unit test không cần MySQL; một số test giao diện cần môi trường có màn hình. `tests/conftest.py` sở hữu fixture Tk chung, dọn widget sau từng test và chỉ kết nối MySQL cho test mang marker `integration`.

Toàn bộ file test trong `tests/unit/` và `tests/integration/` được đặt tên thống nhất theo phân hệ nghiệp vụ (ví dụ: `test_auth_repository.py`, `test_billing_repositories.py`, `test_menu_service.py`, `test_voucher_web.py`, `test_desktop_checkout_dialog.py`, `test_management_and_portal_business.py`).

Integration test dùng duy nhất `cyberhub_manager_test` theo [fixture bảo vệ](../conftest.py).
