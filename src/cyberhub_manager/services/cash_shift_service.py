"""Application service for opening, reconciling and reviewing cash shifts."""

from uuid import uuid4

from cyberhub_manager.domain.cash_shift import (
    CashEntryKind,
    TenderMethod,
    calculate_totals,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.repositories.cash_shift_repository import CashShiftRepository

from .operational_base import OperationalServiceBase


def _money(value, field):
    if type(value) is not int or not 0 <= value <= 1_000_000_000:
        raise ValidationError(field_errors={field: "Số tiền phải từ 0 đến 1.000.000.000 VND"})
    return value


def _note(value, field="note", *, required=True):
    value = value.strip() if isinstance(value, str) else ""
    if (required and not value) or len(value) > 255:
        raise ValidationError(field_errors={field: "Nội dung phải từ 1 đến 255 ký tự"})
    return value


class CashShiftService(OperationalServiceBase):
    def __init__(self, repo=None, **kwargs):
        super().__init__(**kwargs)
        self._repo = repo or CashShiftRepository()

    def overview(self, actor):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.SHIFT_VIEW)
            reviewer = can(current.role, Permission.SHIFT_REVIEW)
            shifts = self._repo.list_shifts(
                conn, current.store_id,
                employee_id=None if reviewer else current.employee_id,
            )
            active = self._repo.active_for_employee(conn, current.employee_id)
            return dict(
                active=active,
                shifts=shifts,
                can_review=reviewer,
                entries=self._repo.entries(conn, active["id"]) if active else [],
            )

    def detail(self, actor, shift_id):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.SHIFT_VIEW)
            shift = self._repo.get_shift(conn, shift_id)
            if shift is None or shift["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy ca làm việc")
            if shift["employee_id"] != current.employee_id and not can(current.role, Permission.SHIFT_REVIEW):
                raise PermissionDeniedError()
            entries = self._repo.entries(conn, shift_id)
            totals = calculate_totals(int(shift["opening_cash"]), entries)
            return dict(shift=shift, entries=entries, totals=totals)

    def open_shift(self, actor, opening_cash):
        opening_cash = _money(opening_cash, "opening_cash")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.SHIFT_OPERATE)
            if self._repo.active_for_employee(conn, current.employee_id, lock=True):
                raise ConflictError("Nhân viên đang có một ca chưa đóng")
            shift_id = self._repo.open_shift(
                conn, code="SHIFT-" + uuid4().hex[:16].upper(),
                store_id=current.store_id, employee_id=current.employee_id,
                opening_cash=opening_cash,
            )
            self._audit.audit(conn, current, "SHIFT_OPEN", shift_id)
            return self._repo.get_shift(conn, shift_id)

    def add_entry(self, actor, *, kind, payment_method, amount, note):
        try:
            kind = CashEntryKind(kind)
            payment_method = TenderMethod(payment_method)
        except ValueError:
            raise ValidationError(field_errors={"kind": "Loại thu chi không hợp lệ"}) from None
        if kind is CashEntryKind.RECEIPT:
            raise PermissionDeniedError("Khoản thu chỉ được tạo từ nghiệp vụ hệ thống")
        amount = _money(amount, "amount")
        if amount == 0:
            raise ValidationError(field_errors={"amount": "Số tiền phải lớn hơn 0"})
        note = _note(note)
        permission = Permission.SHIFT_REVIEW if kind in (
            CashEntryKind.ADJUSTMENT_IN, CashEntryKind.ADJUSTMENT_OUT
        ) else Permission.SHIFT_OPERATE
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, permission)
            shift = self._repo.active_for_employee(conn, current.employee_id, lock=True)
            if shift is None or shift["status"] != "OPEN":
                raise ConflictError("Cần mở ca trước khi ghi thu chi")
            entry_id = self._repo.add_entry(
                conn, shift_id=shift["id"], store_id=current.store_id,
                employee_id=current.employee_id, kind=kind.value,
                payment_method=payment_method.value, amount=amount,
                source_type="MANUAL", source_id=uuid4().hex, note=note,
            )
            self._audit.audit(conn, current, "SHIFT_ENTRY", entry_id)
            return self._repo.entries(conn, shift["id"])[-1]

    def record_system_entry(self, conn, actor, *, kind, payment_method, amount,
                            source_type, source_id, note=""):
        """Record a payment inside the caller's transaction exactly once."""
        current = self._actor(conn, actor, Permission.SHIFT_OPERATE)
        shift = self._repo.active_for_employee(conn, current.employee_id, lock=True)
        if shift is None or shift["status"] != "OPEN":
            raise ConflictError("Nhân viên cần mở ca trước khi thu hoặc chi tiền")
        self._repo.add_entry(
            conn, shift_id=shift["id"], store_id=current.store_id,
            employee_id=current.employee_id, kind=CashEntryKind(kind).value,
            payment_method=TenderMethod(payment_method).value, amount=amount,
            source_type=source_type, source_id=str(source_id), note=note,
        )

    def submit_close(self, actor, counted_cash):
        counted_cash = _money(counted_cash, "counted_cash")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.SHIFT_OPERATE)
            shift = self._repo.active_for_employee(conn, current.employee_id, lock=True)
            if shift is None or shift["status"] != "OPEN":
                raise ConflictError("Không có ca đang mở để đóng")
            totals = calculate_totals(int(shift["opening_cash"]), self._repo.entries(conn, shift["id"]))
            if totals.expected_cash < 0:
                raise ConflictError("Tiền chi vượt quá số tiền mặt dự kiến trong két")
            variance = counted_cash - totals.expected_cash
            if self._repo.submit_close(conn, shift["id"], expected_cash=totals.expected_cash,
                                       counted_cash=counted_cash, variance=variance) != 1:
                raise ConflictError("Ca vừa được xử lý bởi yêu cầu khác")
            self._audit.audit(conn, current, "SHIFT_SUBMIT_CLOSE", shift["id"])
            return self._repo.get_shift(conn, shift["id"])

    def review(self, actor, shift_id, note):
        note = _note(note, "review_note")
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.SHIFT_REVIEW)
            shift = self._repo.get_shift(conn, shift_id, lock=True)
            if shift is None or shift["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy ca làm việc")
            if shift["employee_id"] == current.employee_id:
                raise PermissionDeniedError("Không được tự duyệt chênh lệch ca của mình")
            if self._repo.review(conn, shift_id, current.employee_id, note) != 1:
                raise ConflictError("Ca không còn chờ xác nhận")
            self._audit.audit(conn, current, "SHIFT_REVIEW", shift_id)
            return self._repo.get_shift(conn, shift_id)
