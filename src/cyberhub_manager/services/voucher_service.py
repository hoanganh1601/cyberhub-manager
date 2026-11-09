"""Đợt 2 — Voucher và phần thưởng cơ bản.

Quy tắc chính:
- Voucher không quy đổi thành tiền mặt; không có API nào trả tiền từ voucher.
- Mã voucher sinh ngẫu nhiên (secrets), điều kiện được chụp lúc phát hành.
- Nhân viên xác nhận khi khách dùng: khóa dòng voucher (FOR UPDATE) rồi kiểm tra đúng chủ, còn ISSUED,
  chưa hết hạn, đúng cơ sở, khách đang hoạt động và điều kiện đơn tối thiểu. Đổi trạng thái bằng
  UPDATE có điều kiện status='ISSUED' nên dùng lại hay bấm hai lần đều bị chặn.
- Mọi lần phát hành, sử dụng, thu hồi và CẢ lần bị từ chối đều ghi voucher_events
  (lần từ chối vẫn được commit để lưu vết), thao tác quản trị ghi thêm management_audit.
- `issue_in_transaction` dùng chung cho Đợt 3/4 (game, quảng cáo): UNIQUE(source, source_ref)
  bảo đảm một nguồn chỉ phát một voucher.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.menu import MenuOrderStatus
from cyberhub_manager.domain.p1 import CustomerSession, Permission, can
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.voucher import (
    FOOD_TYPES,
    MAX_VALID_DAYS,
    VALUE_LIMITS,
    RedeemResult,
    RewardType,
    VoucherAction,
    VoucherSource,
    VoucherStatus,
)

from .p1_runtime import errors, retry_on_transient

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ O/0, I/1 để đọc mã không nhầm
CODE_PATTERN = re.compile(r"^[A-Z0-9]{4,20}$")

# Lý do từ chối (ghi vào voucher_events.reason và trả cho nhân viên).
REJECT_MESSAGES = {
    "UNKNOWN": "Mã voucher không tồn tại",
    "WRONG_OWNER": "Voucher không thuộc khách hàng này",
    "USED": "Voucher đã được sử dụng",
    "REVOKED": "Voucher đã bị khóa/thu hồi",
    "EXPIRED": "Voucher đã hết hạn",
    "WRONG_STORE": "Voucher không áp dụng tại cơ sở này",
    "CUSTOMER_INACTIVE": "Tài khoản khách đang bị khóa hoặc ngừng hoạt động",
    "ORDER_REQUIRED": "Voucher đồ ăn/đồ uống cần chọn yêu cầu gọi món của khách",
    "ORDER_INVALID": "Yêu cầu gọi món không thuộc khách này, khác cơ sở hoặc đã hủy",
    "ORDER_HAS_VOUCHER": "Yêu cầu gọi món này đã áp một voucher khác",
    "MIN_ORDER": "Chưa đạt giá trị đơn tối thiểu",
}


def new_voucher_code() -> str:
    return "CH" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def normalize_code(value: object) -> str:
    code = re.sub(r"[\s-]", "", value).upper() if isinstance(value, str) else ""
    if not CODE_PATTERN.fullmatch(code):
        raise ValidationError(field_errors={"code": "Mã voucher không hợp lệ"})
    return code


def _positive_id(value: object) -> bool:
    return type(value) is int and value > 0


class VoucherService:
    def __init__(self, repo=None, p1_repo=None, menu_repo=None, auth_repo=None, transaction_factory=None,
                 actor_provider=None, clock=None):
        self._memory = hasattr(p1_repo, "resolve_actor")
        if not self._memory:
            from cyberhub_manager.database.transaction import transaction
            from cyberhub_manager.repositories.auth_repository import AuthRepository
            from cyberhub_manager.repositories.menu_repository import MenuRepository
            from cyberhub_manager.repositories.p1_repository import P1Repository
            from cyberhub_manager.repositories.voucher_repository import VoucherRepository

            transaction_factory = transaction_factory or transaction
            auth_repo = auth_repo or AuthRepository()
            repo = repo or VoucherRepository()
            p1_repo = p1_repo or P1Repository()
            menu_repo = menu_repo or MenuRepository()
        self._repo = repo
        self._p1 = p1_repo
        self._menu = menu_repo
        self._auth = auth_repo
        self._transaction = transaction_factory
        self._actor_provider = actor_provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _errors(self):
        return errors(self._memory)

    def _now(self) -> datetime:
        return self._clock().astimezone(timezone.utc).replace(microsecond=0)

    # ----- Xác thực (giống MenuService) ----------------------------------------------
    def _actor(self, conn, actor, permission: Permission):
        if actor is None:
            raise PermissionDeniedError()
        if self._memory:
            current = self._p1.resolve_actor(actor)
        else:
            from .access import operating_actor

            logged_in = self._actor_provider() if self._actor_provider else None
            if (
                logged_in is None
                or logged_in.employee_id != actor.employee_id
                or logged_in.store_id != actor.store_id
            ):
                raise PermissionDeniedError()
            current = operating_actor(conn, self._auth, actor)
        if not can(current.role, permission):
            raise PermissionDeniedError()
        return current

    def _customer(self, conn, principal):
        if not isinstance(principal, CustomerSession):
            raise PermissionDeniedError()
        record = self._p1.customer_credentials(conn, account_id=principal.account_id)
        if (
            not record
            or record[0].customer_id != principal.customer_id
            or record[0].auth_version != principal.auth_version
        ):
            raise PermissionDeniedError()
        return record[0]

    # ----- Hiển thị ----------------------------------------------------------------
    def _view(self, voucher, now, store_names):
        return dict(
            id=voucher.id,
            code=voucher.code,
            name=voucher.catalog_name,
            reward_type=voucher.reward_type,
            value=voucher.value,
            min_order_amount=voucher.min_order_amount,
            store_name=store_names.get(voucher.store_id) if voucher.store_id else None,
            state=voucher.state(now),
            source=voucher.source,
            issued_at=voucher.issued_at,
            expires_at=voucher.expires_at,
            used_at=voucher.used_at,
            customer_id=voucher.customer_id,
            customer_name=voucher.customer_name,
        )

    def _store_names(self, conn):
        return {s.id: s.name for s in self._p1.list_stores(conn)}

    # =================================================================================
    # Khách hàng
    # =================================================================================
    def portal_vouchers(self, principal):
        with self._errors(), self._transaction() as conn:
            customer = self._customer(conn, principal)
            now = self._now()
            names = self._store_names(conn)
            items = [self._view(v, now, names) for v in self._repo.account_vouchers(conn, customer.account_id)]
            order = {"ACTIVE": 0, "EXPIRED": 1, "USED": 2, "REVOKED": 3}
            items.sort(key=lambda v: (order[v["state"].value], v["expires_at"]))
            return dict(
                items=items,
                active=sum(1 for v in items if v["state"].value == "ACTIVE"),
                as_of=now,
            )

    # =================================================================================
    # Nhân viên / quản lý
    # =================================================================================
    def overview(self, actor):
        """Trang Voucher: danh mục (quản lý) và nhật ký phát hành/sử dụng của cơ sở."""
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.OPERATE)
            manage = can(current.role, Permission.MANAGE_REWARDS)
            return dict(
                can_manage=manage,
                is_admin=current.role == Role.ADMIN,
                catalog=self._repo.list_catalog(conn, current.store_id) if manage else [],
                events=self._repo.list_events(conn, current.store_id),
            )

    @retry_on_transient
    def save_reward(self, actor, catalog_id, *, code, name, reward_type, value, min_order_amount, valid_days,
                    coin_cost, is_active, all_stores):
        code = code.strip().upper() if isinstance(code, str) else ""
        if not re.fullmatch(r"[A-Z0-9_-]{2,20}", code):
            raise ValidationError(field_errors={"code": "Mã 2–20 ký tự: chữ in hoa, số, - hoặc _"})
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValidationError(field_errors={"name": "Tên từ 1 đến 80 ký tự"})
        try:
            reward_type = RewardType(reward_type)
        except ValueError:
            raise ValidationError(field_errors={"reward_type": "Loại phần thưởng không hợp lệ"}) from None
        limit = VALUE_LIMITS[reward_type]
        if type(value) is not int or not 1 <= value <= limit:
            raise ValidationError(field_errors={"value": f"Giá trị từ 1 đến {limit:,}".replace(",", ".")})
        if type(min_order_amount) is not int or not 0 <= min_order_amount <= 10_000_000:
            raise ValidationError(field_errors={"min_order_amount": "Đơn tối thiểu từ 0 đến 10.000.000"})
        if reward_type not in FOOD_TYPES and min_order_amount:
            raise ValidationError(field_errors={"min_order_amount": "Chỉ voucher đồ ăn/đồ uống có đơn tối thiểu"})
        if type(valid_days) is not int or not 1 <= valid_days <= MAX_VALID_DAYS:
            raise ValidationError(field_errors={"valid_days": f"Hạn dùng từ 1 đến {MAX_VALID_DAYS} ngày"})
        if coin_cost is not None and (type(coin_cost) is not int or not 1 <= coin_cost <= 1_000_000):
            raise ValidationError(field_errors={"coin_cost": "Giá xu từ 1 đến 1.000.000 hoặc để trống"})
        if type(is_active) is not bool or type(all_stores) is not bool:
            raise ValidationError(field_errors={"is_active": "Giá trị không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_REWARDS)
            # Chỉ ADMIN tạo/sửa phần thưởng áp dụng mọi cơ sở.
            if all_stores and current.role != Role.ADMIN:
                raise PermissionDeniedError("Chỉ quản trị viên tạo phần thưởng cho mọi cơ sở")
            store_id = None if all_stores else current.store_id
            if catalog_id is not None:
                existing = self._repo.get_catalog(conn, catalog_id, lock=True) if _positive_id(catalog_id) else None
                if existing is None or (existing.store_id or None) not in (None, current.store_id):
                    raise NotFoundError("Không tìm thấy phần thưởng")
                if existing.store_id is None and current.role != Role.ADMIN:
                    raise PermissionDeniedError("Chỉ quản trị viên sửa phần thưởng dùng chung")
            if self._repo.catalog_code_taken(conn, code, catalog_id):
                raise ConflictError("Mã đã tồn tại", field_errors={"code": "Mã đã tồn tại"})
            fields = dict(code=code, name=name.strip(), store_id=store_id, reward_type=reward_type, value=value,
                          min_order_amount=min_order_amount, valid_days=valid_days, coin_cost=coin_cost,
                          is_active=is_active)
            if catalog_id is None:
                catalog_id = self._repo.insert_catalog(conn, **fields)
            else:
                self._repo.update_catalog(conn, catalog_id, **fields)
            self._p1.audit(conn, current, "REWARD_SAVE", catalog_id)
            return self._repo.get_catalog(conn, catalog_id)

    @retry_on_transient
    def issue_voucher(self, actor, catalog_id, customer_id):
        """Quản lý phát voucher thủ công cho một khách."""
        if not _positive_id(catalog_id) or not _positive_id(customer_id):
            raise ValidationError(field_errors={"customer_id": "Chọn phần thưởng và khách hàng"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_REWARDS)
            catalog = self._repo.get_catalog(conn, catalog_id)
            if catalog is None or catalog.store_id not in (None, current.store_id):
                raise NotFoundError("Không tìm thấy phần thưởng")
            customer = self._repo.customer_account(conn, customer_id)
            if customer is None or str(customer["status"]) != "ACTIVE":
                raise ValidationError(field_errors={"customer_id": REJECT_MESSAGES["CUSTOMER_INACTIVE"]})
            voucher = self.issue_in_transaction(
                conn, catalog=catalog, account_id=customer["account_id"], source=VoucherSource.MANUAL,
                source_ref=None, employee_id=current.employee_id, store_id=current.store_id,
            )
            self._p1.audit(conn, current, "VOUCHER_ISSUE", voucher.id)
            return voucher

    def issue_in_transaction(self, conn, *, catalog, account_id, source: VoucherSource, source_ref,
                             employee_id, store_id):
        """Phát voucher trong transaction của bên gọi (dùng lại cho game/quảng cáo ở Đợt 3/4)."""
        if not catalog.is_active:
            raise ConflictError("Phần thưởng đang tạm ngưng")
        if source_ref is not None:
            existing = self._repo.voucher_by_source(conn, source, source_ref)
            if existing is not None:
                return existing  # idempotent: gửi lại cùng nguồn không phát thêm
        now = self._now()
        voucher_id = self._repo.insert_voucher(
            conn, code=new_voucher_code(), catalog=catalog, account_id=account_id, source=source,
            source_ref=source_ref, issued_by=employee_id, issued_at=now,
            expires_at=now + timedelta(days=catalog.valid_days),
        )
        self._repo.insert_event(conn, voucher_id=voucher_id, action=VoucherAction.ISSUE, employee_id=employee_id,
                                store_id=store_id, reason=source.value)
        return self._repo.get_voucher(conn, voucher_id=voucher_id)

    def lookup(self, actor, code):
        """Xem trước voucher trước khi xác nhận: chủ sở hữu, trạng thái, yêu cầu gọi món áp được."""
        code = normalize_code(code)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.OPERATE)
            voucher = self._repo.get_voucher(conn, code=code)
            if voucher is None:
                raise NotFoundError(REJECT_MESSAGES["UNKNOWN"])
            now = self._now()
            orders = []
            if voucher.reward_type in FOOD_TYPES:
                orders = [
                    o for o in self._menu.account_orders(conn, voucher.account_id, 10)
                    if o.store_id == current.store_id and o.status != MenuOrderStatus.CANCELLED
                ]
            return dict(
                voucher=self._view(voucher, now, self._store_names(conn)),
                applies_here=voucher.store_id in (None, current.store_id),
                orders=orders,
            )

    def redeem(self, actor, code, customer_id, order_id=None):
        """Nhân viên xác nhận khách dùng voucher. Lần bị từ chối vẫn được ghi nhật ký."""
        code = normalize_code(code)
        if not _positive_id(customer_id):
            raise ValidationError(field_errors={"customer_id": "Chọn khách hàng đang dùng voucher"})
        if order_id is not None and not _positive_id(order_id):
            raise ValidationError(field_errors={"order_id": "Yêu cầu gọi món không hợp lệ"})
        rejected = None
        result = None
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.OPERATE)
            voucher = self._repo.get_voucher(conn, code=code, lock=True)
            reason = "UNKNOWN" if voucher is None else self._check(conn, current, voucher, customer_id, order_id)
            if reason:
                detail = REJECT_MESSAGES[reason]
                if reason == "MIN_ORDER":
                    detail += f" ({voucher.min_order_amount:,} VND)".replace(",", ".")
                self._repo.insert_event(
                    conn, voucher_id=None if voucher is None else voucher.id, action=VoucherAction.REJECT,
                    employee_id=current.employee_id, store_id=current.store_id,
                    reason=f"{reason}: {code}" if voucher is None else reason,
                )
                rejected = detail  # không raise trong transaction để nhật ký từ chối được commit
            else:
                result = self._apply(conn, current, voucher, order_id)
        if rejected:
            raise ConflictError(rejected, field_errors={"code": rejected})
        return result

    def _check(self, conn, current, voucher, customer_id, order_id):
        customer = self._repo.customer_account(conn, customer_id)
        if customer is None or customer["account_id"] != voucher.account_id:
            return "WRONG_OWNER"
        if voucher.status == VoucherStatus.USED:
            return "USED"
        if voucher.status == VoucherStatus.REVOKED:
            return "REVOKED"
        if self._now() >= voucher.expires_at:
            return "EXPIRED"
        if voucher.store_id not in (None, current.store_id):
            return "WRONG_STORE"
        if str(customer["status"]) != "ACTIVE":
            return "CUSTOMER_INACTIVE"
        if voucher.reward_type in FOOD_TYPES:
            if order_id is None:
                return "ORDER_REQUIRED"
            order = self._menu.get_order(conn, order_id)
            if (
                order is None
                or order.account_id != voucher.account_id
                or order.store_id != current.store_id
                or order.status == MenuOrderStatus.CANCELLED
            ):
                return "ORDER_INVALID"
            if self._repo.order_has_voucher(conn, order.id):
                return "ORDER_HAS_VOUCHER"
            if order.total_amount < voucher.min_order_amount:
                return "MIN_ORDER"
        return None

    def _apply(self, conn, current, voucher, order_id):
        now = self._now()
        discount = bonus = points = 0
        if voucher.reward_type in FOOD_TYPES:
            order = self._menu.get_order(conn, order_id)
            discount = min(voucher.value, order.total_amount)
        elif voucher.reward_type == RewardType.PLAYTIME_CREDIT:
            # Số dư khuyến mãi: chỉ trả giờ chơi, không rút tiền mặt.
            self._repo.credit_playtime(conn, account_id=voucher.account_id, amount=voucher.value,
                                       employee_id=current.employee_id, store_id=current.store_id)
            bonus = voucher.value
        else:
            self._repo.grant_points(conn, customer_id=voucher.customer_id, voucher_id=voucher.id,
                                    points=voucher.value, employee_id=current.employee_id)
            points = voucher.value
        if not self._repo.mark_used(conn, voucher.id, employee_id=current.employee_id, store_id=current.store_id,
                                    order_id=order_id if voucher.reward_type in FOOD_TYPES else None, used_at=now):
            raise ConflictError(REJECT_MESSAGES["USED"])
        self._repo.insert_event(conn, voucher_id=voucher.id, action=VoucherAction.REDEEM,
                                employee_id=current.employee_id, store_id=current.store_id,
                                reason=f"order={order_id}" if order_id else "")
        self._p1.audit(conn, current, "VOUCHER_REDEEM", voucher.id)
        return RedeemResult(
            voucher=self._repo.get_voucher(conn, voucher_id=voucher.id),
            reward_type=voucher.reward_type,
            discount=discount,
            bonus_credited=bonus,
            points_granted=points,
        )

    @retry_on_transient
    def revoke(self, actor, voucher_id, reason):
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200:
            raise ValidationError(field_errors={"reason": "Nhập lý do khóa từ 3 đến 200 ký tự"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_REWARDS)
            voucher = self._repo.get_voucher(conn, voucher_id=voucher_id, lock=True) if _positive_id(voucher_id) else None
            if voucher is None or voucher.store_id not in (None, current.store_id):
                raise NotFoundError("Không tìm thấy voucher")
            if not self._repo.revoke(conn, voucher.id, reason.strip()):
                raise ConflictError("Chỉ khóa được voucher chưa sử dụng")
            self._repo.insert_event(conn, voucher_id=voucher.id, action=VoucherAction.REVOKE,
                                    employee_id=current.employee_id, store_id=current.store_id,
                                    reason=reason.strip())
            self._p1.audit(conn, current, "VOUCHER_REVOKE", voucher.id)
            return self._repo.get_voucher(conn, voucher_id=voucher.id)
