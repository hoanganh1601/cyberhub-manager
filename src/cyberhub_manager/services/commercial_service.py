"""Commercial partners, sandboxed games, verified rewards and reconciliation.

Browser events are analytics only.  A reward-bearing ``COMPLETE`` event enters
the outbox only after a partner server callback passes HMAC verification.  This
service never exposes a callback secret and never lets iframe JavaScript credit
coins or issue vouchers directly.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import date, datetime, time, timedelta, timezone

from cyberhub_manager.domain.commercial import (
    CLIENT_EVENT_TYPES,
    PARTNER_EVENT_TYPES,
    SAFE_IFRAME_SANDBOX,
    CommercialEventType,
    RevenueModel,
    callback_message,
    hash_launch_token,
    partner_event_message,
    revenue_amount,
    validate_embed_url,
    verify_callback_signature,
    verify_partner_event_signature,
)
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.repositories.commercial_repository import CommercialRepository

from .operational_base import OperationalServiceBase


CODE = re.compile(r"^[A-Z][A-Z0-9_-]{2,31}$")
SECRET_REF = re.compile(r"^CYBERHUB_PARTNER_[A-Z0-9_]+_SECRET$")
EVENT_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,80}$")
PROVIDER_EVENT_ID = re.compile(r"^[A-Za-z0-9._:-]{8,100}$")
PARTNER_TYPES = frozenset({"GAME", "AD_NETWORK", "BOTH"})
PARTNER_STATUSES = frozenset({"ACTIVE", "SUSPENDED", "TERMINATED"})
CAMPAIGN_KINDS = frozenset({"AD", "GAME"})
CAMPAIGN_STATUSES = frozenset({"ACTIVE", "PAUSED", "ENDED"})
CAMPAIGN_TRANSITIONS = {
    "DRAFT": frozenset({"ACTIVE", "ENDED"}),
    "ACTIVE": frozenset({"PAUSED", "ENDED"}),
    "PAUSED": frozenset({"ACTIVE", "ENDED"}),
    "ENDED": frozenset(),
}
REWARD_TYPES = frozenset({"NONE", "COINS", "VOUCHER", "EXTRA_SPIN"})
SURFACES = frozenset({"PORTAL_BANNER", "REWARDED_AD", "GAME_CENTER"})


def _positive_id(value, field="id"):
    if type(value) is not int or value <= 0:
        raise ValidationError(field_errors={field: "Mã định danh không hợp lệ"})
    return value


def _text(value, field, maximum, minimum=1):
    value = value.strip() if isinstance(value, str) else ""
    if not minimum <= len(value) <= maximum:
        raise ValidationError(
            field_errors={field: f"Nhập từ {minimum} đến {maximum} ký tự"}
        )
    return value


def _code(value, field="code", *, maximum=32):
    value = value.strip().upper() if isinstance(value, str) else ""
    if not CODE.fullmatch(value) or len(value) > maximum:
        raise ValidationError(
            field_errors={
                field: (
                    f"Dùng 3-{maximum} ký tự in hoa, số, "
                    "gạch ngang hoặc gạch dưới"
                )
            }
        )
    return value


def _choice(value, choices, field):
    value = value.strip().upper() if isinstance(value, str) else ""
    if value not in choices:
        raise ValidationError(field_errors={field: "Giá trị không hợp lệ"})
    return value


def _integer(value, field, *, minimum=0, maximum=10**12):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError(
            field_errors={field: f"Nhập số nguyên từ {minimum} đến {maximum}"}
        )
    return value


def _date(value, field):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError(field_errors={field: "Ngày không hợp lệ"}) from None


def _instant(value, field):
    if not isinstance(value, datetime):
        try:
            value = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValidationError(field_errors={field: "Thời gian không hợp lệ"}) from None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(field_errors={field: "Thời gian phải có múi giờ"})
    return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)


class CommercialService(OperationalServiceBase):
    def __init__(self, repo=None, *, clock=None, environment=None, **kwargs):
        super().__init__(**kwargs)
        self._repo = repo or CommercialRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._environment = environment or os.environ

    def _now(self):
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)

    def _customer(self, conn, principal):
        account_id = getattr(principal, "account_id", 0)
        record = self._audit.customer_credentials(conn, account_id=account_id)
        if (
            record is None
            or record[0].customer_id != getattr(principal, "customer_id", None)
            or record[0].auth_version != getattr(principal, "auth_version", None)
        ):
            raise PermissionDeniedError()
        return record[0]

    # ----- Administration -----------------------------------------------------
    def overview(self, actor):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_VIEW)
            result = self._repo.overview(
                conn,
                current.store_id,
                include_global=current.role is Role.ADMIN,
            )
            result["can_manage"] = can(current.role, Permission.COMMERCIAL_MANAGE)
            result["can_reconcile"] = can(
                current.role, Permission.COMMERCIAL_RECONCILE
            )
            return result

    def save_partner(self, actor, partner_id=None, **data):
        code = _code(data.get("code"), maximum=24)
        name = _text(data.get("name"), "name", 120)
        partner_type = _choice(data.get("partner_type"), PARTNER_TYPES, "partner_type")
        status = _choice(data.get("status", "ACTIVE"), PARTNER_STATUSES, "status")
        secret_ref = _text(data.get("callback_secret_ref", ""), "callback_secret_ref", 80, 0) or None
        if not (secret_ref and SECRET_REF.fullmatch(secret_ref)):
            raise ValidationError(
                field_errors={
                    "callback_secret_ref": (
                        "Bắt buộc lưu tên biến môi trường "
                        "CYBERHUB_PARTNER_*_SECRET"
                    )
                }
            )
        contact_name = _text(data.get("contact_name", ""), "contact_name", 100, 0) or None
        contact_email = _text(data.get("contact_email", ""), "contact_email", 120, 0) or None
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_MANAGE)
            if partner_id is not None:
                _positive_id(partner_id, "partner_id")
                if self._repo.partner(conn, partner_id, lock=True) is None:
                    raise NotFoundError("Không tìm thấy đối tác")
            entity_id = self._repo.save_partner(
                conn,
                partner_id,
                (code, name, partner_type, status, secret_ref, contact_name, contact_email),
            )
            self._audit.audit(conn, current, "COMMERCIAL_PARTNER_SAVE", entity_id)
            return self._repo.partner(conn, entity_id)

    def create_contract(self, actor, **data):
        partner_id = _positive_id(data.get("partner_id"), "partner_id")
        code = _code(data.get("code"), maximum=24)
        model = _choice(data.get("revenue_model"), {x.value for x in RevenueModel}, "revenue_model")
        rate = _integer(data.get("rate_amount"), "rate_amount", maximum=10**12)
        starts_on = _date(data.get("starts_on"), "starts_on")
        ends_on = _date(data.get("ends_on"), "ends_on")
        if ends_on < starts_on:
            raise ValidationError(field_errors={"ends_on": "Ngày kết thúc phải sau ngày bắt đầu"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_MANAGE)
            partner = self._repo.partner(conn, partner_id, lock=True)
            if partner is None or partner["status"] != "ACTIVE":
                raise ConflictError("Đối tác không hoạt động")
            entity_id = self._repo.create_contract(
                conn, (partner_id, code, model, rate, starts_on, ends_on, current.employee_id)
            )
            self._audit.audit(conn, current, "COMMERCIAL_CONTRACT_CREATE", entity_id)
            return self._repo.contract(conn, entity_id)

    def activate_contract(self, actor, contract_id):
        _positive_id(contract_id, "contract_id")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_MANAGE)
            contract = self._repo.contract(conn, contract_id, lock=True)
            if contract is None:
                raise NotFoundError("Không tìm thấy hợp đồng")
            if contract["created_by"] == current.employee_id:
                raise PermissionDeniedError("Người tạo hợp đồng không được tự duyệt")
            if contract["partner_status"] != "ACTIVE":
                raise ConflictError("Đối tác không hoạt động")
            if self._repo.activate_contract(conn, contract_id, current.employee_id) != 1:
                raise ConflictError("Hợp đồng không còn ở trạng thái chờ duyệt")
            self._audit.audit(conn, current, "COMMERCIAL_CONTRACT_ACTIVATE", contract_id)
            return self._repo.contract(conn, contract_id)

    def create_campaign(self, actor, **data):
        contract_id = _positive_id(data.get("contract_id"), "contract_id")
        code = _code(data.get("code"), maximum=24)
        name = _text(data.get("name"), "name", 120)
        kind = _choice(data.get("kind"), CAMPAIGN_KINDS, "kind")
        starts_at = _instant(data.get("starts_at"), "starts_at")
        ends_at = _instant(data.get("ends_at"), "ends_at")
        if ends_at <= starts_at:
            raise ValidationError(field_errors={"ends_at": "Thời gian kết thúc phải muộn hơn"})
        budget = data.get("budget_amount")
        if budget is not None:
            budget = _integer(budget, "budget_amount", maximum=10**12)
        reward_type = _choice(data.get("reward_type", "NONE"), REWARD_TYPES, "reward_type")
        reward_amount = _integer(data.get("reward_amount", 0), "reward_amount", maximum=10**9)
        if (reward_type == "NONE") != (reward_amount == 0):
            raise ValidationError(field_errors={"reward_amount": "Loại và giá trị thưởng không khớp"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_MANAGE)
            contract = self._repo.contract(conn, contract_id, lock=True)
            if contract is None or contract["status"] != "ACTIVE":
                raise ConflictError("Hợp đồng chưa hoạt động")
            if kind == "GAME" and contract["partner_type"] not in ("GAME", "BOTH"):
                raise ValidationError(field_errors={"kind": "Đối tác không cung cấp game"})
            if kind == "AD" and contract["partner_type"] not in ("AD_NETWORK", "BOTH"):
                raise ValidationError(field_errors={"kind": "Đối tác không cung cấp quảng cáo"})
            if starts_at.date() < contract["starts_on"] or ends_at.date() > contract["ends_on"]:
                raise ValidationError(field_errors={"starts_at": "Chiến dịch phải nằm trong kỳ hợp đồng"})
            entity_id = self._repo.create_campaign(
                conn,
                (
                    contract_id, code, name, kind, "DRAFT", starts_at, ends_at,
                    budget, reward_type, reward_amount, current.employee_id,
                ),
            )
            self._audit.audit(conn, current, "COMMERCIAL_CAMPAIGN_CREATE", entity_id)
            return self._repo.campaign(conn, entity_id)

    def set_campaign_status(self, actor, campaign_id, status):
        _positive_id(campaign_id, "campaign_id")
        status = _choice(status, CAMPAIGN_STATUSES, "status")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_MANAGE)
            campaign = self._repo.campaign(conn, campaign_id, lock=True)
            if campaign is None:
                raise NotFoundError("Không tìm thấy chiến dịch")
            if status not in CAMPAIGN_TRANSITIONS[campaign["status"]]:
                raise ConflictError(
                    "Không thể chuyển chiến dịch từ "
                    f"{campaign['status']} sang {status}"
                )
            if status == "ACTIVE" and (
                campaign["contract_status"] != "ACTIVE"
                or campaign["partner_status"] != "ACTIVE"
            ):
                raise ConflictError("Đối tác hoặc hợp đồng chưa hoạt động")
            if self._repo.set_campaign_status(conn, campaign_id, status) != 1:
                raise ConflictError("Chiến dịch đã ở trạng thái này")
            self._audit.audit(conn, current, f"COMMERCIAL_CAMPAIGN_{status}", campaign_id)
            return self._repo.campaign(conn, campaign_id)

    def create_placement(self, actor, **data):
        campaign_id = _positive_id(data.get("campaign_id"), "campaign_id")
        store_id = data.get("store_id")
        if store_id is not None:
            _positive_id(store_id, "store_id")
        code = _code(data.get("code"))
        placement_type = _choice(data.get("placement_type"), CAMPAIGN_KINDS, "placement_type")
        surface = _choice(data.get("surface"), SURFACES, "surface")
        embed_url = allowed_origin = None
        if placement_type == "GAME":
            embed_url, allowed_origin = validate_embed_url(data.get("embed_url"))
            if surface != "GAME_CENTER":
                raise ValidationError(field_errors={"surface": "Game chỉ được đặt tại GAME_CENTER"})
        elif surface == "GAME_CENTER":
            raise ValidationError(field_errors={"surface": "Vị trí GAME_CENTER chỉ dành cho game"})
        legacy_game_id = data.get("legacy_game_id")
        legacy_ad_id = data.get("legacy_ad_creative_id")
        for value, field in ((legacy_game_id, "legacy_game_id"), (legacy_ad_id, "legacy_ad_creative_id")):
            if value is not None:
                _positive_id(value, field)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_MANAGE)
            campaign = self._repo.campaign(conn, campaign_id, lock=True)
            if campaign is None:
                raise NotFoundError("Không tìm thấy chiến dịch")
            if campaign["kind"] != placement_type:
                raise ValidationError(field_errors={"placement_type": "Loại vị trí không khớp chiến dịch"})
            entity_id = self._repo.create_placement(
                conn,
                (
                    campaign_id, store_id, code, placement_type, surface, embed_url,
                    allowed_origin, SAFE_IFRAME_SANDBOX, legacy_game_id, legacy_ad_id,
                ),
            )
            self._audit.audit(conn, current, "COMMERCIAL_PLACEMENT_CREATE", entity_id)
            return {"id": entity_id, "code": code, "sandbox_policy": SAFE_IFRAME_SANDBOX}

    # ----- Customer portal and iframe analytics -------------------------------
    def launch_external_game(self, principal, placement_code, store_id):
        placement_code = _code(placement_code, "placement_code")
        _positive_id(store_id, "store_id")
        now = self._now()
        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(minutes=15)
        with self._errors(), self._transaction() as conn:
            customer = self._customer(conn, principal)
            placement = self._repo.active_placement(
                conn, placement_code, store_id, now, lock=True
            )
            if placement is None or placement["placement_type"] != "GAME":
                raise NotFoundError("Game không khả dụng tại cơ sở này")
            session_id = self._repo.create_play_session(
                conn,
                (
                    placement["id"], customer.account_id, hash_launch_token(token),
                    placement["reward_type"], placement["reward_amount"], now, expires_at,
                ),
            )
            return {
                "session_id": session_id,
                "launch_token": token,
                "embed_url": placement["embed_url"],
                "allowed_origin": placement["allowed_origin"],
                "sandbox": SAFE_IFRAME_SANDBOX,
                "expires_at": expires_at,
            }

    def record_client_event(self, principal, placement_code, store_id, event_type, event_key):
        placement_code = _code(placement_code, "placement_code")
        _positive_id(store_id, "store_id")
        event_type = _choice(event_type, CLIENT_EVENT_TYPES, "event_type")
        if not isinstance(event_key, str) or not EVENT_KEY.fullmatch(event_key):
            raise ValidationError(field_errors={"event_key": "Khóa sự kiện không hợp lệ"})
        now = self._now()
        with self._errors(), self._transaction() as conn:
            customer = self._customer(conn, principal)
            placement = self._repo.active_placement(conn, placement_code, store_id, now)
            if placement is None:
                raise NotFoundError("Vị trí thương mại không khả dụng")
            existing = self._repo.event_by_key(conn, event_key)
            if existing is not None:
                if (
                    existing["placement_id"] != placement["id"]
                    or existing["account_id"] != customer.account_id
                    or existing["event_type"] != event_type
                ):
                    raise ConflictError("Khóa sự kiện đã được dùng cho dữ liệu khác")
                return {"event_id": existing["id"], "accepted": bool(existing["accepted"])}
            event_id = self._repo.insert_event(
                conn,
                (
                    placement["id"], placement["campaign_id"], None,
                    customer.account_id, event_type, event_key, None, "CLIENT", True,
                    now, None, None,
                ),
            )
            return {"event_id": event_id, "accepted": True}

    # ----- Trusted server-to-server callback ----------------------------------
    def verify_partner_event_callback(
        self,
        placement_code,
        provider_event_id,
        event_type,
        signature,
    ):
        """Accept signed impression/start/click events from a partner server.

        Browser events remain useful for analytics, but only rows produced by
        this callback (or the game-completion SSV callback below) are eligible
        for revenue reconciliation.
        """

        placement_code = _code(placement_code, "placement_code")
        if (
            not isinstance(provider_event_id, str)
            or not PROVIDER_EVENT_ID.fullmatch(provider_event_id)
        ):
            raise ValidationError(
                field_errors={"provider_event_id": "Mã sự kiện không hợp lệ"}
            )
        event_type = _choice(
            event_type,
            PARTNER_EVENT_TYPES,
            "event_type",
        )
        now = self._now()
        with self._errors(), self._transaction() as conn:
            placement = self._repo.callback_placement(
                conn,
                placement_code,
                now,
                lock=True,
            )
            if placement is None:
                raise NotFoundError("Vị trí thương mại không khả dụng")
            secret_ref = placement["callback_secret_ref"]
            secret = self._environment.get(secret_ref, "") if secret_ref else ""
            if not secret:
                raise ServiceUnavailableError(
                    "Chưa cấu hình bí mật callback của đối tác"
                )
            if not verify_partner_event_signature(
                secret,
                placement_code,
                provider_event_id,
                event_type,
                signature,
            ):
                raise PermissionDeniedError("Chữ ký callback không hợp lệ")

            existing = self._repo.event_by_provider_id(
                conn,
                provider_event_id,
            )
            if existing is not None:
                if (
                    existing["placement_id"] != placement["id"]
                    or existing["event_type"] != event_type
                ):
                    raise ConflictError("Mã sự kiện đối tác đã được dùng")
                return {
                    "event_id": existing["id"],
                    "accepted": bool(existing["accepted"]),
                    "idempotent": True,
                }

            canonical = partner_event_message(
                placement_code,
                provider_event_id,
                event_type,
            )
            event_id = self._repo.insert_event(
                conn,
                (
                    placement["id"],
                    placement["campaign_id"],
                    None,
                    None,
                    event_type,
                    f"server:{provider_event_id}",
                    provider_event_id,
                    "SERVER",
                    True,
                    now,
                    now,
                    hashlib.sha256(canonical).hexdigest(),
                ),
            )
            return {
                "event_id": event_id,
                "accepted": True,
                "idempotent": False,
            }

    def verify_game_callback(self, token, provider_event_id, outcome, signature):
        if not isinstance(token, str) or not 32 <= len(token) <= 100:
            raise PermissionDeniedError("Callback không hợp lệ")
        if not isinstance(provider_event_id, str) or not PROVIDER_EVENT_ID.fullmatch(provider_event_id):
            raise ValidationError(field_errors={"provider_event_id": "Mã sự kiện không hợp lệ"})
        if outcome != "complete":
            raise ValidationError(field_errors={"outcome": "Kết quả callback không hỗ trợ"})
        token_hash = hash_launch_token(token)
        now = self._now()
        with self._errors(), self._transaction() as conn:
            play = self._repo.play_session(conn, token_hash, lock=True)
            if play is None:
                raise PermissionDeniedError("Callback không hợp lệ")
            secret_ref = play["callback_secret_ref"]
            secret = self._environment.get(secret_ref, "") if secret_ref else ""
            if not secret:
                raise ServiceUnavailableError("Chưa cấu hình bí mật callback của đối tác")
            if not verify_callback_signature(
                secret, token, provider_event_id, outcome, signature
            ):
                raise PermissionDeniedError("Chữ ký callback không hợp lệ")
            existing = self._repo.event_by_provider_id(conn, provider_event_id)
            if existing is not None:
                if existing["play_session_id"] != play["id"]:
                    raise ConflictError("Mã sự kiện đối tác đã được dùng")
                return {
                    "event_id": existing["id"],
                    "reward_grant_id": existing.get("grant_id"),
                    "reward_status": existing.get("grant_status"),
                    "idempotent": True,
                }
            if (
                play["status"] != "ISSUED"
                or play["expires_at"] < now
                or play["partner_status"] != "ACTIVE"
                or play["campaign_status"] != "ACTIVE"
                or play["contract_status"] != "ACTIVE"
                or play["placement_status"] != "ACTIVE"
            ):
                raise ConflictError("Phiên game không còn hợp lệ")
            digest = hashlib.sha256(
                callback_message(token, provider_event_id, outcome)
            ).hexdigest()
            event_id = self._repo.insert_event(
                conn,
                (
                    play["placement_id"], play["campaign_id"], play["id"],
                    play["account_id"], CommercialEventType.COMPLETE.value,
                    f"ssv:{provider_event_id}", provider_event_id, "SSV", True,
                    now, now, digest,
                ),
            )
            if self._repo.complete_play_session(conn, play["id"], now) != 1:
                raise ConflictError("Phiên game đã được xử lý")
            grant_id = None
            if play["reward_type"] != "NONE":
                grant_id = self._repo.create_reward_grant(
                    conn, event_id, play["account_id"], play["reward_type"], play["reward_amount"]
                )
            return {
                "event_id": event_id,
                "reward_grant_id": grant_id,
                "reward_status": "PENDING" if grant_id else None,
                "idempotent": False,
            }

    # ----- Reconciliation -----------------------------------------------------
    def generate_settlement(
        self,
        actor,
        contract_id,
        period_start,
        period_end,
        adjustment_amount=0,
        adjustment_reason=None,
    ):
        _positive_id(contract_id, "contract_id")
        period_start = _date(period_start, "period_start")
        period_end = _date(period_end, "period_end")
        if period_end < period_start:
            raise ValidationError(field_errors={"period_end": "Kỳ kết thúc phải sau kỳ bắt đầu"})
        adjustment = _integer(
            abs(adjustment_amount) if type(adjustment_amount) is int else adjustment_amount,
            "adjustment_amount",
            maximum=10**12,
        )
        adjustment = -adjustment if type(adjustment_amount) is int and adjustment_amount < 0 else adjustment
        if adjustment:
            adjustment_reason = _text(
                adjustment_reason, "adjustment_reason", 255, 5
            )
        else:
            adjustment_reason = None
        start = datetime.combine(period_start, time.min)
        before = datetime.combine(period_end + timedelta(days=1), time.min)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_RECONCILE)
            contract = self._repo.contract(conn, contract_id, lock=True)
            if contract is None:
                raise NotFoundError("Không tìm thấy hợp đồng")
            if period_start < contract["starts_on"] or period_end > contract["ends_on"]:
                raise ValidationError(field_errors={"period_start": "Kỳ đối soát nằm ngoài hợp đồng"})
            model = RevenueModel(contract["revenue_model"])
            if model is RevenueModel.FIXED and (
                period_start != contract["starts_on"]
                or period_end != contract["ends_on"]
            ):
                raise ValidationError(
                    field_errors={
                        "period_start": (
                            "Hợp đồng FIXED chỉ được đối soát một lần "
                            "cho toàn bộ kỳ hợp đồng"
                        )
                    }
                )
            if self._repo.overlapping_settlement(
                conn, contract_id, period_start, period_end
            ):
                raise ConflictError("Kỳ đối soát bị trùng")
            event_type = {
                RevenueModel.CPM: "IMPRESSION",
                RevenueModel.CPC: "CLICK",
                RevenueModel.CPA: "COMPLETE",
                RevenueModel.FIXED: "FIXED",
            }[model]
            if model is RevenueModel.FIXED:
                placements = self._repo.contract_placements(conn, contract_id)
                if not placements:
                    raise ConflictError(
                        "Hợp đồng chưa có vị trí thương mại để đối soát"
                    )
                unit_rows = placements[:1]
                unit_rows[0]["units"] = 1
            else:
                unit_rows = self._repo.settlement_units(
                    conn, contract_id, event_type, start, before
                )
            lines = []
            gross = 0
            for row in unit_rows:
                amount = revenue_amount(model, int(row["units"]), contract["rate_amount"])
                gross += amount
                lines.append(
                    (
                        row["placement_id"], event_type, int(row["units"]),
                        contract["rate_amount"], amount,
                    )
                )
            net = gross + adjustment
            if net < 0:
                raise ValidationError(field_errors={"adjustment_amount": "Điều chỉnh làm số tiền đối soát âm"})
            settlement_id = self._repo.create_settlement(
                conn,
                (
                    contract_id, period_start, period_end, gross, adjustment,
                    adjustment_reason,
                    net, current.employee_id,
                ),
                lines,
            )
            self._audit.audit(conn, current, "COMMERCIAL_SETTLEMENT_GENERATE", settlement_id)
            return self._repo.settlement(conn, settlement_id)

    def approve_settlement(self, actor, settlement_id):
        _positive_id(settlement_id, "settlement_id")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.COMMERCIAL_RECONCILE)
            settlement = self._repo.settlement(conn, settlement_id, lock=True)
            if settlement is None:
                raise NotFoundError("Không tìm thấy đối soát")
            if settlement["generated_by"] == current.employee_id:
                raise PermissionDeniedError("Người tạo đối soát không được tự duyệt")
            if self._repo.approve_settlement(conn, settlement_id, current.employee_id) != 1:
                raise ConflictError("Đối soát không còn chờ duyệt")
            self._audit.audit(conn, current, "COMMERCIAL_SETTLEMENT_APPROVE", settlement_id)
            return self._repo.settlement(conn, settlement_id)
