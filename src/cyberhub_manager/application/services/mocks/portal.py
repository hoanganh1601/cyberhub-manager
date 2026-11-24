"""In-memory implementation of the customer analytics repository contract."""

from collections import defaultdict
from datetime import timedelta, timezone

VIETNAM = timezone(timedelta(hours=7))


class MemoryPortalRepositoryMixin:
    def list_machine_rooms(self, conn, store_id):
        return [
            dict(
                machine_id=m.id,
                machine_code=m.code,
                name=m.name,
                status=str(m.status),
                room_type=self.room_types.get(m.id, "STANDARD"),
            )
            for m in sorted(self.data.machines.values(), key=lambda m: m.code)
            if m.store_id == store_id and m.is_active
        ]

    def room_machine(self, conn, machine_id):
        m = self.data.machines.get(machine_id)
        return (
            dict(
                id=m.id,
                store_id=m.store_id,
                status=str(m.status),
                is_active=m.is_active,
                active_session=self.data.active_session_for_machine(m.id) is not None,
            )
            if m
            else None
        )

    def set_machine_room(self, conn, machine_id, room_type):
        self.room_types[machine_id] = room_type

    def portal_room_counts(self, conn, store_id):
        machines = [
            m
            for m in self.data.machines.values()
            if m.store_id == store_id and m.is_active
        ]
        result = []
        for kind in ("STANDARD", "VIP", "COUPLE", "SUPER_VIP"):
            group = [
                m for m in machines if self.room_types.get(m.id, "STANDARD") == kind
            ]
            result.append(
                dict(
                    room_type=kind,
                    total=len(group),
                    available=sum(
                        str(m.status) == "AVAILABLE"
                        and self.data.active_session_for_machine(m.id) is None
                        for m in group
                    ),
                    min_hourly_rate=min((m.hourly_rate for m in group), default=None),
                    max_hourly_rate=max((m.hourly_rate for m in group), default=None),
                )
            )
        return result

    def portal_usage_sessions(self, conn, principal, start, end):
        return [
            dict(
                machine_id=u.machine_id,
                store_id=self.data.machines[u.machine_id].store_id,
                store_name=self.data.get_store(
                    self.data.machines[u.machine_id].store_id
                ).name,
                started_at=u.started_at,
                ended_at=u.ended_at,
                status=str(u.status),
            )
            for u in self.data.sessions.values()
            if u.customer_id == principal.customer_id
            and u.started_at < end
            and (u.ended_at is None or u.ended_at > start)
        ]

    def portal_profile(self, conn, principal):
        customer = self.data.get_customer(principal.customer_id)
        return dict(
            customer_code=customer.code,
            full_name=customer.full_name,
            phone=customer.phone,
            account_code=customer.account.code,
            username=customer.account.username,
            account_status=str(customer.account.status),
            member_since=None,
        )

    def portal_phone_taken(self, conn, principal, phone):
        return any(
            c.id != principal.customer_id and c.phone == phone
            for c in self.data.customers.values()
        )

    def portal_update_profile(self, conn, principal, name, phone):
        self.data.get_customer(principal.customer_id).update_profile(name, phone)

    def portal_change_password(self, conn, principal, password_hash):
        self.data.customer_password_hashes[principal.account_id] = password_hash
        self.auth_versions[principal.account_id] = (
            self.auth_versions.get(principal.account_id, 0) + 1
        )

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
        menu_orders = [
            dict(event)
            for event in self.order_notifications
            if event["account_id"] == principal.account_id
            and since <= event["created_at"] <= now
        ]
        menu_orders.sort(
            key=lambda event: (event["created_at"], event["id"]), reverse=True,
        )
        return (*groups, menu_orders[:50])

    def portal_read_keys(self, conn, principal, keys):
        return {
            key
            for key in keys
            if (principal.account_id, key) in self.notification_reads
        }

    def portal_mark_read(self, conn, principal, keys):
        self.notification_reads.update((principal.account_id, key) for key in keys)
