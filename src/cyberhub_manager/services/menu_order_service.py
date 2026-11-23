"""Order lifecycle and reversal operations for the menu/POS service."""

from datetime import date, timedelta

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.menu import MenuOrderStatus, MenuPaymentMethod
from cyberhub_manager.domain.p1 import Permission

from .menu_shared import (
    ORDER_ALREADY_HANDLED,
    ORDER_NOT_FOUND,
    positive_id as _positive_id,
    text as _text,
)
from .p1_runtime import retry_on_transient


class MenuOrderMixin:
    """Order lifecycle behavior composed into MenuService."""

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
            current = self._actor(conn, actor, Permission.VIEW_REVENUE)
            return self._repo.paid_order_report(conn, current.store_id, start, before)

    def maintain_holds(self, *, now=None, limit=100):
        """Trusted worker entry point; retries are safe and never cancel PREPARING."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be 1..500")
        now = now or self._clock()
        if now.tzinfo is None:
            raise ValueError("now must include timezone")
        expired = 0
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
                    expired += 1
        return dict(expired=expired)

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
            self._management.audit(conn, current, f"MENU_ORDER_{status.value}", order.id)
            updated = self._repo.get_order(conn, order.id)
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
            self._management.audit(conn, current, f"MENU_ORDER_PAID_{method.value}", order.id)
            updated = self._repo.get_order(conn, order.id)
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
            self._management.audit(conn, current, "POS_REVERSAL_REQUEST", order.id)
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
                updated = self._repo.get_order(conn, order.id)
            self._management.audit(conn, current,
                           "POS_REVERSAL_APPROVED" if approve else "POS_REVERSAL_REJECTED", order.id)
            return self._repo.get_reversal(conn, order.id)
