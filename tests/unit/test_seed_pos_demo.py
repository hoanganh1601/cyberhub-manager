"""Dữ liệu mẫu POS (scripts/seed_pos_demo.py): kiểm tra tĩnh bảng dữ liệu và rào chắn, không cần MySQL.

Việc nạp thật được kiểm tra thủ công trên cyberhub_manager_migration_test (xem docs/POS_ACCEPTANCE.md).
"""

import importlib.util
from collections import Counter
from pathlib import Path
from uuid import UUID

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_pos_demo.py"


@pytest.fixture(scope="module")
def seed():
    spec = importlib.util.spec_from_file_location("seed_pos_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_is_internally_consistent(seed):
    seed.validate_catalog()


@pytest.mark.parametrize("mutate,message", [
    (lambda s: setattr(s, "ITEMS", s.ITEMS + (("Lạ", "Không có nhóm", 10_000, "", {"Lon Coca": 1}, 9),)), "không hợp lệ"),
    (lambda s: setattr(s, "ITEMS", s.ITEMS + (("Lạ", "Cà phê", 10_000, "", {"Không có": 1}, 9),)), "không hợp lệ"),
    (lambda s: setattr(s, "ITEMS", s.ITEMS + (("Lạ", "Cà phê", 500, "", {"Lon Coca": 1}, 9),)), "không hợp lệ"),
    (lambda s: setattr(s, "ORDERS", s.ORDERS + ((" u", "PC", (("Coca", 1),), "NEW", "không có tiền tố"),)), "không hợp lệ"),
    (lambda s: setattr(s, "ORDERS", s.ORDERS + ((" u", "PC", (("Món lạ", 1),), "NEW", "DEMO: x"),)), "không hợp lệ"),
])
def test_validation_rejects_broken_catalog(seed, monkeypatch, mutate, message):
    monkeypatch.setattr(seed, "ITEMS", seed.ITEMS)
    monkeypatch.setattr(seed, "ORDERS", seed.ORDERS)
    mutate(seed)
    with pytest.raises(ValueError, match=message):
        seed.validate_catalog()


def test_new_accounts_cover_the_two_dedicated_roles(seed):
    assert {role for *_, role in seed.POS_EMPLOYEES} == {"KITCHEN", "INVENTORY"}
    usernames = [u for _, _, u, _ in seed.POS_EMPLOYEES]
    codes = [c for c, *_ in seed.POS_EMPLOYEES]
    assert len(set(usernames)) == len(usernames) and not set(codes) & {"DEMO_EMP_01", "DEMO_EMP_02", "DEMO_EMP_03"}


def test_orders_cover_every_state_the_acceptance_lists_need(seed):
    finals = {final for *_, final, _ in seed.ORDERS}
    assert finals == {"NEW", "PREPARING", "SERVED", "PAID", "CANCELLED", "PAID_REVERSAL_PENDING", "REFUNDED"}
    # Mỗi khách chỉ dùng một máy; chỉ mỗi khách nhiều nhất 3 đơn NEW (giới hạn chống spam).
    machines = {}
    for username, machine, *_ in seed.ORDERS:
        assert machines.setdefault(username, machine) == machine
    assert max(Counter(u for u, *_, final, _ in seed.ORDERS if final == "NEW").values()) <= 3
    assert all(m.startswith("DEMO_PC_") and u.startswith("demo.customer") for u, m, *_ in seed.ORDERS)


def test_stock_scenarios_are_present_and_orders_fit_opening_stock(seed):
    reorder = {name: point for name, _, point, _ in seed.INGREDIENTS}
    opening = {name: qty for name, _, _, qty in seed.INGREDIENTS}
    low = [n for n in opening if 0 < opening[n] <= reorder[n]]
    empty = [n for n in opening if opening[n] == 0]
    assert low and empty  # có cả "sắp hết" lẫn "hết hàng" để thử cảnh báo

    recipes = {name: recipe for name, _, _, _, recipe, _ in seed.ITEMS}
    needed = Counter()
    for *_, lines, final, _ in seed.ORDERS:
        for item, qty in lines:
            for ingredient, per_unit in recipes[item].items():
                needed[ingredient] += per_unit * qty
    assert all(needed[n] <= opening[n] for n in needed), "đơn mẫu không được vượt tồn đầu kỳ"
    out_of_stock_items = {i for i, r in recipes.items() if set(r) & set(empty)}
    assert out_of_stock_items and not any(item in out_of_stock_items for *_, lines, _, _ in seed.ORDERS
                                          for item, _ in lines)


def test_request_ids_are_valid_uuid4_and_stable(seed):
    first = seed.deterministic_request_id("demo-opening", "DEMO_STORE_01", "Sữa đặc")
    assert first == seed.deterministic_request_id("demo-opening", "DEMO_STORE_01", "Sữa đặc")
    assert first != seed.deterministic_request_id("demo-opening", "DEMO_STORE_01", "Mì gói")
    assert UUID(first).version == 4


def test_refuses_the_automated_test_database(seed):
    with pytest.raises(SystemExit, match="database test"):
        seed.check_database("cyberhub_manager_test")
    seed.check_database("cyberhub_manager")
    seed.check_database("cyberhub_manager_migration_test")


def test_every_order_note_is_marked_as_demo(seed):
    assert all(note.startswith(seed.ORDER_NOTE_PREFIX) for *_, note in seed.ORDERS)
