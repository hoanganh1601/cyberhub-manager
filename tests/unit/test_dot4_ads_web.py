"""Đợt 4 — API quảng cáo nhận thưởng qua Flask (chế độ demo)."""

import pytest

pytest.importorskip("flask")

from cyberhub_manager.web import create_app  # noqa: E402


@pytest.fixture
def app():
    return create_app({"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "dot4-ads-web-test"})


def sign_in(client, username, kind=None):
    csrf = client.get("/api/session").json["csrf_token"]
    payload = dict(username=username, password="demo123")
    if kind:
        payload["kind"] = kind
    result = client.post("/api/login", json=payload, headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200, result.json
    return {"X-CSRF-Token": result.json["csrf_token"]}


def test_claiming_immediately_is_rejected_and_token_cannot_be_reused(app):
    c = app.test_client()
    headers = sign_in(c, "nguyenvanan", "customer")
    assert c.get("/api/portal/ads").json["remaining"] == 3

    assert c.post("/api/portal/ads/start", json={}).status_code == 403  # thiếu CSRF
    ad = c.post("/api/portal/ads/start", json={}, headers=headers).json
    # Gửi kèm "đã xem 999 giây" cũng vô ích: máy chủ tự đo thời lượng.
    early = c.post("/api/portal/ads/complete", json={"token": ad["token"], "watched_seconds": 999}, headers=headers)
    assert early.status_code == 409
    again = c.post("/api/portal/ads/complete", json={"token": ad["token"]}, headers=headers)
    assert again.status_code == 409


def test_network_callback_is_not_available_in_demo(app):
    c = app.test_client()
    result = c.get("/ads/callback?token=" + "a" * 32 + "&txn=txn-1&sig=" + "0" * 64)
    assert result.status_code == 404


def test_staff_sees_ad_statistics_customer_does_not(app):
    staff = app.test_client()
    sign_in(staff, "nhanvien01")
    data = staff.get("/api/ads").json
    assert data["can_configure"] is False and len(data["creatives"]) == 3

    customer = app.test_client()
    sign_in(customer, "nguyenvanan", "customer")
    assert customer.get("/api/ads").status_code in (401, 403)


def test_manager_cannot_change_ad_settings(app):
    c = app.test_client()
    headers = sign_in(c, "quanly01")
    body = {"enabled": True, "mode": "HOUSE", "daily_cap": 10, "reward_type": "COINS", "reward_amount": 100}
    assert c.put("/api/ads/settings", json=body, headers=headers).status_code == 403
