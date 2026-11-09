"""Đợt 4 — Quảng cáo nhận thưởng.

Không cộng thưởng chỉ dựa vào tín hiệu từ trình duyệt:
- start(): máy chủ cấp token ngẫu nhiên (secrets) dùng một lần, ghi lại thời điểm bắt đầu,
  thời điểm sớm nhất được nhận (bắt đầu + thời lượng) và hạn token.
- HOUSE complete(): chỉ chấp nhận token còn ISSUED, đúng chủ, đã đủ thời lượng theo đồng hồ máy chủ
  và chưa hết hạn. Gửi sớm/hết hạn/vượt giới hạn thì token bị hủy (REJECTED) — gửi lại không được.
- NETWORK: khách không tự hoàn thành được; chỉ callback có chữ ký HMAC-SHA256 hợp lệ của nhà cung cấp
  (khóa bí mật lấy từ biến môi trường CYBERHUB_AD_SSV_SECRET). Mã giao dịch nhà cung cấp là UNIQUE.
- Mỗi lần bắt đầu xem mới hủy token cũ chưa dùng; tối đa daily_cap lần thưởng và daily_cap × START_FACTOR
  lần bắt đầu mỗi ngày. Sự kiện quảng cáo lưu riêng (ad_reward_events), độc lập với kết quả game.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from cyberhub_manager.domain.ad import (
    REWARD_LIMITS,
    START_FACTOR,
    TOKEN_HOURS,
    AdMode,
    AdRewardType,
    AdSettings,
    AdStatus,
)
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.game import LedgerReason
from cyberhub_manager.domain.p1 import Permission

from .p1_runtime import errors, retry_on_transient

VN = timezone(timedelta(hours=7))
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{32}$")
TXN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{4,80}$")

ADS_PAUSED = "Chương trình quảng cáo nhận thưởng đang tạm dừng"
CAP_REACHED = "Bạn đã nhận đủ thưởng quảng cáo hôm nay"
TOO_MANY_STARTS = "Bạn đã mở quảng cáo quá nhiều lần hôm nay"
WALLET_LOCKED = "Tài khoản trò chơi đang bị khóa"
NO_CREATIVE = "Hiện chưa có quảng cáo nào"
ALREADY_HANDLED = "Lượt quảng cáo này đã được xử lý"
WAIT_PROVIDER = "Đang chờ nhà cung cấp quảng cáo xác nhận"
TOO_EARLY = "Bạn cần xem hết quảng cáo để nhận thưởng"
EXPIRED = "Lượt quảng cáo đã hết hạn"


class AdService:
    def __init__(self, repo=None, game_repo=None, vouchers=None, p1_repo=None, transaction_factory=None,
                 actor_provider=None, clock=None, ssv_secret=None):
        self._memory = hasattr(p1_repo, "resolve_actor")
        if not self._memory:
            from cyberhub_manager.database.transaction import transaction
            from cyberhub_manager.repositories.ad_repository import AdRepository
            from cyberhub_manager.repositories.game_repository import GameRepository
            from cyberhub_manager.repositories.p1_repository import P1Repository
            from .voucher_service import VoucherService

            transaction_factory = transaction_factory or transaction
            repo = repo or AdRepository()
            game_repo = game_repo or GameRepository()
            p1_repo = p1_repo or P1Repository()
            vouchers = vouchers or VoucherService(actor_provider=actor_provider)
        self._repo = repo
        self._games = game_repo
        self._vouchers = vouchers  # dùng lại xác thực khách/nhân viên
        self._p1 = p1_repo
        self._transaction = transaction_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        secret = ssv_secret if ssv_secret is not None else os.getenv("CYBERHUB_AD_SSV_SECRET", "")
        self._secret = secret.encode() if secret else b""

    def _errors(self):
        return errors(self._memory)

    def _now(self) -> datetime:
        return self._clock().astimezone(timezone.utc).replace(microsecond=0)

    # =================================================================================
    # Khách hàng
    # =================================================================================
    def portal_ads(self, principal):
        with self._errors(), self._transaction() as conn:
            customer = self._vouchers._customer(conn, principal)
            settings = self._repo.settings(conn)
            today = self._now().astimezone(VN).date()
            done = self._repo.count_events(conn, customer.account_id, today, AdStatus.COMPLETED)
            wallet = self._games.wallet(conn, customer.account_id)
            return dict(
                enabled=settings.enabled and not wallet.is_locked,
                mode=settings.mode,
                daily_cap=settings.daily_cap,
                remaining=max(0, settings.daily_cap - done),
                reward_type=settings.reward_type,
                reward_amount=settings.reward_amount,
            )

    @retry_on_transient
    def start(self, principal):
        with self._errors(), self._transaction() as conn:
            customer = self._vouchers._customer(conn, principal)
            settings = self._repo.settings(conn)
            if not settings.enabled:
                raise ConflictError(ADS_PAUSED)
            # Khóa ví game: các request của cùng tài khoản chạy tuần tự khi đếm giới hạn.
            wallet = self._games.wallet(conn, customer.account_id, lock=True)
            if wallet.is_locked:
                raise ConflictError(WALLET_LOCKED)
            now = self._now()
            today = now.astimezone(VN).date()
            if self._repo.count_events(conn, customer.account_id, today, AdStatus.COMPLETED) >= settings.daily_cap:
                raise ConflictError(CAP_REACHED)
            if self._repo.count_events(conn, customer.account_id, today) >= settings.daily_cap * START_FACTOR:
                raise ConflictError(TOO_MANY_STARTS)
            creatives = [c for c in self._repo.creatives(conn) if c.is_active]
            if not creatives:
                raise ConflictError(NO_CREATIVE)
            creative = secrets.choice(creatives)
            self._repo.supersede_issued(conn, customer.account_id)
            token = secrets.token_hex(16)
            min_complete = now + timedelta(seconds=creative.duration_seconds)
            self._repo.insert_event(
                conn, token=token, account_id=customer.account_id, creative_id=creative.id, provider=settings.mode,
                reward_type=settings.reward_type, reward_amount=settings.reward_amount, played_on=today,
                issued_at=now, min_complete_at=min_complete, expires_at=now + timedelta(hours=TOKEN_HOURS),
            )
            return dict(
                token=token, provider=settings.mode, duration_seconds=creative.duration_seconds,
                creative=dict(title=creative.title, body=creative.body, cta=creative.cta),
                reward_type=settings.reward_type, reward_amount=settings.reward_amount,
            )

    def complete(self, principal, token):
        """Khách báo đã xem xong (chỉ với HOUSE). Lần bị từ chối hủy token và vẫn được lưu."""
        if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token):
            raise ValidationError(field_errors={"token": "Token không hợp lệ"})
        rejected = None
        result = None
        with self._errors(), self._transaction() as conn:
            customer = self._vouchers._customer(conn, principal)
            self._games.wallet(conn, customer.account_id, lock=True)
            event = self._repo.get_event(conn, token, lock=True)
            if event is None or event.account_id != customer.account_id:
                raise NotFoundError("Không tìm thấy lượt quảng cáo")
            if event.status != AdStatus.ISSUED:
                raise ConflictError(ALREADY_HANDLED)
            if event.provider == AdMode.NETWORK:
                raise ConflictError(WAIT_PROVIDER)
            now = self._now()
            if now < event.min_complete_at:
                rejected = self._reject(conn, event, "TOO_EARLY", TOO_EARLY)
            else:
                rejected, result = self._settle(conn, event, now, txn_id=None)
        if rejected:
            raise ConflictError(rejected)
        return result

    def verify_network_callback(self, token, txn_id, signature):
        """Callback server-to-server của mạng quảng cáo (không cần đăng nhập, cần chữ ký)."""
        if not self._secret:
            raise PermissionDeniedError("Chưa cấu hình xác minh phía máy chủ cho mạng quảng cáo")
        if (
            not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token)
            or not isinstance(txn_id, str) or not TXN_PATTERN.fullmatch(txn_id)
            or not isinstance(signature, str)
        ):
            raise ValidationError(field_errors={"signature": "Tham số không hợp lệ"})
        expected = hmac.new(self._secret, f"{token}:{txn_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.lower()):
            raise PermissionDeniedError("Chữ ký không hợp lệ")
        rejected = None
        result = None
        with self._errors(), self._transaction() as conn:
            event = self._repo.get_event(conn, token, lock=True)
            if event is None or event.provider != AdMode.NETWORK:
                raise NotFoundError("Không tìm thấy lượt quảng cáo")
            if event.status != AdStatus.ISSUED or self._repo.txn_used(conn, txn_id):
                raise ConflictError(ALREADY_HANDLED)  # gửi lại cùng sự kiện/giao dịch
            self._games.wallet(conn, event.account_id, lock=True)
            rejected, result = self._settle(conn, event, self._now(), txn_id=txn_id)
        if rejected:
            raise ConflictError(rejected)
        return result

    def _reject(self, conn, event, code, message):
        self._repo.finish_event(conn, event.id, status=AdStatus.REJECTED, reason=code)
        return message

    def _settle(self, conn, event, now, *, txn_id):
        """Kiểm tra hạn/giới hạn/khóa rồi cộng thưởng; trả (thông báo từ chối, kết quả)."""
        if now > event.expires_at:
            return self._reject(conn, event, "EXPIRED", EXPIRED), None
        settings = self._repo.settings(conn)
        wallet = self._games.wallet(conn, event.account_id, lock=True)
        if wallet.is_locked:
            return self._reject(conn, event, "LOCKED", WALLET_LOCKED), None
        if self._repo.count_events(conn, event.account_id, event.played_on, AdStatus.COMPLETED) >= settings.daily_cap:
            return self._reject(conn, event, "CAP", CAP_REACHED), None
        if not self._repo.finish_event(conn, event.id, status=AdStatus.COMPLETED, completed_at=now, txn_id=txn_id):
            raise ConflictError(ALREADY_HANDLED)
        balance = wallet.balance
        if event.reward_type == AdRewardType.COINS:
            balance += event.reward_amount
            self._games.set_balance(conn, event.account_id, balance)
            self._games.insert_ledger(conn, account_id=event.account_id, delta=event.reward_amount,
                                      reason=LedgerReason.AD, ref=f"ad:{event.token}", balance_after=balance,
                                      voucher_id=None, created_at=now)
        return None, dict(reward_type=event.reward_type, reward_amount=event.reward_amount, coin_balance=balance)

    # =================================================================================
    # Nhân viên / quản trị
    # =================================================================================
    def overview(self, actor):
        with self._errors(), self._transaction() as conn:
            current = self._vouchers._actor(conn, actor, Permission.OPERATE)
            now = self._now()
            since = now.astimezone(VN).date() - timedelta(days=6)
            return dict(
                can_configure=current.role == Role.ADMIN,
                network_ready=bool(self._secret),
                settings=self._repo.settings(conn),
                creatives=self._repo.creatives(conn),
                stats=self._repo.daily_stats(conn, since, now),
                recent=[self._public_event(e) for e in self._repo.recent_events(conn, 30)],
            )

    @staticmethod
    def _public_event(e):
        # Không trả token ra màn quản lý: token là bí mật một lần của khách.
        return dict(id=e.id, customer_name=e.customer_name, provider=e.provider, reward_type=e.reward_type,
                    reward_amount=e.reward_amount, status=e.status, reject_reason=e.reject_reason,
                    issued_at=e.issued_at, completed_at=e.completed_at, expires_at=e.expires_at)

    def _admin(self, conn, actor):
        current = self._vouchers._actor(conn, actor, Permission.MANAGE_REWARDS)
        if current.role != Role.ADMIN:
            raise PermissionDeniedError("Chỉ quản trị viên cấu hình quảng cáo")
        return current

    @retry_on_transient
    def save_settings(self, actor, *, enabled, mode, daily_cap, reward_type, reward_amount):
        try:
            mode, reward_type = AdMode(mode), AdRewardType(reward_type)
        except ValueError:
            raise ValidationError(field_errors={"mode": "Chế độ hoặc loại thưởng không hợp lệ"}) from None
        if type(enabled) is not bool:
            raise ValidationError(field_errors={"enabled": "Giá trị không hợp lệ"})
        if type(daily_cap) is not int or not 1 <= daily_cap <= 10:
            raise ValidationError(field_errors={"daily_cap": "Giới hạn mỗi ngày từ 1 đến 10"})
        limit = REWARD_LIMITS[reward_type]
        if type(reward_amount) is not int or not 1 <= reward_amount <= limit:
            raise ValidationError(field_errors={"reward_amount": f"Phần thưởng từ 1 đến {limit}"})
        if mode == AdMode.NETWORK and not self._secret:
            raise ValidationError(field_errors={"mode": "Cần cấu hình CYBERHUB_AD_SSV_SECRET trước khi dùng mạng quảng cáo"})
        with self._errors(), self._transaction() as conn:
            current = self._admin(conn, actor)
            settings = AdSettings(enabled, mode, daily_cap, reward_type, reward_amount)
            self._repo.save_settings(conn, settings)
            self._p1.audit(conn, current, "AD_SETTINGS_SAVE", 1)
            return self._repo.settings(conn)

    @retry_on_transient
    def save_creative(self, actor, creative_id, *, code, title, body, cta, duration_seconds, is_active):
        code = code.strip().upper() if isinstance(code, str) else ""
        if not re.fullmatch(r"[A-Z0-9_-]{2,20}", code):
            raise ValidationError(field_errors={"code": "Mã 2–20 ký tự: chữ in hoa, số, - hoặc _"})
        for field, value, low, high in (("title", title, 1, 80), ("body", body, 1, 300), ("cta", cta, 0, 40)):
            if not isinstance(value, str) or not low <= len(value.strip()) <= high:
                raise ValidationError(field_errors={field: f"Độ dài từ {low} đến {high} ký tự"})
        if type(duration_seconds) is not int or not 5 <= duration_seconds <= 60:
            raise ValidationError(field_errors={"duration_seconds": "Thời lượng từ 5 đến 60 giây"})
        if type(is_active) is not bool:
            raise ValidationError(field_errors={"is_active": "Giá trị không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            current = self._admin(conn, actor)
            if creative_id is not None and all(c.id != creative_id for c in self._repo.creatives(conn)):
                raise NotFoundError("Không tìm thấy quảng cáo")
            if self._repo.creative_code_taken(conn, code, creative_id):
                raise ConflictError("Mã đã tồn tại", field_errors={"code": "Mã đã tồn tại"})
            saved_id = self._repo.save_creative(conn, creative_id, code=code, title=title.strip(), body=body.strip(),
                                                cta=cta.strip(), duration_seconds=duration_seconds, is_active=is_active)
            self._p1.audit(conn, current, "AD_CREATIVE_SAVE", saved_id)
            return next(c for c in self._repo.creatives(conn) if c.id == saved_id)


def sign_callback(secret: str, token: str, txn_id: str) -> str:
    """Chữ ký mà nhà cung cấp phải gửi kèm callback (dùng cho tài liệu tích hợp và test)."""
    return hmac.new(secret.encode(), f"{token}:{txn_id}".encode(), hashlib.sha256).hexdigest()
