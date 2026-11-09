"""Đợt 2 — VoucherRepository và ràng buộc migration 008 trên MySQL thật (rollback sau mỗi test)."""

from datetime import datetime, timedelta, timezone

import pytest
from mysql.connector import Error as MySQLError

from cyberhub_manager.domain.voucher import RewardType, VoucherAction, VoucherSource, VoucherStatus
from cyberhub_manager.repositories.p1_repository import P1Repository
from cyberhub_manager.repositories.voucher_repository import VoucherRepository

NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def voucher_db(db_conn, test_scenario):
    rows = test_scenario(db_conn)
    repo = VoucherRepository()
    catalog_id = repo.insert_catalog(
        db_conn, code=f"T{rows.token}"[:20], name="Test reward", store_id=rows.store_id,
        reward_type=RewardType.MEMBER_POINTS, value=30, min_order_amount=0, valid_days=7, coin_cost=None,
        is_active=True,
    )
    catalog = repo.get_catalog(db_conn, catalog_id)

    def issue(source=VoucherSource.MANUAL, ref=None, code=None):
        return repo.insert_voucher(
            db_conn, code=code or f"CH{rows.token}{source.value[:1]}"[:20], catalog=catalog,
            account_id=rows.account_id, source=source, source_ref=ref, issued_by=rows.employee_id,
            issued_at=NOW, expires_at=NOW + timedelta(days=7),
        )

    return db_conn, repo, rows, catalog, issue


def test_voucher_snapshot_and_single_use(voucher_db):
    conn, repo, rows, catalog, issue = voucher_db
    voucher_id = issue()

    voucher = repo.get_voucher(conn, voucher_id=voucher_id, lock=True)
    assert voucher.status == VoucherStatus.ISSUED and voucher.value == 30
    assert voucher.customer_id == rows.customer_id

    used = dict(employee_id=rows.employee_id, store_id=rows.store_id, order_id=None, used_at=NOW)
    assert repo.mark_used(conn, voucher_id, **used) is True
    assert repo.mark_used(conn, voucher_id, **used) is False  # không dùng lại được
    assert repo.revoke(conn, voucher_id, "quá muộn") is False


def test_same_source_cannot_issue_twice(voucher_db):
    _, repo, _, _, issue = voucher_db
    issue(VoucherSource.GAME, "spin-1", code="CHGAME0001")

    with pytest.raises(MySQLError):
        issue(VoucherSource.GAME, "spin-1", code="CHGAME0002")


def test_used_state_requires_audit_columns(voucher_db):
    conn, _, _, _, issue = voucher_db
    voucher_id = issue()
    cursor = conn.cursor()
    try:
        with pytest.raises(MySQLError):  # USED mà thiếu used_by/used_at bị CHECK chặn
            cursor.execute("UPDATE customer_vouchers SET status = 'USED' WHERE id = %s", (voucher_id,))
    finally:
        cursor.close()


def test_point_grant_counts_in_membership(voucher_db):
    conn, repo, rows, _, issue = voucher_db
    voucher_id = issue()
    before = P1Repository().loyalty_summary(conn, rows.customer_id)["points"]

    repo.grant_points(conn, customer_id=rows.customer_id, voucher_id=voucher_id, points=30,
                      employee_id=rows.employee_id)

    assert P1Repository().loyalty_summary(conn, rows.customer_id)["points"] == before + 30
    with pytest.raises(MySQLError):  # một voucher chỉ tặng điểm một lần
        repo.grant_points(conn, customer_id=rows.customer_id, voucher_id=voucher_id, points=30,
                          employee_id=rows.employee_id)


def test_playtime_credit_goes_to_promotional_balance(voucher_db):
    conn, repo, rows, _, _ = voucher_db
    repo.credit_playtime(conn, account_id=rows.account_id, amount=10_000, employee_id=rows.employee_id,
                         store_id=rows.store_id)

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT balance, bonus_balance FROM accounts WHERE id = %s", (rows.account_id,))
        account = cursor.fetchone()
        cursor.execute("SELECT type, method, amount FROM account_transactions WHERE account_id = %s",
                       (rows.account_id,))
        ledger = cursor.fetchall()
    finally:
        cursor.close()
    assert account["bonus_balance"] == 10_000 and account["balance"] == 10_000
    assert ledger == [{"type": "PROMOTION", "method": "PROMOTION", "amount": 10_000}]


def test_events_include_rejections_without_voucher(voucher_db):
    conn, repo, rows, _, issue = voucher_db
    voucher_id = issue()
    repo.insert_event(conn, voucher_id=voucher_id, action=VoucherAction.ISSUE, employee_id=rows.employee_id,
                      store_id=rows.store_id, reason="MANUAL")
    repo.insert_event(conn, voucher_id=None, action=VoucherAction.REJECT, employee_id=rows.employee_id,
                      store_id=rows.store_id, reason="UNKNOWN: CHXXXX")

    events = repo.list_events(conn, rows.store_id)

    assert [e.action for e in events] == [VoucherAction.REJECT, VoucherAction.ISSUE]
    assert events[0].voucher_code is None and events[1].voucher_code is not None
