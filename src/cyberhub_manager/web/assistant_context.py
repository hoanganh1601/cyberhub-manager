"""Trusted dynamic context assembly for AI phases 5B and 5C.

This module calls application services only.  It never exposes a database
connection, repository, SQL capability or business action to the model.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import json

from cyberhub_manager.ai.models import AIAccessContext, DynamicAssistantSource
from cyberhub_manager.domain.exceptions import PermissionDeniedError, ValidationError

VN = timezone(timedelta(hours=7))
_MODES = frozenset({"knowledge", "analytics", "personalized"})


def validate_mode(mode, access: AIAccessContext) -> str:
    if mode is None:
        return "knowledge"
    if not isinstance(mode, str) or mode not in _MODES:
        raise ValidationError(field_errors={"mode": "Chế độ trợ lý không hợp lệ"})
    if mode == "analytics" and access.role not in ("MANAGER", "ADMIN"):
        raise PermissionDeniedError()
    if mode == "personalized" and access.role != "CUSTOMER":
        raise PermissionDeniedError()
    return mode


def _primitive(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return _primitive(asdict(value))
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("unsupported assistant snapshot value")


def _content(value) -> str:
    return json.dumps(_primitive(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def analytics_sources(*, services, actor, access, days: int) -> tuple[DynamicAssistantSource, ...]:
    if type(days) is not int or days not in (7, 30, 90):
        raise ValidationError(field_errors={"days": "Chọn kỳ 7, 30 hoặc 90 ngày"})
    today = datetime.now(VN).date()
    first = today - timedelta(days=days - 1)
    snapshot = services.reports.assistant_analytics(actor, access.store_ids, first, today)
    compact = {
        "date_from": snapshot["date_from"], "date_to": snapshot["date_to"],
        "timezone": snapshot["timezone"], "total_revenue": snapshot["total_revenue"],
        "invoice_count": snapshot["invoice_count"], "stores": [],
    }
    for store in snapshot["stores"]:
        compact["stores"].append({
            key: store[key] for key in (
                "store_id", "store_code", "store_name", "total_revenue",
                "invoice_count", "average_daily_revenue", "previous_total_revenue",
                "change_percent", "low_days", "top_machines", "peak_hours",
            )
        })
    return (DynamicAssistantSource(
        source_id="analytics-live-snapshot",
        title="Số liệu vận hành đã lọc theo quyền",
        section=f"Kỳ {days} ngày · {len(compact['stores'])} cơ sở",
        content=_content(compact), source="runtime/analytics-live.md",
        audience=("MANAGER", "ADMIN"), store_ids=access.store_ids,
        generated_at=datetime.now(timezone.utc),
    ),)


def _menu_items(menu) -> list[dict]:
    items = []
    for page in menu.get("pages", []):
        page_name = _primitive(page.get("page"))
        for group in page.get("categories", []):
            category = group.get("category")
            category_name = getattr(category, "name", "")
            for item in group.get("items", []):
                if getattr(item, "is_visible", False) and getattr(item, "is_available", False):
                    items.append({
                        "page": page_name, "category": category_name,
                        "name": item.name, "description": item.description,
                        "price": item.price,
                    })
    return items[:40]


def personalized_sources(*, services, customer, access, store_id=None) -> tuple[DynamicAssistantSource, ...]:
    if store_id is not None and (type(store_id) is not int or store_id <= 0):
        raise ValidationError(field_errors={"store_id": "Cơ sở không hợp lệ"})
    dashboard = services.portal.dashboard(customer, 30, store_id)
    selected = dashboard["store_id"]
    menu = services.menu.portal_menu(customer, selected)
    vouchers = services.vouchers.portal_vouchers(customer)
    game = services.games.portal_game(customer)
    ads = services.ads.portal_ads(customer)
    generated = dashboard["as_of"]
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)

    membership = {
        "store_id": selected,
        "store_name": menu["store_name"],
        "member": dashboard["member"],
        "last_30_days": dashboard["totals"],
        "promotions": [
            {
                "name": offer.name, "minimum_amount": offer.minimum_amount,
                "bonus_percent": offer.bonus_percent, "minimum_tier": offer.minimum_tier,
                "minimum_points": offer.minimum_points, "ends_at": offer.ends_at,
                "personal": offer.target_customer_id is not None,
            }
            for offer in dashboard["promotions"]
        ],
    }
    voucher_items = [
        {
            "name": item["name"], "reward_type": item["reward_type"],
            "value": item["value"], "minimum_order": item["min_order_amount"],
            "store_name": item["store_name"], "state": item["state"],
            "expires_at": item["expires_at"],
        }
        for item in vouchers["items"] if _primitive(item["state"]) == "ACTIVE"
    ]
    rewards = {
        "active_vouchers": voucher_items,
        "game_wallet": {"coins": game["wallet"]["balance"], "locked": game["wallet"]["is_locked"]},
        "spins_left": game["spins_left"], "bonus_spins": game["bonus_spins"],
        "exchange_catalog": game["shop"],
        "rewarded_ads": {
            "enabled": ads["enabled"], "remaining_today": ads["remaining"],
            "reward_type": ads["reward_type"], "reward_amount": ads["reward_amount"],
        },
    }
    common = dict(audience=("CUSTOMER",), store_ids=(), generated_at=generated)
    return (
        DynamicAssistantSource(
            source_id="personalized-membership", title="Hạng, điểm và ưu đãi của bạn",
            section="Snapshot tài khoản hiện tại", content=_content(membership),
            source="runtime/personalized-membership.md", **common,
        ),
        DynamicAssistantSource(
            source_id="personalized-menu", title="Menu đang phục vụ",
            section=menu["store_name"], content=_content({
                "store_id": selected, "store_name": menu["store_name"],
                "can_order_now": menu["can_order"], "available_items": _menu_items(menu),
            }), source="runtime/personalized-menu.md", **common,
        ),
        DynamicAssistantSource(
            source_id="personalized-rewards", title="Voucher, xu và lượt thưởng của bạn",
            section="Quyền lợi hiện có", content=_content(rewards),
            source="runtime/personalized-rewards.md", **common,
        ),
    )
