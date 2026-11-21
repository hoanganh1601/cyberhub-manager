"""Pure, deterministic non-stacking POS promotion evaluation."""

from __future__ import annotations

from cyberhub_manager.domain.loyalty import TIERS


PRIORITY = {"BOGO": 3, "PLAY_DRINK": 2, "TIER_PERCENT": 1}


def price_order(lines, promotions, tier):
    gross = sum(line.amount for line in lines)
    tier = str(tier)
    candidates = []
    for promotion in promotions:
        kind = promotion["kind"]
        amount = 0
        if kind == "BOGO":
            amount = sum(line.unit_price * (line.quantity // 3)
                         for line in lines if line.item_id == promotion["item_id"])
        elif kind == "PLAY_DRINK":
            amount = sum(min(line.unit_price, promotion["value"]) * line.quantity
                         for line in lines if line.item_id == promotion["item_id"])
        elif kind == "TIER_PERCENT" and tier in TIERS and promotion["minimum_tier"] in TIERS:
            if TIERS.index(tier) >= TIERS.index(promotion["minimum_tier"]):
                amount = gross * promotion["value"] // 100
        if amount > 0:
            candidates.append((min(gross, amount), PRIORITY[kind], -promotion["id"], promotion))
    winner = max(candidates, default=None)
    selected = winner[3] if winner else None
    discount = winner[0] if winner else 0
    return dict(promotion_id=selected["id"] if selected else None,
                promotion_code=selected["code"] if selected else None,
                promotion_kind=selected["kind"] if selected else None,
                discount_amount=discount, final_amount=gross-discount,
                snapshot={"gross_amount":gross, "discount_amount":discount,
                          "final_amount":gross-discount, "member_tier":tier,
                          "rule": dict(selected) if selected else None,
                          "lines":[dict(item_id=line.item_id, name=line.item_name,
                                        unit_price=line.unit_price, quantity=line.quantity)
                                   for line in lines]})
