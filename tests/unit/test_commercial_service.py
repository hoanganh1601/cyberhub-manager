from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.commercial import (
    callback_signature,
    hash_launch_token,
    partner_event_signature,
)
from cyberhub_manager.domain.exceptions import PermissionDeniedError, ValidationError
from cyberhub_manager.application.services.commercial_service import CommercialService


NOW = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
TOKEN = "a" * 43
PROVIDER_EVENT_ID = "partner-event-0001"
SECRET_REF = "CYBERHUB_PARTNER_ACME_SECRET"


class FakeCommercialRepository:
    def __init__(self):
        self.events = []
        self.grants = []
        self.completed = []
        self.existing = None

    def play_session(self, _conn, token_hash, *, lock=False):
        assert token_hash == hash_launch_token(TOKEN)
        assert lock is True
        return {
            "id": 11,
            "placement_id": 22,
            "campaign_id": 33,
            "account_id": 44,
            "callback_secret_ref": SECRET_REF,
            "status": "ISSUED",
            "expires_at": (NOW + timedelta(minutes=5)).replace(tzinfo=None),
            "partner_status": "ACTIVE",
            "campaign_status": "ACTIVE",
            "contract_status": "ACTIVE",
            "placement_status": "ACTIVE",
            "reward_type": "COINS",
            "reward_amount": 25,
        }

    def event_by_provider_id(self, _conn, provider_event_id):
        assert provider_event_id == PROVIDER_EVENT_ID
        return self.existing

    def callback_placement(self, _conn, code, now, *, lock=False):
        assert code == "PORTAL_BANNER_01"
        assert now == NOW.replace(tzinfo=None)
        assert lock is True
        return {
            "id": 22,
            "campaign_id": 33,
            "callback_secret_ref": SECRET_REF,
        }

    def insert_event(self, _conn, values):
        self.events.append(values)
        return 55

    def complete_play_session(self, _conn, session_id, completed_at):
        self.completed.append((session_id, completed_at))
        return 1

    def create_reward_grant(self, _conn, event_id, account_id, reward_type, reward_amount):
        self.grants.append((event_id, account_id, reward_type, reward_amount))
        return 66


@contextmanager
def transaction():
    yield object()


def build_service(repo):
    return CommercialService(
        repo=repo,
        transaction_factory=transaction,
        clock=lambda: NOW,
        environment={SECRET_REF: "partner-secret"},
    )


def test_verified_callback_creates_server_event_and_pending_reward_outbox():
    repo = FakeCommercialRepository()
    service = build_service(repo)
    signature = callback_signature(
        "partner-secret", TOKEN, PROVIDER_EVENT_ID, "complete"
    )

    result = service.verify_game_callback(
        TOKEN, PROVIDER_EVENT_ID, "complete", signature
    )

    assert result == {
        "event_id": 55,
        "reward_grant_id": 66,
        "reward_status": "PENDING",
        "idempotent": False,
    }
    assert repo.events[0][4:9] == (
        "COMPLETE",
        f"ssv:{PROVIDER_EVENT_ID}",
        PROVIDER_EVENT_ID,
        "SSV",
        True,
    )
    assert repo.completed[0][0] == 11
    assert repo.grants == [(55, 44, "COINS", 25)]


def test_callback_rejects_bad_signature_before_writing_any_reward():
    repo = FakeCommercialRepository()

    with pytest.raises(PermissionDeniedError):
        build_service(repo).verify_game_callback(
            TOKEN, PROVIDER_EVENT_ID, "complete", "0" * 64
        )

    assert repo.events == []
    assert repo.completed == []
    assert repo.grants == []


def test_replayed_provider_event_is_idempotent():
    repo = FakeCommercialRepository()
    repo.existing = {
        "id": 55,
        "play_session_id": 11,
        "grant_id": 66,
        "grant_status": "PENDING",
    }
    signature = callback_signature(
        "partner-secret", TOKEN, PROVIDER_EVENT_ID, "complete"
    )

    result = build_service(repo).verify_game_callback(
        TOKEN, PROVIDER_EVENT_ID, "complete", signature
    )

    assert result["idempotent"] is True
    assert result["reward_grant_id"] == 66
    assert repo.events == []
    assert repo.grants == []


def test_browser_cannot_submit_complete_event():
    service = build_service(FakeCommercialRepository())

    with pytest.raises(ValidationError) as exc_info:
        service.record_client_event(
            object(), "GAME_CENTER_01", 1, "COMPLETE", "event-key-0001"
        )

    assert "event_type" in exc_info.value.field_errors


def test_signed_partner_event_is_server_verified_and_revenue_eligible():
    repo = FakeCommercialRepository()
    signature = partner_event_signature(
        "partner-secret",
        "PORTAL_BANNER_01",
        PROVIDER_EVENT_ID,
        "IMPRESSION",
    )

    result = build_service(repo).verify_partner_event_callback(
        "PORTAL_BANNER_01",
        PROVIDER_EVENT_ID,
        "IMPRESSION",
        signature,
    )

    assert result == {
        "event_id": 55,
        "accepted": True,
        "idempotent": False,
    }
    assert repo.events[0][4:9] == (
        "IMPRESSION",
        f"server:{PROVIDER_EVENT_ID}",
        PROVIDER_EVENT_ID,
        "SERVER",
        True,
    )
    assert repo.completed == []
    assert repo.grants == []


def test_signed_partner_event_rejects_bad_signature_before_insert():
    repo = FakeCommercialRepository()

    with pytest.raises(PermissionDeniedError):
        build_service(repo).verify_partner_event_callback(
            "PORTAL_BANNER_01",
            PROVIDER_EVENT_ID,
            "CLICK",
            "0" * 64,
        )

    assert repo.events == []
