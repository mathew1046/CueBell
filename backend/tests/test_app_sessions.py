import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app
from tests.conftest import ACCESS_CODE, activate, pair


def test_app_sessions_default_off_and_environment_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_APP_SESSIONS", raising=False)
    assert Settings(_env_file=None).allow_app_sessions is False
    monkeypatch.setenv("ALLOW_APP_SESSIONS", "true")
    assert Settings(_env_file=None).allow_app_sessions is True


@pytest.mark.parametrize("body", [{}, {"access_code": None}])
def test_missing_code_requires_explicit_opt_in(settings, intelligence, body):
    settings.allow_app_sessions = False
    with TestClient(create_app(settings, intelligence)) as client:
        assert client.post("/v1/sessions", json=body).status_code == 401


@pytest.mark.parametrize("body", [{}, {"access_code": None}])
def test_app_session_needs_no_operator_secret(settings, intelligence, body):
    settings.allow_app_sessions = True
    settings.demo_access_code = ""
    with TestClient(create_app(settings, intelligence)) as client:
        response = client.post("/v1/sessions", json=body)
        assert response.status_code == 200
        assert set(response.json()) == {"token", "expires_at", "venue", "disclosure"}
        assert response.json()["expires_at"] > time.time()
        assert "Gnani" in response.json()["disclosure"]
        assert "OpenAI" in response.json()["disclosure"]
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("code", ["wrong", "മലയാളം", "🔑"])
def test_opt_in_never_bypasses_supplied_wrong_code(settings, intelligence, code):
    settings.allow_app_sessions = True
    with TestClient(create_app(settings, intelligence)) as client:
        assert client.post("/v1/sessions", json={"access_code": code}).status_code == 401
        assert client.post("/v1/sessions", json={}).status_code == 200
        pair(client)


def test_supplied_code_still_requires_configured_secret(settings, intelligence):
    settings.allow_app_sessions = True
    settings.demo_access_code = ""
    with TestClient(create_app(settings, intelligence)) as client:
        assert client.post("/v1/sessions", json={"access_code": ACCESS_CODE}).status_code == 503


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        {"access_code": ""},
        {"access_code": "x" * 257},
        {"access_code": 123},
        {"access_code": True},
        {"access_code": []},
        {"access_code": {}},
        {"api_key": "no"},
        [],
        "",
    ],
)
def test_malformed_session_payload_stays_strict(settings, intelligence, enabled, body):
    settings.allow_app_sessions = enabled
    with TestClient(create_app(settings, intelligence)) as client:
        assert client.post("/v1/sessions", json=body).status_code == 422


@pytest.mark.parametrize("body", [b"", b"null", b'{"access_code":'])
def test_missing_or_invalid_json_is_not_an_app_session(settings, intelligence, body):
    settings.allow_app_sessions = True
    with TestClient(create_app(settings, intelligence)) as client:
        response = client.post(
            "/v1/sessions", content=body, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


def test_app_ip_limit_survives_deletion_and_ignores_forwarding_headers(settings, intelligence):
    settings.allow_app_sessions = True
    with TestClient(create_app(settings, intelligence)) as client:
        for index in range(3):
            response = client.post(
                "/v1/sessions", json={}, headers={"X-Forwarded-For": f"192.0.2.{index}"}
            )
            assert response.status_code == 200
            auth = {"Authorization": "Bearer " + response.json()["token"]}
            assert client.delete("/v1/session", headers=auth).status_code == 200
        response = client.post("/v1/sessions", json={}, headers={"X-Forwarded-For": "192.0.2.99"})
        assert response.status_code == 429
        assert "IP limit" in response.json()["detail"]
        # Code-authenticated pairing is not subject to the anonymous IP limit.
        pair(client)


async def test_ip_buckets_are_separate_bounded_and_expire(settings, intelligence, monkeypatch):
    settings.allow_app_sessions = True
    clock = [time.monotonic()]
    monkeypatch.setattr("app.main.APP_SESSION_IP_BUCKETS", 2)
    monkeypatch.setattr(
        "app.main.time", SimpleNamespace(time=time.time, monotonic=lambda: clock[0])
    )
    app = create_app(settings, intelligence)

    async def admit(ip):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(ip, 1234)), base_url="http://test"
        ) as client:
            response = await client.post("/v1/sessions", json={})
            if response.status_code == 200:
                auth = {"Authorization": "Bearer " + response.json()["token"]}
                assert (await client.delete("/v1/session", headers=auth)).status_code == 200
            return response

    for _ in range(3):
        assert (await admit("192.0.2.1")).status_code == 200
    assert (await admit("192.0.2.1")).status_code == 429
    assert (await admit("192.0.2.2")).status_code == 200
    response = await admit("192.0.2.3")
    assert response.status_code == 429
    assert "admission capacity" in response.json()["detail"]
    # Filling the table never evicts an active limiter.
    assert (await admit("192.0.2.1")).status_code == 429
    clock[0] += 600
    assert (await admit("192.0.2.3")).status_code == 200
    assert (await admit("192.0.2.1")).status_code == 200


