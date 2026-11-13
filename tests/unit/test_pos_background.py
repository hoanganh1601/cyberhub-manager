"""Tác vụ nền POS: vòng lặp worker, worker gửi thông báo (bản bộ nhớ) và kênh webhook. Không cần MySQL."""

import hashlib
import hmac
import json
import logging
import threading
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.menu import MenuOrderStatus
from cyberhub_manager.services.mocks import build_mock_services
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.notification import MemoryNotificationDeliveryRepository, no_transaction
from cyberhub_manager.services.notification_dispatcher import NotificationDispatcher
from cyberhub_manager.services.notification_sinks import (
    LogSink,
    PermanentDeliveryError,
    TransientDeliveryError,
    WebhookSink,
    sink_from_env,
)
from cyberhub_manager.worker import backoff_delay, run_worker

NOW = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)


# ----- Vòng lặp worker -------------------------------------------------------------------------------------------
def make_wait(stop, after):
    delays = []

    def wait(seconds):
        delays.append(seconds)
        if len(delays) >= after:
            stop.set()
        return stop.is_set()

    return wait, delays


def test_backoff_doubles_and_is_capped():
    assert [backoff_delay(30, n) for n in range(5)] == [30, 60, 120, 240, 300]
    assert backoff_delay(600, 3) == 600  # interval dài hơn trần thì giữ nguyên interval


def test_worker_survives_failures_backs_off_and_resets_after_success(caplog):
    stop = threading.Event()
    wait, delays = make_wait(stop, 5)
    outcomes = iter([RuntimeError("boom"), RuntimeError("boom"), {"sent": 2}, {"sent": 0}, {"sent": 0}])

    def job():
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    with caplog.at_level(logging.INFO):
        code = run_worker("test", job, interval=10, stop=stop, wait=wait)

    assert code == 0 and delays == [20, 40, 10, 10, 10]
    assert sum(r.levelno == logging.ERROR for r in caplog.records) == 2  # mỗi lỗi ghi log một lần, kèm traceback
    assert any("sent=2" in r.getMessage() for r in caplog.records)


def test_once_returns_exit_code_and_never_waits():
    def fail():
        raise RuntimeError("boom")

    def waiting(_):
        raise AssertionError("must not wait in --once")

    assert run_worker("t", lambda: {"x": 0}, interval=5, once=True, wait=waiting) == 0
    assert run_worker("t", fail, interval=5, once=True, wait=waiting) == 1


def test_worker_stops_before_first_run_when_asked():
    stop = threading.Event()
    stop.set()
    calls = []
    assert run_worker("t", lambda: calls.append(1), interval=5, stop=stop) == 0 and calls == []


# ----- Worker xử lý đơn hết hạn: một đơn lỗi không chặn các đơn khác ------------------------------------------------
def find_coca(bundle, customer):
    menu = bundle.menu.portal_menu(customer)
    return next(i for p in menu["pages"] for g in p["categories"] for i in g["items"] if i.name == "Coca")


def test_poison_order_does_not_block_other_expired_orders(caplog):
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, clock=clock)
    customer = bundle.portal.login("lethibinh", "demo123")
    item = find_coca(bundle, customer)
    first = bundle.menu.place_order(customer, [{"item_id": item.id, "quantity": 1}])
    second = bundle.menu.place_order(customer, [{"item_id": item.id, "quantity": 1}])
    clock.advance(minutes=20)

    repo = bundle.menu._repo
    original = repo.record_order_notification

    def flaky(conn, order, status, created_at):
        if order.id == first.id:
            raise RuntimeError("disk full")
        return original(conn, order, status, created_at)

    repo.record_order_notification = flaky
    with caplog.at_level(logging.ERROR):
        result = bundle.menu.maintain_holds()

    assert result == {"warned": 0, "expired": 1, "failed": 1}
    assert repo.get_order(None, second.id).status is MenuOrderStatus.CANCELLED
    assert repo.get_order(None, first.id).status is MenuOrderStatus.NEW  # rollback riêng, còn nguyên để thử lại
    assert any(str(first.id) in r.getMessage() for r in caplog.records)

    repo.record_order_notification = original  # sự cố hết: lượt sau xử lý nốt, không xử lý lại đơn đã hủy
    assert bundle.menu.maintain_holds() == {"warned": 0, "expired": 1, "failed": 0}
    assert bundle.menu.maintain_holds() == {"warned": 0, "expired": 0, "failed": 0}


