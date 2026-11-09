"""Đợt 2 — Repository voucher trong bộ nhớ cho chế độ demo và unit test.

Cùng chữ ký với repositories/voucher_repository.py. Transaction bọc transaction của
MemoryP1Repository (khách, tài khoản, audit) và tự chụp lại trạng thái voucher, giao dịch ví,
điểm tặng để rollback khi lỗi.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from cyberhub_manager.domain.enums import PaymentMethod, TransactionType
from cyberhub_manager.domain.models import AccountTransaction
from cyberhub_manager.domain.voucher import (
    RewardCatalogItem,
    RewardType,
    Voucher,
    VoucherAction,
    VoucherEvent,
    VoucherSource,
    VoucherStatus,
)

# (mã, tên, loại, giá trị, đơn tối thiểu, số ngày hiệu lực, giá xu cho Đợt 3)
DEMO_REWARDS = (
    ("GIAM20K", "Giảm 20.000đ đồ ăn", RewardType.FOOD_DISCOUNT, 20_000, 50_000, 30, 200),
    ("NUOCFREE", "Tặng 1 nước (tối đa 20.000đ)", RewardType.FREE_DRINK, 20_000, 0, 14, 150),
    ("GIO10K", "Cộng 10.000đ giờ chơi", RewardType.PLAYTIME_CREDIT, 10_000, 0, 30, 120),
    ("DIEM50", "Tặng 50 điểm thành viên", RewardType.MEMBER_POINTS, 50, 0, 30, 80),
)


def _value(enum_or_text):
    return getattr(enum_or_text, "value", enum_or_text)


class MemoryVoucherRepository:
    def __init__(self, data, p1_repo, clock=None):
        self.data = data
        self.p1 = p1_repo
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.catalog: dict[int, RewardCatalogItem] = {}
        self.vouchers: dict[int, dict] = {}
        self.events: list[dict] = []
        if not hasattr(data, "loyalty_point_grants"):
            data.loyalty_point_grants = []
        self._ids = {"catalog": 0, "voucher": 0, "event": 0}

    # ----- Transaction ----------------------------------------------------------
    @contextmanager
    def transaction(self):
        with self.p1.transaction() as conn:
            snapshot = deepcopy((self.catalog, self.vouchers, self.events, self._ids,
                                 self.data.transactions, self.data.transaction_stores,
                                 self.data.loyalty_point_grants))
            try:
                yield conn
            except Exception:
                (self.catalog, self.vouchers, self.events, self._ids, self.data.transactions,
                 self.data.transaction_stores, self.data.loyalty_point_grants) = snapshot
                raise

    def _next(self, kind):
        self._ids[kind] += 1
        return self._ids[kind]

    # ----- Dữ liệu mẫu -----------------------------------------------------------
    def seed_demo(self):
        ids = {}
        for code, name, reward_type, value, minimum, days, coins in DEMO_REWARDS:
            ids[code] = self.insert_catalog(None, code=code, name=name, store_id=None, reward_type=reward_type,
                                            value=value, min_order_amount=minimum, valid_days=days,
                                            coin_cost=coins, is_active=True)
        accounts = {c.account.username: c.account.id for c in self.data.customers.values()}
        now = self.clock().replace(microsecond=0)
        plan = (
            ("nguyenvanan", "GIO10K", 0, None),
            ("nguyenvanan", "DIEM50", 0, None),
            ("nguyenvanan", "GIAM20K", 40, None),  # đã hết hạn
            ("lethibinh", "GIAM20K", 0, None),
            ("lethibinh", "NUOCFREE", 0, None),
            ("lethibinh", "DIEM50", 5, "USED"),  # đã dùng
        )
        for username, reward, days_ago, status in plan:
            if username not in accounts:
                continue
            catalog = self.catalog[ids[reward]]
            issued = now - timedelta(days=days_ago)
            voucher_id = self.insert_voucher(
                None, code=f"CHDEMO{len(self.vouchers) + 1:04d}", catalog=catalog, account_id=accounts[username],
                source=VoucherSource.MANUAL, source_ref=None, issued_by=None, issued_at=issued,
                expires_at=issued + timedelta(days=catalog.valid_days),
            )
            if status == "USED":
                store_id = next(iter(self.data.stores))
                self.vouchers[voucher_id].update(status=VoucherStatus.USED, used_at=issued + timedelta(days=1),
                                                 used_by=None, used_store_id=store_id)

    # ----- Danh mục ----------------------------------------------------------------
    def list_catalog(self, conn, store_id):
        return sorted((c for c in self.catalog.values() if c.store_id in (None, store_id)),
                      key=lambda c: (not c.is_active, c.reward_type, c.value, c.id))

    def get_catalog(self, conn, catalog_id, *, lock=False):
        return self.catalog.get(catalog_id)

    def catalog_code_taken(self, conn, code, exclude_id):
        return any(c.code == code and c.id != exclude_id for c in self.catalog.values())

    def insert_catalog(self, conn, **f):
        catalog_id = self._next("catalog")
        self.catalog[catalog_id] = RewardCatalogItem(id=catalog_id, **f)
        return catalog_id

    def update_catalog(self, conn, catalog_id, **f):
        self.catalog[catalog_id] = replace(self.catalog[catalog_id], **f)

    # ----- Khách hàng ----------------------------------------------------------------
    def customer_account(self, conn, customer_id, *, lock=False):
        customer = self.data.customers.get(customer_id)
        if customer is None:
            return None
        return dict(customer_id=customer.id, account_id=customer.account.id, full_name=customer.full_name,
                    status=_value(customer.status), account_status=_value(customer.account.status))

    # ----- Voucher --------------------------------------------------------------------
    def _to_voucher(self, row):
        customer = next(c for c in self.data.customers.values() if c.account.id == row["account_id"])
        return Voucher(
            id=row["id"], code=row["code"], catalog_id=row["catalog_id"],
            catalog_name=self.catalog[row["catalog_id"]].name, account_id=row["account_id"],
            customer_id=customer.id, customer_name=customer.full_name, store_id=row["store_id"],
            reward_type=row["reward_type"], value=row["value"], min_order_amount=row["min_order_amount"],
            status=row["status"], source=row["source"], issued_at=row["issued_at"], expires_at=row["expires_at"],
            used_at=row["used_at"], used_store_id=row["used_store_id"], used_order_id=row["used_order_id"],
            revoked_reason=row["revoked_reason"],
        )

    def insert_voucher(self, conn, *, code, catalog, account_id, source, source_ref, issued_by, issued_at,
                       expires_at):
        if source_ref is not None and any(v["source"] == source and v["source_ref"] == source_ref
                                          for v in self.vouchers.values()):
            raise ValueError("duplicate voucher source")  # tương đương UNIQUE(source, source_ref)
        voucher_id = self._next("voucher")
        self.vouchers[voucher_id] = dict(
            id=voucher_id, code=code, catalog_id=catalog.id, account_id=account_id, store_id=catalog.store_id,
            reward_type=catalog.reward_type, value=catalog.value, min_order_amount=catalog.min_order_amount,
            status=VoucherStatus.ISSUED, source=source, source_ref=source_ref, issued_by=issued_by,
            issued_at=issued_at, expires_at=expires_at, used_at=None, used_by=None, used_store_id=None,
            used_order_id=None, revoked_reason=None,
        )
        return voucher_id

    def voucher_by_source(self, conn, source, source_ref):
        row = next((v for v in self.vouchers.values() if v["source"] == source and v["source_ref"] == source_ref), None)
        return None if row is None else self._to_voucher(row)

    def get_voucher(self, conn, *, voucher_id=None, code=None, lock=False):
        if voucher_id is not None:
            row = self.vouchers.get(voucher_id)
        else:
            row = next((v for v in self.vouchers.values() if v["code"] == code), None)
        return None if row is None else self._to_voucher(row)

    def account_vouchers(self, conn, account_id):
        found = [self._to_voucher(v) for v in self.vouchers.values() if v["account_id"] == account_id]
        return sorted(found, key=lambda v: (v.issued_at, v.id), reverse=True)

    def order_has_voucher(self, conn, order_id):
        return any(v["used_order_id"] == order_id for v in self.vouchers.values())

    def mark_used(self, conn, voucher_id, *, employee_id, store_id, order_id, used_at):
        row = self.vouchers.get(voucher_id)
        if row is None or row["status"] != VoucherStatus.ISSUED:
            return False
        row.update(status=VoucherStatus.USED, used_at=used_at, used_by=employee_id, used_store_id=store_id,
                   used_order_id=order_id)
        return True

    def revoke(self, conn, voucher_id, reason):
        row = self.vouchers.get(voucher_id)
        if row is None or row["status"] != VoucherStatus.ISSUED:
            return False
        row.update(status=VoucherStatus.REVOKED, revoked_reason=reason)
        return True

    # ----- Nhật ký ----------------------------------------------------------------
    def insert_event(self, conn, *, voucher_id, action, employee_id, store_id, reason=""):
        self.events.append(dict(id=self._next("event"), voucher_id=voucher_id, action=VoucherAction(action),
                                employee_id=employee_id, store_id=store_id, reason=reason[:200],
                                created_at=self.clock()))

    def list_events(self, conn, store_id, limit=50):
        found = [e for e in reversed(self.events) if e["store_id"] == store_id][:limit]
        result = []
        for e in found:
            voucher = self.vouchers.get(e["voucher_id"]) if e["voucher_id"] else None
            employee = self.data.employees.get(e["employee_id"]) if e["employee_id"] else None
            result.append(VoucherEvent(e["id"], e["voucher_id"], voucher["code"] if voucher else None, e["action"],
                                       employee.full_name if employee else None, e["reason"], e["created_at"]))
        return result

    # ----- Thực hiện phần thưởng -------------------------------------------------------
    def grant_points(self, conn, *, customer_id, voucher_id, points, employee_id):
        if any(g["voucher_id"] == voucher_id for g in self.data.loyalty_point_grants):
            raise ValueError("duplicate grant")  # tương đương UNIQUE(voucher_id)
        self.data.loyalty_point_grants.append(dict(customer_id=customer_id, voucher_id=voucher_id, points=points,
                                                   employee_id=employee_id, created_at=self.clock()))

    def credit_playtime(self, conn, *, account_id, amount, employee_id, store_id):
        customer = next(c for c in self.data.customers.values() if c.account.id == account_id)
        transaction_id = self.data.next_id("transaction")
        self.data.transactions[transaction_id] = AccountTransaction(
            id=transaction_id, code=self.data.make_code("transaction", transaction_id), account_id=account_id,
            employee_id=employee_id, session_id=None, type=TransactionType.PROMOTION, amount=amount,
            method=PaymentMethod.PROMOTION, created_at=self.clock(),
        )
        self.data.transaction_stores[transaction_id] = store_id
        customer.account.credit_bonus(amount)

