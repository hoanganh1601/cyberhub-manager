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
from cyberhub_manager.application.services.pos_pricing import price_order

from cyberhub_manager.application.services.p1_runtime import errors, retry_on_transient

from cyberhub_manager.application.services.menu_shared import (
    ITEM_NOT_FOUND,
    ITEM_UNAVAILABLE,
    NEED_ACTIVE_SESSION,
    STORE_INVALID,
    TOO_MANY_OPEN,
    new_order_code,
    positive_id as _positive_id,
)
from cyberhub_manager.application.services.menu_catalog_service import MenuCatalogMixin
from cyberhub_manager.application.services.menu_inventory_service import MenuInventoryMixin
from cyberhub_manager.application.services.menu_order_service import MenuOrderMixin


class MenuService(MenuCatalogMixin, MenuInventoryMixin, MenuOrderMixin):
    def __init__(
        self,
        repo=None,
        p1_repo=None,
        auth_repo=None,
        transaction_factory=None,
        actor_provider=None,
        clock=None,
        inventory_repo=None,
        shift_service=None,
        management_repo=None,
        portal_repo=None,
        loyalty_repo=None,
    ):
        # Bản demo dùng repository bộ nhớ có resolve_actor; bản thật dùng MySQL.
        memory_repo = management_repo or p1_repo
        self._memory = hasattr(memory_repo, "resolve_actor")
        if not self._memory:
            from cyberhub_manager.infrastructure.database.transaction import transaction
            from cyberhub_manager.infrastructure.repositories.auth_repository import AuthRepository
            from cyberhub_manager.infrastructure.repositories.inventory_repository import InventoryRepository
            from cyberhub_manager.infrastructure.repositories.loyalty_repository import LoyaltyRepository
            from cyberhub_manager.infrastructure.repositories.management_repository import ManagementRepository
            from cyberhub_manager.infrastructure.repositories.menu_repository import MenuRepository
            from cyberhub_manager.infrastructure.repositories.portal_repository import PortalRepository

            transaction_factory = transaction_factory or transaction
            auth_repo = auth_repo or AuthRepository()
            repo = repo or MenuRepository()
            management_repo = management_repo or p1_repo or ManagementRepository()
            portal_repo = portal_repo or (
                p1_repo if hasattr(p1_repo, "customer_credentials") else PortalRepository()
            )
            loyalty_repo = loyalty_repo or (
                p1_repo if hasattr(p1_repo, "loyalty_summary") else LoyaltyRepository()
            )
            inventory_repo = inventory_repo or InventoryRepository()
        else:
            management_repo = memory_repo
            portal_repo = portal_repo or memory_repo
            loyalty_repo = loyalty_repo or memory_repo
        self._repo = repo
        self._inventory = inventory_repo
        self._management = management_repo
        self._portal = portal_repo
        self._loyalty = loyalty_repo
        self._auth = auth_repo
        self._transaction = transaction_factory
        self._actor_provider = actor_provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._shifts = shift_service
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
            current = self._management.resolve_actor(actor)
        else:
            from cyberhub_manager.application.services.access import operating_actor

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
        record = self._portal.customer_credentials(conn, account_id=principal.account_id)
        if (
            not record
            or record[0].customer_id != principal.customer_id
            or record[0].auth_version != principal.auth_version
        ):
            raise PermissionDeniedError()
        return record[0]

    def _active_store(self, conn, store_id):
        store = self._management.store(conn, store_id) if _positive_id(store_id) else None
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
            stores = [s for s in self._management.list_stores(conn) if s.status == "ACTIVE"]
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
            member = self._loyalty.loyalty_summary(conn, customer.customer_id)
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