# ----- Worker gửi thông báo -----------------------------------------------------------------------------------------
class FakeSink:
    channel = "fake"

    def __init__(self, *script):
        self.script = list(script)
        self.sent = []

    def deliver(self, message):
        self.sent.append(message)
        outcome = self.script.pop(0) if self.script else None
        if outcome is not None:
            raise outcome


def event(event_id, created_at=NOW, key=None):
    return dict(id=event_id, notification_key=key or f"menu-order:{event_id}:NEW", account_id=7, store_id=1,
                kind="MENU_ORDER_NEW", code=f"PC{event_id:02d}", amount=25_000, created_at=created_at)


def dispatcher(sink, events, clock, **options):
    repo = MemoryNotificationDeliveryRepository(events)
    return NotificationDispatcher(sink, repo, no_transaction, clock.now, **options), repo


def test_events_are_delivered_once_with_idempotency_key():
    clock = MockClock(NOW)
    sink = FakeSink()
    worker, repo = dispatcher(sink, [event(1), event(2)], clock)

    assert worker.run_once() == dict(queued=2, sent=2, retried=0, dead=0, unrecorded=0)
    assert worker.run_once() == dict(queued=0, sent=0, retried=0, dead=0, unrecorded=0)

    assert [m["idempotency_key"] for m in sink.sent] == ["menu-order:1:NEW", "menu-order:2:NEW"]
    assert sink.sent[0]["amount"] == 25_000 and sink.sent[0]["created_at"] == NOW.isoformat()
    assert "customer_name" not in sink.sent[0] and "phone" not in sink.sent[0]
    assert worker.stats() == {"SENT": 2}


def test_new_events_appear_in_later_runs_and_old_ones_are_skipped():
    clock = MockClock(NOW)
    old = event(1, created_at=NOW - timedelta(days=3))
    events = [old]
    sink = FakeSink()
    worker, _ = dispatcher(sink, events, clock)

    assert worker.run_once()["queued"] == 0  # lịch sử cũ ngoài lookback không bị xả ra kênh mới
    events.append(event(2))
    assert worker.run_once()["sent"] == 1 and [m["id"] for m in sink.sent] == [2]


def test_transient_failure_retries_with_doubling_backoff_then_succeeds():
    clock = MockClock(NOW)
    sink = FakeSink(TransientDeliveryError("HTTP 503"), TransientDeliveryError("HTTP 503"))
    worker, repo = dispatcher(sink, [event(1)], clock, base_delay_seconds=30)

    assert worker.run_once()["retried"] == 1
    assert repo.deliveries[0]["last_error"] == "HTTP 503" and repo.deliveries[0]["status"] == "PENDING"
    assert worker.run_once()["sent"] == 0 and len(sink.sent) == 1  # chưa đến hạn: không gửi lại ngay

    clock.advance(seconds=30)
    assert worker.run_once()["retried"] == 1
    clock.advance(seconds=59)
    assert worker.run_once()["sent"] == 0  # lần hai chờ 60 giây
    clock.advance(seconds=1)
    assert worker.run_once()["sent"] == 1 and len(sink.sent) == 3
    assert repo.deliveries[0]["attempts"] == 3 and repo.deliveries[0]["last_error"] is None


def test_gives_up_after_max_attempts_and_never_resends_a_dead_delivery():
    clock = MockClock(NOW)
    sink = FakeSink(*[TransientDeliveryError("timeout")] * 5)
    worker, repo = dispatcher(sink, [event(1)], clock, max_attempts=3, base_delay_seconds=10)

    worker.run_once()
    clock.advance(seconds=10)
    worker.run_once()
    clock.advance(seconds=20)
    assert worker.run_once()["dead"] == 1
    clock.advance(hours=5)
    assert worker.run_once() == dict(queued=0, sent=0, retried=0, dead=0, unrecorded=0)
    assert len(sink.sent) == 3 and worker.stats() == {"DEAD": 1}


