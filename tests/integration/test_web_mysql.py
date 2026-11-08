"""Exercise the browser adapter against real services and isolated MySQL records."""

from uuid import uuid4

import pytest

pytest.importorskip("flask")

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.security import hash_password
from cyberhub_manager.web import create_app


def execute(sql, params=()):
    with transaction() as conn:
        cur = conn.cursor(buffered=True)
        try:
            cur.execute(sql, params)
            return cur.fetchone() if cur.with_rows else cur.lastrowid
        finally:
            cur.close()


@pytest.fixture
def mysql_web(test_scenario):
    with transaction() as conn:
        records = test_scenario(conn)
    password = "web-integration-only"
    token = uuid4().hex[:10]
    customer_ids = [records.customer_id]
    execute(
        "UPDATE employees SET password_hash = %s, role = 'MANAGER' WHERE id = %s",
        (hash_password(password), records.employee_id),
    )
    username = execute(
        "SELECT username FROM employees WHERE id = %s", (records.employee_id,)
    )[0]
    app = create_app(
        {
            "TESTING": True,
            "WEB_MODE": "mysql",
            "SECRET_KEY": "isolated-web-integration-secret-32-characters",
        }
    )
    try:
        yield app, records, username, password, token, customer_ids
    finally:
        # Delete only records from this fixture's unique store and customer IDs.
        with transaction() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "DELETE FROM invoices WHERE store_id = %s", (records.store_id,)
                )
                for cid in customer_ids:
                    cursor.execute(
                        "DELETE t FROM account_transactions t JOIN accounts a ON a.id = t.account_id WHERE a.customer_id = %s",
                        (cid,),
                    )
                    cursor.execute(
                        "DELETE FROM usage_sessions WHERE customer_id = %s", (cid,)
                    )
                    cursor.execute(
                        "DELETE FROM accounts WHERE customer_id = %s", (cid,)
                    )
                    cursor.execute("DELETE FROM customers WHERE id = %s", (cid,))
                cursor.execute(
                    "DELETE FROM machines WHERE store_id = %s", (records.store_id,)
                )
                cursor.execute(
                    "DELETE FROM employees WHERE store_id = %s", (records.store_id,)
                )
                cursor.execute("DELETE FROM stores WHERE id = %s", (records.store_id,))
            finally:
                cursor.close()


def signed_in(app, username, password):
    c = app.test_client()
    csrf = c.get("/api/session").json["csrf_token"]
    response = c.post(
        "/api/login",
        json=dict(username=username, password=password),
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.json
    return c, response.json["csrf_token"]


def test_mysql_actor_lookup_outage_is_safe_and_session_can_recover(mysql_web, monkeypatch, caplog):
    from mysql.connector import OperationalError
    from cyberhub_manager.repositories.auth_repository import AuthRepository

    app, records, username, password, token, customer_ids = mysql_web
    c, csrf = signed_in(app, username, password)

    def unavailable(*args, **kwargs):
        raise OperationalError("internal_db_host", errno=2013)

    with monkeypatch.context() as scoped:
        scoped.setattr(AuthRepository, "get_active_session_by_id", unavailable)
        response = c.get("/api/customers")
    assert response.status_code == 503
    assert response.json["error"]["details"] == {}
    assert "internal_db_host" not in response.get_data(as_text=True)
    assert "errno=2013" in caplog.text
    assert c.get("/api/customers").status_code == 200


def test_mysql_web_customer_wallet_session_invoice_and_revenue(mysql_web):
    app, records, username, password, token, customer_ids = mysql_web
    c, csrf = signed_in(app, username, password)

    def post(path, payload):
        return c.post(path, json=payload, headers={"X-CSRF-Token": csrf})

    result = post(
        "/api/customers",
        dict(
            full_name="Web integration customer",
            phone="03" + str(int(token, 16) % 100_000_000).zfill(8),
            username=f"web.{token}",
            password="customer-password",
        ),
    )
    assert result.status_code == 201, result.json
    cid = result.json["customer_id"]
    customer_ids.append(cid)
    assert (
        post(
            f"/api/customers/{cid}/topup",
            dict(amount=10000, method="CASH", employee_id=999999),
        ).status_code
        == 200
    )
    assert post(
        f"/api/machines/{records.machine_id}/open-preview", dict(customer_id=cid)
    ).json["can_open"]
    assert (
        post(
            f"/api/machines/{records.machine_id}/open", dict(customer_id=cid)
        ).status_code
        == 201
    )
    preview = c.get(f"/api/machines/{records.machine_id}/checkout-preview").json
    assert preview["settlement_required"] == 0
    paid = post(
        f"/api/machines/{records.machine_id}/checkout",
        dict(settlement_amount=0, method=None),
    )
    assert paid.status_code == 200, paid.json
    inv = paid.json["invoice"]["invoice"]
    assert inv["employee_id"] == records.employee_id
    assert paid.json["balance_after"] == 10000 - inv["usage_cost"]
    assert (
        c.get(f"/api/invoices/{inv['invoice_id']}").json["invoice"]["invoice_id"]
        == inv["invoice_id"]
    )
    assert c.get("/api/revenue").json["total_revenue"] == inv["usage_cost"]


def test_mysql_web_reloads_role_and_employee_status_each_request(mysql_web):
    app, records, username, password, _, _ = mysql_web
    c, csrf = signed_in(app, username, password)
    execute("UPDATE employees SET role = 'STAFF' WHERE id = %s", (records.employee_id,))
    result = c.post(
        f"/api/machines/{records.machine_id}/maintenance",
        json=dict(enabled=True, actor={"role": "ADMIN"}),
        headers={"X-CSRF-Token": csrf},
    )
    assert result.status_code == 403
    assert c.get("/api/session").json["actor"]["role"] == "STAFF"
    execute(
        "UPDATE employees SET status = 'LOCKED' WHERE id = %s", (records.employee_id,)
    )
    assert c.get("/api/machines").status_code == 401
