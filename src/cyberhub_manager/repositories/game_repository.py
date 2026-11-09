"""Đợt 3 — Truy cập dữ liệu game và xu (MySQL). Không tự commit."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from cyberhub_manager.domain.game import (
    CoinLedgerEntry,
    Game,
    GamePrize,
    GameSession,
    GameWallet,
    LedgerReason,
)
from cyberhub_manager.repositories.p1_repository import execute, rows


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _wallet(r: dict) -> GameWallet:
    return GameWallet(
        account_id=int(r["account_id"]),
        balance=int(r["balance"]),
        is_locked=bool(r["is_locked"]),
        locked_reason=r["locked_reason"],
        locked_at=_utc(r["locked_at"]),
        suspicious_count=int(r["suspicious_count"]),
        suspicious_on=r["suspicious_on"],
    )


def _ledger(r: dict) -> CoinLedgerEntry:
    return CoinLedgerEntry(
        id=int(r["id"]),
        account_id=int(r["account_id"]),
        delta=int(r["delta"]),
        reason=LedgerReason(r["reason"]),
        ref=r["ref"],
        balance_after=int(r["balance_after"]),
        voucher_id=None if r["voucher_id"] is None else int(r["voucher_id"]),
        created_at=_utc(r["created_at"]),
    )


_SESSION_SELECT = """
    SELECT g.id, g.account_id, c.full_name AS customer_name, g.prize_index, g.prize_label, g.coins,
           g.played_on, g.created_at
    FROM game_sessions AS g
    JOIN accounts AS a ON a.id = g.account_id
    JOIN customers AS c ON c.id = a.customer_id
