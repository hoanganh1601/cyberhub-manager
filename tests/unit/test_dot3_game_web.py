"""Đợt 3 — API vòng quay qua Flask (chế độ demo): CSRF, trình duyệt không gửi được kết quả."""

import pytest

pytest.importorskip("flask")

from cyberhub_manager.web import create_app  # noqa: E402


@pytest.fixture
def app():
    return create_app({"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "dot3-game-web-test"})


def sign_in(client, username, kind=None):
    csrf = client.get("/api/session").json["csrf_token"]
    payload = dict(username=username, password="demo123")
    if kind:
        payload["kind"] = kind
    result = client.post("/api/login", json=payload, headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200, result.json
    return {"X-CSRF-Token": result.json["csrf_token"]}


def test_spin_ignores_client_supplied_result_and_requires_csrf(app):
    c = app.test_client()
    headers = sign_in(c, "nguyenvanan", "customer")
    forged = {"coins": 1000, "prize_index": 5, "balance": 999999}

    assert c.post("/api/portal/game/spin", json=forged).status_code == 403  # thiếu CSRF
    result = c.post("/api/portal/game/spin", json=forged, headers=headers)

    assert result.status_code == 200, result.json
    prizes = c.get("/api/portal/game").json["game"]["prizes"]
    won = next(p for p in prizes if p["index"] == result.json["prize_index"])
    assert result.json["coins"] == won["coins"] <= 100
    assert c.get("/api/portal/game").json["wallet"]["balance"] == result.json["coins"]


def test_second_spin_too_fast_conflicts(app):
    c = app.test_client()
    headers = sign_in(c, "nguyenvanan", "customer")
    assert c.post("/api/portal/game/spin", json={}, headers=headers).status_code == 200
    assert c.post("/api/portal/game/spin", json={}, headers=headers).status_code == 409


def test_redeem_without_coins_conflicts(app):
    c = app.test_client()
    headers = sign_in(c, "nguyenvanan", "customer")
    result = c.post("/api/portal/game/redeem", json={"catalog_id": 1, "request_key": "web-key-000001"},
                    headers=headers)
    assert result.status_code == 409


def test_staff_views_game_admin_but_customer_cannot(app):
    staff = app.test_client()
    sign_in(staff, "nhanvien01")
    data = staff.get("/api/games").json
    assert data["can_configure"] is False and "stats" in data

    customer = app.test_client()
    sign_in(customer, "nguyenvanan", "customer")
    assert customer.get("/api/games").status_code in (401, 403)


def test_manager_cannot_change_wheel(app):
    c = app.test_client()
    headers = sign_in(c, "quanly01")
    body = {"is_active": True, "daily_limit": 10, "min_interval_seconds": 1,
            "prizes": [{"label": "A", "coins": 1000, "weight": 1}, {"label": "B", "coins": 1000, "weight": 1}]}
    assert c.put("/api/games", json=body, headers=headers).status_code == 403