def test_permanent_error_is_dead_immediately():
    clock = MockClock(NOW)
    worker, repo = dispatcher(FakeSink(PermanentDeliveryError("HTTP 400")), [event(1)], clock)
    assert worker.run_once()["dead"] == 1
    assert repo.deliveries[0]["last_error"] == "HTTP 400"


def test_unexpected_sink_exception_is_logged_and_retried(caplog):
    clock = MockClock(NOW)
    worker, repo = dispatcher(FakeSink(KeyError("secret-token")), [event(1)], clock)
    with caplog.at_level(logging.ERROR):
        assert worker.run_once()["retried"] == 1
    assert repo.deliveries[0]["last_error"] == "unexpected KeyError"  # không lưu nội dung lỗi (có thể chứa bí mật)
    assert any(r.exc_info for r in caplog.records)


def test_one_bad_delivery_does_not_stop_the_batch():
    clock = MockClock(NOW)
    sink = FakeSink(PermanentDeliveryError("HTTP 410"), None)
    worker, _ = dispatcher(sink, [event(1), event(2)], clock)
    assert worker.run_once() == dict(queued=2, sent=1, retried=0, dead=1, unrecorded=0)


def test_crash_after_send_redelivers_with_same_key_after_lease_expires():
    clock = MockClock(NOW)
    sink = FakeSink()
    worker, repo = dispatcher(sink, [event(1)], clock, lease_seconds=60)
    # Mô phỏng worker chết sau khi gửi, trước khi ghi kết quả: dòng đã bị thuê nhưng chưa SENT.
    repo.enqueue_missing(None, "fake", NOW, NOW - timedelta(hours=1), 10)
    repo.claim(None, "fake", NOW, NOW + timedelta(seconds=60), 6, 10)
    sink.deliver(dict(idempotency_key="menu-order:1:NEW"))

    assert worker.run_once()["sent"] == 0  # còn trong thời hạn thuê
    clock.advance(seconds=61)
    assert worker.run_once()["sent"] == 1
    assert [m["idempotency_key"] for m in sink.sent] == ["menu-order:1:NEW"] * 2  # giao ít nhất một lần


def test_expired_lease_on_last_attempt_becomes_dead_instead_of_resending():
    clock = MockClock(NOW)
    sink = FakeSink()
    worker, repo = dispatcher(sink, [event(1)], clock, max_attempts=1, lease_seconds=60)
    repo.enqueue_missing(None, "fake", NOW, NOW - timedelta(hours=1), 10)
    repo.claim(None, "fake", NOW, NOW + timedelta(seconds=60), 1, 10)

    clock.advance(seconds=61)
    assert worker.run_once()["sent"] == 0 and sink.sent == []
    assert repo.deliveries[0]["status"] == "DEAD"


def test_failure_while_recording_is_counted_and_retried_after_lease():
    clock = MockClock(NOW)
    sink = FakeSink()
    worker, repo = dispatcher(sink, [event(1)], clock, lease_seconds=60)
    original = repo.mark_sent
    repo.mark_sent = lambda *a: (_ for _ in ()).throw(RuntimeError("db down"))

    assert worker.run_once()["unrecorded"] == 1
    repo.mark_sent = original
    clock.advance(seconds=61)
    assert worker.run_once()["sent"] == 1


def test_dispatcher_rejects_bad_configuration():
    repo = MemoryNotificationDeliveryRepository([])
    with pytest.raises(ValueError):
        NotificationDispatcher(FakeSink(), repo)  # thiếu transaction_factory
    for options in (dict(max_attempts=0), dict(lease_seconds=1), dict(base_delay_seconds=100, max_delay_seconds=10),
                    dict(lookback_hours=0)):
        with pytest.raises(ValueError):
            NotificationDispatcher(FakeSink(), repo, no_transaction, **options)
    with pytest.raises(ValueError):
        NotificationDispatcher(FakeSink(), repo, no_transaction).run_once(limit=0)


