"""Sổ gửi thông báo (migration 021) trên MySQL thật: thuê lô, retry, DEAD, chạy lại không trùng. Rollback sau mỗi test."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from mysql.connector import Error as MySQLError

from cyberhub_manager.repositories.notification_repository import NotificationDeliveryRepository
from cyberhub_manager.services.notification_dispatcher import NotificationDispatcher
from cyberhub_manager.services.notification_sinks import PermanentDeliveryError, TransientDeliveryError

# Sự kiện test nằm ở năm 2099 để không lẫn với dữ liệu thật đã commit trong database test.
EVENT_TIME = datetime(2099, 1, 1, 9, 0, tzinfo=timezone.utc)
SINCE = datetime(2098, 1, 1, tzinfo=timezone.utc)
NOW = EVENT_TIME + timedelta(minutes=1)


def _insert(conn, sql, params):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.lastrowid
    finally:
        cursor.close()


def _delivery(conn, delivery_id):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM notification_deliveries WHERE id = %s", (delivery_id,))
        return cursor.fetchone()
    finally:
        cursor.close()


@pytest.fixture
def ledger(db_conn, test_scenario):
    rows = test_scenario(db_conn)
    channel = f"t{rows.token}"
    event_ids = [
        _insert(
            db_conn,
            "INSERT INTO customer_notification_events"
            " (notification_key, account_id, store_id, kind, code, amount, created_at)"
            " VALUES (%s, %s, %s, 'MENU_ORDER_NEW', %s, 25000, %s)",
            (f"test-{rows.token}-{n}", rows.account_id, rows.store_id, f"PC{n:02d}", EVENT_TIME.replace(tzinfo=None)),
        )
        for n in (1, 2)
    ]
    return db_conn, NotificationDeliveryRepository(), channel, event_ids, rows


def test_enqueue_is_idempotent_and_respects_the_lookback(ledger):
    conn, repo, channel, events, _ = ledger

    assert repo.enqueue_missing(conn, channel, NOW, SINCE, 10) == 2
    assert repo.enqueue_missing(conn, channel, NOW, SINCE, 10) == 0
    assert repo.enqueue_missing(conn, "other", NOW, EVENT_TIME + timedelta(days=1), 10) == 0  # sự kiện quá cũ
    assert repo.counts(conn, channel) == {"PENDING": 2}


def test_claim_leases_due_rows_once_and_returns_event_data(ledger):
    conn, repo, channel, events, rows = ledger
    repo.enqueue_missing(conn, channel, NOW, SINCE, 10)

    claimed = repo.claim(conn, channel, NOW, NOW + timedelta(minutes=5), 6, 10)

    assert [c["event_id"] for c in claimed] == events and all(c["attempts"] == 1 for c in claimed)
    assert claimed[0]["notification_key"] == f"test-{rows.token}-1" and claimed[0]["amount"] == 25_000
    assert claimed[0]["created_at"].tzinfo is not None and claimed[0]["account_id"] == rows.account_id
    assert repo.claim(conn, channel, NOW, NOW + timedelta(minutes=5), 6, 10) == []  # còn hạn thuê

    again = repo.claim(conn, channel, NOW + timedelta(minutes=6), NOW + timedelta(minutes=11), 6, 10)
    assert [c["attempts"] for c in again] == [2, 2]  # worker chết: hết hạn thuê thì nhận lại


def test_claim_respects_next_attempt_and_batch_limit(ledger):
    conn, repo, channel, events, _ = ledger
    repo.enqueue_missing(conn, channel, NOW + timedelta(hours=1), SINCE, 10)

    assert repo.claim(conn, channel, NOW, NOW + timedelta(minutes=5), 6, 10) == []  # chưa đến hạn
    one = repo.claim(conn, channel, NOW + timedelta(hours=1), NOW + timedelta(hours=2), 6, 1)
    assert [c["event_id"] for c in one] == events[:1]


def test_outcomes_only_apply_to_leased_rows(ledger):
    conn, repo, channel, events, _ = ledger
    repo.enqueue_missing(conn, channel, NOW, SINCE, 10)
    first, second = repo.claim(conn, channel, NOW, NOW + timedelta(minutes=5), 6, 10)

    assert repo.mark_sent(conn, first["delivery_id"], NOW) is True
    assert repo.mark_sent(conn, first["delivery_id"], NOW) is False  # đã SENT: gọi lại không đổi gì
    assert repo.mark_failed(conn, first["delivery_id"], "x", None) is False

    retry_at = NOW + timedelta(seconds=90)
    assert repo.mark_failed(conn, second["delivery_id"], "HTTP 503", retry_at) is True
    row = _delivery(conn, second["delivery_id"])
    assert (row["status"], row["last_error"], row["next_attempt_at"], row["locked_until"]) == (
        "PENDING", "HTTP 503", retry_at.replace(tzinfo=None), None)
    assert _delivery(conn, first["delivery_id"])["sent_at"] == NOW.replace(tzinfo=None)

    [again] = repo.claim(conn, channel, retry_at, retry_at + timedelta(minutes=5), 6, 10)
    assert again["delivery_id"] == second["delivery_id"] and again["attempts"] == 2
    assert repo.mark_failed(conn, again["delivery_id"], "x" * 400, None) is True
    dead = _delivery(conn, again["delivery_id"])
    assert dead["status"] == "DEAD" and len(dead["last_error"]) == 255
    assert repo.counts(conn, channel) == {"SENT": 1, "DEAD": 1}


def test_lease_expired_on_the_last_attempt_goes_dead(ledger):
    conn, repo, channel, events, _ = ledger
    repo.enqueue_missing(conn, channel, NOW, SINCE, 10)
    claimed = repo.claim(conn, channel, NOW, NOW + timedelta(minutes=5), 1, 10)

    assert repo.claim(conn, channel, NOW + timedelta(minutes=6), NOW + timedelta(minutes=11), 1, 10) == []
    assert {_delivery(conn, c["delivery_id"])["status"] for c in claimed} == {"DEAD"}


def test_database_rejects_bad_status_duplicate_pair_and_unknown_event(ledger):
    conn, repo, channel, events, _ = ledger
    insert = "INSERT INTO notification_deliveries (event_id, channel, status, next_attempt_at) VALUES (%s, %s, %s, %s)"
    _insert(conn, insert, (events[0], channel, "PENDING", NOW.replace(tzinfo=None)))
    with pytest.raises(MySQLError):
        _insert(conn, insert, (events[0], channel, "PENDING", NOW.replace(tzinfo=None)))
    with pytest.raises(MySQLError):
        _insert(conn, insert, (events[1], channel, "LOST", NOW.replace(tzinfo=None)))
    with pytest.raises(MySQLError):
        _insert(conn, insert, (events[1] + 10_000_000, channel, "PENDING", NOW.replace(tzinfo=None)))


class Script:
    def __init__(self, *outcomes):
        self.outcomes, self.sent = list(outcomes), []

    def deliver(self, message):
        self.sent.append(message["idempotency_key"])
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome


def test_dispatcher_end_to_end_on_mysql(ledger):
    conn, repo, channel, events, rows = ledger
    clock = [NOW]

    @contextmanager
    def same_connection():  # dùng chung transaction của test để rollback dọn sạch
        yield conn

    sink = Script(TransientDeliveryError("HTTP 503"), PermanentDeliveryError("HTTP 400"))
    sink.channel = channel
    worker = NotificationDispatcher(sink, repo, same_connection, lambda: clock[0], base_delay_seconds=30,
                                    lookback_hours=24 * 30)
    # lookback_hours tính từ now (năm 2099) nên cả hai sự kiện test đều nằm trong khoảng.

    assert worker.run_once() == dict(queued=2, sent=0, retried=1, dead=1, unrecorded=0)
    assert worker.run_once()["sent"] == 0  # event thứ nhất chưa đến hạn retry; event thứ hai đã DEAD
    clock[0] += timedelta(seconds=30)
    assert worker.run_once() == dict(queued=0, sent=1, retried=0, dead=0, unrecorded=0)
    clock[0] += timedelta(hours=1)
    assert worker.run_once() == dict(queued=0, sent=0, retried=0, dead=0, unrecorded=0)

    assert sink.sent == [f"test-{rows.token}-1", f"test-{rows.token}-2", f"test-{rows.token}-1"]
    assert worker.stats() == {"SENT": 1, "DEAD": 1}
