"""Strict 3NF and database integrity verification against real MySQL 8.4.

Verifies migrations 028 through 031 directly against cyberhub_manager_test:
- Zero generated columns and zero JSON columns in all 74 business base tables.
- Explicit InnoDB + utf8mb4_0900_ai_ci on all 74 business base tables (INT-04).
- All 18 compatibility/reporting read views exist and return expected derived values.
- Occupancy tables (active_usage_sessions, active_employee_shifts) prevent double-open
  and reject reopening closed sessions/shifts.
- NULL-safe CHECK constraints & Separation-of-Duties rules reject MySQL UNKNOWN loopholes
  and self-approval attempts even when written directly via SQL (INT-02).
- Cross-store & cross-owner DB triggers reject invalid links directly in MySQL (INT-01).
- Immutable policy versions preserve historical invoices and POS promotion snapshots (NF-04).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from mysql.connector import Error as MySQLError, IntegrityError

from cyberhub_manager.infrastructure.repositories.sql import execute, rows


READ_VIEWS = (
    "v_accounts",
    "v_invoices",
    "v_cash_shifts",
    "v_cash_shift_entries",
    "v_commercial_events",
    "v_commercial_settlements",
    "v_commercial_settlement_lines",
    "v_menu_items",
    "v_menu_orders",
    "v_pos_order_reversals",
    "v_inventory_movements",
    "v_inventory_counts",
    "v_machine_incidents",
    "v_purchase_orders",
    "v_goods_receipts",
    "v_supplier_payables",
    "v_employees",
    "v_menu_order_pricing",
)


def _make_employee(conn, store_id: int, role: str = "MANAGER", suffix: str | None = None) -> int:
    tok = suffix or uuid4().hex[:8]
    profile_id = execute(
        conn,
        "INSERT INTO employee_profiles (code, home_store_id, full_name) VALUES (%s, %s, %s)",
        (f"T3NF-EMP-{tok}", store_id, f"3NF Employee {tok}"),
    )
    return int(
        execute(
            conn,
            "INSERT INTO employees (profile_id, username, password_hash, role) VALUES (%s, %s, 'x', %s)",
            (profile_id, f"t3nf.{tok}", role),
        )
    )


def _make_store(conn, suffix: str | None = None) -> int:
    tok = suffix or uuid4().hex[:8]
    return int(
        execute(
            conn,
            "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
            (f"T3NF-ST-{tok}", f"Store {tok}", "Test addr"),
        )
    )


def _make_customer_account(conn, suffix: str | None = None) -> tuple[int, int]:
    tok = suffix or uuid4().hex[:8]
    customer_id = int(
        execute(
            conn,
            "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
            (f"T3NF-C-{tok}", f"Cust {tok}", "06" + str(uuid4().int % 100_000_000).zfill(8)),
        )
    )
    account_id = int(
        execute(
            conn,
            "INSERT INTO accounts (code, customer_id, username, password_hash) VALUES (%s, %s, %s, 'x')",
            (f"T3NF-A-{tok}", customer_id, f"t3nfc.{tok}"),
        )
    )
    return customer_id, account_id


# ---------------------------------------------------------------------------
# 1. Structural 3NF metadata invariants (NF-01..NF-04, INT-04)
# ---------------------------------------------------------------------------
def test_base_tables_have_zero_generated_and_zero_json_columns(db_conn):
    generated = rows(
        db_conn,
        """
        SELECT TABLE_NAME, COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME <> 'schema_migrations'
          AND TABLE_NAME NOT LIKE 'v\\_%'
          AND GENERATION_EXPRESSION <> ''
        """,
    )
    assert generated == [], f"Generated columns remain in base tables: {generated}"

    json_cols = rows(
        db_conn,
        """
        SELECT TABLE_NAME, COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME <> 'schema_migrations'
          AND TABLE_NAME NOT LIKE 'v\\_%'
          AND DATA_TYPE = 'json'
        """,
    )
    assert json_cols == [], f"JSON columns remain in base tables: {json_cols}"


def test_all_business_tables_use_innodb_and_utf8mb4(db_conn):
    bad = rows(
        db_conn,
        """
        SELECT TABLE_NAME, ENGINE, TABLE_COLLATION
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME <> 'schema_migrations'
          AND (ENGINE <> 'InnoDB' OR TABLE_COLLATION <> 'utf8mb4_0900_ai_ci')
        """,
    )
    assert bad == [], f"Tables with non-standard engine/collation: {bad}"


def test_all_compatibility_views_exist_and_query_cleanly(db_conn):
    existing = {
        r["TABLE_NAME"]
        for r in rows(
            db_conn,
            """
            SELECT TABLE_NAME FROM information_schema.VIEWS
            WHERE TABLE_SCHEMA = DATABASE()
            """,
        )
    }
    for view in READ_VIEWS:
        assert view in existing, f"Missing view: {view}"
        rows(db_conn, f"SELECT * FROM `{view}` LIMIT 1")


def test_dropped_derived_and_transitive_columns_are_absent(db_conn):
    removed = (
        ("invoices", "total_amount"),
        ("invoices", "loyalty_eligible_amount"),
        ("invoices", "loyalty_points"),
        ("invoices", "loyalty_unit"),
        ("accounts", "cash_balance"),
        ("commercial_settlements", "net_amount"),
        ("commercial_settlement_lines", "amount"),
        ("cash_shifts", "variance"),
        ("cash_shifts", "active_employee_id"),
        ("usage_sessions", "active_machine_id"),
        ("usage_sessions", "active_customer_id"),
        ("cash_shift_entries", "store_id"),
        ("commercial_events", "campaign_id"),
        ("goods_receipts", "store_id"),
        ("supplier_payables", "supplier_id"),
        ("supplier_payables", "store_id"),
        ("purchase_orders", "store_id"),
        ("pos_order_reversals", "store_id"),
        ("inventory_movements", "store_id"),
        ("inventory_counts", "store_id"),
        ("machine_incidents", "store_id"),
        ("menu_orders", "store_id"),
        ("menu_orders", "machine_id"),
        ("menu_orders", "account_id"),
        ("menu_items", "store_id"),
        ("employees", "code"),
        ("employees", "store_id"),
        ("employees", "full_name"),
        ("employee_profiles", "employee_id"),
        ("menu_order_pricing", "promotion_id"),
        ("menu_order_pricing", "promotion_code"),
        ("menu_order_pricing", "promotion_kind"),
        ("menu_order_pricing", "final_amount"),
        ("menu_order_pricing", "snapshot_json"),
        ("game_sessions", "played_on"),
        ("ad_reward_events", "played_on"),
        ("account_transactions", "session_id"),
    )
    existing = {
        (r["TABLE_NAME"], r["COLUMN_NAME"])
        for r in rows(
            db_conn,
            "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()",
        )
    }
    leftovers = [pair for pair in removed if pair in existing]
    assert leftovers == [], f"Dropped columns still exist: {leftovers}"


# ---------------------------------------------------------------------------
# 2. Physical 3NF occupancy tables (NF-01)
# ---------------------------------------------------------------------------
def test_active_usage_sessions_occupancy_and_no_reopen(db_conn, test_scenario):
    s = test_scenario(db_conn)
    cust2, _ = _make_customer_account(db_conn)
    machine2 = int(
        execute(
            db_conn,
            "INSERT INTO machines (code, store_id, name, hourly_rate) VALUES (%s, %s, 'PC2', 5000)",
            (f"PC2-{s.token}", s.store_id),
        )
    )
    sid1 = int(
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
            " VALUES (%s, %s, %s, %s, 5000)",
            (f"S1-{s.token}", s.customer_id, s.machine_id, s.employee_id),
        )
    )
    assert rows(db_conn, "SELECT * FROM active_usage_sessions WHERE session_id=%s", (sid1,)) == [
        {"session_id": sid1, "machine_id": s.machine_id, "customer_id": s.customer_id}
    ]
    # Same machine cannot have two ACTIVE sessions.
    with pytest.raises(IntegrityError):
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
            " VALUES (%s, %s, %s, %s, 5000)",
            (f"S2-{s.token}", cust2, s.machine_id, s.employee_id),
        )
    # Same customer cannot have two ACTIVE sessions.
    with pytest.raises(IntegrityError):
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
            " VALUES (%s, %s, %s, %s, 5000)",
            (f"S3-{s.token}", s.customer_id, machine2, s.employee_id),
        )
    # Completing removes occupancy and blocks reopening.
    execute(
        db_conn,
        "UPDATE usage_sessions SET status='COMPLETED', closed_by=%s, ended_at=UTC_TIMESTAMP(), cost=5000 WHERE id=%s",
        (s.employee_id, sid1),
    )
    assert rows(db_conn, "SELECT * FROM active_usage_sessions WHERE session_id=%s", (sid1,)) == []
    with pytest.raises(MySQLError):
        execute(db_conn, "UPDATE usage_sessions SET status='ACTIVE' WHERE id=%s", (sid1,))
    # Reusing machine & customer in a new session now succeeds.
    sid4 = int(
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
            " VALUES (%s, %s, %s, %s, 5000)",
            (f"S4-{s.token}", s.customer_id, s.machine_id, s.employee_id),
        )
    )
    assert rows(db_conn, "SELECT session_id FROM active_usage_sessions WHERE machine_id=%s", (s.machine_id,)) == [
        {"session_id": sid4}
    ]


def test_active_employee_shifts_occupancy_and_no_reopen(db_conn, test_scenario):
    s = test_scenario(db_conn)
    shift1 = int(
        execute(
            db_conn,
            "INSERT INTO cash_shifts (code, store_id, employee_id, opening_cash) VALUES (%s, %s, %s, 0)",
            (f"SH1-{s.token}", s.store_id, s.employee_id),
        )
    )
    assert rows(db_conn, "SELECT * FROM active_employee_shifts WHERE shift_id=%s", (shift1,)) == [
        {"shift_id": shift1, "employee_id": s.employee_id}
    ]
    with pytest.raises(IntegrityError):
        execute(
            db_conn,
            "INSERT INTO cash_shifts (code, store_id, employee_id, opening_cash) VALUES (%s, %s, %s, 0)",
            (f"SH2-{s.token}", s.store_id, s.employee_id),
        )
    execute(
        db_conn,
        "UPDATE cash_shifts SET status='CLOSED', expected_cash=0, counted_cash=0,"
        " submitted_at=UTC_TIMESTAMP(), closed_at=UTC_TIMESTAMP() WHERE id=%s",
        (shift1,),
    )
    assert rows(db_conn, "SELECT * FROM active_employee_shifts WHERE shift_id=%s", (shift1,)) == []
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE cash_shifts SET status='OPEN', expected_cash=NULL, counted_cash=NULL,"
            " submitted_at=NULL, closed_at=NULL WHERE id=%s",
            (shift1,),
        )


# ---------------------------------------------------------------------------
# 3. INT-02: NULL-safe CHECK constraints & Separation-of-Duties (SQL level)
# ---------------------------------------------------------------------------
def test_null_safe_checks_close_mysql_unknown_loopholes(db_conn, test_scenario):
    s = test_scenario(db_conn)
    other_emp = _make_employee(db_conn, s.store_id, role="MANAGER")
    sid = int(
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
            " VALUES (%s, %s, %s, %s, 5000)",
            (f"SN-{s.token}", s.customer_id, s.machine_id, s.employee_id),
        )
    )
    order_id = int(
        execute(
            db_conn,
            "INSERT INTO menu_orders (code, session_id, note, total_amount) VALUES (%s, %s, '', 20000)",
            (f"ON-{s.token}", sid),
        )
    )
    # Loophole test: PAID with payment_method=NULL MUST be rejected.
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE menu_orders SET status='PAID', payment_method=NULL,"
            " paid_at=UTC_TIMESTAMP(), paid_by=%s WHERE id=%s",
            (s.employee_id, order_id),
        )

    # Self-approval on pos_order_reversals MUST be rejected.
    rev_id = int(
        execute(
            db_conn,
            "INSERT INTO pos_order_reversals (order_id, requested_by, reason, disposition)"
            " VALUES (%s, %s, 'Khách đổi ý', 'WASTE')",
            (order_id, s.employee_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE pos_order_reversals SET status='REJECTED', decided_by=%s, decided_at=UTC_TIMESTAMP() WHERE id=%s",
            (s.employee_id, rev_id),
        )
    # APPROVED refund with refund_amount > 0 and refund_method=NULL MUST be rejected.
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE pos_order_reversals SET status='APPROVED', decided_by=%s, decided_at=UTC_TIMESTAMP(),"
            " refund_amount=20000, refund_method=NULL WHERE id=%s",
            (other_emp, rev_id),
        )

    # Commercial settlement: adjustment != 0 with NULL adjustment_reason MUST be rejected; SoD enforced.
    partner_id = int(
        execute(
            db_conn,
            "INSERT INTO commercial_partners (code, name, partner_type) VALUES (%s, 'P', 'AD_NETWORK')",
            (f"CP-{s.token}",),
        )
    )
    # Contract self-approval MUST be rejected.
    contract_id = int(
        execute(
            db_conn,
            "INSERT INTO commercial_contracts (partner_id, code, revenue_model, rate_amount,"
            " starts_on, ends_on, created_by) VALUES (%s, %s, 'FIXED', 100000, %s, %s, %s)",
            (partner_id, f"CT-{s.token}", date(2026, 11, 1), date(2026, 11, 30), s.employee_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE commercial_contracts SET status='ACTIVE', approved_by=%s, approved_at=UTC_TIMESTAMP() WHERE id=%s",
            (s.employee_id, contract_id),
        )
    # Settlement with NULL adjustment_reason MUST be rejected.
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO commercial_settlements (contract_id, period_start, period_end, gross_amount,"
            " adjustment_amount, adjustment_reason, generated_by) VALUES (%s, %s, %s, 1000, 100, NULL, %s)",
            (contract_id, date(2026, 11, 1), date(2026, 11, 30), s.employee_id),
        )
    settle_id = int(
        execute(
            db_conn,
            "INSERT INTO commercial_settlements (contract_id, period_start, period_end, gross_amount,"
            " adjustment_amount, adjustment_reason, generated_by) VALUES (%s, %s, %s, 1000, 0, NULL, %s)",
            (contract_id, date(2026, 11, 1), date(2026, 11, 30), s.employee_id),
        )
    )
    # Settlement self-approval MUST be rejected.
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE commercial_settlements SET status='APPROVED', reviewed_by=%s,"
            " reviewed_at=UTC_TIMESTAMP() WHERE id=%s",
            (s.employee_id, settle_id),
        )

    # Inventory count self-approval MUST be rejected.
    ing_id = int(
        execute(
            db_conn,
            "INSERT INTO inventory_ingredients (store_id, code, name, unit) VALUES (%s, %s, 'Đường', 'g')",
            (s.store_id, f"ING-{s.token}"),
        )
    )
    count_id = int(
        execute(
            db_conn,
            "INSERT INTO inventory_counts (ingredient_id, request_id, expected_on_hand, expected_reserved,"
            " expected_movement_id, counted_on_hand, proposed_by, reason) VALUES (%s, %s, 0, 0, 0, 10, %s, 'Kiểm kê')",
            (ing_id, f"CNT-{s.token}", s.employee_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE inventory_counts SET status='APPROVED', decided_by=%s, decided_at=UTC_TIMESTAMP() WHERE id=%s",
            (s.employee_id, count_id),
        )

    # Purchase request self-approval MUST be rejected.
    pr_id = int(
        execute(
            db_conn,
            "INSERT INTO purchase_requests (code, store_id, requested_by, reason) VALUES (%s, %s, %s, 'Cần nhập')",
            (f"PR-{s.token}", s.store_id, s.employee_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE purchase_requests SET status='APPROVED', decided_by=%s, decided_at=UTC_TIMESTAMP() WHERE id=%s",
            (s.employee_id, pr_id),
        )

    # Machine incident: VERIFIED self-verification MUST be rejected.
    inc_id = int(
        execute(
            db_conn,
            "INSERT INTO machine_incidents (code, machine_id, reported_by, assigned_to, severity, status,"
            " title, description, resolution, started_at, completed_at)"
            " VALUES (%s, %s, %s, %s, 'HIGH', 'COMPLETED', 'Lỗi', 'Mô tả', 'Đã sửa',"
            " UTC_TIMESTAMP(), UTC_TIMESTAMP())",
            (f"INC-{s.token}", s.machine_id, other_emp, s.employee_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE machine_incidents SET status='VERIFIED', verified_by=%s, verified_at=UTC_TIMESTAMP() WHERE id=%s",
            (s.employee_id, inc_id),
        )

    # Cash shift: self-review MUST be rejected.
    sh_id = int(
        execute(
            db_conn,
            "INSERT INTO cash_shifts (code, store_id, employee_id, opening_cash) VALUES (%s, %s, %s, 10000)",
            (f"SHS-{s.token}", s.store_id, s.employee_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE cash_shifts SET status='CLOSED', expected_cash=10000, counted_cash=9000,"
            " submitted_at=UTC_TIMESTAMP(), closed_at=UTC_TIMESTAMP(), reviewed_by=%s, review_note='OK' WHERE id=%s",
            (s.employee_id, sh_id),
        )

    # Customer voucher: ISSUED with non-null used_store_id or REVOKED without reason MUST be rejected.
    cat_id = int(
        execute(
            db_conn,
            "INSERT INTO reward_catalog (code, name, reward_type, value, valid_days)"
            " VALUES (%s, 'Test', 'MEMBER_POINTS', 10, 7)",
            (f"RC-{s.token}",),
        )
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO customer_vouchers (code, catalog_id, account_id, reward_type, value,"
            " status, source, issued_at, expires_at, used_store_id)"
            " VALUES (%s, %s, %s, 'MEMBER_POINTS', 10, 'ISSUED', 'MANUAL', %s, %s, %s)",
            (f"V1-{s.token}", cat_id, s.account_id, now, now + timedelta(days=7), s.store_id),
        )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO customer_vouchers (code, catalog_id, account_id, reward_type, value,"
            " status, source, issued_at, expires_at, revoked_reason)"
            " VALUES (%s, %s, %s, 'MEMBER_POINTS', 10, 'REVOKED', 'MANUAL', %s, %s, NULL)",
            (f"V2-{s.token}", cat_id, s.account_id, now, now + timedelta(days=7)),
        )


# ---------------------------------------------------------------------------
# 4. INT-01: Cross-store & Cross-owner MySQL triggers
# ---------------------------------------------------------------------------
def test_cross_store_and_cross_owner_triggers_enforce_invariants(db_conn, test_scenario):
    s = test_scenario(db_conn)
    store_b = _make_store(db_conn)
    other_emp = _make_employee(db_conn, s.store_id, role="MANAGER")
    cust2, _ = _make_customer_account(db_conn)

    # Menu items: duplicate name across two categories in SAME store rejected; DIFFERENT store allowed.
    cat_a1 = int(
        execute(
            db_conn,
            "INSERT INTO menu_categories (store_id, page, name) VALUES (%s, 'DRINK', 'Trà A1')",
            (s.store_id,),
        )
    )
    cat_a2 = int(
        execute(
            db_conn,
            "INSERT INTO menu_categories (store_id, page, name) VALUES (%s, 'DRINK', 'Trà A2')",
            (s.store_id,),
        )
    )
    cat_b = int(
        execute(
            db_conn,
            "INSERT INTO menu_categories (store_id, page, name) VALUES (%s, 'DRINK', 'Trà B')",
            (store_b,),
        )
    )
    item_a = int(
        execute(
            db_conn,
            "INSERT INTO menu_items (category_id, name, price) VALUES (%s, 'Trà sữa 3NF', 30000)",
            (cat_a1,),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO menu_items (category_id, name, price) VALUES (%s, 'Trà sữa 3NF', 30000)",
            (cat_a2,),
        )
    item_b = int(
        execute(
            db_conn,
            "INSERT INTO menu_items (category_id, name, price) VALUES (%s, 'Trà sữa 3NF', 30000)",
            (cat_b,),
        )
    )
    assert item_b > 0

    # Cross-store menu_item_recipes MUST be rejected.
    ing_b = int(
        execute(
            db_conn,
            "INSERT INTO inventory_ingredients (store_id, code, name, unit) VALUES (%s, %s, 'Sữa B', 'ml')",
            (store_b, f"INGB-{s.token}"),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO menu_item_recipes (item_id, ingredient_id, quantity_per_unit) VALUES (%s, %s, 50)",
            (item_a, ing_b),
        )

    # Cross-store menu_promotions MUST be rejected.
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO menu_promotions (store_id, code, kind, item_id, value, starts_at, ends_at)"
            " VALUES (%s, %s, 'BOGO', %s, 1, %s, %s)",
            (s.store_id, f"PRB-{s.token}", item_b, now, now + timedelta(days=1)),
        )

    # Cross-store procurement: PR in store A cannot accept ingredient or supplier from store B.
    pr_a = int(
        execute(
            db_conn,
            "INSERT INTO purchase_requests (code, store_id, requested_by, status, decided_by, decided_at, reason)"
            " VALUES (%s, %s, %s, 'APPROVED', %s, UTC_TIMESTAMP(), 'Nhập kho')",
            (f"PRA-{s.token}", s.store_id, s.employee_id, other_emp),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO purchase_request_lines (request_id, ingredient_id, quantity) VALUES (%s, %s, 10)",
            (pr_a, ing_b),
        )
    sup_b = int(
        execute(
            db_conn,
            "INSERT INTO suppliers (store_id, code, name) VALUES (%s, %s, 'NCC B')",
            (store_b, f"SUPB-{s.token}"),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO purchase_orders (code, request_id, supplier_id, created_by, total_amount)"
            " VALUES (%s, %s, %s, %s, 10000)",
            (f"POX-{s.token}", pr_a, sup_b, other_emp),
        )

    # Payable approver cannot self-pay (trg_supplier_payables_bu).
    sup_a = int(
        execute(
            db_conn,
            "INSERT INTO suppliers (store_id, code, name) VALUES (%s, %s, 'NCC A')",
            (s.store_id, f"SUPA-{s.token}"),
        )
    )
    po_a = int(
        execute(
            db_conn,
            "INSERT INTO purchase_orders (code, request_id, supplier_id, created_by, total_amount)"
            " VALUES (%s, %s, %s, %s, 10000)",
            (f"POA-{s.token}", pr_a, sup_a, other_emp),
        )
    )
    gr_a = int(
        execute(
            db_conn,
            "INSERT INTO goods_receipts (code, order_id, received_by, request_id, accepted_amount)"
            " VALUES (%s, %s, %s, %s, 10000)",
            (f"GRA-{s.token}", po_a, s.employee_id, uuid4().hex),
        )
    )
    pay_a = int(
        execute(
            db_conn,
            "INSERT INTO supplier_payables (receipt_id, amount, due_date) VALUES (%s, 10000, %s)",
            (gr_a, date(2026, 12, 1)),
        )
    )
    execute(
        db_conn,
        "INSERT INTO supplier_payable_approvals (payable_id, approved_by, note) VALUES (%s, %s, 'Duyệt chi')",
        (pay_a, other_emp),
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "UPDATE supplier_payables SET status='PAID', paid_amount=amount,"
            " paid_at=UTC_TIMESTAMP(), paid_by=%s, payment_method='CASH' WHERE id=%s",
            (other_emp, pay_a),
        )

    # Invoice with mismatched customer or store MUST be rejected (trg_invoices_bi).
    sess_id = int(
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, closed_by,"
            " started_at, ended_at, hourly_rate, cost, status)"
            " VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(), 5000, 5000, 'COMPLETED')",
            (f"SINV-{s.token}", s.customer_id, s.machine_id, s.employee_id, s.employee_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO invoices (code, session_id, customer_id, employee_id, store_id, usage_cost)"
            " VALUES (%s, %s, %s, %s, %s, 5000)",
            (f"INVM-{s.token}", sess_id, cust2, s.employee_id, s.store_id),
        )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO invoices (code, session_id, customer_id, employee_id, store_id, usage_cost)"
            " VALUES (%s, %s, %s, %s, %s, 5000)",
            (f"INVS-{s.token}", sess_id, s.customer_id, s.employee_id, store_b),
        )

    # loyalty_point_grants with wrong customer_id MUST be rejected (trg_loyalty_point_grants_bi).
    cat_id = int(
        execute(
            db_conn,
            "INSERT INTO reward_catalog (code, name, reward_type, value, valid_days)"
            " VALUES (%s, 'Points', 'MEMBER_POINTS', 50, 7)",
            (f"RCP-{s.token}",),
        )
    )
    voucher_id = int(
        execute(
            db_conn,
            "INSERT INTO customer_vouchers (code, catalog_id, account_id, reward_type, value,"
            " status, source, issued_at, expires_at) VALUES (%s, %s, %s, 'MEMBER_POINTS', 50,"
            " 'ISSUED', 'MANUAL', %s, %s)",
            (f"VP-{s.token}", cat_id, s.account_id, now, now + timedelta(days=7)),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO loyalty_point_grants (customer_id, voucher_id, points, employee_id)"
            " VALUES (%s, %s, 50, %s)",
            (cust2, voucher_id, s.employee_id),
        )


# ---------------------------------------------------------------------------
# 5. NF-04: Historical immutability of policy versions
# ---------------------------------------------------------------------------
def test_loyalty_policy_version_preserves_historical_invoice_points(db_conn, test_scenario):
    s = test_scenario(db_conn)
    cur_ver = rows(db_conn, "SELECT current_version FROM loyalty_settings WHERE id=1")[0]["current_version"]
    next_ver = int(cur_ver) + 100
    execute(
        db_conn,
        "INSERT INTO loyalty_policy_versions (version, enabled, unit_amount, silver_spend, gold_spend, platinum_spend)"
        " VALUES (%s, TRUE, 10000, 1000000, 3000000, 5000000)",
        (next_ver,),
    )
    sess_id = int(
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, closed_by,"
            " started_at, ended_at, hourly_rate, cost, status)"
            " VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(), 10000, 50000, 'COMPLETED')",
            (f"SLV-{s.token}", s.customer_id, s.machine_id, s.employee_id, s.employee_id),
        )
    )
    inv_id = int(
        execute(
            db_conn,
            "INSERT INTO invoices (code, session_id, customer_id, employee_id, store_id,"
            " usage_cost, bonus_used, loyalty_rule_version) VALUES (%s, %s, %s, %s, %s, 50000, 10000, %s)",
            (f"INVLV-{s.token}", sess_id, s.customer_id, s.employee_id, s.store_id, next_ver),
        )
    )
    # Publish a newer policy version with a completely different unit_amount (5000 instead of 10000).
    execute(
        db_conn,
        "INSERT INTO loyalty_policy_versions (version, enabled, unit_amount, silver_spend, gold_spend, platinum_spend)"
        " VALUES (%s, TRUE, 5000, 1000000, 3000000, 5000000)",
        (next_ver + 1,),
    )
    execute(db_conn, "UPDATE loyalty_settings SET current_version=%s WHERE id=1", (next_ver + 1,))
    # Historical invoice still resolves through its original version (40_000 / 10_000 = 4 points, NOT 8).
    inv_view = rows(db_conn, "SELECT * FROM v_invoices WHERE id=%s", (inv_id,))[0]
    assert inv_view["total_amount"] == 50_000
    assert inv_view["loyalty_eligible_amount"] == 40_000
    assert inv_view["loyalty_unit"] == 10_000
    assert inv_view["loyalty_points"] == 4


# ---------------------------------------------------------------------------
# 6. Migration 032: 3NF session_transactions & immutable financial ledger
# ---------------------------------------------------------------------------
def test_migration_032_ledger_immutability_and_session_transactions(db_conn, test_scenario):
    s = test_scenario(db_conn)
    store_b = _make_store(db_conn)
    cust2, acc2 = _make_customer_account(db_conn)

    # NULL store_id on account_transactions MUST be rejected.
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO account_transactions (code, account_id, employee_id, store_id, type, amount, method)"
            " VALUES (%s, %s, %s, NULL, 'TOP_UP', 1000, 'CASH')",
            (f"TXNULL-{s.token}", s.account_id, s.employee_id),
        )

    sess_id = int(
        execute(
            db_conn,
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, closed_by,"
            " started_at, ended_at, hourly_rate, cost, status)"
            " VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(), 10000, 10000, 'COMPLETED')",
            (f"S032-{s.token}", s.customer_id, s.machine_id, s.employee_id, s.employee_id),
        )
    )
    topup_id = int(
        execute(
            db_conn,
            "INSERT INTO account_transactions (code, account_id, employee_id, store_id, type, amount, method)"
            " VALUES (%s, %s, %s, %s, 'TOP_UP', 50000, 'CASH')",
            (f"TXTOP-{s.token}", s.account_id, s.employee_id, s.store_id),
        )
    )
    # TOP_UP cannot link to session_transactions.
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO session_transactions (transaction_id, session_id) VALUES (%s, %s)",
            (topup_id, sess_id),
        )
    # Cross-owner usage payment cannot link to session_transactions.
    other_tx = int(
        execute(
            db_conn,
            "INSERT INTO account_transactions (code, account_id, employee_id, store_id, type, amount, method)"
            " VALUES (%s, %s, %s, %s, 'USAGE_PAYMENT', -10000, 'ACCOUNT_BALANCE')",
            (f"TXOWN-{s.token}", acc2, s.employee_id, s.store_id),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO session_transactions (transaction_id, session_id) VALUES (%s, %s)",
            (other_tx, sess_id),
        )
    # Cross-store usage payment cannot link to session_transactions.
    cross_store_tx = int(
        execute(
            db_conn,
            "INSERT INTO account_transactions (code, account_id, employee_id, store_id, type, amount, method)"
            " VALUES (%s, %s, %s, %s, 'USAGE_PAYMENT', -10000, 'ACCOUNT_BALANCE')",
            (f"TXSTR-{s.token}", s.account_id, s.employee_id, store_b),
        )
    )
    with pytest.raises(MySQLError):
        execute(
            db_conn,
            "INSERT INTO session_transactions (transaction_id, session_id) VALUES (%s, %s)",
            (cross_store_tx, sess_id),
        )

    # Valid link -> immutable via BEFORE UPDATE & protected by ON DELETE RESTRICT.
    valid_tx = int(
        execute(
            db_conn,
            "INSERT INTO account_transactions (code, account_id, employee_id, store_id, type, amount, method)"
            " VALUES (%s, %s, %s, %s, 'USAGE_PAYMENT', -10000, 'ACCOUNT_BALANCE')",
            (f"TXOK-{s.token}", s.account_id, s.employee_id, s.store_id),
        )
    )
    execute(
        db_conn,
        "INSERT INTO session_transactions (transaction_id, session_id) VALUES (%s, %s)",
        (valid_tx, sess_id),
    )
    with pytest.raises(MySQLError):
        execute(db_conn, "UPDATE account_transactions SET amount = -1 WHERE id = %s", (valid_tx,))
    with pytest.raises(MySQLError):
        execute(db_conn, "UPDATE session_transactions SET session_id = %s WHERE transaction_id = %s", (sess_id, valid_tx))
    with pytest.raises(IntegrityError):
        execute(db_conn, "DELETE FROM account_transactions WHERE id = %s", (valid_tx,))

