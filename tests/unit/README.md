# Phạm vi unit test

Chạy từ gốc repository: `python -m pytest tests/unit -q`. Unit test không cần MySQL; một số test giao diện cần môi trường có màn hình. `tests/conftest.py` sở hữu fixture Tk chung, dọn widget sau từng test và chỉ kết nối MySQL cho test mang marker `integration`.

Test được tổ chức theo module hoặc theo đợt đã bàn giao. Prefix `dot`, `ha`, `li`, `ng`, `p1` lưu dấu test hồi quy của từng đợt; tên tương tự không đồng nghĩa hành vi trùng. Khi thêm test, ưu tiên tên miền nghiệp vụ (`test_forecasting.py`, `test_commercial_service.py`, v.v.); giữ test cũ cho đến khi xác định cùng đầu vào, hành vi và kết quả mong đợi.

Chi tiết: [kiểm kê coverage và fixture](../../history/docs/testing/TEST_COVERAGE_AUDIT.md). Integration test dùng duy nhất `cyberhub_manager_test` theo [fixture bảo vệ](../conftest.py).
