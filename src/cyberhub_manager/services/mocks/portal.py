"""In-memory implementation of the customer analytics repository contract."""

from collections import defaultdict
from datetime import timedelta, timezone

VIETNAM = timezone(timedelta(hours=7))


class MemoryPortalRepositoryMixin:
    def _portal_rows(self, principal, kind):
        if kind == "transactions":
            return [
                dict(
                    id=t.id,
                    code=t.code,
                    type=str(t.type),
                    amount=t.amount,
                    method=str(t.method),
                    created_at=t.created_at,
                    store_name=self.data.get_store(
                        self.data.transaction_stores.get(
                            t.id, self.data.employees[t.employee_id].store_id
                        )
                    ).name,
                )
                for t in self.data.transactions_for_account(principal.account_id)
            ]
        if kind == "invoices":
            return [
                dict(
                    id=i.id,
                    code=i.code,
                    usage_cost=i.usage_cost,
                    bonus_used=self.data.invoice_bonus.get(i.id, 0),
                    settlement_amount=i.settlement_amount,
                    status=str(i.status),
                    created_at=i.created_at,
                    store_name=self.data.get_store(i.store_id).name,
                )
                for i in self.data.invoices.values()
                if i.customer_id == principal.customer_id
            ]
        return [
            dict(
                id=u.id,
                code=u.code,
                machine_code=self.data.machines[u.machine_id].code,
                store_name=self.data.get_store(
                    self.data.machines[u.machine_id].store_id
                ).name,
                started_at=u.started_at,
                ended_at=u.ended_at,
                hourly_rate=u.hourly_rate,
                status=str(u.status),
                cost=u.cost,
            )
            for u in self.data.sessions.values()
            if u.customer_id == principal.customer_id
        ]

    def portal_totals(self, conn, principal, start, end, now):
        invoices = [
            i
            for i in self._portal_rows(principal, "invoices")
            if i["status"] == "PAID" and start <= i["created_at"] < end
        ]
        credits = [
            t
            for t in self._portal_rows(principal, "transactions")
            if start <= t["created_at"] < end
        ]
        seconds = sum(
            max(
                0,
                int(
                    (
                        min(u["ended_at"] or now, now, end)
                        - max(u["started_at"], start)
                    ).total_seconds()
                ),
            )
            for u in self._portal_rows(principal, "sessions")
            if u["status"] in ("ACTIVE", "COMPLETED")
        )
        daily_paid, daily_topups = defaultdict(int), defaultdict(int)
        for i in invoices:
            daily_paid[i["created_at"].astimezone(VIETNAM).date()] += i["usage_cost"]
        for tx in credits:
            if tx["type"] == "TOP_UP":
                daily_topups[tx["created_at"].astimezone(VIETNAM).date()] += tx[
                    "amount"
                ]
        totals = dict(
            spent=sum(i["usage_cost"] for i in invoices),
            paid_invoices=len(invoices),
            bonus_spent=sum(i["bonus_used"] for i in invoices),
            usage_seconds=seconds,
            topped_up=sum(t["amount"] for t in credits if t["type"] == "TOP_UP"),
            bonus_received=sum(
                t["amount"] for t in credits if t["type"] == "PROMOTION"
            ),
        )
        return (
            totals,
            [dict(day=k, spent=v) for k, v in daily_paid.items()],
            [dict(day=k, topped_up=v) for k, v in daily_topups.items()],
        )

    def portal_active_sessions(self, conn, principal):
        return [
            r
            for r in self._portal_rows(principal, "sessions")
            if r["status"] == "ACTIVE"
        ]

    def portal_history(
        self, conn, principal, kind, status, start, end, page, page_size
    ):
        time = "started_at" if kind == "sessions" else "created_at"
        column = "type" if kind == "transactions" else "status"
        items = sorted(
            [
                r
                for r in self._portal_rows(principal, kind)
                if (status == "all" or r[column] == status)
                and (start is None or r[time] >= start)
                and (end is None or r[time] < end)
            ],
            key=lambda r: (r[time], r["id"]),
            reverse=True,
        )
        return dict(
            items=items[(page - 1) * page_size : page * page_size],
            total=len(items),
            page=page,
            page_size=page_size,
        )

    def portal_events(self, conn, principal, since, now):
        groups = []
        for kind in ("transactions", "invoices"):
            events = [
                dict(
                    id=r["id"],
                    code=r["code"],
                    kind=r.get("type", r.get("status")),
                    amount=r.get("amount", r.get("usage_cost")),
                    created_at=r["created_at"],
                )
                for r in self._portal_rows(principal, kind)
                if since <= r["created_at"] <= now
                and (kind == "invoices" or r["type"] in ("TOP_UP", "PROMOTION"))
            ]
            groups.append(
                sorted(events, key=lambda r: (r["created_at"], r["id"]), reverse=True)[
                    :50
                ]
            )
        return tuple(groups)

    def portal_read_keys(self, conn, principal, keys):
        return {
            key
            for key in keys
            if (principal.account_id, key) in self.notification_reads
        }

    def portal_mark_read(self, conn, principal, keys):
        self.notification_reads.update((principal.account_id, key) for key in keys)