"""


def _session(r: dict) -> GameSession:
    return GameSession(
        id=int(r["id"]),
        account_id=int(r["account_id"]),
        customer_name=r["customer_name"],
        prize_index=int(r["prize_index"]),
        prize_label=r["prize_label"],
        coins=int(r["coins"]),
        played_on=r["played_on"],
        created_at=_utc(r["created_at"]),
    )


class GameRepository:
    # ----- Cấu hình game ---------------------------------------------------------
    def get_game(self, conn: Any, code: str, *, lock: bool = False) -> Game | None:
        result = rows(
            conn,
            "SELECT id, code, name, is_active, daily_limit, min_interval_seconds FROM games WHERE code = %s"
            + (" FOR UPDATE" if lock else ""),
            (code,),
        )
        if not result:
            return None
        r = result[0]
        prizes = tuple(
            GamePrize(int(p["sort_order"]), p["label"], int(p["coins"]), int(p["weight"]))
            for p in rows(
                conn,
                "SELECT sort_order, label, coins, weight FROM game_prizes WHERE game_id = %s ORDER BY sort_order",
                (r["id"],),
            )
        )
        return Game(int(r["id"]), r["code"], r["name"], bool(r["is_active"]), int(r["daily_limit"]),
                    int(r["min_interval_seconds"]), prizes)

    def save_game(self, conn: Any, game_id: int, *, is_active, daily_limit, min_interval_seconds,
                  prizes: list[GamePrize]) -> None:
        execute(
            conn,
            "UPDATE games SET is_active = %s, daily_limit = %s, min_interval_seconds = %s WHERE id = %s",
            (is_active, daily_limit, min_interval_seconds, game_id),
        )
        # Phiên chơi chụp lại nhãn/xu nên thay toàn bộ ô giải thưởng không ảnh hưởng lịch sử.
        execute(conn, "DELETE FROM game_prizes WHERE game_id = %s", (game_id,))
        for prize in prizes:
            execute(
                conn,
                "INSERT INTO game_prizes (game_id, sort_order, label, coins, weight) VALUES (%s, %s, %s, %s, %s)",
                (game_id, prize.sort_order, prize.label, prize.coins, prize.weight),
            )

    # ----- Ví xu -------------------------------------------------------------------
    def account_exists(self, conn: Any, account_id: int) -> bool:
        return bool(rows(conn, "SELECT id FROM accounts WHERE id = %s", (account_id,)))

    def wallet(self, conn: Any, account_id: int, *, lock: bool = False) -> GameWallet:
        """Ví xu của tài khoản; tạo ví rỗng ở lần đầu. lock=True khóa dòng để tuần tự hóa theo tài khoản."""
        execute(conn, "INSERT IGNORE INTO game_wallets (account_id) VALUES (%s)", (account_id,))
        return _wallet(
            rows(
                conn,
                "SELECT account_id, balance, is_locked, locked_reason, locked_at, suspicious_count, suspicious_on"
                " FROM game_wallets WHERE account_id = %s" + (" FOR UPDATE" if lock else ""),
                (account_id,),
            )[0]
        )

    def set_balance(self, conn: Any, account_id: int, balance: int) -> None:
        execute(conn, "UPDATE game_wallets SET balance = %s WHERE account_id = %s", (balance, account_id))

    def set_suspicious(self, conn: Any, account_id: int, count: int, day) -> None:
        execute(
            conn,
            "UPDATE game_wallets SET suspicious_count = %s, suspicious_on = %s WHERE account_id = %s",
            (count, day, account_id),
        )

    def lock_wallet(self, conn: Any, account_id: int, reason: str, at) -> None:
        execute(
            conn,
            "UPDATE game_wallets SET is_locked = TRUE, locked_reason = %s, locked_at = %s WHERE account_id = %s",
            (reason[:200], _naive(at), account_id),
        )

    def unlock_wallet(self, conn: Any, account_id: int) -> None:
        execute(
            conn,
            "UPDATE game_wallets SET is_locked = FALSE, locked_reason = NULL, locked_at = NULL,"
            " suspicious_count = 0, suspicious_on = NULL WHERE account_id = %s",
            (account_id,),
        )

    def locked_wallets(self, conn: Any) -> list[dict]:
        result = rows(
            conn,
            "SELECT w.account_id, c.full_name AS customer_name, w.balance, w.locked_reason, w.locked_at"
            " FROM game_wallets AS w JOIN accounts AS a ON a.id = w.account_id"
            " JOIN customers AS c ON c.id = a.customer_id WHERE w.is_locked = TRUE ORDER BY w.locked_at DESC",
        )
        for r in result:
            r["locked_at"] = _utc(r["locked_at"])
        return result

    # ----- Phiên chơi ----------------------------------------------------------------
    def count_sessions(self, conn: Any, account_id: int, game_id: int, day) -> int:
        return int(
            rows(
                conn,
                "SELECT COUNT(*) AS total FROM game_sessions WHERE account_id = %s AND game_id = %s AND played_on = %s",
                (account_id, game_id, day),
            )[0]["total"]
        )

    def last_session_at(self, conn: Any, account_id: int):
        result = rows(
            conn,
            "SELECT MAX(created_at) AS last FROM game_sessions WHERE account_id = %s",
            (account_id,),
        )
        return _utc(result[0]["last"]) if result else None

    def insert_session(self, conn: Any, *, account_id, game_id, prize_index, prize_label, coins, played_on,
                       created_at) -> int:
        return int(
            execute(
                conn,
                "INSERT INTO game_sessions (account_id, game_id, prize_index, prize_label, coins, played_on, created_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (account_id, game_id, prize_index, prize_label, coins, played_on, _naive(created_at)),
            )
        )

    def account_sessions(self, conn: Any, account_id: int, limit: int = 10) -> list[GameSession]:
        return [
            _session(r)
            for r in rows(conn, _SESSION_SELECT + " WHERE g.account_id = %s ORDER BY g.created_at DESC, g.id DESC LIMIT %s",
                          (account_id, limit))
        ]

    def recent_sessions(self, conn: Any, game_id: int, limit: int = 20) -> list[GameSession]:
        return [
            _session(r)
            for r in rows(conn, _SESSION_SELECT + " WHERE g.game_id = %s ORDER BY g.created_at DESC, g.id DESC LIMIT %s",
                          (game_id, limit))
        ]

    def stats(self, conn: Any, game_id: int, day) -> dict:
        played = rows(
            conn,
            "SELECT COUNT(*) AS sessions, COUNT(DISTINCT account_id) AS players, COALESCE(SUM(coins), 0) AS coins"
            " FROM game_sessions WHERE game_id = %s AND played_on = %s",
            (game_id, day),
        )[0]
        redeemed = rows(
            conn,
            "SELECT COALESCE(SUM(-delta), 0) AS coins, COUNT(*) AS vouchers FROM game_coin_ledger"
            " WHERE reason = 'REDEEM' AND DATE(DATE_ADD(created_at, INTERVAL 7 HOUR)) = %s",
            (day,),
        )[0]
        return dict(sessions=int(played["sessions"]), players=int(played["players"]),
                    coins_awarded=int(played["coins"]), coins_redeemed=int(redeemed["coins"]),
                    vouchers=int(redeemed["vouchers"]))

    # ----- Sổ cái xu ------------------------------------------------------------------
    def insert_ledger(self, conn: Any, *, account_id, delta, reason: LedgerReason, ref, balance_after,
                      voucher_id, created_at) -> None:
        execute(
            conn,
            "INSERT INTO game_coin_ledger (account_id, delta, reason, ref, balance_after, voucher_id, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (account_id, delta, reason.value, ref, balance_after, voucher_id, _naive(created_at)),
        )

    def ledger_by_ref(self, conn: Any, reason: LedgerReason, ref: str) -> CoinLedgerEntry | None:
        result = rows(
            conn,
            "SELECT id, account_id, delta, reason, ref, balance_after, voucher_id, created_at"
            " FROM game_coin_ledger WHERE reason = %s AND ref = %s",
            (reason.value, ref),
        )
        return _ledger(result[0]) if result else None

    def account_ledger(self, conn: Any, account_id: int, limit: int = 10) -> list[CoinLedgerEntry]:
        return [
            _ledger(r)
            for r in rows(
                conn,
                "SELECT id, account_id, delta, reason, ref, balance_after, voucher_id, created_at"
                " FROM game_coin_ledger WHERE account_id = %s ORDER BY created_at DESC, id DESC LIMIT %s",
                (account_id, limit),
            )
        ]
