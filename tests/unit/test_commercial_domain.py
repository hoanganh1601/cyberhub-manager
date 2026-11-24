import pytest

from cyberhub_manager.domain.commercial import (
    CLIENT_EVENT_TYPES,
    SAFE_IFRAME_SANDBOX,
    RevenueModel,
    callback_signature,
    partner_event_signature,
    revenue_amount,
    validate_embed_url,
    verify_callback_signature,
    verify_partner_event_signature,
)
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import ValidationError
from cyberhub_manager.domain.policies import Permission, can


def test_external_game_origin_and_sandbox_are_restricted():
    url, origin = validate_embed_url("https://games.example.vn/play?id=42")

    assert url == "https://games.example.vn/play?id=42"
    assert origin == "https://games.example.vn"
    assert SAFE_IFRAME_SANDBOX == "allow-scripts allow-pointer-lock"
    for forbidden in ("allow-same-origin", "allow-forms", "allow-popups", "allow-top-navigation"):
        assert forbidden not in SAFE_IFRAME_SANDBOX


@pytest.mark.parametrize(
    "url",
    [
        "http://games.example.vn/play",
        "https://user:secret@games.example.vn/play",
        "https://games.example.vn:8443/play",
        "https://games.example.vn:not-a-port/play",
        "not-a-url",
        None,
    ],
)
def test_external_game_rejects_unsafe_urls(url):
    with pytest.raises(ValidationError):
        validate_embed_url(url)


def test_partner_callback_signature_is_canonical_and_tamper_evident():
    signature = callback_signature("secret", "launch-token", "event-0001", "complete")

    assert verify_callback_signature(
        "secret", "launch-token", "event-0001", "complete", signature
    )
    assert not verify_callback_signature(
        "secret", "launch-token", "event-0002", "complete", signature
    )
    assert not verify_callback_signature(
        "wrong", "launch-token", "event-0001", "complete", signature
    )


def test_ad_event_signature_is_namespaced_and_tamper_evident():
    signature = partner_event_signature(
        "secret", "PORTAL_BANNER_01", "event-0001", "IMPRESSION"
    )

    assert verify_partner_event_signature(
        "secret", "PORTAL_BANNER_01", "event-0001", "IMPRESSION", signature
    )
    assert not verify_partner_event_signature(
        "secret", "PORTAL_BANNER_02", "event-0001", "IMPRESSION", signature
    )
    assert not verify_partner_event_signature(
        "secret", "PORTAL_BANNER_01", "event-0001", "CLICK", signature
    )
    # A game-completion signature cannot be replayed as an ad delivery event.
    assert signature != callback_signature(
        "secret", "PORTAL_BANNER_01", "event-0001", "IMPRESSION"
    )


def test_revenue_models_use_integer_vnd_rules():
    assert revenue_amount(RevenueModel.CPM, 1_999, 50_000) == 99_950
    assert revenue_amount(RevenueModel.CPC, 7, 2_000) == 14_000
    assert revenue_amount(RevenueModel.CPA, 3, 25_000) == 75_000
    assert revenue_amount(RevenueModel.FIXED, 1, 5_000_000) == 5_000_000
    assert revenue_amount(RevenueModel.FIXED, 0, 5_000_000) == 0


def test_client_cannot_claim_completion_and_commercial_permissions_are_explicit():
    assert CLIENT_EVENT_TYPES == {"IMPRESSION", "START", "CLICK"}
    assert can(Role.MANAGER, Permission.COMMERCIAL_VIEW)
    assert not can(Role.MANAGER, Permission.COMMERCIAL_MANAGE)
    assert not can(Role.MANAGER, Permission.COMMERCIAL_RECONCILE)
    assert can(Role.ADMIN, Permission.COMMERCIAL_MANAGE)
    assert can(Role.ADMIN, Permission.COMMERCIAL_RECONCILE)
    assert not can(Role.STAFF, Permission.COMMERCIAL_VIEW)
