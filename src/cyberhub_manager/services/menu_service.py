"""Đợt 1 — Menu đồ ăn/đồ uống và yêu cầu gọi món.

Quy tắc:
- Khách xem menu của cửa hàng đang hoạt động; chỉ được gọi món khi đang có phiên ACTIVE,
  và món phải thuộc đúng cửa hàng của máy đang ngồi.
- Giá, tên món, trạng thái còn món luôn đọc lại từ database lúc đặt; trình duyệt chỉ gửi
  mã món và số lượng. Món ẩn, hết món hoặc thuộc nhóm đã tắt đều bị từ chối.
- Chưa trừ tiền trong ví: nhân viên phục vụ và thu tiền tại quầy (không đụng luồng thanh toán phiên).
- MANAGER/ADMIN quản lý menu (Permission.MANAGE_MENU); mọi nhân viên được đánh dấu còn/hết món
  và xử lý yêu cầu gọi món (Permission.OPERATE). Thay đổi giá/trạng thái được lưu lịch sử,
  thao tác quản trị được ghi management_audit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

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
    MenuPage,
)
from cyberhub_manager.domain.p1 import CustomerSession, Permission, can

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


def new_order_code() -> str:
    # "ORD-" + 16 hex = 20 ký tự, vừa cột menu_orders.code.
    return "ORD-" + uuid4().hex[:16].upper()


class MenuService:
    def __init__(self, repo=None, p1_repo=None, auth_repo=None, transaction_factory=None,
                 actor_provider=None, clock=None):
        # Bản demo dùng repository bộ nhớ có resolve_actor; bản thật dùng MySQL.
        self._memory = hasattr(p1_repo, "resolve_actor")
        if not self._memory:
            from cyberhub_manager.database.transaction import transaction
            from cyberhub_manager.repositories.auth_repository import AuthRepository
            from cyberhub_manager.repositories.menu_repository import MenuRepository
            from cyberhub_manager.repositories.p1_repository import P1Repository

            transaction_factory = transaction_factory or transaction
            auth_repo = auth_repo or AuthRepository()
            repo = repo or MenuRepository()
            p1_repo = p1_repo or P1Repository()
        self._repo = repo
        self._p1 = p1_repo
        self._auth = auth_repo
        self._transaction = transaction_factory
        self._actor_provider = actor_provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))

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

    @retry_on_transient
    def place_order(self, principal, lines, note=""):
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
            )
            return self._repo.get_order(conn, order_id)

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
            current = self._actor(conn, actor, Permission.OPERATE)
            menu = self._menu(conn, current.store_id, public=False)
            return dict(
                store_id=current.store_id,
                can_manage=can(current.role, Permission.MANAGE_MENU),
                categories=menu["categories"],
                items=menu["items"],
            )

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
            current = self._actor(conn, actor, Permission.OPERATE)
            return self._repo.list_orders(conn, current.store_id, status)

    @retry_on_transient
    def finish_order(self, actor, order_id, status):
        try:
            status = MenuOrderStatus(status)
        except ValueError:
            status = None
        if status not in (MenuOrderStatus.SERVED, MenuOrderStatus.CANCELLED):
            raise ValidationError(field_errors={"status": "Chọn Đã phục vụ hoặc Hủy"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.OPERATE)
            order = self._repo.get_order(conn, order_id) if _positive_id(order_id) else None
            if order is None or order.store_id != current.store_id:
                raise NotFoundError(ORDER_NOT_FOUND)
            # Cập nhật có điều kiện status='NEW': hai nhân viên bấm cùng lúc chỉ một người thắng.
            if not self._repo.finish_order(conn, order.id, status, current.employee_id):
                raise ConflictError(ORDER_ALREADY_HANDLED)
            self._p1.audit(conn, current, f"MENU_ORDER_{status.value}", order.id)
            return self._repo.get_order(conn, order.id)
