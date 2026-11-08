"""Private avatar uploads and membership configuration over the actual Flask routes."""

from io import BytesIO
from random import Random
import pytest
from PIL import Image
from cyberhub_manager.web import create_app


@pytest.fixture
def client():
    return create_app(
        dict(TESTING=True, WEB_MODE="demo", SECRET_KEY="membership-unit-tests")
    ).test_client()


def login(client, username="nguyenvanan", kind="customer"):
    token = client.get("/api/session").json["csrf_token"]
    response = client.post(
        "/api/login",
        json=dict(username=username, password="demo123", kind=kind),
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["csrf_token"]}


def test_avatar_multipart_over_old_16kb_limit_and_private_read(client):
    headers = login(client)
    image = Image.frombytes("RGB", (128, 128), Random(42).randbytes(128 * 128 * 3))
    buf = BytesIO()
    image.save(buf, format="PNG")
    content = buf.getvalue()
    assert len(content) > 16384
    assert (
        client.post(
            "/api/portal/avatar", data={"avatar": (BytesIO(content), "photo.png")}
        ).status_code
        == 403
    )
    result = client.post(
        "/api/portal/avatar",
        data={"avatar": (BytesIO(content), "photo.png")},
        headers=headers,
    )
    assert result.status_code == 200, result.json
    assert list(result.json) == ["avatar_version"]
    photo = client.get("/api/portal/avatar")
    assert photo.status_code == 200 and photo.mimetype == "image/webp"
    assert (
        photo.headers["Cache-Control"] == "no-store"
        and photo.headers["X-Content-Type-Options"] == "nosniff"
    )
    assert client.delete("/api/portal/avatar", headers=headers).status_code == 200
    assert client.get("/api/portal/avatar").status_code == 404


def test_membership_is_owned_and_customer_cannot_change_program(client):
    headers = login(client)
    member = client.get("/api/portal/member").json
    assert member["points"] == 5 and member["history"]["total"] == 2
    assert client.get("/api/loyalty/settings").status_code == 401
    assert (
        client.put("/api/loyalty/settings", json={}, headers=headers).status_code == 401
    )
    assert (
        client.post(
            "/api/portal/avatar",
            data={"avatar": (BytesIO(b"<svg/>"), "x.png")},
            headers=headers,
        ).status_code
        == 422
    )
    assert client.get("/api/portal/member?page=0").status_code == 422


def test_admin_can_configure_and_employee_cannot_upload_customer_avatar(client):
    headers = login(client, "admin01", "employee")
    settings = client.get("/api/loyalty/settings").json
    settings["unit_amount"] = 5000
    result = client.put("/api/loyalty/settings", json=settings, headers=headers)
    assert result.status_code == 200 and result.json["version"] == 2
    assert (
        client.put("/api/loyalty/settings", json=settings, headers=headers).status_code
        == 409
    )
    assert client.get("/api/portal/avatar").status_code == 403


def test_personal_offer_is_automatically_applied_by_eligible_customer_preview(client):
    headers = login(client)
    result = client.post(
        "/api/portal/topup-preview",
        json={"store_id": 1, "amount": 300000},
        headers=headers,
    )
    assert result.status_code == 200 and result.json["bonus_amount"] == 75000
