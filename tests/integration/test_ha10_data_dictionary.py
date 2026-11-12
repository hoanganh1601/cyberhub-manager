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
                  "usage_sessions", "account_transactions", "invoices", "promotions", "management_audit", "customer_notification_reads", "machine_room_types", "loyalty_settings", "customer_avatars",
                  "menu_categories", "menu_items", "menu_item_images", "menu_item_changes",
                      "menu_orders", "menu_order_items", "inventory_ingredients",
                      "menu_item_recipes", "menu_order_recipe_snapshots", "inventory_movements",
                      "inventory_counts", "customer_notification_events",
                  "reward_catalog", "customer_vouchers", "voucher_events", "loyalty_point_grants",
                  "games", "game_prizes", "game_wallets", "game_sessions", "game_coin_ledger",
                  "ad_settings", "ad_creatives", "ad_reward_events"):
        assert f"### {table}" in content
    # 59 khóa ngoại trước kho + 14 khóa ngoại của kho, kiểm kê và thông báo đơn.
    assert content.count(" — 0..") == 73
    assert "password_hash" in content and "bcrypt" in content
