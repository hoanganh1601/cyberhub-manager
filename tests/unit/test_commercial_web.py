"""HTTP boundary tests for public, signed commercial callbacks."""

from types import SimpleNamespace

from flask import Flask, jsonify

from cyberhub_manager.web.feature_routes import register_feature_routes


class CallbackService:
    def __init__(self):
        self.calls = []

    def verify_game_callback(self, token, provider_event_id, outcome, signature):
        self.calls.append(("game", token, provider_event_id, outcome, signature))
        return {
            "event_id": 51,
            "reward_grant_id": 52,
            "reward_status": "PENDING",
            "idempotent": False,
        }

    def verify_partner_event_callback(
        self, placement_code, provider_event_id, event_type, signature
    ):
        self.calls.append(
            ("event", placement_code, provider_event_id, event_type, signature)
        )
        return {"event_id": 53, "accepted": True, "idempotent": False}


def build_client(commercial=None):
    app = Flask(__name__)
    app.config["TESTING"] = True

    def reply(value, status=200):
        return jsonify(value), status

    def error(code, vi, _en, status):
        return reply({"error": {"code": code, "message": vi}}, status)

    register_feature_routes(
        app,
        reply=reply,
        body=lambda: {},
        error=error,
        real_services=SimpleNamespace(commercial=commercial),
    )
    return app.test_client()


def test_public_game_callback_passes_signature_only_to_service():
    service = CallbackService()
    response = build_client(service).post(
        "/commercial/callback/game",
        json={
            "token": "launch-token",
            "provider_event_id": "game-event-1",
            "outcome": "complete",
        },
        headers={"X-CyberHub-Signature": "signed-game"},
    )

    assert response.status_code == 200
    assert response.json["reward_status"] == "PENDING"
    assert service.calls == [
        ("game", "launch-token", "game-event-1", "complete", "signed-game")
    ]


def test_public_partner_event_callback_passes_signature_only_to_service():
    service = CallbackService()
    response = build_client(service).post(
        "/commercial/callback/event",
        json={
            "placement_code": "PORTAL_BANNER_01",
            "provider_event_id": "ad-event-1",
            "event_type": "IMPRESSION",
        },
        headers={"X-CyberHub-Signature": "signed-event"},
    )

    assert response.status_code == 200
    assert response.json == {
        "accepted": True,
        "event_id": 53,
        "idempotent": False,
        "ok": True,
    }
    assert service.calls == [
        (
            "event",
            "PORTAL_BANNER_01",
            "ad-event-1",
            "IMPRESSION",
            "signed-event",
        )
    ]


def test_public_callbacks_fail_closed_when_commercial_service_is_missing():
    client = build_client()

    assert client.post("/commercial/callback/game", json={}).status_code == 503
    assert client.post("/commercial/callback/event", json={}).status_code == 503
