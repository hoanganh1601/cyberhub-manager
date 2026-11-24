"""Inventory operations for the menu/POS service."""

from uuid import UUID, uuid4

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.policies import Permission, can

from cyberhub_manager.application.services.menu_shared import (
    ITEM_NOT_FOUND,
    flag as _flag,
    positive_id as _positive_id,
    request_uuid as _request_uuid,
    stock_quantity as _stock_quantity,
    text as _text,
)
from cyberhub_manager.application.services.service_runtime import retry_on_transient


class MenuInventoryMixin:
    """Inventory behavior composed into MenuService."""

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
                            counts=[], movements=[], items=[], recipes=[], tracking={},
                            **capabilities)
            ingredients = self._inventory.list_ingredients(conn, current.store_id)
            counts = self._inventory.list_counts(conn, current.store_id) if can_count or can_approve else []
            movements = (
                self._inventory.list_movements(conn, current.store_id)
                if hasattr(self._inventory, "list_movements") else []
            )
            tracking = {}
            recipes = []
            items = []
            if can_configure:
                items = self._repo.list_items(conn, current.store_id)
                tracking = {row["item_id"]: bool(row["is_stock_tracked"])
                            for row in self._inventory.item_tracking(conn, current.store_id)}
                recipes = [dict(item_id=item.id, parts=self._inventory.get_recipe(conn, item.id))
                           for item in items]
            return dict(enabled=True, store_id=current.store_id,
                        actor_id=current.employee_id, ingredients=ingredients,
                        counts=counts, movements=movements, items=items,
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
            self._management.audit(conn, current, "INVENTORY_INGREDIENT_CREATE", ingredient_id)
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
                self._management.audit(conn, current, "INVENTORY_RECEIVE", ingredient_id)
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
                self._management.audit(conn, current, f"INVENTORY_{kind}", ingredient_id)
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
                self._management.audit(conn, current, "INVENTORY_COUNT_PROPOSE", proposal["id"])
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
            self._management.audit(conn, current,
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
            self._management.audit(conn, current, "INVENTORY_RECIPE_SAVE", item.id)
            return dict(item_id=item.id, track_stock=track_stock,
                        parts=self._inventory.get_recipe(conn, item.id))