def test_events_written_by_pos_flow_reach_the_sink():
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, clock=clock)
    customer = bundle.portal.login("lethibinh", "demo123")
    placed = bundle.menu.place_order(customer, [{"item_id": find_coca(bundle, customer).id, "quantity": 1}])
    sink = FakeSink()
    worker = NotificationDispatcher(sink, MemoryNotificationDeliveryRepository(bundle.menu._repo.p1.order_notifications),
                                    no_transaction, clock.now)

    assert worker.run_once()["sent"] >= 1
    assert f"menu-order:{placed.id}:NEW" in {m["idempotency_key"] for m in sink.sent}


# ----- Kênh gửi ------------------------------------------------------------------------------------------------------
class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n):
        return b""


class FakeOpener:
    def __init__(self, result=None):
        self.result, self.requests = result, []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.result, BaseException):
            raise self.result
        return FakeResponse()


def message():
    return dict(idempotency_key="menu-order:1:NEW", kind="MENU_ORDER_NEW", code="PC01", amount=5)


def test_webhook_signs_body_and_sends_idempotency_key():
    opener = FakeOpener()
    sink = WebhookSink("https://hooks.example.com/in", "s3cret", clock=lambda: 1_700_000_000, opener=opener)
    sink.deliver(message())

    request, timeout = opener.requests[0]
    assert timeout == 5 and request.get_method() == "POST"
    assert request.get_header("Idempotency-key") == "menu-order:1:NEW"
    expected = hmac.new(b"s3cret", b"1700000000." + request.data, hashlib.sha256).hexdigest()
    assert request.get_header("X-cyberhub-signature") == f"sha256={expected}"
    assert json.loads(request.data)["code"] == "PC01"


@pytest.mark.parametrize("code,error", [(500, TransientDeliveryError), (503, TransientDeliveryError),
                                        (429, TransientDeliveryError), (408, TransientDeliveryError),
                                        (400, PermanentDeliveryError), (404, PermanentDeliveryError),
                                        (302, PermanentDeliveryError)])
def test_webhook_classifies_http_status(code, error):
    opener = FakeOpener(urllib.error.HTTPError("https://x", code, "msg", {}, None))
    with pytest.raises(error, match=f"HTTP {code}"):
        WebhookSink("https://hooks.example.com/in", opener=opener).deliver(message())


def test_webhook_network_errors_are_transient_and_do_not_leak_details():
    opener = FakeOpener(urllib.error.URLError("secret.internal:5432 refused"))
    with pytest.raises(TransientDeliveryError) as info:
        WebhookSink("https://hooks.example.com/in", opener=opener).deliver(message())
    assert "secret.internal" not in str(info.value)
    with pytest.raises(TransientDeliveryError):
        WebhookSink("https://hooks.example.com/in", opener=FakeOpener(TimeoutError())).deliver(message())


@pytest.mark.parametrize("url", ["http://hooks.example.com/in", "ftp://x.com/a", "https:///nohost", "hooks.example.com"])
def test_webhook_rejects_insecure_or_malformed_urls(url):
    with pytest.raises(ValueError):
        WebhookSink(url)


def test_webhook_allows_plain_http_only_for_localhost():
    WebhookSink("http://localhost:9000/hook")
    WebhookSink("http://127.0.0.1:9000/hook")


def test_sink_from_env_selection_and_errors():
    assert isinstance(sink_from_env({}), LogSink)
    assert isinstance(sink_from_env({"CYBERHUB_NOTIFY_SINK": " LOG "}), LogSink)
    hook = sink_from_env({"CYBERHUB_NOTIFY_SINK": "webhook", "CYBERHUB_NOTIFY_WEBHOOK_URL": "https://h.example.com/x"})
    assert isinstance(hook, WebhookSink)
    with pytest.raises(ValueError):
        sink_from_env({"CYBERHUB_NOTIFY_SINK": "webhook"})
    with pytest.raises(ValueError):
        sink_from_env({"CYBERHUB_NOTIFY_SINK": "sms"})
