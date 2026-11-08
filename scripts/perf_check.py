"""HA-09 — Đo thời gian thao tác demo và EXPLAIN mọi câu SELECT trên dữ liệu lớn.

Chỉ chạy trên cyberhub_manager_test. Mỗi lần chạy sở hữu một namespace riêng;
chỉ dữ liệu của lần chạy đó được dọn khi kết thúc.

    python scripts/perf_check.py            # mặc định 5.000 khách, 60.000 phiên đã đóng
    python scripts/perf_check.py --scale 0.2
"""

from __future__ import annotations

import argparse
import math
import os
import random
import re
import sys
import time
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch
from uuid import uuid4

TEST_DATABASE = "cyberhub_manager_test"

from mysql.connector import cursor as py_cursor  # noqa: E402

from cyberhub_manager.database import connection  # noqa: E402
from cyberhub_manager.domain.dtos import InvoiceFilters  # noqa: E402
from cyberhub_manager.domain.enums import PaymentMethod  # noqa: E402
from cyberhub_manager.security import hash_password  # noqa: E402

try:
    from mysql.connector import cursor_cext
except ImportError:  # pragma: no cover
    cursor_cext = None

LIMIT_SECONDS = 2.0
PASSWORD = "perf-demo-123"
PREFIX = "PF" + uuid4().hex[:8].upper()
BATCH = 2_000

captured: list[tuple[str, Any]] = []


def _capture(cls: type, stack: ExitStack) -> None:
    original = cls.execute

    def execute(self, operation, params=None, *args, **kwargs):
        sql = operation.decode() if isinstance(operation, bytes) else str(operation)
        if sql.lstrip().upper().startswith("SELECT"):
            captured.append((sql, params))
        return original(self, operation, params, *args, **kwargs)

    stack.enter_context(patch.object(cls, "execute", execute))


@contextmanager
def capture_selects():
    """Scope instrumentation to the benchmark; restore drivers even on failure."""
    captured.clear()
    with ExitStack() as stack:
        _capture(py_cursor.MySQLCursor, stack)
        if cursor_cext is not None:
            _capture(cursor_cext.CMySQLCursor, stack)
        yield


# ----------------------------------------------------------------------
# Dữ liệu
# ----------------------------------------------------------------------
def _run(conn, sql: str, params: tuple = ()) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall() if cur.with_rows else []
    finally:
        cur.close()


def _many(conn, sql: str, rows: list[tuple]) -> None:
    cur = conn.cursor()
    try:
        for start in range(0, len(rows), BATCH):
            cur.executemany(sql, rows[start : start + BATCH])
    finally:
        cur.close()


def cleanup(conn) -> None:
    like = PREFIX + "%"
    store = _run(conn, "SELECT id FROM stores WHERE code = %s", (f"{PREFIX}_STORE",))
    if store:
        sid = store[0][0]
        _run(conn, "DELETE FROM invoices WHERE store_id = %s", (sid,))
        _run(
            conn,
            "DELETE t FROM account_transactions t JOIN employees e ON e.id = t.employee_id WHERE e.store_id = %s",
            (sid,),
        )
        _run(
            conn,
            "DELETE s FROM usage_sessions s JOIN machines m ON m.id = s.machine_id WHERE m.store_id = %s",
            (sid,),
        )
        _run(conn, "DELETE FROM machines WHERE store_id = %s", (sid,))
        _run(conn, "DELETE FROM employees WHERE store_id = %s", (sid,))
        _run(conn, "DELETE FROM stores WHERE id = %s", (sid,))
    _run(conn, "DELETE a FROM accounts a JOIN customers c ON c.id = a.customer_id WHERE c.code LIKE %s", (like,))
    _run(conn, "DELETE FROM customers WHERE code LIKE %s", (like,))
    conn.commit()


