"""Customer-facing phase 1: owner-scoped analytics, offers and read receipts."""

from datetime import date, datetime, time, timedelta, timezone

from cyberhub_manager.domain.exceptions import PermissionDeniedError, ValidationError
from cyberhub_manager.domain.p1 import CustomerSession, quote_top_up

VIETNAM = timezone(timedelta(hours=7))
HISTORY_STATUSES = {
    "transactions": {"all", "TOP_UP", "PROMOTION", "USAGE_PAYMENT", "DEBT_SETTLEMENT"},
    "invoices": {"all", "PAID", "VOID"},
    "sessions": {"all", "ACTIVE", "COMPLETED", "CANCELLED"},
}


def local_midnight(value):
    return datetime.combine(value, time.min, VIETNAM).astimezone(timezone.utc)


def effective_policies(policies, store_id, now, customer_id=None, member=None):
    # The reduced project keeps general top-up promotions and has no membership tiers.
    active = [
        p for p in policies
        if p.is_active
        and p.store_id in (None, store_id)
        and p.starts_at <= now < p.ends_at
    ]
    return [
        quote_top_up(amount, active, store_id, now).promotion
        for amount in sorted({p.minimum_amount for p in active})
    ]

class PortalExperienceMixin:
    def _principal(self, conn, principal):
        if not isinstance(principal, CustomerSession):
            raise PermissionDeniedError()
        record = self._repo.customer_credentials(conn, account_id=principal.account_id)
        if (
            not record
            or record[0].customer_id != principal.customer_id
            or record[0].auth_version != principal.auth_version
        ):
            raise PermissionDeniedError()
        return record[0]

    def _offers(self, conn, now, store_id=None, principal=None):
        stores = [s for s in self._management.list_stores(conn) if s.status == "ACTIVE"]
        if store_id is not None and (
            type(store_id) is not int or store_id not in {s.id for s in stores}
        ):
            raise ValidationError(field_errors={"store_id": "Cơ sở không khả dụng"})
        selected = (
            store_id if store_id is not None else (stores[0].id if stores else None)
        )
        policies = (
            self._management.list_promotions(conn, selected) if selected is not None else []
        )
        # This compact schema applies only general promotions, not member tiers.
        member = None
        return (
            stores,
            selected,
            effective_policies(
                policies,
                selected,
                now,
                principal.customer_id if principal else None,
                member,
            ),
        )

    def dashboard(self, principal, days=30, store_id=None):
        if type(days) is not int or days not in (7, 30, 90):
            raise ValidationError(field_errors={"days": "Chọn 7, 30 hoặc 90 ngày"})
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            now = self._clock()
            today = now.astimezone(VIETNAM).date()
            first = today - timedelta(days=days - 1)
            start = local_midnight(first)
            end = now + timedelta(microseconds=1)
            snapshot = self._repo.customer_snapshot(conn, principal)
            totals, paid, topups = self._repo.portal_totals(
                conn, principal, start, end, now
            )
            totals = {k: int(v) for k, v in totals.items()}
            totals["principal_spent"] = totals["spent"] - totals["bonus_spent"]
            totals["average_invoice"] = (
                totals["spent"] // totals["paid_invoices"]
                if totals["paid_invoices"]
                else 0
            )
            paid = {r["day"]: int(r["spent"]) for r in paid}
            topups = {r["day"]: int(r["topped_up"]) for r in topups}
            chart = [
                dict(
                    day=first + timedelta(days=i),
                    spent=paid.get(first + timedelta(days=i), 0),
                    topped_up=topups.get(first + timedelta(days=i), 0),
                )
                for i in range(days)
            ]
            active = []
            for u in self._repo.portal_active_sessions(conn, principal):
                seconds = max(0, int((now - u["started_at"]).total_seconds()))
                minutes = max(1, (seconds + 59) // 60)
                estimated = (minutes * u["hourly_rate"] + 59) // 60
                projected = snapshot["wallet"]["balance"] - estimated
                active.append(
                    {
                        **u,
                        "elapsed_seconds": seconds,
                        "estimated_cost": estimated,
                        "projected_balance": projected,
                        "remaining_minutes": max(0, projected * 60 // u["hourly_rate"]),
                    }
                )
            stores, selected, policies = self._offers(conn, now, store_id, principal)
            return dict(
                profile=principal,
                wallet=snapshot["wallet"],
                account_status="ACTIVE",
                as_of=now,
                timezone="Asia/Ho_Chi_Minh",
                date_from=first,
                date_to=today,
                days=days,
                totals=totals,
                chart=chart,
                active_sessions=active,
                stores=stores,
                store_id=selected,
                promotions=policies,
            )

    def history(
        self,
        principal,
        kind="transactions",
        status="all",
        date_from=None,
        date_to=None,
        page=1,
        page_size=10,
    ):
        if kind not in HISTORY_STATUSES or status not in HISTORY_STATUSES[kind]:
            raise ValidationError(field_errors={"status": "Bộ lọc không hợp lệ"})
        if (
            type(page) is not int
            or not 1 <= page <= 1_000_000
            or type(page_size) is not int
            or page_size not in (10, 20, 50)
        ):
            raise ValidationError(field_errors={"page": "Trang không hợp lệ"})
        try:
            first = date.fromisoformat(date_from) if date_from else None
            last = date.fromisoformat(date_to) if date_to else None
            if first and last and first > last:
                raise ValueError()
            start = local_midnight(first) if first else None
            end = local_midnight(last + timedelta(days=1)) if last else None
        except (ValueError, TypeError, OverflowError):
            raise ValidationError(
                field_errors={"date_to": "Khoảng ngày không hợp lệ"}
            ) from None
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            return self._repo.portal_history(
                conn, principal, kind, status, start, end, page, page_size
            )

    def promotion_quote(self, principal, store_id, amount):
        with self._errors(), self._transaction() as conn:
            self._principal(conn, principal)
            now = self._clock()
            _, selected, policies = self._offers(conn, now, store_id, principal)
            if selected is None or store_id is None:
                raise ValidationError(field_errors={"store_id": "Vui lòng chọn cơ sở"})
            quote = quote_top_up(
                amount,
                policies,
                selected,
                now,
            )
            higher = next((p for p in policies if p.minimum_amount > amount), None)
            return dict(
                amount=quote.amount,
                bonus_amount=quote.bonus_amount,
                credited_total=quote.amount + quote.bonus_amount,
                promotion=quote.promotion,
                next_tier=higher,
                amount_to_next=higher.minimum_amount - amount if higher else 0,
                as_of=now,
                store_id=selected,
            )
