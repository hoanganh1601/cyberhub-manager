"""Customer-facing phase 1: owner-scoped analytics, offers and read receipts."""

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256

from cyberhub_manager.domain.exceptions import PermissionDeniedError, ValidationError
from cyberhub_manager.domain.p1 import CustomerSession, quote_top_up
from cyberhub_manager.domain.loyalty import audience_matches

VIETNAM = timezone(timedelta(hours=7))
HISTORY_STATUSES = {
    "transactions": {"all", "TOP_UP", "PROMOTION", "USAGE_PAYMENT", "DEBT_SETTLEMENT"},
    "invoices": {"all", "PAID", "VOID"},
    "sessions": {"all", "ACTIVE", "COMPLETED", "CANCELLED"},
}


def local_midnight(value):
    return datetime.combine(value, time.min, VIETNAM).astimezone(timezone.utc)


def effective_policies(policies, store_id, now, customer_id=None, member=None):
    active = [
        p
        for p in policies
        if p.is_active
        and p.store_id in (None, store_id)
        and p.starts_at <= now < p.ends_at
        and audience_matches(p, customer_id, member)
    ]
    return [
        quote_top_up(
            amount, active, store_id, now, customer_id=customer_id, member=member
        ).promotion
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
        stores = [s for s in self._repo.list_stores(conn) if s.status == "ACTIVE"]
        if store_id is not None and (
            type(store_id) is not int or store_id not in {s.id for s in stores}
        ):
            raise ValidationError(field_errors={"store_id": "Cơ sở không khả dụng"})
        selected = (
            store_id if store_id is not None else (stores[0].id if stores else None)
        )
        policies = (
            self._repo.list_promotions(conn, selected) if selected is not None else []
        )
        # Show the exact policy that the wallet would apply at each threshold.
        member = (
            self._repo.loyalty_summary(conn, principal.customer_id)
            if principal
            else None
        )
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
                member=self._repo.loyalty_summary(conn, principal.customer_id),
                avatar_version=self._repo.avatar_metadata(conn, principal.account_id),
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
                customer_id=principal.customer_id,
                member=self._repo.loyalty_summary(conn, principal.customer_id),
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

    def _notifications(self, conn, principal, now):
        events = self._repo.portal_events(
            conn, principal, now - timedelta(days=30), now
        )
        transactions, invoices, *extra_groups = events
        menu_orders = extra_groups[0] if extra_groups else []
        items = [
            {**r, "key": f"tx:{r['id']}", "severity": "success"} for r in transactions
        ]
        items += [
            {
                **r,
                "key": f"invoice:{r['id']}:{r['kind']}",
                "severity": "warning" if r["kind"] == "VOID" else "info",
            }
            for r in invoices
        ]
        items += [
            {
                **r,
                "key": r["notification_key"],
                "severity": (
                    "warning" if r["kind"] == "MENU_ORDER_CANCELLED"
                    else "success" if r["kind"] in ("MENU_ORDER_SERVED", "MENU_ORDER_PAID")
                    else "info"
                ),
            }
            for r in menu_orders
        ]
        stores = [s for s in self._repo.list_stores(conn) if s.status == "ACTIVE"]
        # All active, effective offers across locations; one notification per policy revision.
        offers = {}
        policies = self._repo.list_promotions(conn)
        member = self._repo.loyalty_summary(conn, principal.customer_id)
        for store in stores:
            for p in effective_policies(
                policies, store.id, now, principal.customer_id, member
            ):
                offers[p.id] = p
        for p in offers.values():
            revision = sha256(
                f"{p.code}|{p.name}|{p.store_id}|{p.minimum_amount}|{p.bonus_percent}|{p.starts_at}|{p.ends_at}|{p.minimum_tier}|{p.minimum_points}|{p.target_customer_id}".encode()
            ).hexdigest()[:16]
            items.append(
                dict(
                    key=f"offer:{p.id}:{revision}",
                    kind="OFFER",
                    code=p.code,
                    name=p.name,
                    amount=p.minimum_amount,
                    bonus_percent=p.bonus_percent,
                    store_name=next(
                        (s.name for s in stores if s.id == p.store_id), None
                    ),
                    ends_at=p.ends_at,
                    created_at=p.starts_at,
                    severity="info",
                )
            )
        snapshot = self._repo.customer_snapshot(conn, principal)
        wallet = snapshot["wallet"]
        latest_transaction = (
            snapshot["transactions"][0]["code"]
            if snapshot["transactions"]
            else "initial"
        )
        wallet_version = sha256(
            f"{wallet['balance']}|{wallet['bonus_balance']}|{latest_transaction}".encode()
        ).hexdigest()[:16]
        active = self._repo.portal_active_sessions(conn, principal)
        for u in active:
            seconds = max(0, int((now - u["started_at"]).total_seconds()))
            cost = (max(1, (seconds + 59) // 60) * u["hourly_rate"] + 59) // 60
            projected = wallet["balance"] - cost
            remaining = max(0, projected * 60 // u["hourly_rate"])
            if remaining <= 15:
                # A new wallet event or escalation to depleted must be unread again.
                band = "depleted" if projected <= 0 else "low"
                items.append(
                    dict(
                        key=f"session-low:{u['id']}:{band}:{wallet_version}",
                        kind="SESSION_DEPLETED" if projected <= 0 else "SESSION_LOW",
                        code=u["machine_code"],
                        amount=projected,
                        remaining_minutes=remaining,
                        created_at=now,
                        severity="warning",
                    )
                )
        if not active and wallet["balance"] < 10_000:
            items.append(
                dict(
                    key=f"wallet-low:{wallet_version}",
                    kind="WALLET_LOW",
                    amount=wallet["balance"],
                    created_at=now,
                    severity="warning",
                )
            )
        items = sorted(
            items,
            key=lambda r: (
                r["severity"] == "warning",
                r["created_at"],
                r.get("id", 0),
                r["key"],
            ),
            reverse=True,
        )[:50]
        reads = self._repo.portal_read_keys(conn, principal, [r["key"] for r in items])
        for item in items:
            item["read"] = item["key"] in reads
        return dict(
            items=items,
            unread=sum(not x["read"] for x in items),
            limit=50,
            days=30,
            as_of=now,
        )

    def notifications(self, principal):
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            return self._notifications(conn, principal, self._clock())

    def mark_notifications_read(self, principal, keys):
        if (
            not isinstance(keys, list)
            or len(keys) > 50
            or any(not isinstance(k, str) or len(k) > 100 for k in keys)
        ):
            raise ValidationError(field_errors={"keys": "Danh sách không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            notifications = self._notifications(conn, principal, self._clock())
            owned = {n["key"] for n in notifications["items"]}
            if not set(keys) <= owned:
                raise ValidationError(
                    field_errors={"keys": "Thông báo không còn khả dụng"}
                )
            self._repo.portal_mark_read(conn, principal, set(keys))
            return dict(marked=len(set(keys)))
