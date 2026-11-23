"""Catalog and promotion operations for the menu/POS service."""

from datetime import datetime

from cyberhub_manager.domain.exceptions import ConflictError, NotFoundError, ValidationError
from cyberhub_manager.domain.menu import MenuPage
from cyberhub_manager.domain.p1 import Permission, can

from .menu_shared import (
    CATEGORY_NOT_FOUND,
    DUPLICATE_NAME,
    flag as _flag,
    positive_id as _positive_id,
    price as _price,
    sort_order as _sort,
    text as _text,
)
from .p1_runtime import retry_on_transient


class MenuCatalogMixin:
    """Catalog maintenance behavior composed into MenuService."""

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
            return self._repo.list_promotions(conn, current.store_id)

    @retry_on_transient
    def save_promotion(self, actor, *, promotion_id=None, code, kind, item_id,
                       value, starts_at, ends_at, is_active):
        code = _text(code, "code", 3, 30).upper()
        if not all(c.isascii() and (c.isalnum() or c in "_-") for c in code):
            raise ValidationError(field_errors={"code": "Chỉ dùng chữ, số, _ và -"})
        if kind not in ("BOGO", "PLAY_DRINK"):
            raise ValidationError(field_errors={"kind": "Promotion type is invalid"})
        if type(value) is not int or not 1 <= value <= 1_000_000:
            raise ValidationError(field_errors={"value": "Promotion value is invalid"})
        if kind == "BOGO" and value != 1:
            raise ValidationError(field_errors={"value": "Buy 3 pay 2 uses value 1"})
        if not _positive_id(item_id):
            raise ValidationError(field_errors={"item_id": "Select a menu item"})
        if (not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime)
                or starts_at.tzinfo is None or ends_at.tzinfo is None
                or starts_at >= ends_at):
            raise ValidationError(field_errors={"starts_at": "Khoảng thời gian không hợp lệ"})
        is_active = _flag(is_active, "is_active")
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
                code, kind, item_id, value, starts_at, ends_at, is_active)
            self._management.audit(conn, current, "POS_PROMOTION_SAVE", promo_id)
            return self._repo.get_promotion(conn, promo_id)

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
            self._management.audit(conn, current, "MENU_CATEGORY_SAVE", category_id)
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
            else:
                self._item_in_store(conn, item_id, current.store_id, lock=True)
                self._repo.update_item(conn, item_id, **fields)
            self._management.audit(conn, current, "MENU_ITEM_SAVE", item_id)
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
                self._management.audit(conn, current, "MENU_ITEM_AVAILABILITY", item.id)
            return self._repo.get_item(conn, item.id)
