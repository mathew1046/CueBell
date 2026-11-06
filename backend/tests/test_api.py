import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import ACCESS_CODE, activate, make_intent, pair


def test_health_discloses_configuration_without_secrets(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "speech_configured": False,
        "intent_configured": True,
        "text_provider": "openai_fallback",
        "evon": "contract_not_configured",
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("code", ["wrong", "മലയാളം", "🔑"])
def test_incorrect_and_unicode_pairing_codes_return_401(client, code):
    assert client.post("/v1/sessions", json={"access_code": code}).status_code == 401


def test_pair_requires_operator_secret(settings, intelligence):
    settings.demo_access_code = "short"
    with TestClient(create_app(settings, intelligence)) as client:
        assert client.post("/v1/sessions", json={"access_code": "short"}).status_code == 503


def test_capacity_and_pairing_rate_limit(settings, intelligence):
    settings.max_sessions = 1
    with TestClient(create_app(settings, intelligence)) as client:
        pair(client)
        assert client.post("/v1/sessions", json={"access_code": ACCESS_CODE}).status_code == 429
    with TestClient(create_app(settings, intelligence)) as client:
        for _ in range(20):
            assert client.post("/v1/sessions", json={"access_code": "bad"}).status_code == 401
        assert client.post("/v1/sessions", json={"access_code": ACCESS_CODE}).status_code == 429


def test_auth_requires_bearer_and_isolated_sessions(client, auth):
    assert client.get("/v1/state").status_code == 401
    assert (
        client.get("/v1/state", headers={"Authorization": auth["Authorization"][7:]}).status_code
        == 401
    )
    assert client.get("/v1/state", headers={"Authorization": "Basic x"}).status_code == 401
    activate(client, auth)
    second = pair(client)
    assert client.get("/v1/state", headers=second).json()["rule"] is None
    assert client.get("/v1/state", headers=auth).json()["rule"]["token"] == "P042"


def test_session_expiry(client, auth, monkeypatch):
    future = time.time() + 20000
    monkeypatch.setattr("app.main.time.time", lambda: future)
    assert client.get("/v1/state", headers=auth).status_code == 401
    assert client.delete("/v1/session", headers=auth).status_code == 401


def test_authenticated_request_limit(client, auth):
    for _ in range(30):
        assert client.get("/v1/state", headers=auth).status_code == 200
    assert client.get("/v1/state", headers=auth).status_code == 429
    # Deletion must remain possible after a request rate limit.
    assert client.delete("/v1/session", headers=auth).status_code == 200
    assert client.get("/v1/state", headers=auth).status_code == 401


def test_request_confirmation_is_explicit_and_one_use(client, auth):
    assert (
        client.post("/v1/confirm", headers=auth, json={"proposal_id": "unknown"}).status_code == 409
    )
    response = client.post(
        "/v1/intent",
        headers=auth,
        json={
            "text": "Vibrate for P042",
            "consent_to_text_processing": True,
        },
    )
    assert response.json()["status"] == "confirm"
    assert client.get("/v1/state", headers=auth).json()["rule"] is None
    body = {"proposal_id": response.json()["proposal_id"]}
    confirmed = client.post("/v1/confirm", headers=auth, json=body)
    assert confirmed.json()["rule"]["alert_preferences"] == ["vibration", "visual"]
    assert client.post("/v1/confirm", headers=auth, json=body).status_code == 409


def test_text_consent_and_strict_json(client, auth, intelligence):
    assert (
        client.post(
            "/v1/intent",
            headers=auth,
            json={
                "text": "Vibrate for P042",
                "consent_to_text_processing": False,
            },
        ).status_code
        == 400
    )
    assert not intelligence.intent_calls
    for body in [
        {"text": "x", "consent_to_text_processing": "true"},
        {"text": "x", "consent_to_text_processing": True, "api_key": "no"},
        {"text": "x" * 1501, "consent_to_text_processing": True},
        {"text": "", "consent_to_text_processing": True},
    ]:
        assert client.post("/v1/intent", headers=auth, json=body).status_code == 422


def test_malayalam_token_ten_can_be_reviewed_and_confirmed(client, auth, intelligence):
    intelligence.intent_result = make_intent(
        token="10",
        target_evidence="പത്ത്",
        context="queue",
        alert_preferences=["visual", "vibration", "sound"],
    )
    proposal = client.post(
        "/v1/intent",
        headers=auth,
        json={
            "text": "ടോക്കൺ പത്ത് ആകുമ്പോൾ വൈബ്രേറ്റ് ചെയ്യുക",
            "consent_to_text_processing": True,
        },
    ).json()
    assert proposal["status"] == "confirm"
    confirmed = client.post(
        "/v1/confirm",
        headers=auth,
        json={"proposal_id": proposal["proposal_id"]},
    ).json()
    assert confirmed["rule"]["token"] == "10"
    assert set(confirmed["rule"]["alert_preferences"]) == {"visual", "vibration", "sound"}


def test_clarification_invalidates_old_proposal(client, auth, intelligence):
    proposal = client.post(
        "/v1/intent",
        headers=auth,
        json={
            "text": "Vibrate for P042",
            "consent_to_text_processing": True,
        },
    ).json()["proposal_id"]
    intelligence.intent_result = make_intent(token=None, clarification="Which token?")
    response = client.post(
        "/v1/intent",
        headers=auth,
        json={
            "text": "Vibrate for some token",
            "consent_to_text_processing": True,
        },
    )
    assert response.json()["status"] == "clarify"
    assert response.json()["messages"]
    assert (
        client.post("/v1/confirm", headers=auth, json={"proposal_id": proposal}).status_code == 409
    )


def test_provider_failure_is_sanitized_and_invalidates_proposal(client, auth, intelligence):
    proposal = client.post(
        "/v1/intent",
        headers=auth,
        json={
            "text": "Vibrate for P042",
            "consent_to_text_processing": True,
        },
    ).json()["proposal_id"]

    async def fail(text):
        raise RuntimeError("private-provider-credential")

    intelligence.intent = fail
    response = client.post(
        "/v1/intent",
        headers=auth,
        json={
            "text": "Vibrate for P042",
            "consent_to_text_processing": True,
        },
    )
    assert response.status_code == 502
    assert "private-provider-credential" not in response.text
    assert (
        client.post("/v1/confirm", headers=auth, json={"proposal_id": proposal}).status_code == 409
    )


def test_missing_model_is_not_a_fake_success(settings):
    with TestClient(create_app(settings)) as client:
        auth = pair(client)
        assert (
            client.post(
                "/v1/intent",
                headers=auth,
                json={
                    "text": "Vibrate for P042",
                    "consent_to_text_processing": True,
                },
            ).status_code
            == 503
        )


def test_controls_and_deletion(client, auth):
    assert client.post("/v1/control", headers=auth, json={"action": "pause"}).status_code == 409
    activate(client, auth)
    for action, status in [("pause", "PAUSED"), ("resume", "ACTIVE"), ("stop", "STOPPED")]:
        response = client.post("/v1/control", headers=auth, json={"action": action})
        assert response.status_code == 200
        assert response.json()["rule"]["status"] == status
    state = client.get("/v1/state", headers=auth).json()
    assert state["alerts"] == []
    assert state["history"] == []
    assert (
        client.post(
            "/v1/control",
            headers=auth,
            json={
                "action": "acknowledge",
                "alert_id": "unknown",
            },
        ).status_code
        == 409
    )
    assert client.post("/v1/control", headers=auth, json={"action": "arbitrary"}).status_code == 422
    assert client.delete("/v1/session", headers=auth).json() == {"deleted": True}
    assert client.get("/v1/state", headers=auth).status_code == 401


def test_stop_cannot_be_bypassed_with_pause_or_resume(client, auth):
    activate(client, auth)
    assert client.post("/v1/control", headers=auth, json={"action": "stop"}).status_code == 200
    for action in ["pause", "resume"]:
        response = client.post("/v1/control", headers=auth, json={"action": action})
        assert response.status_code == 409
        assert "confirm" in response.json()["detail"]
    assert client.get("/v1/state", headers=auth).json()["rule"]["status"] == "STOPPED"
    assert activate(client, auth)["rule"]["status"] == "ACTIVE"


def test_https_is_required_and_proxy_headers_are_not_blindly_trusted(settings):
    settings.allow_insecure_local = False
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"X-Forwarded-Proto": "https"})
        assert response.status_code == 400
        assert response.headers["cache-control"] == "no-store"
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("length", ["8193", "-1", "invalid", "9" * 5000])
def test_bad_content_length_is_rejected(client, length):
    response = client.post("/v1/sessions", headers={"Content-Length": length}, content=b"{}")
    assert response.status_code == 413


