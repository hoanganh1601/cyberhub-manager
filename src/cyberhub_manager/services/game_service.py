"""Đợt 3 — Vòng quay may mắn và xu game.

Chống gian lận:
- Endpoint quay không nhận dữ liệu nào từ trình duyệt; máy chủ bốc thăm bằng `secrets.SystemRandom`
  theo trọng số cấu hình, ghi phiên chơi và cộng xu trong cùng transaction.
- Dòng ví xu bị khóa (FOR UPDATE) trong mỗi lượt quay/đổi thưởng, nên các request song song của
  cùng tài khoản chạy tuần tự: không vượt số lượt/ngày, không đổi vượt số dư.
- Đổi thưởng cần `request_key` do client sinh: gửi lại cùng khóa trả về đúng voucher cũ
  (UNIQUE(reason, ref) ở sổ cái + UNIQUE(source, source_ref) ở voucher), không trừ xu lần hai.
- Mỗi lần bị chặn vì hết lượt/quay quá nhanh được đếm (vẫn commit dù request lỗi). Vượt
  SUSPICIOUS_LIMIT lần trong ngày thì tự khóa ví game; quản lý xem lại và mở khóa (có audit).
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.game import (
    DEFAULT_GAME,
    MAX_PRIZES,
    MIN_PRIZES,
    SUSPICIOUS_LIMIT,
    GamePrize,
    LedgerReason,
    expected_coins,
)
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.domain.voucher import VoucherSource

from .p1_runtime import errors, retry_on_transient

VN = timezone(timedelta(hours=7))
REQUEST_KEY = re.compile(r"^[A-Za-z0-9-]{8,64}$")

GAME_PAUSED = "Trò chơi đang tạm dừng"
WALLET_LOCKED = "Tài khoản trò chơi đang bị khóa. Vui lòng liên hệ nhân viên."
LIMIT_REACHED = "Bạn đã hết lượt quay hôm nay"
TOO_FAST = "Thao tác quá nhanh, vui lòng chờ vài giây"
AUTO_LOCK_REASON = "Tự động: quá nhiều lượt chơi bị chặn trong ngày"
AUTO_LOCKED = "Phát hiện thao tác bất thường; tài khoản trò chơi đã bị tạm khóa."


def _positive_id(value: object) -> bool:
    return type(value) is int and value > 0


class GameService:
    def __init__(self, repo=None, p1_repo=None, vouchers=None, transaction_factory=None, actor_provider=None,
                 clock=None, random=None):
        self._memory = hasattr(p1_repo, "resolve_actor")
        if not self._memory:
            from cyberhub_manager.database.transaction import transaction
            from cyberhub_manager.repositories.game_repository import GameRepository
            from cyberhub_manager.repositories.p1_repository import P1Repository
            from .voucher_service import VoucherService

            transaction_factory = transaction_factory or transaction
            repo = repo or GameRepository()
            p1_repo = p1_repo or P1Repository()
            vouchers = vouchers or VoucherService(actor_provider=actor_provider)
        self._repo = repo
        self._p1 = p1_repo
        # Dùng lại VoucherService: xác thực nhân viên/khách và phát voucher trong cùng transaction.
        self._vouchers = vouchers
        self._transaction = transaction_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._random = random or secrets.SystemRandom()

    def _errors(self):
        return errors(self._memory)

    def _now(self) -> datetime:
        return self._clock().astimezone(timezone.utc).replace(microsecond=0)

    @staticmethod
    def _local_day(moment: datetime):
        return moment.astimezone(VN).date()

    def _game(self, conn, *, lock=False):
        game = self._repo.get_game(conn, DEFAULT_GAME, lock=lock)
        if game is None:
            raise NotFoundError("Trò chơi chưa được cấu hình")
        return game

    # =================================================================================
    # Khách hàng
    # =================================================================================
    def portal_game(self, principal):
        with self._errors(), self._transaction() as conn:
            customer = self._vouchers._customer(conn, principal)
            game = self._game(conn)
            wallet = self._repo.wallet(conn, customer.account_id)
            now = self._now()
            used = self._repo.count_sessions(conn, customer.account_id, game.id, self._local_day(now))
            stores = {s.id: s.name for s in self._p1.list_stores(conn)}
            playable = game.is_active and not wallet.is_locked
            return dict(
                game=dict(name=game.name, is_active=game.is_active, daily_limit=game.daily_limit,
                          min_interval_seconds=game.min_interval_seconds,
                          prizes=[dict(index=p.sort_order, label=p.label, coins=p.coins) for p in game.prizes]),
                wallet=dict(balance=wallet.balance, is_locked=wallet.is_locked, locked_reason=wallet.locked_reason),
                spins_left=max(0, game.daily_limit - used) if playable else 0,
                history=self._repo.account_sessions(conn, customer.account_id, 10),
                ledger=self._repo.account_ledger(conn, customer.account_id, 10),
                shop=[
                    dict(id=c.id, name=c.name, reward_type=c.reward_type, value=c.value, coin_cost=c.coin_cost,
                         valid_days=c.valid_days, store_name=stores.get(c.store_id) if c.store_id else None)
                    for c in self._vouchers._repo.coin_catalog(conn)
                ],
                as_of=now,
            )

    def spin(self, principal):
        """Một lượt quay. Lần bị chặn vẫn được đếm và commit để phát hiện spam."""
        rejected = None
        result = None
        with self._errors(), self._transaction() as conn:
            customer = self._vouchers._customer(conn, principal)
            game = self._game(conn)
            if not game.is_active:
                raise ConflictError(GAME_PAUSED)
            wallet = self._repo.wallet(conn, customer.account_id, lock=True)
            if wallet.is_locked:
                raise ConflictError(WALLET_LOCKED)
            now = self._now()
            today = self._local_day(now)
            used = self._repo.count_sessions(conn, customer.account_id, game.id, today)
            last = self._repo.last_session_at(conn, customer.account_id)
            if used >= game.daily_limit:
                rejected = LIMIT_REACHED
            elif last is not None and (now - last).total_seconds() < game.min_interval_seconds:
                rejected = TOO_FAST
            if rejected:
                count = (wallet.suspicious_count if wallet.suspicious_on == today else 0) + 1
                self._repo.set_suspicious(conn, customer.account_id, count, today)
                if count >= SUSPICIOUS_LIMIT:
                    self._repo.lock_wallet(conn, customer.account_id, AUTO_LOCK_REASON, now)
                    rejected = AUTO_LOCKED
            else:
                prize = self._random.choices(game.prizes, weights=[p.weight for p in game.prizes])[0]
                session_id = self._repo.insert_session(
                    conn, account_id=customer.account_id, game_id=game.id, prize_index=prize.sort_order,
                    prize_label=prize.label, coins=prize.coins, played_on=today, created_at=now,
                )
                balance = wallet.balance + prize.coins
                if prize.coins:
                    self._repo.set_balance(conn, customer.account_id, balance)
                    self._repo.insert_ledger(conn, account_id=customer.account_id, delta=prize.coins,
                                             reason=LedgerReason.PLAY, ref=f"session:{session_id}",
                                             balance_after=balance, voucher_id=None, created_at=now)
                result = dict(session_id=session_id, prize_index=prize.sort_order, label=prize.label,
                              coins=prize.coins, balance=balance, spins_left=game.daily_limit - used - 1)
        if rejected:
            raise ConflictError(rejected)
        return result

    @retry_on_transient
    def redeem(self, principal, catalog_id, request_key):
        """Đổi xu lấy voucher. Gửi lại cùng request_key không trừ xu lần hai."""
        if not _positive_id(catalog_id):
            raise ValidationError(field_errors={"catalog_id": "Chọn phần thưởng"})
        if not isinstance(request_key, str) or not REQUEST_KEY.fullmatch(request_key):
            raise ValidationError(field_errors={"request_key": "Khóa yêu cầu không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            customer = self._vouchers._customer(conn, principal)
            # Khóa ví trước khi kiểm tra khóa yêu cầu: hai request trùng khóa chạy tuần tự.
            wallet = self._repo.wallet(conn, customer.account_id, lock=True)
            now = self._now()
            stores = {s.id: s.name for s in self._p1.list_stores(conn)}
            replay = self._repo.ledger_by_ref(conn, LedgerReason.REDEEM, request_key)
            if replay is not None:
                if replay.account_id != customer.account_id:
                    raise ConflictError("Khóa yêu cầu không hợp lệ")
                voucher = self._vouchers._repo.get_voucher(conn, voucher_id=replay.voucher_id)
                return dict(voucher=self._vouchers._view(voucher, now, stores), balance=wallet.balance, replayed=True)
            if wallet.is_locked:
                raise ConflictError(WALLET_LOCKED)
            catalog = self._vouchers._repo.get_catalog(conn, catalog_id)
            if catalog is None or catalog.coin_cost is None or not catalog.is_active:
                raise NotFoundError("Phần thưởng này không đổi được bằng xu")
            if wallet.balance < catalog.coin_cost:
                message = f"Không đủ xu: cần {catalog.coin_cost}, bạn đang có {wallet.balance}"
                raise ConflictError(message, field_errors={"catalog_id": message})
            voucher = self._vouchers.issue_in_transaction(
                conn, catalog=catalog, account_id=customer.account_id, source=VoucherSource.GAME,
                source_ref=f"coin:{request_key}", employee_id=None, store_id=None,
            )
            balance = wallet.balance - catalog.coin_cost
            self._repo.set_balance(conn, customer.account_id, balance)
            self._repo.insert_ledger(conn, account_id=customer.account_id, delta=-catalog.coin_cost,
                                     reason=LedgerReason.REDEEM, ref=request_key, balance_after=balance,
                                     voucher_id=voucher.id, created_at=now)
            return dict(voucher=self._vouchers._view(voucher, now, stores), balance=balance, replayed=False)

    # =================================================================================
    # Nhân viên / quản lý
    # =================================================================================
    def manage(self, actor):
        with self._errors(), self._transaction() as conn:
            current = self._vouchers._actor(conn, actor, Permission.OPERATE)
            game = self._game(conn)
            today = self._local_day(self._now())
            return dict(
                can_manage=can(current.role, Permission.MANAGE_REWARDS),
                can_configure=current.role == Role.ADMIN,
                game=dict(name=game.name, is_active=game.is_active, daily_limit=game.daily_limit,
                          min_interval_seconds=game.min_interval_seconds, prizes=list(game.prizes),
                          expected_coins=round(expected_coins(game.prizes), 1)),
                stats=self._repo.stats(conn, game.id, today),
                locked=self._repo.locked_wallets(conn),
                recent=self._repo.recent_sessions(conn, game.id, 20),
                suspicious_limit=SUSPICIOUS_LIMIT,
            )

    @retry_on_transient
    def save_game(self, actor, *, is_active, daily_limit, min_interval_seconds, prizes):
        """Cấu hình vòng quay dùng chung mọi cơ sở nên chỉ ADMIN được sửa."""
        if type(is_active) is not bool:
            raise ValidationError(field_errors={"is_active": "Giá trị không hợp lệ"})
        if type(daily_limit) is not int or not 1 <= daily_limit <= 20:
            raise ValidationError(field_errors={"daily_limit": "Số lượt mỗi ngày từ 1 đến 20"})
        if type(min_interval_seconds) is not int or not 1 <= min_interval_seconds <= 60:
            raise ValidationError(field_errors={"min_interval_seconds": "Khoảng cách từ 1 đến 60 giây"})
        if not isinstance(prizes, list) or not MIN_PRIZES <= len(prizes) <= MAX_PRIZES:
            raise ValidationError(field_errors={"prizes": f"Vòng quay cần {MIN_PRIZES}–{MAX_PRIZES} ô"})
        cleaned = []
        for index, prize in enumerate(prizes):
            label = prize.get("label") if isinstance(prize, dict) else None
            coins = prize.get("coins") if isinstance(prize, dict) else None
            weight = prize.get("weight") if isinstance(prize, dict) else None
            if (
                not isinstance(label, str) or not 1 <= len(label.strip()) <= 40
                or type(coins) is not int or not 0 <= coins <= 1000
                or type(weight) is not int or not 1 <= weight <= 1000
            ):
                raise ValidationError(field_errors={"prizes": f"Ô {index + 1}: nhãn 1–40 ký tự, xu 0–1000, tỉ lệ 1–1000"})
            cleaned.append(GamePrize(index, label.strip(), coins, weight))
        with self._errors(), self._transaction() as conn:
            current = self._vouchers._actor(conn, actor, Permission.MANAGE_REWARDS)
            if current.role != Role.ADMIN:
                raise PermissionDeniedError("Chỉ quản trị viên cấu hình trò chơi")
            game = self._game(conn, lock=True)
            self._repo.save_game(conn, game.id, is_active=is_active, daily_limit=daily_limit,
                                 min_interval_seconds=min_interval_seconds, prizes=cleaned)
            self._p1.audit(conn, current, "GAME_SAVE", game.id)
            return self._game(conn)

    @retry_on_transient
    def set_wallet_lock(self, actor, account_id, locked, reason=""):
        if not _positive_id(account_id) or type(locked) is not bool:
            raise ValidationError(field_errors={"account_id": "Tài khoản không hợp lệ"})
        if locked and (not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200):
            raise ValidationError(field_errors={"reason": "Nhập lý do khóa từ 3 đến 200 ký tự"})
        with self._errors(), self._transaction() as conn:
            current = self._vouchers._actor(conn, actor, Permission.MANAGE_REWARDS)
            if not self._repo.account_exists(conn, account_id):
                raise NotFoundError("Không tìm thấy tài khoản")
            wallet = self._repo.wallet(conn, account_id, lock=True)
            if locked == wallet.is_locked:
                raise ConflictError("Ví game đã ở trạng thái này")
            if locked:
                self._repo.lock_wallet(conn, account_id, reason.strip(), self._now())
            else:
                self._repo.unlock_wallet(conn, account_id)
            self._p1.audit(conn, current, "GAME_WALLET_LOCK" if locked else "GAME_WALLET_UNLOCK", account_id)
            return self._repo.wallet(conn, account_id)
