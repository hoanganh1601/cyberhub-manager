"""POS rule evaluation and immutable order price at placement."""

from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.domain.menu import MenuOrderLine
from cyberhub_manager.services.pos_pricing import price_order
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services


NOW = datetime(2026, 11, 13, 8, tzinfo=timezone.utc)


def test_best_single_rule_and_tie_priority():
    lines = [MenuOrderLine(1, "Coca", 10_000, 3)]
    rules = [dict(id=1, code="DRINK", kind="PLAY_DRINK", item_id=1,
                  value=5000, minimum_tier=None),
             dict(id=2, code="THREE", kind="BOGO", item_id=1,
                  value=1, minimum_tier=None),
             dict(id=3, code="VIP", kind="TIER_PERCENT", item_id=None,
                  value=10, minimum_tier="GOLD")]
    priced = price_order(lines, rules, "GOLD")
    assert priced["promotion_code"] == "DRINK"
    assert priced["discount_amount"] == 15_000
    assert priced["final_amount"] == 15_000
    rules[0]["value"] = 3_333
    assert price_order(lines, rules, "BRONZE")["promotion_code"] == "THREE"


def test_demo_pricing_snapshot_survives_rule_change_and_manager_can_edit():
    bundle = build_mock_services(p1=True, clock=MockClock(NOW))
    customer = bundle.portal.login("lethibinh", "demo123")
    manager = bundle.auth.login("quanly01", "demo123")
    staff = bundle.auth.login("nhanvien01", "demo123")
    coca = next(i for page in bundle.menu.portal_menu(customer)["pages"]
                for group in page["categories"] for i in group["items"] if i.name == "Coca")
    order = bundle.menu.place_order(customer, [{"item_id": coca.id, "quantity": 3}])
    assert order.discount_amount == 15_000
    assert order.promotion_code == "DEMO_NUOC_5000"
    snapshot = bundle.menu._repo.order_pricing[order.id]["snapshot"]
    assert snapshot["final_amount"] == 15_000
    promo = next(p for p in bundle.menu.list_promotions(manager) if p["code"] == "DEMO_NUOC_5000")
    with pytest.raises(PermissionDeniedError):
        bundle.menu.save_promotion(staff, promotion_id=promo["id"], code=promo["code"],
            kind=promo["kind"], item_id=promo["item_id"], value=1000,
            starts_at=NOW, ends_at=NOW+timedelta(days=1), is_active=True)
    bundle.menu.save_promotion(manager, promotion_id=promo["id"], code=promo["code"],
        kind=promo["kind"], item_id=promo["item_id"], value=1000,
        starts_at=NOW, ends_at=NOW+timedelta(days=1), is_active=True)
    assert bundle.menu._repo.get_order(None, order.id).discount_amount == 15_000
    assert bundle.menu._repo.order_pricing[order.id]["snapshot"] == snapshot
