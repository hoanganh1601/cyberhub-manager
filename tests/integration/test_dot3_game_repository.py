"""Đợt 3 — GameRepository và ràng buộc migration 009 trên MySQL thật (rollback sau mỗi test)."""

from datetime import datetime, timezone

import pytest
from mysql.connector import Error as MySQLError

from cyberhub_manager.domain.game import DEFAULT_GAME, LedgerReason
from cyberhub_manager.repositories.game_repository import GameRepository

NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def game_db(db_conn, test_scenario):
    rows = test_scenario(db_conn)
    return db_conn, GameRepository(), rows


def test_default_wheel_is_seeded_by_migration(game_db):
    conn, repo, _ = game_db
    game = repo.get_game(conn, DEFAULT_GAME)

    assert game is not None and game.daily_limit >= 1
    assert len(game.prizes) >= 2 and [p.sort_order for p in game.prizes] == list(range(len(game.prizes)))


def test_wallet_is_created_once_and_balance_cannot_go_negative(game_db):
    conn, repo, rows = game_db
    assert repo.wallet(conn, rows.account_id, lock=True).balance == 0
    assert repo.wallet(conn, rows.account_id).balance == 0  # INSERT IGNORE không tạo ví thứ hai

    with pytest.raises(MySQLError):
        repo.set_balance(conn, rows.account_id, -1)


def test_sessions_counted_per_local_day(game_db):
    conn, repo, rows = game_db
    game = repo.get_game(conn, DEFAULT_GAME)
    day = NOW.date()
    for coins in (5, 0):
        repo.insert_session(conn, account_id=rows.account_id, game_id=game.id, prize_index=0, prize_label="x",
                            coins=coins, played_on=day, created_at=NOW)

    assert repo.count_sessions(conn, rows.account_id, game.id, day) == 2
    assert repo.last_session_at(conn, rows.account_id) == NOW
    assert len(repo.account_sessions(conn, rows.account_id)) == 2


def test_ledger_reference_is_unique_per_reason(game_db):
    conn, repo, rows = game_db
    repo.wallet(conn, rows.account_id)
    entry = dict(account_id=rows.account_id, delta=10, reason=LedgerReason.PLAY, ref=f"session:t{rows.token}",
                 balance_after=10, voucher_id=None, created_at=NOW)
    repo.insert_ledger(conn, **entry)

    with pytest.raises(MySQLError):
        repo.insert_ledger(conn, **entry)  # cùng phiên không được cộng xu hai lần
    assert repo.ledger_by_ref(conn, LedgerReason.PLAY, entry["ref"]).delta == 10


def test_lock_requires_reason_and_unlock_clears_it(game_db):
    conn, repo, rows = game_db
    repo.wallet(conn, rows.account_id)
    repo.lock_wallet(conn, rows.account_id, "Spam", NOW)
    assert repo.wallet(conn, rows.account_id).is_locked is True
    assert any(w["account_id"] == rows.account_id for w in repo.locked_wallets(conn))

    repo.unlock_wallet(conn, rows.account_id)
    wallet = repo.wallet(conn, rows.account_id)
    assert wallet.is_locked is False and wallet.locked_reason is None and wallet.suspicious_count == 0
