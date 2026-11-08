"""Frozen per-invoice earning rules and current, configurable membership thresholds."""

from dataclasses import dataclass

TIERS = ("BRONZE", "SILVER", "GOLD", "PLATINUM")


@dataclass(frozen=True)
class LoyaltySettings:
    enabled: bool = True
    unit_amount: int = 10000
    silver_spend: int = 1000000
    gold_spend: int = 3000000
    platinum_spend: int = 5000000
    version: int = 1


def invoice_award(cost, bonus_used, settings):
    eligible = max(0, cost - bonus_used)
    return dict(
        eligible_amount=eligible,
        points=eligible // settings.unit_amount if settings.enabled else 0,
        unit_amount=settings.unit_amount,
        rule_version=settings.version,
    )


def membership(points, eligible_spend, settings):
    thresholds = (
        0,
        settings.silver_spend,
        settings.gold_spend,
        settings.platinum_spend,
    )
    rank = max(i for i, amount in enumerate(thresholds) if eligible_spend >= amount)
    next_spend = thresholds[rank + 1] if rank < 3 else None
    start = thresholds[rank]
    return dict(
        points=int(points),
        eligible_spend=int(eligible_spend),
        tier=TIERS[rank],
        next_tier=TIERS[rank + 1] if rank < 3 else None,
        next_spend=next_spend,
        remaining_spend=max(0, next_spend - eligible_spend) if next_spend else 0,
        progress_percent=(
            min(100, (eligible_spend - start) * 100 // (next_spend - start))
            if next_spend
            else 100
        ),
        enabled=settings.enabled,
        unit_amount=settings.unit_amount,
        rule_version=settings.version,
        tiers=[
            dict(tier=tier, minimum_spend=thresholds[i]) for i, tier in enumerate(TIERS)
        ],
    )


def personalized(policy):
    return (
        policy.minimum_tier != "BRONZE"
        or policy.minimum_points > 0
        or policy.target_customer_id is not None
    )


def audience_matches(policy, customer_id=None, member=None):
    if not personalized(policy):
        return True
    if customer_id is None or member is None:
        return False
    return (
        policy.target_customer_id in (None, customer_id)
        and TIERS.index(member["tier"]) >= TIERS.index(policy.minimum_tier)
        and member["points"] >= policy.minimum_points
    )
