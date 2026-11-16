"""Commercial partner rules shared by service, callback adapter and tests."""

from __future__ import annotations

import hashlib
import hmac
from enum import StrEnum
from urllib.parse import urlsplit

from .exceptions import ValidationError


SAFE_IFRAME_SANDBOX = "allow-scripts allow-pointer-lock"
CLIENT_EVENT_TYPES = frozenset({"IMPRESSION", "START", "CLICK"})
PARTNER_EVENT_TYPES = frozenset({"IMPRESSION", "START", "CLICK"})


class RevenueModel(StrEnum):
    CPM = "CPM"
    CPC = "CPC"
    CPA = "CPA"
    FIXED = "FIXED"


class CommercialEventType(StrEnum):
    IMPRESSION = "IMPRESSION"
    START = "START"
    COMPLETE = "COMPLETE"
    CLICK = "CLICK"


def validate_embed_url(value: object) -> tuple[str, str]:
    """Return an HTTPS embed URL and its exact origin.

    Credentials and non-default ports are rejected so a configured placement
    cannot silently redirect browser credentials or broaden its trust origin.
    """

    if not isinstance(value, str) or len(value.strip()) > 500:
        raise ValidationError(field_errors={"embed_url": "URL game không hợp lệ"})
    value = value.strip()
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        raise ValidationError(
            field_errors={"embed_url": "Cổng trong URL game không hợp lệ"}
        ) from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ValidationError(
            field_errors={"embed_url": "Game ngoài phải dùng URL HTTPS an toàn"}
        )
    origin = f"https://{parsed.hostname.lower()}"
    return value, origin


def hash_launch_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def callback_message(token: str, provider_event_id: str, outcome: str) -> bytes:
    """Canonical bytes signed by a partner server."""

    return f"{token}\n{provider_event_id}\n{outcome}".encode("utf-8")


def callback_signature(
    secret: str, token: str, provider_event_id: str, outcome: str
) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        callback_message(token, provider_event_id, outcome),
        hashlib.sha256,
    ).hexdigest()


def verify_callback_signature(
    secret: str,
    token: str,
    provider_event_id: str,
    outcome: str,
    signature: object,
) -> bool:
    if not isinstance(signature, str) or len(signature) != 64:
        return False
    expected = callback_signature(secret, token, provider_event_id, outcome)
    return hmac.compare_digest(expected, signature.lower())


def partner_event_message(
    placement_code: str,
    provider_event_id: str,
    event_type: str,
) -> bytes:
    """Canonical bytes for signed ad-network delivery callbacks.

    This namespace is deliberately different from the game-completion message,
    so a signature captured from one callback type cannot be replayed as the
    other type.
    """

    return (
        f"commercial-event\n{placement_code}\n{provider_event_id}\n{event_type}"
    ).encode("utf-8")


def partner_event_signature(
    secret: str,
    placement_code: str,
    provider_event_id: str,
    event_type: str,
) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        partner_event_message(placement_code, provider_event_id, event_type),
        hashlib.sha256,
    ).hexdigest()


def verify_partner_event_signature(
    secret: str,
    placement_code: str,
    provider_event_id: str,
    event_type: str,
    signature: object,
) -> bool:
    if not isinstance(signature, str) or len(signature) != 64:
        return False
    expected = partner_event_signature(
        secret,
        placement_code,
        provider_event_id,
        event_type,
    )
    return hmac.compare_digest(expected, signature.lower())


def revenue_amount(model: RevenueModel | str, units: int, rate_amount: int) -> int:
    """Calculate VND revenue using the contract snapshot.

    CPM prorates the contract rate over verified impressions and truncates only
    the fractional VND result. CPC/CPA multiply each verified unit. FIXED is
    charged once for a non-empty reconciliation period.
    """

    model = RevenueModel(model)
    if type(units) is not int or units < 0:
        raise ValueError("units must be a non-negative integer")
    if type(rate_amount) is not int or rate_amount < 0:
        raise ValueError("rate_amount must be a non-negative integer")
    if model is RevenueModel.CPM:
        return units * rate_amount // 1_000
    if model is RevenueModel.FIXED:
        return rate_amount if units else 0
    return units * rate_amount
