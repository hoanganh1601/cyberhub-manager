"""Durable atomic request quotas, audit privacy and identity namespace isolation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from uuid import uuid4

import pytest

from cyberhub_manager.ai.audit import AssistantAuditEvent
from cyberhub_manager.ai.models import AIAccessContext
from cyberhub_manager.ai.policy_store import (
    AssistantLimits, AssistantQuotaExceeded, SQLiteAssistantPolicyStore,
)

NOW = datetime(2026, 11, 9, 9, 0, 10, tzinfo=timezone.utc)
STAFF = AIAccessContext(1, "STAFF", (1,))


def reserve(store, access=STAFF, now=NOW):
    key = uuid4().hex
    store.reserve(key, access, now=now)
    return key


def test_persistent_quota_survives_new_store_and_identity_changes(tmp_path):
    path = tmp_path / "assistant.sqlite3"
    limits = AssistantLimits(per_minute=1)
    first = SQLiteAssistantPolicyStore(path, limits=limits)
    key = reserve(first)
    second = SQLiteAssistantPolicyStore(path, limits=limits)
    assert second.result(key) == "ACCEPTED"
    for scope in (AIAccessContext(1, "ADMIN", (99,), "en"), STAFF):
        with pytest.raises(AssistantQuotaExceeded) as exc:
            reserve(second, scope)
        assert exc.value.retry_after == 50
    # Customer accounts and employee IDs are different identity namespaces.
    reserve(second, AIAccessContext(1, "CUSTOMER", ()))
    reserve(second, now=NOW + timedelta(minutes=1))


def test_daily_actor_and_global_limits_do_not_reset_on_new_instance(tmp_path):
    path = tmp_path / "audit.sqlite3"
    limits = AssistantLimits(per_minute=10, per_day=1, global_per_day=2)
    store = SQLiteAssistantPolicyStore(path, limits=limits)
    reserve(store)
    with pytest.raises(AssistantQuotaExceeded):
        reserve(store, now=NOW + timedelta(minutes=2))
    reserve(store, AIAccessContext(2, "STAFF", (1,)))
    store = SQLiteAssistantPolicyStore(path, limits=limits)
    with pytest.raises(AssistantQuotaExceeded):
        reserve(store, AIAccessContext(3, "STAFF", (1,)))
    reserve(store, now=NOW + timedelta(days=1))


def test_parallel_instances_admit_at_most_configured_limit(tmp_path):
    path = tmp_path / "audit.sqlite3"
    stores = [SQLiteAssistantPolicyStore(path, limits=AssistantLimits(per_minute=3)) for _ in range(8)]

    def attempt(store):
        try:
            reserve(store)
            return True
        except AssistantQuotaExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(attempt, stores))
    assert results.count(True) == 3
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM assistant_requests").fetchone() == (3,)


def test_final_audit_is_bound_to_admitted_identity_and_keeps_only_metadata(tmp_path):
    store = SQLiteAssistantPolicyStore(tmp_path / "audit.sqlite3")
    key = reserve(store)
    event = AssistantAuditEvent(key, 1, "STAFF", (1,), "vi", ("chunk-123",), "ANSWERED", 20, NOW)
    wrong = AssistantAuditEvent(key, 2, "STAFF", (1,), "vi", (), "ANSWERED", 20, NOW)
    with pytest.raises(RuntimeError):
        store.record(wrong)
    assert store.result(key) == "ACCEPTED"
    store.record(event)
    with pytest.raises(RuntimeError):
        store.record(event)
    with sqlite3.connect(store.path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(assistant_requests)")]
        assert not set(columns) & {"question", "prompt", "answer", "password", "content"}
        assert json.loads(conn.execute("SELECT chunk_ids FROM assistant_requests").fetchone()[0]) == ["chunk-123"]
    store.suppress(key)
    assert store.result(key) == "ACCESS_CHANGED"
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT chunk_ids FROM assistant_requests").fetchone() == ("[]",)


def test_duplicate_request_rolls_back_and_retention_removes_only_old_metadata(tmp_path):
    store = SQLiteAssistantPolicyStore(tmp_path / "audit.sqlite3", limits=AssistantLimits(retention_days=2))
    key = reserve(store)
    with pytest.raises(sqlite3.IntegrityError):
        store.reserve(key, STAFF, now=NOW)
    reserve(store, now=NOW + timedelta(days=4))
    assert store.result(key) is None
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM assistant_requests").fetchone() == (1,)


def test_store_rejects_relative_or_symlink_paths_and_naive_time(tmp_path):
    with pytest.raises(ValueError):
        SQLiteAssistantPolicyStore("relative.sqlite3")
    target = tmp_path / "audit.sqlite3"
    store = SQLiteAssistantPolicyStore(target)
    link = tmp_path / "link.sqlite3"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable for this OS/user")
    with pytest.raises(ValueError):
        SQLiteAssistantPolicyStore(link)
    with pytest.raises(ValueError):
        reserve(store, now=NOW.replace(tzinfo=None))


@pytest.mark.parametrize("value", [0, -1, True, "10", 1.5])
def test_invalid_limits_rejected(value):
    with pytest.raises(ValueError):
        AssistantLimits(per_minute=value)
