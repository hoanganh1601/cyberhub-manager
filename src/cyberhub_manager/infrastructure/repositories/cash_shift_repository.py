"""Persistence for employee shifts and immutable tender entries."""

from cyberhub_manager.infrastructure.repositories.sql import execute, rows


_SHIFT_VARIANCE = (
    "CASE WHEN s.counted_cash IS NOT NULL AND s.expected_cash IS NOT NULL "
    "THEN CAST(s.counted_cash AS SIGNED) - CAST(s.expected_cash AS SIGNED) ELSE NULL END AS variance"
)


class CashShiftRepository:
    def get_shift(self, conn, shift_id, *, lock=False):
        if lock:
            if not rows(conn, "SELECT id FROM cash_shifts WHERE id=%s FOR UPDATE", (shift_id,)):
                return None
        result = rows(conn,
            f"SELECT s.*,{_SHIFT_VARIANCE},ep.full_name AS employee_name,rp.full_name AS reviewer_name "
            "FROM cash_shifts s JOIN employees e ON e.id=s.employee_id "
            "JOIN employee_profiles ep ON ep.id=e.profile_id "
            "LEFT JOIN employees r ON r.id=s.reviewed_by "
            "LEFT JOIN employee_profiles rp ON rp.id=r.profile_id WHERE s.id=%s", (shift_id,))
        return result[0] if result else None

    def active_for_employee(self, conn, employee_id, *, lock=False):
        result = rows(conn,
            f"SELECT s.*,{_SHIFT_VARIANCE} FROM cash_shifts s WHERE s.employee_id=%s "
            "AND s.status IN ('OPEN','PENDING_REVIEW') ORDER BY s.id DESC LIMIT 1" +
            (" FOR UPDATE" if lock else ""), (employee_id,))
        return result[0] if result else None

    def list_shifts(self, conn, store_id, limit=100, *, employee_id=None):
        employee_filter = " AND s.employee_id=%s" if employee_id is not None else ""
        params = (store_id, employee_id, limit) if employee_id is not None else (store_id, limit)
        return rows(conn,
            f"SELECT s.*,{_SHIFT_VARIANCE},ep.full_name AS employee_name,rp.full_name AS reviewer_name "
            "FROM cash_shifts s JOIN employees e ON e.id=s.employee_id "
            "JOIN employee_profiles ep ON ep.id=e.profile_id "
            "LEFT JOIN employees r ON r.id=s.reviewed_by "
            "LEFT JOIN employee_profiles rp ON rp.id=r.profile_id WHERE s.store_id=%s "
            + employee_filter + " ORDER BY s.opened_at DESC,s.id DESC LIMIT %s", params)

    def entries(self, conn, shift_id):
        return rows(conn,
            "SELECT x.*,s.store_id,ep.full_name AS employee_name FROM cash_shift_entries x "
            "JOIN cash_shifts s ON s.id=x.shift_id "
            "JOIN employees e ON e.id=x.employee_id "
            "JOIN employee_profiles ep ON ep.id=e.profile_id WHERE x.shift_id=%s "
            "ORDER BY x.created_at,x.id", (shift_id,))

    def open_shift(self, conn, *, code, store_id, employee_id, opening_cash):
        return execute(conn,
            "INSERT INTO cash_shifts(code,store_id,employee_id,opening_cash) "
            "VALUES(%s,%s,%s,%s)", (code,store_id,employee_id,opening_cash))

    def add_entry(self, conn, *, shift_id, store_id, employee_id, kind,
                  payment_method, amount, source_type, source_id, note):
        # store_id is derived from cash_shifts (NF-02); parameter kept for call compatibility.
        _ = store_id
        return execute(conn,
            "INSERT INTO cash_shift_entries(shift_id,employee_id,kind,"
            "payment_method,amount,source_type,source_id,note) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (shift_id,employee_id,kind,payment_method,amount,
             source_type,source_id,note))

    def submit_close(self, conn, shift_id, *, expected_cash, counted_cash, variance, requires_review=False):
        # variance is derived from counted_cash - expected_cash (NF-01).
        _ = variance
        return execute(conn,
            "UPDATE cash_shifts SET status=CASE WHEN %s=0 THEN 'CLOSED' "
            "ELSE 'PENDING_REVIEW' END,expected_cash=%s,counted_cash=%s,"
            "submitted_at=UTC_TIMESTAMP(),closed_at=CASE WHEN %s=0 THEN UTC_TIMESTAMP() ELSE NULL END "
            "WHERE id=%s AND status='OPEN'",
            (int(requires_review),expected_cash,counted_cash,int(requires_review),shift_id))

    def review(self, conn, shift_id, reviewer_id, note):
        return execute(conn,
            "UPDATE cash_shifts SET status='CLOSED',reviewed_by=%s,review_note=%s,"
            "closed_at=UTC_TIMESTAMP() WHERE id=%s AND status='PENDING_REVIEW'",
            (reviewer_id,note,shift_id))
