"""Đợt 1 — Menu đồ ăn/đồ uống và yêu cầu gọi món.

Quy tắc:
- Khách xem menu của cửa hàng đang hoạt động; chỉ được gọi món khi đang có phiên ACTIVE,
  và món phải thuộc đúng cửa hàng của máy đang ngồi.
- Giá, tên món, trạng thái còn món luôn đọc lại từ database lúc đặt; trình duyệt chỉ gửi
  mã món và số lượng. Món ẩn, hết món hoặc thuộc nhóm đã tắt đều bị từ chối.
- Chưa trừ tiền trong ví: nhân viên phục vụ và thu tiền tại quầy (không đụng luồng thanh toán phiên).
- MANAGER/ADMIN quản lý menu (Permission.MANAGE_MENU); mọi nhân viên được đánh dấu còn/hết món.
  Quyền xem, chuẩn bị, phục vụ, hủy và thu tiền POS được kiểm tra riêng ở backend.
  Thay đổi giá/trạng thái được lưu lịch sử,
  thao tác quản trị được ghi management_audit.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from uuid import uuid4
from uuid import UUID

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.menu import (
    MAX_OPEN_ORDERS,
    MAX_ORDER_LINES,
    MAX_PRICE,
    MAX_QUANTITY,
    MAX_SORT_ORDER,
    MIN_PRICE,
    MenuChangeField,
    MenuItem,
    MenuOrderLine,
    MenuOrderStatus,
    MenuPaymentMethod,
    MenuPage,
)
from cyberhub_manager.domain.p1 import CustomerSession, Permission, can
from cyberhub_manager.domain.loyalty import TIERS
from .pos_pricing import price_order

from .p1_runtime import errors, retry_on_transient

ITEM_NOT_FOUND = "Không tìm thấy món"
CATEGORY_NOT_FOUND = "Không tìm thấy nhóm món"
ORDER_NOT_FOUND = "Không tìm thấy yêu cầu gọi món"
STORE_INVALID = "Cơ sở không khả dụng"
NEED_ACTIVE_SESSION = "Bạn cần đang sử dụng máy tại CyberHub để gọi món"
ITEM_UNAVAILABLE = "Món này hiện không phục vụ"
TOO_MANY_OPEN = f"Bạn đang có {MAX_OPEN_ORDERS} yêu cầu chưa được phục vụ. Vui lòng chờ nhân viên."
ORDER_ALREADY_HANDLED = "Yêu cầu này đã được xử lý"
DUPLICATE_NAME = "Tên đã tồn tại trong cơ sở này"

PROMOTION_FIELDS = ("code", "kind", "item_id", "value", "minimum_tier", "starts_at", "ends_at", "is_active")
MAX_PROMOTION_DAYS = 366
PROMOTION_NOT_FOUND = "Không tìm thấy ưu đãi"
PROMOTION_EXPIRED = "Thời gian kết thúc đã qua. Chọn ngày kết thúc trong tương lai hoặc tắt ưu đãi."


def _aware(value):
    """MySQL lưu giờ UTC và đọc ra không kèm múi giờ: gắn UTC để so sánh và hiển thị đúng."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _promotion_value(field, value):
    """Giá trị ưu đãi dạng JSON ổn định để so sánh trước/sau và ghi lịch sử."""
    if field in ("starts_at", "ends_at"):
        return _aware(value).astimezone(timezone.utc).isoformat()
    if field == "is_active":
        return bool(value)
    return value


def _promotion_state(promo, now):
    """OFF: đang tắt · SCHEDULED: chưa đến ngày bắt đầu · EXPIRED: đã hết hạn · ACTIVE: đang áp dụng."""
    if not promo["is_active"]:
        return "OFF"
    if now < promo["starts_at"]:
        return "SCHEDULED"
    if now >= promo["ends_at"]:
        return "EXPIRED"
    return "ACTIVE"


def _promotion_view(promo, now, usage=None):
    view = dict(promo)
    view["starts_at"] = _aware(promo["starts_at"])
    view["ends_at"] = _aware(promo["ends_at"])
    view["is_active"] = bool(promo["is_active"])
    view["state"] = _promotion_state(view, now)
    used = (usage or {}).get(view["id"], {})
    view["orders_count"] = used.get("orders", 0)
    view["discount_total"] = used.get("discount", 0)
    return view


def _positive_id(value: object) -> bool:
    return type(value) is int and value > 0


