"""Exercise browser admission against the real relay with mocked speech and text providers."""

import asyncio
import threading
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app
from tests.conftest import activate, pair
from tests.test_stream import CONSENT, FakePrisma, expect_closed, ready, receive_type

ORIGIN = "https://app.example.com"


@pytest.fixture
def browser_relay(settings, intelligence, monkeypatch):
    settings.web_origins = [ORIGIN]
    settings.gnani_api_key = "dummy-test-key"
    created = []

    @asynccontextmanager
    async def provider(_settings):
        fake = FakePrisma()
        created.append(fake)
        yield fake

    monkeypatch.setattr("app.main.prisma", provider)
    with TestClient(create_app(settings, intelligence)) as client:
        yield client, created


def handshake(auth, **changes):
    return {
        "type": "authenticate",
        "token": auth["Authorization"][7:],
        "consent": "audio-gnani;text-openai",
        **changes,
    }


def test_browser_monitor_reuses_native_pcm_transcript_and_grounded_alert_pipeline(browser_relay):
    client, created = browser_relay
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream?mode=monitor", headers={"Origin": ORIGIN}) as socket:
        socket.send_json(handshake(auth))
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        transcript = receive_type(socket, "transcript")
        assert transcript["mode"] == "monitor"
        alert = receive_type(socket, "alert")["alert"]
        assert alert["token"] == "P042"
        assert alert["counter"] == "2"
    assert created[0].audio == [b"\0" * 1024]


@pytest.mark.parametrize("browser", [False, True])
@pytest.mark.parametrize("optimized", [False, True])
def test_stream_retries_during_provider_shutdown_without_losing_task(
    settings, intelligence, monkeypatch, browser, optimized
):
    settings.web_origins = [ORIGIN]
    settings.gnani_api_key = "dummy-test-key"
    settings.optimized_scheduling = optimized
    settings.outbound_writer = optimized
    closing, release, created = threading.Event(), asyncio.Event(), []

    @asynccontextmanager
    async def provider(_settings):
        fake = FakePrisma(transcripts=[])
        created.append(fake)
        try:
            yield fake
        finally:
            if len(created) == 1:
                closing.set()
                await release.wait()

    monkeypatch.setattr("app.main.prisma", provider)
    with TestClient(create_app(settings, intelligence)) as client:
        auth = pair(client)
        activate(client, auth)
        task = client.get("/v1/state", headers=auth).json()["rule"]
        headers = {"Origin": ORIGIN} if browser else {**auth, **CONSENT}
        with client.websocket_connect("/v1/stream?mode=monitor", headers=headers) as first:
            if browser:
                first.send_json(handshake(auth))
            ready(first)
            first.send_json({"type": "stop"})
            try:
                assert closing.wait(2)
                with pytest.raises(WebSocketDisconnect) as rejected:
                    with client.websocket_connect(
                        "/v1/stream?mode=monitor", headers=headers
                    ) as retry:
                        if browser:
                            retry.send_json(handshake(auth))
                        retry.receive_json()
                assert rejected.value.code == 4409  # Busy, not an invalid session.
                assert len(created) == 1  # Never open overlapping provider streams.
                state = client.get("/v1/state", headers=auth)
                assert state.status_code == 200
                assert state.json()["rule"] == task
            finally:
                first.portal.call(release.set)
            expect_closed(first)

        with client.websocket_connect("/v1/stream?mode=monitor", headers=headers) as retry:
            if browser:
                retry.send_json(handshake(auth))
            ready(retry)
            retry.send_bytes(b"\0" * 1024)
            assert retry.receive_json()["state"] == "LISTENING"
            retry.send_json({"type": "stop"})
            expect_closed(retry)
        assert len(created) == 2
        assert client.get("/v1/state", headers=auth).json()["rule"] == task


@pytest.mark.parametrize(
    "changes",
    [
        {"token": "invalid"},
        {"token": None},
        {"token": []},
        {"consent": None},
        {"consent": "audio-gnani"},
        {"type": "audio"},
    ],
)
def test_browser_rejects_invalid_authentication_before_opening_provider(browser_relay, changes):
    client, created = browser_relay
    auth = pair(client)
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(
            "/v1/stream?mode=request", headers={"Origin": ORIGIN}
        ) as socket:
            socket.send_json(handshake(auth, **changes))
            socket.receive_json()
    assert error.value.code == 4403
    assert created == []


@pytest.mark.parametrize("payload", ["not json", "[]", "x" * 2049])
def test_browser_rejects_malformed_or_oversized_handshake(browser_relay, payload):
    client, created = browser_relay
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/v1/stream?mode=request", headers={"Origin": ORIGIN}
        ) as socket:
            socket.send_text(payload)
            socket.receive_json()
    assert created == []


def test_browser_query_token_cannot_replace_authentication_or_consent(browser_relay):
    client, created = browser_relay
    auth = pair(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/v1/stream?mode=request&token=" + auth["Authorization"][7:], headers={"Origin": ORIGIN}
        ) as socket:
            socket.send_json({"type": "authenticate", "consent": "audio-gnani;text-openai"})
            socket.receive_json()
    assert created == []


def test_cors_accepts_only_configured_origins_and_auth_headers(browser_relay):
    client, _ = browser_relay
    headers = {
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    allowed = client.options("/v1/sessions", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    rejected = client.options(
        "/v1/sessions", headers={**headers, "Origin": "https://untrusted.example"}
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


@pytest.mark.parametrize(
    "origin",
    ["*", "https://*.example.com", "http://public.example", "https://app.example.com/", "null"],
)
def test_browser_origins_require_exact_secure_origin(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, web_origins=[origin])