async def test_anonymous_admission_rejects_missing_client_address(settings, intelligence):
    settings.allow_app_sessions = True
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, intelligence), client=None),
        base_url="http://test",
    ) as client:
        response = await client.post("/v1/sessions", json={})
        assert response.status_code == 400
        assert response.json()["detail"] == "Client address unavailable."
        # Code-authenticated clients retain their previous admission behavior.
        assert (
            await client.post("/v1/sessions", json={"access_code": ACCESS_CODE})
        ).status_code == 200


async def test_anonymous_sessions_share_global_attempt_limit(settings, intelligence, monkeypatch):
    settings.allow_app_sessions = True
    settings.max_sessions = 100
    clock = [time.monotonic()]
    monkeypatch.setattr(
        "app.main.time", SimpleNamespace(time=time.time, monotonic=lambda: clock[0])
    )
    app = create_app(settings, intelligence)
    for index in range(21):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(f"192.0.2.{index}", 1234)),
            base_url="http://test",
        ) as client:
            response = await client.post("/v1/sessions", json={})
            assert response.status_code == (200 if index < 20 else 429)
            if index == 20:
                assert "Pairing rate limit" in response.json()["detail"]
                assert (
                    await client.post("/v1/sessions", json={"access_code": ACCESS_CODE})
                ).status_code == 429
                clock[0] += 60
                assert (await client.post("/v1/sessions", json={})).status_code == 200


def test_anonymous_sessions_share_capacity(settings, intelligence):
    settings.allow_app_sessions = True
    settings.max_sessions = 1
    with TestClient(create_app(settings, intelligence)) as client:
        auth = pair(client)
        response = client.post("/v1/sessions", json={})
        assert response.status_code == 429
        assert "session capacity" in response.json()["detail"]
        assert client.delete("/v1/session", headers=auth).status_code == 200
        assert client.post("/v1/sessions", json={}).status_code == 200
        assert client.post("/v1/sessions", json={"access_code": ACCESS_CODE}).status_code == 429


def test_expired_anonymous_session_releases_capacity(settings, intelligence, monkeypatch):
    settings.allow_app_sessions = True
    settings.max_sessions = 1
    with TestClient(create_app(settings, intelligence)) as client:
        response = client.post("/v1/sessions", json={}).json()
        monkeypatch.setattr(
            "app.main.time",
            SimpleNamespace(time=lambda: response["expires_at"] + 1, monotonic=time.monotonic),
        )
        assert client.post("/v1/sessions", json={}).status_code == 200


def test_anonymous_bearer_expiry_consent_controls_and_limits(settings, intelligence, monkeypatch):
    settings.allow_app_sessions = True
    settings.session_ttl_seconds = 60
    with TestClient(create_app(settings, intelligence)) as client:
        now = time.time()
        response = client.post("/v1/sessions", json={}).json()
        assert now + 60 <= response["expires_at"] <= time.time() + 60
        assert len(response["token"]) >= 40
        assert client.get("/v1/state").status_code == 401
        assert (
            client.get("/v1/state", headers={"Authorization": response["token"]}).status_code == 401
        )
        auth = {"Authorization": "Bearer " + response["token"]}
        assert (
            client.post(
                "/v1/intent",
                headers=auth,
                json={"text": "Vibrate for P042", "consent_to_text_processing": False},
            ).status_code
            == 400
        )
        activate(client, auth)
        assert client.post("/v1/control", headers=auth, json={"action": "pause"}).status_code == 200
        assert (
            client.post("/v1/control", headers=auth, json={"action": "resume"}).status_code == 200
        )
        assert client.post("/v1/control", headers=auth, json={"action": "stop"}).status_code == 200
        # Six authenticated requests above leave 24 in the same ordinary HTTP budget.
        for _ in range(24):
            assert client.get("/v1/state", headers=auth).status_code == 200
        assert client.get("/v1/state", headers=auth).status_code == 429
        assert client.delete("/v1/session", headers=auth).status_code == 200
        assert client.get("/v1/state", headers=auth).status_code == 401

        fresh = client.post("/v1/sessions", json={}).json()
        fresh_auth = {"Authorization": "Bearer " + fresh["token"]}
        monkeypatch.setattr(
            "app.main.time",
            SimpleNamespace(time=lambda: fresh["expires_at"], monotonic=time.monotonic),
        )
        assert client.get("/v1/state", headers=fresh_auth).status_code == 401
        assert client.delete("/v1/session", headers=fresh_auth).status_code == 401


def test_anonymous_opt_in_does_not_disable_tls_or_websocket_auth(settings, intelligence):
    settings.allow_app_sessions = True
    settings.allow_insecure_local = False
    app = create_app(settings, intelligence)
    with TestClient(app) as client:
        assert client.post("/v1/sessions", json={}).status_code == 400
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/v1/sessions", json={}).status_code == 200
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("wss://testserver/v1/stream?mode=request"):
                pass
        assert error.value.code == 4403
