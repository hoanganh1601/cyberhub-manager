"""Đợt 4 — AdRepository và ràng buộc migration 010 trên MySQL thật (rollback sau mỗi test)."""

import secrets
from datetime import datetime, timedelta, timezone

import pytest
from mysql.connector import Error as MySQLError

from cyberhub_manager.domain.ad import AdMode, AdRewardType, AdStatus
from cyberhub_manager.repositories.ad_repository import AdRepository
from cyberhub_manager.repositories.game_repository import GameRepository

NOW = datetime.now(timezone.utc).replace(microsecond=0)
DAY = NOW.date()


@pytest.fixture
def ad_db(db_conn, test_scenario):
    rows = test_scenario(db_conn)
    repo = AdRepository()

    def start(token=None, seconds=15):
        token = token or secrets.token_hex(16)
        repo.insert_event(db_conn, token=token, account_id=rows.account_id, creative_id=None, provider=AdMode.HOUSE,
                          reward_type=AdRewardType.EXTRA_SPIN, reward_amount=1, played_on=DAY, issued_at=NOW,
                          min_complete_at=NOW + timedelta(seconds=seconds), expires_at=NOW + timedelta(hours=1))
        return repo.get_event(db_conn, token, lock=True)

    return db_conn, repo, rows, start


def test_settings_and_seeded_creatives(ad_db):
    conn, repo, _, _ = ad_db
    settings = repo.settings(conn)

    assert settings.daily_cap >= 1 and settings.mode in (AdMode.HOUSE, AdMode.NETWORK)
    assert {c.code for c in repo.creatives(conn)} >= {"COMBO_NIGHT", "VIP_ROOM", "VOUCHER_WEEK"}


def test_event_finishes_once_and_counts_as_extra_spin(ad_db):
    conn, repo, rows, start = ad_db
    event = start()

    assert repo.finish_event(conn, event.id, status=AdStatus.COMPLETED, completed_at=NOW) is True
    assert repo.finish_event(conn, event.id, status=AdStatus.COMPLETED, completed_at=NOW) is False
    assert repo.count_events(conn, rows.account_id, DAY, AdStatus.COMPLETED) == 1
    assert GameRepository().count_ad_spins(conn, rows.account_id, DAY) == 1


def test_token_and_provider_transaction_are_unique(ad_db):
    conn, repo, _, start = ad_db
    first = start()
    with pytest.raises(MySQLError):
        start(token=first.token)  # token chỉ dùng một lần

    second = start()
    repo.finish_event(conn, first.id, status=AdStatus.COMPLETED, completed_at=NOW, txn_id="net-txn-1")
    with pytest.raises(MySQLError):
        repo.finish_event(conn, second.id, status=AdStatus.COMPLETED, completed_at=NOW, txn_id="net-txn-1")


def test_supersede_and_rejection_require_reason(ad_db):
    conn, repo, rows, start = ad_db
    event = start()
    repo.supersede_issued(conn, rows.account_id)
    assert repo.get_event(conn, event.token).reject_reason == "SUPERSEDED"

    other = start()
    with pytest.raises(MySQLError):  # REJECTED mà không có lý do bị CHECK chặn
        repo.finish_event(conn, other.id, status=AdStatus.REJECTED, reason=None)


def test_daily_stats_split_valid_rejected(ad_db):
    conn, repo, _, start = ad_db
    ok, bad = start(), start()
    repo.finish_event(conn, ok.id, status=AdStatus.COMPLETED, completed_at=NOW)
    repo.finish_event(conn, bad.id, status=AdStatus.REJECTED, reason="TOO_EARLY")

    today = next(r for r in repo.daily_stats(conn, DAY, NOW) if r["day"] == DAY)
    assert today["completed"] >= 1 and today["rejected"] >= 1 and today["spins"] >= 1
