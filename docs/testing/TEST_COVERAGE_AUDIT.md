# Kiểm kê phạm vi unit và integration test

Nguồn: `tests/`, `tests/conftest.py`, `pyproject.toml`, baseline ngày 17/11/2026 tại commit `960beb1a0a0ffa4b4e517f6cc75f9e1ef1b6300f` (Python 3.13.14, Windows).

## Phạm vi

| Nhóm | File Python | Điều kiện chạy | Kết quả baseline |
|---|---:|---|---|
| `tests/unit` | 83 (gồm `__init__.py`) | Không cần MySQL; test Tk cần màn hình | **1.887 passed, 5 skipped** / 493,52 giây |
| `tests/integration` | 28 (gồm `__init__.py`) | Chỉ `cyberhub_manager_test` | **NOT VERIFIED**: Docker/MySQL không chạy |
| `tests/browser` | 2 script `.cjs` | Browser và server phù hợp | Không chạy trong baseline pytest |
| `tests/manual` | 1 checklist | Người nghiệm thu, môi trường riêng | Chưa ký nghiệm thu |

Lệnh đầy đủ `python -m pytest -q`: **1.887 passed, 5 skipped, 247 errors** / 524,55 giây. 247 lỗi phát sinh ở bước setup integration, đều báo `MySQL test database is unavailable`; không phải kết quả kiểm thử nghiệp vụ thất bại. Năm skip do Windows/user không hỗ trợ symlink. Không kết luận integration pass khi thiếu MySQL.

`pyproject.toml` dùng `testpaths=["tests"]`, `pythonpath=["src"]`, `-ra --strict-markers`. `tests/conftest.py` tự gắn marker `integration`, ép `MYSQL_DATABASE=cyberhub_manager_test`, kiểm tra `SELECT DATABASE()` trước khi cấp kết nối; `db_conn` rollback sau test. Fixture `tk_root` dùng chung root và dọn widget. Không di chuyển fixture hoặc thay đổi guard.

Sau chỉnh tài liệu và index test: `python -m pytest tests/unit -q` cho **1.887 passed, 5 skipped** / 367,14 giây. `python -m pytest -q` cho **1.887 passed, 5 skipped, 247 errors** / 379,50 giây; 247 lỗi vẫn xuất hiện trong setup integration với thông báo MySQL test unavailable. Số lượng và trạng thái tương đương baseline. Coverage % chưa đo.

## Phân loại test theo hợp đồng

| Hợp đồng | Ví dụ file hiện có | Cần giữ |
|---|---|---|
| Nghiệp vụ service/domain | `test_session_service.py`, `test_wallet_service.py`, `test_operational_domains.py` | Điều kiện thành công, validation, rollback, phân quyền và lỗi kết nối |
| Web và quyền truy cập | `test_web_app.py`, `test_commercial_web.py`, `test_forecasting_web.py` | Route, dữ liệu phản hồi và từ chối sai quyền |
| UI desktop/mock | `test_ui_foundation.py`, `test_ng03_machines.py`, `test_ng08_integration.py` | Hành vi giao diện và hồi quy của từng đợt |
| AI/RAG | `test_ai_*.py` | Retrieval, quyền truy cập và câu trả lời an toàn |
| Repository/MySQL | `tests/integration/test_*` | Constraint, transaction và query trên DB test |

Trong `tests/unit` có 24 tên file gắn mã đợt và 58 tên theo chức năng (không tính `__init__.py`). Ba tên hàm test lặp ở nhiều file đã đối chiếu: bộ lọc máy khác bộ lọc khách; chặn máy khác cơ sở ở machine service khác session service; lỗi DB trong report service khác checkout. **Không có test nào được chứng minh trùng cả đầu vào, hành vi và kết quả, nên không xóa/gộp test.** Các `FakeAuthRepository`, `FakeDatabase`, `make_actor` cùng tên là helper riêng theo hợp đồng từng service; gom chung ngay có nguy cơ thay đổi fixture.

Các file dài đáng xem xét sau khi có baseline integration: `test_session_service.py` (1.403 dòng), `test_ui_foundation.py` (1.233), `test_report_service.py` (804). Chia file chỉ khi xác nhận cùng fixture và collection trước/sau; tránh đổi tên chỉ vì prefix đợt. `pytest --cov` có trong môi trường nhưng chưa đo coverage trước/sau trong lượt này; **coverage %: NOT VERIFIED**.

## Lệnh nghiệm thu khi MySQL sẵn sàng

```powershell
python -m pytest tests/unit -q
python -m pytest -q
```

Trước lệnh thứ hai xác minh Docker, target `cyberhub_manager_test` và migration bằng các kiểm tra chỉ đọc. Nếu test DB thiếu schema, chuẩn bị DB theo [README](../../README.md) trong một bước riêng; không chạy `prepare_test_db.py` trên database ứng dụng.
