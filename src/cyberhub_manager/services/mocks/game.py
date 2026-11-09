"""Đợt 3 — Repository game/xu trong bộ nhớ cho chế độ demo và unit test.

Cùng chữ ký với repositories/game_repository.py. Transaction bọc transaction của
MemoryVoucherRepository (voucher + P1) để đổi xu và phát voucher cùng thành công hoặc cùng rollback.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta, timezone

from cyberhub_manager.domain.game import (
    DEFAULT_GAME,
    CoinLedgerEntry,
    Game,
    GamePrize,
    GameSession,
    GameWallet,
)

DEFAULT_PRIZES = (
    GamePrize(0, "5 xu", 5, 30),
    GamePrize(1, "Chúc may mắn", 0, 25),
    GamePrize(2, "10 xu", 10, 25),
    GamePrize(3, "20 xu", 20, 15),
    GamePrize(4, "50 xu", 50, 5),
    GamePrize(5, "100 xu", 100, 2),
)
VN = timezone(timedelta(hours=7))


class MemoryGameRepository:
    def __init__(self, data, voucher_repo):
        self.data = data
        self.vouchers = voucher_repo
        self.game = Game(1, DEFAULT_GAME, "Vòng quay CyberHub", True, 3, 3, DEFAULT_PRIZES)
        self.wallets: dict[int, GameWallet] = {}
        self.sessions: list[dict] = []
        self.ledger: list[CoinLedgerEntry] = []

    @contextmanager
    def transaction(self):
        with self.vouchers.transaction() as conn:
            snapshot = deepcopy((self.game, self.wallets, self.sessions, self.ledger))
            try:
                yield conn
            except Exception:
                self.game, self.wallets, self.sessions, self.ledger = snapshot
                raise

    def _name(self, account_id):
        customer = next((c for c in self.data.customers.values() if c.account.id == account_id), None)
        return customer.full_name if customer else ""

    # ----- Cấu hình -------------------------------------------------------------------
    def get_game(self, conn, code, *, lock=False):
        return self.game if code == self.game.code else None

    def save_game(self, conn, game_id, *, is_active, daily_limit, min_interval_seconds, prizes):
        self.game = replace(self.game, is_active=is_active, daily_limit=daily_limit,
                            min_interval_seconds=min_interval_seconds, prizes=tuple(prizes))

    # ----- Ví ---------------------------------------------------------------------------
    def account_exists(self, conn, account_id):
        return any(c.account.id == account_id for c in self.data.customers.values())

    def wallet(self, conn, account_id, *, lock=False):
        return self.wallets.setdefault(account_id, GameWallet(account_id, 0, False, None, None, 0, None))

    def set_balance(self, conn, account_id, balance):
        if balance < 0:
            raise ValueError("balance must not be negative")  # tương đương CHECK balance >= 0
        self.wallets[account_id] = replace(self.wallet(conn, account_id), balance=balance)

    def set_suspicious(self, conn, account_id, count, day):
        self.wallets[account_id] = replace(self.wallet(conn, account_id), suspicious_count=count, suspicious_on=day)

    def lock_wallet(self, conn, account_id, reason, at):
        self.wallets[account_id] = replace(self.wallet(conn, account_id), is_locked=True,
                                           locked_reason=reason[:200], locked_at=at)

    def unlock_wallet(self, conn, account_id):
        self.wallets[account_id] = replace(self.wallet(conn, account_id), is_locked=False, locked_reason=None,
                                           locked_at=None, suspicious_count=0, suspicious_on=None)

    def locked_wallets(self, conn):
        locked = [w for w in self.wallets.values() if w.is_locked]
        return [dict(account_id=w.account_id, customer_name=self._name(w.account_id), balance=w.balance,
                     locked_reason=w.locked_reason, locked_at=w.locked_at)
                for w in sorted(locked, key=lambda w: w.locked_at, reverse=True)]

    # ----- Phiên chơi -------------------------------------------------------------------
    def count_sessions(self, conn, account_id, game_id, day):
        return sum(1 for s in self.sessions if s["account_id"] == account_id and s["played_on"] == day)

    def last_session_at(self, conn, account_id):
        times = [s["created_at"] for s in self.sessions if s["account_id"] == account_id]
        return max(times) if times else None

    def insert_session(self, conn, *, account_id, game_id, prize_index, prize_label, coins, played_on, created_at):
        session_id = len(self.sessions) + 1
        self.sessions.append(dict(id=session_id, account_id=account_id, prize_index=prize_index,
                                  prize_label=prize_label, coins=coins, played_on=played_on, created_at=created_at))
        return session_id

    def _session(self, s):
        return GameSession(s["id"], s["account_id"], self._name(s["account_id"]), s["prize_index"],
                           s["prize_label"], s["coins"], s["played_on"], s["created_at"])

    def account_sessions(self, conn, account_id, limit=10):
        found = [s for s in self.sessions if s["account_id"] == account_id]
        return [self._session(s) for s in sorted(found, key=lambda s: (s["created_at"], s["id"]), reverse=True)[:limit]]

    def recent_sessions(self, conn, game_id, limit=20):
        found = sorted(self.sessions, key=lambda s: (s["created_at"], s["id"]), reverse=True)[:limit]
        return [self._session(s) for s in found]

    def stats(self, conn, game_id, day):
        today = [s for s in self.sessions if s["played_on"] == day]
        redeemed = [e for e in self.ledger
                    if e.reason == "REDEEM" and e.created_at.astimezone(VN).date() == day]
        return dict(sessions=len(today), players=len({s["account_id"] for s in today}),
                    coins_awarded=sum(s["coins"] for s in today), coins_redeemed=sum(-e.delta for e in redeemed),
                    vouchers=len(redeemed))

    # ----- Sổ cái ------------------------------------------------------------------------
    def insert_ledger(self, conn, *, account_id, delta, reason, ref, balance_after, voucher_id, created_at):
        if any(e.reason == reason and e.ref == ref for e in self.ledger):
            raise ValueError("duplicate ledger ref")  # tương đương UNIQUE(reason, ref)
        self.ledger.append(CoinLedgerEntry(len(self.ledger) + 1, account_id, delta, reason, ref, balance_after,
                                           voucher_id, created_at))

    def ledger_by_ref(self, conn, reason, ref):
        return next((e for e in self.ledger if e.reason == reason and e.ref == ref), None)

    def account_ledger(self, conn, account_id, limit=10):
        found = [e for e in self.ledger if e.account_id == account_id]
        return sorted(found, key=lambda e: (e.created_at, e.id), reverse=True)[:limit]