def test_duplicate_content_length_is_rejected(client):
    response = client.post(
        "/v1/sessions", headers=[("Content-Length", "2"), ("Content-Length", "2")], content=b"{}"
    )
    assert response.status_code == 413


def test_body_limit_allows_exact_boundary(client):
    body = '{"access_code":"' + ACCESS_CODE + '"}'
    response = client.post(
        "/v1/sessions",
        headers={"Content-Type": "application/json"},
        content=body + " " * (8192 - len(body)),
    )
    assert response.status_code == 200


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "1"}])
async def test_actual_streamed_body_is_bounded(settings, intelligence, headers):
    async def chunks():
        yield b"x" * 4096
        yield b"x" * 4096
        yield b"x"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, intelligence)),
        base_url="http://test",
        timeout=5,
    ) as client:
        response = await client.post("/v1/sessions", headers=headers, content=chunks())
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


async def test_confirmation_and_stop_cannot_race_extraction(settings, intelligence):
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow_intent(text):
        started.set()
        await finish.wait()
        return make_intent()

    app = create_app(settings, intelligence)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        token = (await client.post("/v1/sessions", json={"access_code": ACCESS_CODE})).json()[
            "token"
        ]
        auth = {"Authorization": "Bearer " + token}
        body = {"text": "Vibrate for P042", "consent_to_text_processing": True}
        old = (await client.post("/v1/intent", headers=auth, json=body)).json()["proposal_id"]
        await client.post("/v1/confirm", headers=auth, json={"proposal_id": old})
        intelligence.intent = slow_intent
        pending = asyncio.create_task(client.post("/v1/intent", headers=auth, json=body))
        await asyncio.wait_for(started.wait(), 2)
        try:
            assert (await client.post("/v1/intent", headers=auth, json=body)).status_code == 409
            assert (
                await client.post("/v1/confirm", headers=auth, json={"proposal_id": old})
            ).status_code == 409
            assert (
                await client.post("/v1/control", headers=auth, json={"action": "stop"})
            ).status_code == 200
        finally:
            finish.set()
        assert (await pending).status_code == 409
