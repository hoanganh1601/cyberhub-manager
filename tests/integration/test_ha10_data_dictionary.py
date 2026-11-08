"""HA-10 — docs/diagrams/data_dictionary.md phải khớp schema sau migration.

Đổi schema (thêm cột, ràng buộc, index) mà quên chạy `python scripts/gen_data_dictionary.py`
thì test này fail; cột mới chưa có mô tả cũng fail.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen_data_dictionary.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("gen_data_dictionary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_data_dictionary_matches_migrated_schema(db_conn):
    script = _load_script()
    expected = script.build_markdown(db_conn)
    actual = script.OUTPUT.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert actual == expected, "Chạy lại: python scripts/gen_data_dictionary.py"


def test_every_business_table_and_foreign_key_is_documented(db_conn):
    content = _load_script().build_markdown(db_conn)

    for table in ("stores", "employees", "customers", "accounts", "machines",
                  "usage_sessions", "account_transactions", "invoices", "promotions", "management_audit"):
        assert f"### {table}" in content
    assert content.count(" — 0..") == 19  # mỗi khóa ngoại một dòng trong bảng cardinality, gồm P1
    assert "password_hash" in content and "bcrypt" in content