def _text(value: object, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValidationError(field_errors={field: f"Nhập từ {minimum} đến {maximum} ký tự"})
    return value.strip()


def _flag(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(field_errors={field: "Giá trị không hợp lệ"})
    return value


def _sort(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SORT_ORDER:
        raise ValidationError(field_errors={"sort_order": f"Thứ tự từ 0 đến {MAX_SORT_ORDER}"})
    return value


def _price(value: object) -> int:
    if type(value) is not int or not MIN_PRICE <= value <= MAX_PRICE:
        raise ValidationError(
            field_errors={"price": f"Giá từ {MIN_PRICE:,} đến {MAX_PRICE:,} VND".replace(",", ".")}
        )
    return value


def _stock_quantity(value: object, *, allow_zero=False, field="quantity") -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or not minimum <= value <= 1_000_000_000:
        raise ValidationError(field_errors={field: "Số lượng không hợp lệ"})
    return value


def _request_uuid(value: object) -> str:
    try:
        parsed = UUID(value)
        if parsed.version != 4:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(field_errors={"request_id": "Cần mã yêu cầu UUID v4"}) from None
    return parsed.hex


def new_order_code() -> str:
    # "ORD-" + 16 hex = 20 ký tự, vừa cột menu_orders.code.
    return "ORD-" + uuid4().hex[:16].upper()


class MenuService:
    def __init__(self, repo=None, p1_repo=None, auth_repo=None, transaction_factory=None,
                 actor_provider=None, clock=None, inventory_repo=None):
        # Bản demo dùng repository bộ nhớ có resolve_actor; bản thật dùng MySQL.
        self._memory = hasattr(p1_repo, "resolve_actor")
        if not self._memory:
            from cyberhub_manager.database.transaction import transaction
            from cyberhub_manager.repositories.auth_repository import AuthRepository
            from cyberhub_manager.repositories.menu_repository import MenuRepository
            from cyberhub_manager.repositories.inventory_repository import InventoryRepository
            from cyberhub_manager.repositories.p1_repository import P1Repository

            transaction_factory = transaction_factory or transaction
            auth_repo = auth_repo or AuthRepository()
            repo = repo or MenuRepository()
            p1_repo = p1_repo or P1Repository()
            inventory_repo = inventory_repo or InventoryRepository()
        self._repo = repo
        self._inventory = inventory_repo
        self._p1 = p1_repo
        self._auth = auth_repo
        self._transaction = transaction_factory
        self._actor_provider = actor_provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        hold = int(os.getenv("CYBERHUB_POS_HOLD_MINUTES", "15"))
        if not 5 <= hold <= 120:
            raise ValueError("CYBERHUB_POS_HOLD_MINUTES must be between 5 and 120")
        self._hold_duration = timedelta(minutes=hold)

    def _errors(self):
        return errors(self._memory)

    # ----- Xác thực --------------------------------------------------------------
    def _actor(self, conn, actor, permission: Permission):
        """Đọc lại nhân viên từ DB/kho demo; không tin role/store do client gửi."""
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

    def _active_store(self, conn, store_id):
        store = self._p1.store(conn, store_id) if _positive_id(store_id) else None
        if store is None or store.status != "ACTIVE":
            raise ValidationError(field_errors={"store_id": STORE_INVALID})
        return store

    # ----- Dữ liệu dùng chung --------------------------------------------------------
    def _menu(self, conn, store_id, *, public: bool):
        categories = self._repo.list_categories(conn, store_id)
        items = self._repo.list_items(conn, store_id)
        if public:
            active = {c.id for c in categories if c.is_active}
            categories = [c for c in categories if c.is_active]
            items = [i for i in items if i.is_visible and i.category_id in active]
        pages = []
        for page in MenuPage:
            groups = []
            for category in sorted((c for c in categories if c.page == page), key=lambda c: (c.sort_order, c.id)):
                group_items = sorted((i for i in items if i.category_id == category.id),
                                     key=lambda i: (i.sort_order, i.id))
                if public and not group_items:
                    continue
                groups.append(dict(category=category, items=group_items))
            pages.append(dict(page=page, categories=groups))
        return dict(categories=categories, items=items, pages=pages)

    def _item_in_store(self, conn, item_id, store_id, *, lock=False) -> MenuItem:
        item = self._repo.get_item(conn, item_id, lock=lock) if _positive_id(item_id) else None
        if item is None or item.store_id != store_id:
            raise NotFoundError(ITEM_NOT_FOUND)
        return item

    def _category_in_store(self, conn, category_id, store_id):
        category = self._repo.get_category(conn, category_id) if _positive_id(category_id) else None
        if category is None or category.store_id != store_id:
            raise ValidationError(field_errors={"category_id": CATEGORY_NOT_FOUND})
        return category

    # =================================================================================
    # Khách hàng
    # =================================================================================
    def portal_menu(self, principal, store_id=None):
        """Menu công khai của một cơ sở + phiên đang chơi + yêu cầu gần đây của khách."""
        with self._errors(), self._transaction() as conn:
            customer = self._customer(conn, principal)
            session = self._repo.active_session(conn, customer.customer_id)
            stores = [s for s in self._p1.list_stores(conn) if s.status == "ACTIVE"]
            if store_id is None:
                store_id = session["store_id"] if session else (stores[0].id if stores else None)
            store = self._active_store(conn, store_id)
            menu = self._menu(conn, store.id, public=True)
            return dict(
                store_id=store.id,
                store_name=store.name,
                stores=[dict(id=s.id, name=s.name) for s in stores],
                pages=menu["pages"],
                session=None if session is None else dict(
                    machine_code=session["machine_code"], store_id=session["store_id"]
                ),
                can_order=session is not None and session["store_id"] == store.id,
                orders=self._repo.account_orders(conn, customer.account_id, 5),
            )

    def place_order(self, principal, lines, note=""):
        try:
            return self._place_order(principal, lines, note)
        except ConflictError as exc:
            if str(exc).startswith((ITEM_UNAVAILABLE, "Không đủ nguyên liệu:",
                                    "Tồn khả dụng vừa thay đổi")):
                with self._errors(), self._transaction() as conn:
                    customer = self._customer(conn, principal)
                    session = self._repo.active_session(conn, customer.customer_id)
                    if session is not None:
                        self._repo.record_unavailable_notification(conn, customer.account_id,
                            session["store_id"], self._clock())
            raise

    @retry_on_transient
    def _place_order(self, principal, lines, note=""):
        """Tạo yêu cầu gọi món; giá và trạng thái món lấy từ database."""
        if not isinstance(lines, list) or not 1 <= len(lines) <= MAX_ORDER_LINES:
            raise ValidationError(field_errors={"lines": f"Chọn từ 1 đến {MAX_ORDER_LINES} món"})
        requested: dict[int, int] = {}
        for line in lines:
            item_id = line.get("item_id") if isinstance(line, dict) else None
            quantity = line.get("quantity") if isinstance(line, dict) else None
            if not _positive_id(item_id) or type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
                raise ValidationError(field_errors={"lines": f"Số lượng mỗi món từ 1 đến {MAX_QUANTITY}"})
            if item_id in requested:
                raise ValidationError(field_errors={"lines": "Mỗi món chỉ xuất hiện một lần"})
            requested[item_id] = quantity
        if not isinstance(note, str) or len(note.strip()) > 200:
            raise ValidationError(field_errors={"note": "Ghi chú tối đa 200 ký tự"})

        with self._errors(), self._transaction() as conn:
            customer = self._customer(conn, principal)
            session = self._repo.active_session(conn, customer.customer_id)
            if session is None:
                raise ValidationError(field_errors={"session": NEED_ACTIVE_SESSION})
            if self._repo.count_open_orders(conn, customer.account_id) >= MAX_OPEN_ORDERS:
                raise ConflictError(TOO_MANY_OPEN)
            active_categories = {
                c.id for c in self._repo.list_categories(conn, session["store_id"]) if c.is_active
            }
            order_lines = []
            unavailable = []
            for item_id, quantity in requested.items():
                # FOR SHARE: món không bị tắt/đổi giá giữa lúc kiểm tra và lúc ghi.
                item = self._repo.get_item(conn, item_id, lock="share")
                if item is None or item.store_id != session["store_id"]:
                    raise NotFoundError(ITEM_NOT_FOUND)
                if not (item.is_visible and item.is_available and item.category_id in active_categories):
                    unavailable.append(item.name)
                    continue
                order_lines.append(MenuOrderLine(item.id, item.name, item.price, quantity))
            if unavailable:
                message = f"{ITEM_UNAVAILABLE}: {', '.join(unavailable)}"
                raise ConflictError(message, field_errors={"lines": message})
            member = self._p1.loyalty_summary(conn, customer.customer_id)
            pricing = price_order(order_lines,
                self._repo.active_promotions(conn, session["store_id"], self._clock()),
                member["tier"] if member["enabled"] else "BRONZE")
            code = new_order_code()
            order_id = self._repo.insert_order(
                conn,
                code=code,
                store_id=session["store_id"],
                account_id=customer.account_id,
                session_id=session["session_id"],
                machine_id=session["machine_id"],
                note=note.strip(),
                lines=order_lines,
                expires_at=self._clock() + self._hold_duration,
            )
            self._repo.save_order_pricing(conn, order_id, pricing)
            if self._inventory is not None:
                self._inventory.reserve_order(
                    conn, order_id, session["store_id"], customer.account_id, order_lines
                )
            order = self._repo.get_order(conn, order_id)
            self._repo.record_order_notification(
                conn, order, MenuOrderStatus.NEW, order.created_at,
            )
            return order

    def portal_image(self, principal, item_id):
        with self._errors(), self._transaction() as conn:
            self._customer(conn, principal)
            item = self._repo.get_item(conn, item_id) if _positive_id(item_id) else None
            if item is None or not item.is_visible:
                raise NotFoundError(ITEM_NOT_FOUND)
            return self._image(conn, item)

    def _image(self, conn, item):
        data = self._repo.get_image(conn, item.id)
        if data is None:
            raise NotFoundError("Món chưa có ảnh")
        return data

    # =================================================================================
    # Nhân viên / quản lý
    # =================================================================================
    def manage_menu(self, actor):
        """Toàn bộ menu của cơ sở đang thao tác, kể cả món ẩn, cho trang quản trị."""
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.POS_VIEW_ORDERS)
            menu = self._menu(conn, current.store_id, public=False)
            return dict(
                store_id=current.store_id,
                can_manage=can(current.role, Permission.MANAGE_MENU),
                can_set_availability=can(current.role, Permission.OPERATE),
                can_prepare=can(current.role, Permission.POS_PREPARE_ORDERS),
                can_serve=can(current.role, Permission.POS_SERVE_ORDERS),
                can_cancel=can(current.role, Permission.POS_CANCEL_ORDERS),
                can_collect_payment=can(current.role, Permission.POS_COLLECT_PAYMENT),
                categories=menu["categories"],
                items=menu["items"],
            )

    def list_promotions(self, actor):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            now = self._clock()
            usage = self._repo.promotion_usage(conn, current.store_id)
            return [_promotion_view(p, now, usage) for p in self._repo.list_promotions(conn, current.store_id)]

    def promotion_history(self, actor, promotion_id):
        """Lịch sử tạo/sửa/bật/tắt của một ưu đãi (mới nhất trước)."""
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            promo = self._repo.get_promotion(conn, promotion_id) if _positive_id(promotion_id) else None
            if promo is None or promo["store_id"] != current.store_id:
                raise NotFoundError(PROMOTION_NOT_FOUND)
            return self._repo.promotion_changes(conn, promotion_id)

    def _record_promotion_change(self, conn, actor, promotion_id, before, after):
        if before is None:
            action = "CREATE"
            changes = {f: [None, _promotion_value(f, after[f])] for f in PROMOTION_FIELDS}
        else:
            changes = {f: [_promotion_value(f, before[f]), _promotion_value(f, after[f])]
                       for f in PROMOTION_FIELDS
                       if _promotion_value(f, before[f]) != _promotion_value(f, after[f])}
            if not changes:
                return  # lưu lại y nguyên: không tạo dòng lịch sử rỗng
            action = ("ENABLE" if after["is_active"] else "DISABLE") if list(changes) == ["is_active"] else "UPDATE"
        self._repo.record_promotion_change(conn, promotion_id, actor.employee_id, action, changes)

    @retry_on_transient
    def set_promotion_active(self, actor, promotion_id, is_active):
        """Bật/tắt nhanh một ưu đãi. Không bật lại được ưu đãi đã quá ngày kết thúc."""
        is_active = _flag(is_active, "is_active")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            before = self._repo.get_promotion(conn, promotion_id) if _positive_id(promotion_id) else None
            if before is None or before["store_id"] != current.store_id:
                raise NotFoundError(PROMOTION_NOT_FOUND)
            if bool(before["is_active"]) != is_active:
                if is_active and _aware(before["ends_at"]) <= self._clock():
                    raise ValidationError(field_errors={"ends_at": PROMOTION_EXPIRED})
                self._repo.set_promotion_active(conn, current.store_id, promotion_id, is_active)
                after = self._repo.get_promotion(conn, promotion_id)
                self._record_promotion_change(conn, current, promotion_id, before, after)
                self._p1.audit(conn, current,
                               "POS_PROMOTION_ENABLE" if is_active else "POS_PROMOTION_DISABLE", promotion_id)
            return _promotion_view(self._repo.get_promotion(conn, promotion_id), self._clock())

    def quote_order(self, principal, lines):
        """Báo giá cho giỏ món của khách: cùng quy tắc ưu đãi như lúc đặt nhưng KHÔNG ghi gì.
        Số tiền thật vẫn do máy chủ tính lại khi đặt; món hết/ẩn không được tính vào báo giá."""
        if not isinstance(lines, list) or not 1 <= len(lines) <= MAX_ORDER_LINES:
            raise ValidationError(field_errors={"lines": f"Chọn từ 1 đến {MAX_ORDER_LINES} món"})
        requested: dict[int, int] = {}
        for line in lines:
            item_id = line.get("item_id") if isinstance(line, dict) else None
            quantity = line.get("quantity") if isinstance(line, dict) else None
            if not _positive_id(item_id) or type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
                raise ValidationError(field_errors={"lines": f"Số lượng mỗi món từ 1 đến {MAX_QUANTITY}"})
            if item_id in requested:
                raise ValidationError(field_errors={"lines": "Mỗi món chỉ xuất hiện một lần"})
            requested[item_id] = quantity
        with self._errors(), self._transaction() as conn:
            customer = self._customer(conn, principal)
            session = self._repo.active_session(conn, customer.customer_id)
            if session is None:
                raise ValidationError(field_errors={"session": NEED_ACTIVE_SESSION})
            active_categories = {c.id for c in self._repo.list_categories(conn, session["store_id"]) if c.is_active}
            order_lines, unavailable = [], []
            for item_id, quantity in requested.items():
                item = self._repo.get_item(conn, item_id)
                if item is None or item.store_id != session["store_id"]:
                    raise NotFoundError(ITEM_NOT_FOUND)
                if item.is_visible and item.is_available and item.category_id in active_categories:
                    order_lines.append(MenuOrderLine(item.id, item.name, item.price, quantity))
                else:
                    unavailable.append(item.name)
            member = self._p1.loyalty_summary(conn, customer.customer_id)
            pricing = price_order(order_lines,
                self._repo.active_promotions(conn, session["store_id"], self._clock()),
                member["tier"] if member["enabled"] else "BRONZE")
            return dict(gross_amount=pricing["snapshot"]["gross_amount"],
                        discount_amount=pricing["discount_amount"], final_amount=pricing["final_amount"],
                        promotion_code=pricing["promotion_code"], promotion_kind=pricing["promotion_kind"],
                        unavailable=unavailable)

    @retry_on_transient
    def save_promotion(self, actor, *, promotion_id=None, code, kind, item_id=None,
                       value, minimum_tier=None, starts_at, ends_at, is_active):
        code = _text(code, "code", 3, 30).upper()
        if not all(c.isascii() and (c.isalnum() or c in "_-") for c in code):
            raise ValidationError(field_errors={"code": "Chỉ dùng chữ, số, _ và -"})
        if kind not in ("BOGO", "PLAY_DRINK", "TIER_PERCENT"):
            raise ValidationError(field_errors={"kind": "Loại ưu đãi không hợp lệ"})
        if type(value) is not int or not 1 <= value <= (100 if kind == "TIER_PERCENT" else 1_000_000):
            raise ValidationError(field_errors={"value": "Giá trị ưu đãi không hợp lệ"})
        if kind == "BOGO" and value != 1:
            raise ValidationError(field_errors={"value": "Mua 3 trả 2 dùng giá trị 1"})
        if kind == "TIER_PERCENT":
            if minimum_tier not in TIERS or item_id is not None:
                raise ValidationError(field_errors={"minimum_tier": "Chọn hạng hợp lệ"})
        elif minimum_tier is not None or not _positive_id(item_id):
            raise ValidationError(field_errors={"item_id": "Chọn món áp dụng"})
        if (not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime)
                or starts_at.tzinfo is None or ends_at.tzinfo is None
                or starts_at >= ends_at):
            raise ValidationError(field_errors={"starts_at": "Khoảng thời gian không hợp lệ"})
        if ends_at - starts_at > timedelta(days=MAX_PROMOTION_DAYS):
            raise ValidationError(field_errors={"ends_at": f"Ưu đãi kéo dài tối đa {MAX_PROMOTION_DAYS} ngày"})
        is_active = _flag(is_active, "is_active")
        if is_active and ends_at <= self._clock():
            raise ValidationError(field_errors={"ends_at": PROMOTION_EXPIRED})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            if item_id is not None:
                item = self._item_in_store(conn, item_id, current.store_id)
                if kind == "PLAY_DRINK" and self._category_in_store(
                        conn, item.category_id, current.store_id).page is not MenuPage.DRINK:
                    raise ValidationError(field_errors={"item_id": "Chọn món thuộc nhóm đồ uống"})
            existing = self._repo.get_promotion(conn, promotion_id) if promotion_id is not None else None
            if promotion_id is not None and (existing is None or existing["store_id"] != current.store_id):
                raise NotFoundError("Không tìm thấy ưu đãi")
            promo_id = self._repo.save_promotion(conn, current.store_id, promotion_id,
                code, kind, item_id, value, minimum_tier, starts_at, ends_at, is_active)
            after = self._repo.get_promotion(conn, promo_id)
            self._record_promotion_change(conn, current, promo_id, existing, after)
            self._p1.audit(conn, current, "POS_PROMOTION_SAVE", promo_id)
            return _promotion_view(after, self._clock())

    def inventory_overview(self, actor):
        """Read stock for the actor's store; memory demo has no stock ledger."""
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.INVENTORY_VIEW)
            can_configure = can(current.role, Permission.INVENTORY_CONFIGURE)
            can_receive = can(current.role, Permission.INVENTORY_RECEIVE)
            can_issue = can(current.role, Permission.INVENTORY_ISSUE)
            can_count = can(current.role, Permission.INVENTORY_COUNT)
            can_approve = can(current.role, Permission.INVENTORY_APPROVE)
            capabilities = dict(
                can_configure=can_configure, can_receive=can_receive,
                can_issue=can_issue, can_count=can_count, can_approve=can_approve,
                can_manage=can_configure and can_receive,
            )
            if self._inventory is None:
                return dict(enabled=False, store_id=current.store_id,
                            actor_id=current.employee_id, ingredients=[],
                            counts=[], recipes=[], tracking={}, **capabilities)
            ingredients = self._inventory.list_ingredients(conn, current.store_id)
            counts = self._inventory.list_counts(conn, current.store_id) if can_count or can_approve else []
            tracking = {}
            recipes = []
            if can_configure:
                items = self._repo.list_items(conn, current.store_id)
                tracking = {row["item_id"]: bool(row["is_stock_tracked"])
                            for row in self._inventory.item_tracking(conn, current.store_id)}
                recipes = [dict(item_id=item.id, parts=self._inventory.get_recipe(conn, item.id))
                           for item in items]
            return dict(enabled=True, store_id=current.store_id,
                        actor_id=current.employee_id, ingredients=ingredients,
                        counts=counts,
                        recipes=recipes, tracking=tracking,
                        **capabilities)

    @retry_on_transient
    def add_ingredient(self, actor, *, name, unit, reorder_point=0):
        name = _text(name, "name", 1, 100)
        if unit not in ("g", "ml", "each"):
            raise ValidationError(field_errors={"unit": "Chọn g, ml hoặc cái"})
        if type(reorder_point) is not int or not 0 <= reorder_point <= 1_000_000_000:
            raise ValidationError(field_errors={"reorder_point": "Ngưỡng phải là số nguyên không âm"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.INVENTORY_CONFIGURE)
            if self._inventory is None:
                raise ConflictError("Kho chỉ khả dụng với database MySQL")
            ingredient_id = self._inventory.create_ingredient(
                conn, store_id=current.store_id,
                code="ING-" + uuid4().hex[:16].upper(), name=name, unit=unit,
                reorder_point=reorder_point,
            )
            self._p1.audit(conn, current, "INVENTORY_INGREDIENT_CREATE", ingredient_id)
            return self._inventory.get_ingredient(conn, ingredient_id)

    @retry_on_transient
    def receive_ingredient(self, actor, ingredient_id, *, quantity, reference_code,
                           request_id, note=""):
        if not _positive_id(ingredient_id):
            raise NotFoundError("Không tìm thấy nguyên liệu")
        if type(quantity) is not int or not 1 <= quantity <= 1_000_000_000:
            raise ValidationError(field_errors={"quantity": "Số lượng phải là số nguyên dương"})
        reference_code = _text(reference_code, "reference_code", 1, 60)
        if not isinstance(note, str) or len(note.strip()) > 255:
            raise ValidationError(field_errors={"note": "Ghi chú tối đa 255 ký tự"})
        try:
            request_uuid = UUID(request_id)
            if request_uuid.version != 4:
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            raise ValidationError(field_errors={"request_id": "Cần mã yêu cầu UUID v4"}) from None
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.INVENTORY_RECEIVE)
            if self._inventory is None:
                raise ConflictError("Kho chỉ khả dụng với database MySQL")
            ingredient = self._inventory.get_ingredient(conn, ingredient_id, lock=True)
            if ingredient is None or ingredient["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy nguyên liệu")
            if not ingredient["is_active"]:
                raise ConflictError("Nguyên liệu đã ngừng sử dụng")
            changed = self._inventory.receive(
                conn, ingredient=ingredient, quantity=quantity,
                reference_code=reference_code, note=note.strip(),
                employee_id=current.employee_id,
                idempotency_key="receive:" + request_uuid.hex,
            )
            if changed:
                self._p1.audit(conn, current, "INVENTORY_RECEIVE", ingredient_id)
            return self._inventory.get_ingredient(conn, ingredient_id)

    @retry_on_transient
    def move_ingredient(self, actor, ingredient_id, *, kind, quantity,
                        reference_code, request_id, note=""):
        """Issue unreserved stock or return physically reusable stock."""
        if not _positive_id(ingredient_id):
            raise NotFoundError("Không tìm thấy nguyên liệu")
        if kind not in ("ISSUE", "RETURN"):
            raise ValidationError(field_errors={"kind": "Chỉ được xuất hoặc trả kho"})
        quantity = _stock_quantity(quantity)
        reference_code = _text(reference_code, "reference_code", 1, 60)
        note = _text(note, "note", 1, 255)
        request_hex = _request_uuid(request_id)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.INVENTORY_ISSUE)
            if self._inventory is None:
                raise ConflictError("Kho chỉ khả dụng với database MySQL")
            ingredient = self._inventory.get_ingredient(conn, ingredient_id, lock=True)
            if ingredient is None or ingredient["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy nguyên liệu")
            if not ingredient["is_active"]:
                raise ConflictError("Nguyên liệu đã ngừng sử dụng")
            changed = self._inventory.manual_movement(
                conn, ingredient=ingredient, quantity=quantity, reference_code=reference_code,
                note=note, employee_id=current.employee_id,
                idempotency_key=f"{kind.lower()}:{request_hex}", kind=kind,
            )
            if changed:
                self._p1.audit(conn, current, f"INVENTORY_{kind}", ingredient_id)
            return self._inventory.get_ingredient(conn, ingredient_id)

    @retry_on_transient
    def propose_inventory_count(self, actor, ingredient_id, *, counted_on_hand,
                                reason, request_id):
        if not _positive_id(ingredient_id):
            raise NotFoundError("Không tìm thấy nguyên liệu")
        counted_on_hand = _stock_quantity(counted_on_hand, allow_zero=True,
                                          field="counted_on_hand")
        reason = _text(reason, "reason", 1, 255)
        request_hex = _request_uuid(request_id)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.INVENTORY_COUNT)
            if self._inventory is None:
                raise ConflictError("Kho chỉ khả dụng với database MySQL")
            ingredient = self._inventory.get_ingredient(conn, ingredient_id, lock=True)
            if ingredient is None or ingredient["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy nguyên liệu")
            if not ingredient["is_active"]:
                raise ConflictError("Nguyên liệu đã ngừng sử dụng")
            proposal, created = self._inventory.propose_count(
                conn, ingredient=ingredient, counted_on_hand=counted_on_hand,
                reason=reason, employee_id=current.employee_id, request_id=request_hex,
            )
            if created:
                self._p1.audit(conn, current, "INVENTORY_COUNT_PROPOSE", proposal["id"])
            return proposal

    @retry_on_transient
    def decide_inventory_count(self, actor, count_id, *, approve):
        if not _positive_id(count_id):
            raise NotFoundError("Không tìm thấy phiếu kiểm kê")
        approve = _flag(approve, "approve")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.INVENTORY_APPROVE)
            if self._inventory is None:
                raise ConflictError("Kho chỉ khả dụng với database MySQL")
            preview = self._inventory.get_count(conn, count_id)
            if preview is None or preview["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy phiếu kiểm kê")
            ingredient = self._inventory.get_ingredient(conn, preview["ingredient_id"], lock=True)
            if ingredient is None or ingredient["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy nguyên liệu")
            proposal = self._inventory.get_count(conn, count_id, lock=True)
            if (proposal is None or proposal["store_id"] != current.store_id
                    or proposal["ingredient_id"] != ingredient["id"]):
                raise ConflictError("Phiếu kiểm kê vừa thay đổi")
            if proposal["proposed_by"] == current.employee_id:
                raise PermissionDeniedError("Người đề xuất không được tự duyệt")
            decided = self._inventory.decide_count(
                conn, count=proposal, ingredient=ingredient,
                employee_id=current.employee_id, approve=approve,
            )
            self._p1.audit(conn, current,
                           "INVENTORY_COUNT_APPROVE" if approve else "INVENTORY_COUNT_REJECT",
                           count_id)
            return decided

    @retry_on_transient
    def set_item_recipe(self, actor, item_id, *, parts, track_stock=True):
        if not _positive_id(item_id):
            raise NotFoundError(ITEM_NOT_FOUND)
        track_stock = _flag(track_stock, "track_stock")
        if not isinstance(parts, list) or len(parts) > 30 or (track_stock and not parts):
            raise ValidationError(field_errors={"parts": "Món quản lý kho cần từ 1 đến 30 nguyên liệu"})
        parsed = []
        seen = set()
        for part in parts:
            ingredient_id = part.get("ingredient_id") if isinstance(part, dict) else None
            quantity = part.get("quantity_per_unit") if isinstance(part, dict) else None
            if (not _positive_id(ingredient_id) or ingredient_id in seen or
                    type(quantity) is not int or not 1 <= quantity <= 1_000_000_000):
                raise ValidationError(field_errors={"parts": "Nguyên liệu hoặc định lượng không hợp lệ"})
            parsed.append((ingredient_id, quantity))
            seen.add(ingredient_id)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.INVENTORY_CONFIGURE)
            if self._inventory is None:
                raise ConflictError("Kho chỉ khả dụng với database MySQL")
            item = self._item_in_store(conn, item_id, current.store_id, lock=True)
            for ingredient in self._inventory._lock_ingredients(conn, seen).values():
                if ingredient["store_id"] != current.store_id or not ingredient["is_active"]:
                    raise ValidationError(field_errors={"parts": "Nguyên liệu không khả dụng tại cửa hàng"})
            self._inventory.replace_recipe(conn, item.id, parsed, track_stock)
            self._p1.audit(conn, current, "INVENTORY_RECIPE_SAVE", item.id)
            return dict(item_id=item.id, track_stock=track_stock,
                        parts=self._inventory.get_recipe(conn, item.id))

    @retry_on_transient
    def save_category(self, actor, category_id, *, page, name, sort_order, is_active):
        try:
            page = MenuPage(page)
        except ValueError:
            raise ValidationError(field_errors={"page": "Chọn trang Đồ ăn hoặc Đồ uống"}) from None
        name = _text(name, "name", 1, 60)
        sort_order = _sort(sort_order)
        is_active = _flag(is_active, "is_active")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            others = [c for c in self._repo.list_categories(conn, current.store_id) if c.id != category_id]
            if any(c.name.casefold() == name.casefold() for c in others):
                raise ConflictError(DUPLICATE_NAME, field_errors={"name": DUPLICATE_NAME})
            if category_id is None:
                category_id = self._repo.insert_category(
                    conn, store_id=current.store_id, page=page, name=name,
                    sort_order=sort_order, is_active=is_active,
                )
            else:
                existing = self._repo.get_category(conn, category_id, lock=True) if _positive_id(category_id) else None
                if existing is None or existing.store_id != current.store_id:
                    raise NotFoundError(CATEGORY_NOT_FOUND)
                self._repo.update_category(conn, category_id, page=page, name=name,
                                           sort_order=sort_order, is_active=is_active)
            self._p1.audit(conn, current, "MENU_CATEGORY_SAVE", category_id)
            return self._repo.get_category(conn, category_id)

    @retry_on_transient
    def save_item(self, actor, item_id, *, category_id, name, description, price, sort_order,
                  is_visible, is_available):
        name = _text(name, "name", 1, 80)
        if not isinstance(description, str) or len(description.strip()) > 200:
            raise ValidationError(field_errors={"description": "Mô tả tối đa 200 ký tự"})
        description = description.strip()
        price = _price(price)
        sort_order = _sort(sort_order)
        is_visible = _flag(is_visible, "is_visible")
        is_available = _flag(is_available, "is_available")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            category = self._category_in_store(conn, category_id, current.store_id)
            others = [i for i in self._repo.list_items(conn, current.store_id) if i.id != item_id]
            if any(i.name.casefold() == name.casefold() for i in others):
                raise ConflictError(DUPLICATE_NAME, field_errors={"name": DUPLICATE_NAME})
            fields = dict(category_id=category.id, name=name, description=description, price=price,
                          sort_order=sort_order, is_visible=is_visible, is_available=is_available)
            if item_id is None:
                item_id = self._repo.insert_item(conn, store_id=current.store_id, **fields)
                self._change(conn, current, item_id, MenuChangeField.CREATE, None, f"{name} · {price}")
            else:
                before = self._item_in_store(conn, item_id, current.store_id, lock=True)
                self._repo.update_item(conn, item_id, **fields)
                for field, old, new in (
                    (MenuChangeField.NAME, before.name, name),
                    (MenuChangeField.CATEGORY, before.category_id, category.id),
                    (MenuChangeField.PRICE, before.price, price),
                    (MenuChangeField.VISIBLE, before.is_visible, is_visible),
                    (MenuChangeField.AVAILABLE, before.is_available, is_available),
                ):
                    if old != new:
                        self._change(conn, current, item_id, field, old, new)
            self._p1.audit(conn, current, "MENU_ITEM_SAVE", item_id)
            return self._repo.get_item(conn, item_id)

    @retry_on_transient
    def set_item_available(self, actor, item_id, available):
        """Mọi nhân viên được đánh dấu còn/hết món ngay tại quầy."""
        available = _flag(available, "available")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.OPERATE)
            item = self._item_in_store(conn, item_id, current.store_id, lock=True)
            if item.is_available != available:
                self._repo.set_item_available(conn, item.id, available)
                self._change(conn, current, item.id, MenuChangeField.AVAILABLE, item.is_available, available)
                self._p1.audit(conn, current, "MENU_ITEM_AVAILABILITY", item.id)
            return self._repo.get_item(conn, item.id)

    @retry_on_transient
    def upload_item_image(self, actor, item_id, content):
        from .avatar import normalize_avatar

        try:
            data, digest = normalize_avatar(content)
        except ValidationError as error:
            raise ValidationError(field_errors={"image": next(iter(error.field_errors.values()))}) from None
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            item = self._item_in_store(conn, item_id, current.store_id, lock=True)
            self._repo.save_image(conn, item.id, data, digest)
            self._change(conn, current, item.id, MenuChangeField.IMAGE, item.image_version, digest[:12])
            self._p1.audit(conn, current, "MENU_ITEM_IMAGE", item.id)
            return self._repo.get_item(conn, item.id)

    def item_image(self, actor, item_id):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.OPERATE)
            return self._image(conn, self._item_in_store(conn, item_id, current.store_id))

    def item_history(self, actor, item_id):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            item = self._item_in_store(conn, item_id, current.store_id)
            return self._repo.item_changes(conn, item.id)

    def _change(self, conn, actor, item_id, field, old, new):
        self._repo.record_change(
            conn,
            item_id=item_id,
            employee_id=actor.employee_id,
            field=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
        )

    # ----- Yêu cầu gọi món --------------------------------------------------------------
    def list_orders(self, actor, status="NEW"):
        try:
            status = None if status in (None, "", "ALL") else MenuOrderStatus(status)
        except ValueError:
            raise ValidationError(field_errors={"status": "Trạng thái không hợp lệ"}) from None
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.POS_VIEW_ORDERS)
            return self._repo.list_orders(conn, current.store_id, status)

    def paid_revenue(self, actor, date_from, date_to):
        """Only settled orders count; the caller's store defines the scope."""
        from cyberhub_manager.services.report_service import local_dates_to_utc_range

        if (type(date_from) is not date or type(date_to) is not date
                or date_from > date_to or (date_to - date_from).days > 3660):
            raise ValidationError(field_errors={"date_to": "Chọn khoảng ngày hợp lệ, tối đa 10 năm"})
        start, before = local_dates_to_utc_range(date_from, date_to)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_MENU)
            return self._repo.paid_order_report(conn, current.store_id, start, before)

    def maintain_holds(self, *, now=None, limit=100):
        """Trusted worker entry point; retries are safe and never cancel PREPARING."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be 1..500")
        now = now or self._clock()
        if now.tzinfo is None:
            raise ValueError("now must include timezone")
        warned = expired = 0
        with self._errors(), self._transaction() as conn:
            candidates = self._repo.pending_holds(conn, now + timedelta(minutes=2), limit)
        for order_id in candidates:
            with self._errors(), self._transaction() as conn:
                order = self._repo.get_order(conn, order_id, lock=True)
                if order is None or order.status is not MenuOrderStatus.NEW or order.reservation_expires_at is None:
                    continue
                if order.reservation_expires_at <= now:
                    if not self._repo.finish_order(conn, order.id, MenuOrderStatus.CANCELLED,
                                                   None, reason="AUTO_EXPIRED"):
                        continue
                    if self._inventory is not None:
                        self._inventory.transition_order(conn, order, MenuOrderStatus.CANCELLED,
                                                         None, reason="AUTO_EXPIRED")
                    updated = self._repo.get_order(conn, order.id)
                    self._repo.record_order_notification(conn, updated, MenuOrderStatus.CANCELLED, now)
                    expired += 1
                elif order.reservation_expires_at <= now + timedelta(minutes=2):
                    warned += int(self._repo.record_hold_warning(conn, order, now))
        return dict(warned=warned, expired=expired)

    @retry_on_transient
    def finish_order(self, actor, order_id, status, *, reason=None):
        try:
            status = MenuOrderStatus(status)
        except ValueError:
            status = None
        if status not in (MenuOrderStatus.PREPARING, MenuOrderStatus.SERVED, MenuOrderStatus.CANCELLED):
            raise ValidationError(field_errors={"status": "Chọn Đang chuẩn bị, Đã phục vụ hoặc Hủy"})
        permission = {
            MenuOrderStatus.PREPARING: Permission.POS_PREPARE_ORDERS,
            MenuOrderStatus.SERVED: Permission.POS_SERVE_ORDERS,
            MenuOrderStatus.CANCELLED: Permission.POS_CANCEL_ORDERS,
        }[status]
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, permission)
            order = self._repo.get_order(conn, order_id, lock=True) if _positive_id(order_id) else None
            if order is None or order.store_id != current.store_id:
                raise NotFoundError(ORDER_NOT_FOUND)
            if status is MenuOrderStatus.CANCELLED:
                if order.status is MenuOrderStatus.PREPARING or reason is not None:
                    reason = _text(reason, "reason", 1, 255)
            else:
                reason = None
            # The reason belongs to the order, including orders without stock tracking.
            if not self._repo.finish_order(
                conn, order.id, status, current.employee_id, reason=reason,
            ):
                raise ConflictError(ORDER_ALREADY_HANDLED)
            if self._inventory is not None:
                self._inventory.transition_order(
                    conn, order, status, current.employee_id, reason=reason,
                )
            self._p1.audit(conn, current, f"MENU_ORDER_{status.value}", order.id)
            updated = self._repo.get_order(conn, order.id)
            self._repo.record_order_notification(
                conn, updated, status, self._clock(),
            )
            return updated

    @retry_on_transient
    def pay_order(self, actor, order_id, method):
        try:
            method = MenuPaymentMethod(method)
        except ValueError:
            raise ValidationError(field_errors={"method": "Chọn tiền mặt hoặc chuyển khoản"}) from None
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.POS_COLLECT_PAYMENT)
            order = self._repo.get_order(conn, order_id, lock=True) if _positive_id(order_id) else None
            if order is None or order.store_id != current.store_id:
                raise NotFoundError(ORDER_NOT_FOUND)
            if not self._repo.pay_order(conn, order.id, method, current.employee_id, self._clock()):
                raise ConflictError("Chỉ thanh toán đơn đã phục vụ và chưa thanh toán")
            self._p1.audit(conn, current, f"MENU_ORDER_PAID_{method.value}", order.id)
            updated = self._repo.get_order(conn, order.id)
            self._repo.record_order_notification(
                conn, updated, MenuOrderStatus.PAID, updated.paid_at,
            )
            return updated

    @retry_on_transient
    def request_reversal(self, actor, order_id, *, reason, disposition):
        reason = _text(reason, "reason", 5, 255)
        if disposition not in ("RESTOCK", "WASTE"):
            raise ValidationError(field_errors={"disposition": "Chọn nhập trả hoặc hao hụt"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.POS_REQUEST_REVERSAL)
            order = self._repo.get_order(conn, order_id, lock=True) if _positive_id(order_id) else None
            if order is None or order.store_id != current.store_id:
                raise NotFoundError(ORDER_NOT_FOUND)
            if order.status not in (MenuOrderStatus.SERVED, MenuOrderStatus.PAID):
                raise ConflictError("Chỉ được đề xuất hủy/hoàn đơn đã phục vụ")
            if self._repo.get_reversal(conn, order.id):
                raise ConflictError("Đơn này đã có yêu cầu hủy/hoàn")
            reversal_id = self._repo.request_reversal(conn, order, current.employee_id,
                                                      reason, disposition)
            if not reversal_id:
                raise ConflictError("Đơn này đã có yêu cầu hủy/hoàn")
            self._p1.audit(conn, current, "POS_REVERSAL_REQUEST", order.id)
            return self._repo.get_reversal(conn, order.id)

    def list_reversals(self, actor, status="PENDING"):
        if status not in ("PENDING", "APPROVED", "REJECTED"):
            raise ValidationError(field_errors={"status": "Trạng thái không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.POS_REQUEST_REVERSAL)
            return self._repo.list_reversals(conn, current.store_id, status)

    @retry_on_transient
    def decide_reversal(self, actor, order_id, *, approve, refund_confirmed=False,
                        refund_method=None, refund_reference=None):
        if type(approve) is not bool or type(refund_confirmed) is not bool:
            raise ValidationError("Quyết định không hợp lệ")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.POS_APPROVE_REVERSAL)
            order = self._repo.get_order(conn, order_id, lock=True) if _positive_id(order_id) else None
            if order is None or order.store_id != current.store_id:
                raise NotFoundError(ORDER_NOT_FOUND)
            request = self._repo.get_reversal(conn, order.id, lock=True)
            if request is None or request["status"] != "PENDING":
                raise ConflictError("Không có yêu cầu đang chờ duyệt")
            if request["requested_by"] == current.employee_id:
                raise PermissionDeniedError("Người đề xuất không được tự duyệt")
            if order.status not in (MenuOrderStatus.SERVED, MenuOrderStatus.PAID):
                raise ConflictError("Trạng thái đơn đã thay đổi")
            amount = max(0, order.total_amount - order.discount_amount) if order.status is MenuOrderStatus.PAID else 0
            if approve and amount:
                if not refund_confirmed or refund_method not in ("CASH", "TRANSFER"):
                    raise ValidationError(field_errors={"refund_confirmed": "Xác nhận đã hoàn tiền và chọn phương thức"})
                if refund_method == "TRANSFER":
                    refund_reference = _text(refund_reference, "refund_reference", 3, 100)
                else:
                    refund_reference = None
            else:
                refund_method = refund_reference = None
            now = self._clock()
            if not self._repo.decide_reversal(conn, request["id"], current.employee_id,
                                               now, approve, amount if approve else 0,
                                               refund_method, refund_reference):
                raise ConflictError("Yêu cầu đã được xử lý")
            if approve:
                target = (MenuOrderStatus.REFUNDED if order.status is MenuOrderStatus.PAID
                          else MenuOrderStatus.CANCELLED)
                if not self._repo.set_reversed_status(conn, order, target, current.employee_id,
                                                      request["reason"]):
                    raise ConflictError("Trạng thái đơn đã thay đổi")
                if self._inventory is not None:
                    self._inventory.reverse_served_order(conn, order, current.employee_id,
                        restock=request["disposition"] == "RESTOCK", reason=request["reason"])
                updated = self._repo.get_order(conn, order.id)
                self._repo.record_order_notification(conn, updated, target, now)
            self._p1.audit(conn, current,
                           "POS_REVERSAL_APPROVED" if approve else "POS_REVERSAL_REJECTED", order.id)
            return self._repo.get_reversal(conn, order.id)