def seed(conn, scale: float) -> dict[str, Any]:
    rng = random.Random(42)
    n_customers = max(1, int(5_000 * scale))
    n_machines = 60
    n_sessions = max(1, int(60_000 * scale))
    n_topups = max(1, int(20_000 * scale))
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    _run(conn, "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)", (f"{PREFIX}_STORE", "Perf store", "HN"))
    store_id = _run(conn, "SELECT LAST_INSERT_ID()")[0][0]
    pw = hash_password(PASSWORD)
    _many(
        conn,
        "INSERT INTO employees (code, store_id, full_name, username, password_hash, role) VALUES (%s,%s,%s,%s,%s,%s)",
        [(f"{PREFIX}_EMP_1", store_id, "Perf manager", f"{PREFIX}.manager", pw, "MANAGER")],
    )
    employee_id = _run(conn, "SELECT id FROM employees WHERE code = %s", (f"{PREFIX}_EMP_1",))[0][0]

    used_phones = {row[0] for row in _run(conn, "SELECT phone FROM customers")}
    phones = []
    candidate = int(uuid4().hex[:8], 16) % 100_000_000
    while len(phones) < n_customers:
        phone = f"09{candidate % 100_000_000:08d}"
        if phone not in used_phones:
            phones.append(phone)
            used_phones.add(phone)
        candidate += 1
    _many(
        conn,
        "INSERT INTO customers (code, full_name, phone) VALUES (%s,%s,%s)",
        [(f"{PREFIX}_CUS_{i:05d}", f"Khách perf {i:05d}", phones[i]) for i in range(n_customers)],
    )
    customer_ids = [r[0] for r in _run(conn, "SELECT id FROM customers WHERE code LIKE %s ORDER BY id", (PREFIX + "%",))]
    _many(
        conn,
        "INSERT INTO accounts (code, customer_id, username, password_hash, balance) VALUES (%s,%s,%s,%s,%s)",
        [(f"{PREFIX}_ACC_{i:05d}", cid, f"{PREFIX}.cus{i:05d}", pw, 200_000) for i, cid in enumerate(customer_ids)],
    )
    accounts = dict(_run(conn, "SELECT customer_id, id FROM accounts WHERE code LIKE %s", (PREFIX + "%",)))

    _many(
        conn,
        "INSERT INTO machines (code, store_id, name, hourly_rate) VALUES (%s,%s,%s,%s)",
        [(f"{PREFIX}_PC_{i:02d}", store_id, f"Máy perf {i:02d}", 10_000) for i in range(n_machines)],
    )
    machine_ids = [r[0] for r in _run(conn, "SELECT id FROM machines WHERE store_id = %s ORDER BY id", (store_id,))]

    sessions = []
    for i in range(n_sessions):
        minutes = rng.randint(10, 240)
        start = now - timedelta(minutes=minutes + rng.randint(1, 90 * 24 * 60))
        sessions.append(
            (f"{PREFIX}S{i:07d}", rng.choice(customer_ids), rng.choice(machine_ids), employee_id, employee_id,
             start, start + timedelta(minutes=minutes), 10_000, (minutes * 10_000 + 59) // 60, "COMPLETED")
        )
    _many(
        conn,
        "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, closed_by, started_at, ended_at,"
        " hourly_rate, cost, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        sessions,
    )
    rows = _run(
        conn,
        "SELECT id, customer_id, ended_at, cost FROM usage_sessions WHERE code LIKE %s",
        (PREFIX + "S%",),
    )
    _many(
        conn,
        "INSERT INTO invoices (code, session_id, customer_id, employee_id, store_id, usage_cost, total_amount, created_at)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        [(f"{PREFIX}I{sid:07d}", sid, cid, employee_id, store_id, cost, cost, ended) for sid, cid, ended, cost in rows],
    )
    tx = [(f"{PREFIX}U{sid:07d}", accounts[cid], employee_id, sid, "USAGE_PAYMENT", -cost, "ACCOUNT_BALANCE", ended)
          for sid, cid, ended, cost in rows if cost > 0]
    tx += [(f"{PREFIX}T{i:07d}", accounts[rng.choice(customer_ids)], employee_id, None, "TOP_UP", 50_000, "CASH",
            now - timedelta(minutes=rng.randint(1, 90 * 24 * 60))) for i in range(n_topups)]
    _many(
        conn,
        "INSERT INTO account_transactions (code, account_id, employee_id, session_id, type, amount, method, created_at)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        tx,
    )
    conn.commit()
    for table in ("customers", "accounts", "machines", "usage_sessions", "invoices", "account_transactions"):
        _run(conn, f"ANALYZE TABLE {table}")
    return {
        "store_id": store_id, "customers": n_customers, "sessions": n_sessions, "transactions": len(tx),
        "customer_id": customer_ids[len(customer_ids) // 2], "machine_id": machine_ids[0],
        "phone": phones[min(1234, len(phones) - 1)],
    }


# ----------------------------------------------------------------------
# Đo
# ----------------------------------------------------------------------
def timed(label: str, func: Callable[[], Any], results: list) -> Any:
    start_index = len(captured)
    start = time.perf_counter()
    value = func()
    elapsed = time.perf_counter() - start
    results.append((label, elapsed, captured[start_index:]))
    return value


def explain(conn, sql: str, params: Any) -> list[dict]:
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("EXPLAIN " + sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def _benchmark(conn, args) -> int:
    t0 = time.perf_counter()
    info = seed(conn, args.scale)
    print(f"Seed: {info['customers']} khách, {info['sessions']} phiên/hóa đơn, "
          f"{info['transactions']} giao dịch ({time.perf_counter() - t0:.1f}s)")

    from cyberhub_manager.services.bootstrap import create_service_bundle

    state = {"actor": None}
    svc = create_service_bundle(actor_provider=lambda: state["actor"])
    results: list = []
    store_id, cid, mid = info["store_id"], info["customer_id"], info["machine_id"]
    today = datetime.now(timezone(timedelta(hours=7))).date()
    with capture_selects():
        actor = timed("login", lambda: svc.auth.login(f"{PREFIX}.manager", PASSWORD), results)
        state["actor"] = actor
        timed("list_machines", lambda: svc.machines.list_machines(store_id), results)
        timed("search_customers (tên)", lambda: svc.customers.search_customers("perf 0123"), results)
        timed("search_customers (sđt)", lambda: svc.customers.search_customers(info["phone"]), results)
        timed("search_customers (rỗng)", lambda: svc.customers.search_customers(""), results)
        timed("get_customer", lambda: svc.customers.get_customer(cid), results)
        timed("top_up", lambda: svc.wallet.top_up(cid, 20_000, PaymentMethod.CASH, actor.employee_id), results)
        timed("get_history", lambda: svc.wallet.get_history(cid), results)
        timed("preview_open", lambda: svc.sessions.preview_open(cid, mid, actor), results)
        timed("open_session", lambda: svc.sessions.open_session(cid, mid, actor), results)
        preview = timed("preview_checkout",
                        lambda: svc.sessions.preview_checkout(mid, datetime.now(timezone.utc)), results)
        timed("complete_checkout", lambda: svc.sessions.complete_checkout(
            mid, actor, preview.settlement_required,
            PaymentMethod.CASH if preview.settlement_required else None), results)
        invoices = timed("list_invoices (hôm nay)", lambda: svc.reports.list_invoices(
            store_id, InvoiceFilters(date_from=today, date_to=today)), results)
        timed("list_invoices (30 ngày)", lambda: svc.reports.list_invoices(
            store_id, InvoiceFilters(date_from=today - timedelta(days=29), date_to=today)), results)
        timed("list_invoices (từ khóa)", lambda: svc.reports.list_invoices(
            store_id, InvoiceFilters(date_from=today - timedelta(days=29), date_to=today, keyword="perf 0123")), results)
        timed("get_invoice", lambda: svc.reports.get_invoice(invoices[0].invoice_id), results)
        timed("daily_revenue (30 ngày)", lambda: svc.reports.daily_revenue(
            store_id, today - timedelta(days=29), today), results)
        timed("daily_revenue (90 ngày)", lambda: svc.reports.daily_revenue(
            store_id, today - timedelta(days=89), today), results)

        print(f"\n{'Thao tác':<28}{'Thời gian':>10}  SELECT  Kết quả")
        slow = 0
        for label, elapsed, _ in results:
            ok = elapsed < LIMIT_SECONDS
            slow += not ok
            print(f"{label:<28}{elapsed * 1000:>8.0f}ms  {len(_):>6}  {'OK' if ok else 'CHẬM'}")

        print("\nEXPLAIN (bảng bị quét toàn bộ hoặc filesort):")
        seen: set[str] = set()
        flagged = 0
        for label, _, queries in results:
            for sql, params in queries:
                key = re.sub(r"\s+", " ", sql).strip()
                if key in seen:
                    continue
                seen.add(key)
                for row in explain(conn, sql, params):
                    extra = row.get("Extra") or ""
                    full_scan = row["type"] == "ALL" and (row.get("rows") or 0) > 100
                    if full_scan or "filesort" in extra or "temporary" in extra:
                        flagged += 1
                        print(f"- [{label}] {row['table']}: type={row['type']} key={row['key']} "
                              f"rows={row['rows']} extra={extra}")
                        print(f"    {key[:220]}")
        print(f"\nTổng: {len(seen)} câu SELECT khác nhau, {flagged} dòng cần xem, {slow} thao tác chậm hơn {LIMIT_SECONDS}s")
        return 1 if slow else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--keep", action="store_true", help="giữ riêng dữ liệu namespace được in ra")
    args = parser.parse_args(argv)
    if not math.isfinite(args.scale) or not 0 < args.scale <= 10:
        parser.error("--scale must be greater than 0 and at most 10")
    # Set only in the CLI, never on import. An explicit non-test DB is refused.
    os.environ.setdefault("MYSQL_DATABASE", TEST_DATABASE)
    if os.environ["MYSQL_DATABASE"] != TEST_DATABASE:
        parser.error("perf_check only permits cyberhub_manager_test")
    conn = connection.get_connection()
    verified = False
    try:
        if _run(conn, "SELECT DATABASE()")[0][0] != TEST_DATABASE:
            parser.error("Connected database is not cyberhub_manager_test")
        verified = True
        print(f"Database: {TEST_DATABASE}; namespace: {PREFIX}")
        return _benchmark(conn, args)
    finally:
        try:
            conn.rollback()
            if verified and not args.keep:
                cleanup(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
