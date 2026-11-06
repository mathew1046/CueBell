import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from app.engine import Engine
from app.main import create_app
from app.models import Extraction
from tests.conftest import ACCESS_CODE, activate, make_event, pair

CONSENT = {"x-processing-consent": "audio-gnani;text-openai"}


class FakePrisma:
    def __init__(self, config=None, transcripts=None):
        self.messages = asyncio.Queue()
        self.messages.put_nowait(
            json.dumps(
                {
                    "type": "connected",
                    "config": config
                    if config is not None
                    else {
                        "sample_rate": 16000,
                        "chunk_size": 512,
                    },
                }
            )
        )
        self.audio = []
        self.transcripts = (
            transcripts
            if transcripts is not None
            else [
                {
                    "type": "transcript",
                    "text": "P042 to counter 2",
                    "segment_id": "p1",
                    "is_final": True,
                }
            ]
        )

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.messages.get()

    async def send(self, data):
        self.audio.append(data)
        if len(self.audio) == 1:
            for transcript in self.transcripts:
                self.messages.put_nowait(json.dumps(transcript))


@pytest.fixture
def relay(settings, intelligence, monkeypatch):
    settings.gnani_api_key = "dummy-test-key"
    settings.request_pause_seconds = 1
    created = []
    options = {}

    @asynccontextmanager
    async def provider(settings):
        fake = FakePrisma(**options)
        created.append(fake)
        yield fake

    monkeypatch.setattr("app.main.prisma", provider)
    with TestClient(create_app(settings, intelligence)) as client:
        yield client, created, options


def ready(socket):
    assert socket.receive_json()["state"] == "STARTING"
    assert socket.receive_json()["state"] == "READY"


def receive_type(socket, kind):
    # Bound the number of status/transcript messages while waiting for the desired event.
    for _ in range(20):
        message = socket.receive_json()
        if message.get("type") == kind:
            return message
    pytest.fail(f"No {kind} event")


def expect_closed(socket):
    for _ in range(20):
        try:
            event = socket.receive_json()
        except WebSocketDisconnect:
            return
        assert event.get("type") != "alert"
    pytest.fail("Stream did not close")


@pytest.mark.parametrize(
    ("mode", "headers"),
    [
        ("request", {}),
        ("request", CONSENT),
        ("invalid", CONSENT),
        ("request", {**CONSENT, "Origin": "https://browser.example"}),
        ("request", {"x-processing-consent": "audio-gnani"}),
        ("monitor", CONSENT),
    ],
)
def test_stream_rejects_missing_auth_consent_origin_mode_or_confirmation(relay, mode, headers):
    client, created, _ = relay
    auth = pair(client)
    # The first two cases deliberately omit auth or consent.
    actual_headers = headers if headers == CONSENT and mode == "request" else {**auth, **headers}
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/v1/stream?mode={mode}", headers=actual_headers):
            pass
    assert error.value.code == 4403
    assert not created


def test_request_stream_forwards_pcm_and_returns_one_final_transcript(relay):
    client, created, options = relay
    options["transcripts"] = [
        {"type": "transcript", "text": "partial", "segment_id": "p0", "is_final": False},
        {"type": "transcript", "text": "പി പൂജ്യം നാല് രണ്ട്", "segment_id": "p1", "is_final": True},
    ]
    auth = pair(client)
    with client.websocket_connect("/v1/stream?mode=request", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        transcript = receive_type(socket, "transcript")
        assert transcript["mode"] == "request"
        assert transcript["segment"]["text"] == "പി പൂജ്യം നാല് രണ്ട്"
        assert transcript["segment"]["id"].endswith(":request")
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert created[0].audio == [b"\0" * 1024]
    state = client.get("/v1/state", headers=auth).json()
    assert state["rule"] is None
    assert not state["stream_connected"]


def test_request_waits_through_sentence_pause_and_unfinished_partial(relay):
    client, created, options = relay
    options["transcripts"] = [
        {"type": "transcript", "text": "Token ten.", "segment_id": "p1", "is_final": True},
    ]
    auth = pair(client)
    with client.websocket_connect("/v1/stream?mode=request", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        # Cross a short pause, then signal unfinished speech before the quiet deadline.
        time.sleep(0.5)
        socket.portal.call(
            created[0].messages.put_nowait,
            json.dumps(
                {
                    "type": "transcript",
                    "text": "Vibrate",
                    "segment_id": "p2",
                    "is_final": False,
                }
            ),
        )
        time.sleep(1.2)
        # Ping proves the connection did not close on the first final or on an interim pause.
        socket.send_json({"type": "ping"})
        receive_type(socket, "pong")
        final = {
            "type": "transcript",
            "text": "Vibrate and sound an alarm.",
            "segment_id": "p2",
            "is_final": True,
        }
        finished = time.monotonic()
        socket.portal.call(created[0].messages.put_nowait, json.dumps(final))
        socket.portal.call(created[0].messages.put_nowait, json.dumps(final))
        transcript = receive_type(socket, "transcript")
        assert time.monotonic() - finished >= 0.9
        assert transcript["segment"]["text"] == "Token ten. Vibrate and sound an alarm."
        expect_closed(socket)
    assert client.get("/v1/state", headers=auth).json()["rule"] is None


def test_monitor_stream_dedups_provider_segments_and_alerts(relay, intelligence):
    client, created, options = relay
    final = {
        "type": "transcript",
        "text": "P042 to counter 2",
        "segment_id": "p1",
        "is_final": True,
    }
    options["transcripts"] = [final, final]
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        assert (
            client.post(
                "/v1/intent",
                headers=auth,
                json={
                    "text": "Vibrate for P042",
                    "consent_to_text_processing": True,
                },
            ).status_code
            == 409
        )
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/v1/stream?mode=request", headers={**auth, **CONSENT}):
                pass
        assert error.value.code == 4403
        socket.send_bytes(b"\0" * 1024)
        alert = receive_type(socket, "alert")
        assert alert["alert"]["token"] == "P042"
        assert len(intelligence.extract_calls) == 1
        assert intelligence.extract_calls[0][1] == []
        socket.send_json({"type": "stop"})
        expect_closed(socket)
    assert len(created[0].audio) == 1
    state = client.get("/v1/state", headers=auth).json()
    assert len(state["alerts"]) == 1
    assert not state["stream_connected"]


@pytest.mark.parametrize(
    "config",
    [
        {"sample_rate": 8000, "chunk_size": 512},
        {"sample_rate": 16000, "chunk_size": 1024},
        {"sample_rate": 16000},
    ],
)
def test_provider_negotiation_fails_closed(relay, config):
    client, _, options = relay
    options["config"] = config
    auth = pair(client)
    with client.websocket_connect("/v1/stream?mode=request", headers={**auth, **CONSENT}) as socket:
        assert socket.receive_json()["state"] == "STARTING"
        assert socket.receive_json()["state"] == "DISCONNECTED"
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


@pytest.mark.parametrize("frame", [b"x", b"x" * 2048, "not-json", "x" * 1025, "[]"])
def test_malformed_native_frames_close_stream(relay, frame):
    client, _, _ = relay
    auth = pair(client)
    with client.websocket_connect("/v1/stream?mode=request", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        if isinstance(frame, bytes):
            socket.send_bytes(frame)
        else:
            socket.send_text(frame)
        assert socket.receive_json()["state"] == "DISCONNECTED"
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_gap_control_marks_coverage_loss_and_disconnects(relay):
    client, _, _ = relay
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
        socket.send_json({"type": "gap"})
        assert socket.receive_json()["state"] == "DEGRADED"
        assert socket.receive_json()["state"] == "DISCONNECTED"
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert not client.get("/v1/state", headers=auth).json()["stream_connected"]


def test_http_pause_closes_socket_and_clears_pending(relay):
    client, _, _ = relay
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        assert client.post("/v1/control", headers=auth, json={"action": "pause"}).status_code == 200
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert client.get("/v1/state", headers=auth).json()["rule"]["status"] == "PAUSED"


def test_stream_configuration_and_tls_gates(settings, intelligence):
    with TestClient(create_app(settings, intelligence)) as client:
        auth = pair(client)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/stream?mode=request", headers={**auth, **CONSENT}):
                pass
    settings.allow_insecure_local = False
    settings.gnani_api_key = "dummy-test-key"
    with TestClient(create_app(settings, intelligence), base_url="https://testserver") as client:
        auth = pair(client)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "ws://testserver/v1/stream?mode=request", headers={**auth, **CONSENT}
            ):
                pass


@pytest.mark.parametrize(
    ("upstream_status", "close_code"), [(401, 4403), (403, 4403), (429, 1000), (503, 1000)]
)
def test_provider_upgrade_failure_close_code_and_session_cleanup(
    relay, monkeypatch, upstream_status, close_code
):
    client, _, _ = relay
    auth = pair(client)

    @asynccontextmanager
    async def rejected_provider(settings):
        raise InvalidStatus(
            Response(
                upstream_status,
                "private-provider-reason",
                Headers({"X-Private": "private-provider-header"}),
                body=b"private-provider-body",
            )
        )
        yield  # pragma: no cover

    with monkeypatch.context() as patch:
        patch.setattr("app.main.prisma", rejected_provider)
        with client.websocket_connect(
            "/v1/stream?mode=request", headers={**auth, **CONSENT}
        ) as socket:
            assert socket.receive_json()["state"] == "STARTING"
            status = socket.receive_json()
            assert status["state"] == "DEGRADED"
            assert "private-provider" not in json.dumps(status)
            if close_code == 4403:
                assert "Gnani" in status["message"]
                assert "authentication" in status["message"].lower()
            with pytest.raises(WebSocketDisconnect) as error:
                socket.receive_json()
            assert error.value.code == close_code

    assert not client.get("/v1/state", headers=auth).json()["stream_connected"]
    # Authentication failures must release the session, not leave it permanently busy.
    with client.websocket_connect("/v1/stream?mode=request", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_json({"type": "stop"})
        expect_closed(socket)


def test_gap_cancels_inflight_extraction_and_reconnect_has_fresh_context(relay, intelligence):
    client, _, _ = relay
    auth = pair(client)
    activate(client, auth)
    started, cancelled = threading.Event(), threading.Event()

    async def blocked_extract(window, recent):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    original = intelligence.extract
    intelligence.extract = blocked_extract
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        receive_type(socket, "transcript")
        assert started.wait(2)
        socket.send_json({"type": "gap"})
        for _ in range(10):
            message = socket.receive_json()
            assert message.get("type") != "alert"
            if message.get("state") == "DISCONNECTED":
                break
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert cancelled.wait(2)
    state = client.get("/v1/state", headers=auth).json()
    assert not state["stream_connected"]
    assert not state["alerts"]
    intelligence.extract = original
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        assert receive_type(socket, "alert")["alert"]["token"] == "P042"
        assert intelligence.extract_calls[-1][1] == []
        assert len(intelligence.extract_calls[-1][0]) == 1
        socket.send_json({"type": "stop"})
        expect_closed(socket)


def test_uncertain_correction_queued_behind_call_never_releases_pending_alert(relay, intelligence):
    client, _, options = relay
    options["transcripts"] = [
        {"type": "transcript", "text": "P042 to counter 2", "segment_id": "p1", "is_final": True},
        {"type": "transcript", "text": "Correction unclear", "segment_id": "p2", "is_final": True},
    ]

    async def extract(window, recent):
        newest = window[-1]
        if len(window) == 1:
            event = make_event(source_segment_ids=[newest.id])
        else:
            event = make_event(
                type="UNCERTAIN",
                token_raw=None,
                token_normalized=None,
                counter=None,
                evidence_text=newest.text,
                source_segment_ids=[newest.id],
                ambiguity_reason="Unclear correction",
            )
        return Extraction(events=[event])

    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        for _ in range(10):
            event = socket.receive_json()
            assert event.get("type") != "alert"
            if event.get("type") == "observation" and event["observation"]["type"] == "UNCERTAIN":
                break
        else:
            pytest.fail("No uncertain correction observation")
        socket.send_json({"type": "stop"})
        with pytest.raises(WebSocketDisconnect):
            while True:
                assert socket.receive_json().get("type") != "alert"
    assert client.get("/v1/state", headers=auth).json()["alerts"] == []


async def test_failed_accept_does_not_leave_session_busy(settings, intelligence):
    settings.gnani_api_key = "dummy-test-key"
    app = create_app(settings, intelligence)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = (await client.post("/v1/sessions", json={"access_code": ACCESS_CODE})).json()[
            "token"
        ]
        auth = {"Authorization": "Bearer " + token}
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "scheme": "ws",
            "path": "/v1/stream",
            "raw_path": b"/v1/stream",
            "root_path": "",
            "query_string": b"mode=request",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "subprotocols": [],
            "headers": [
                (key.lower().encode(), value.encode()) for key, value in {**auth, **CONSENT}.items()
            ],
        }

        async def receive():
            return {"type": "websocket.connect"}

        async def send(message):
            raise OSError("Peer disconnected during accept")

        with pytest.raises(OSError, match="during accept"):
            await app(scope, receive, send)
        response = await client.get("/v1/state", headers=auth)
        assert not response.json()["stream_connected"]


def test_oversized_extraction_cannot_discard_a_correction_and_release_call(relay, intelligence):
    client, _, _ = relay

    async def oversized_extract(window, recent):
        source = [window[-1].id]
        return Extraction(
            events=[make_event(source_segment_ids=source)]
            + [make_event(type="OTHER", source_segment_ids=source) for _ in range(15)]
            + [
                make_event(
                    type="UNCERTAIN",
                    source_segment_ids=source,
                    ambiguity_reason="Unclear correction",
                )
            ]
        )

    intelligence.extract = oversized_extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        expect_closed(socket)
    state = client.get("/v1/state", headers=auth).json()
    assert state["alerts"] == []
    assert not state["stream_connected"]


def test_slow_extraction_does_not_relabel_old_observations_as_new(relay, intelligence, monkeypatch):
    client, _, _ = relay
    auth = pair(client)
    activate(client, auth)
    now = time.time()
    clock = {"now": now}
    monkeypatch.setattr("app.main.time.time", lambda: clock["now"])
    original = intelligence.extract
    original_flush = Engine.flush
    flushed = threading.Event()

    def flush(engine, at):
        events = original_flush(engine, at)
        if at >= now + 16:
            flushed.set()
        return events

    monkeypatch.setattr(Engine, "flush", flush)

    async def slow_extract(window, recent):
        # Simulate model latency without audio, sleeping, or a real provider request.
        clock["now"] += 14
        return await original(window, recent)

    intelligence.extract = slow_extract
    with client.websocket_connect("/v1/stream?mode=monitor", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        transcript = receive_type(socket, "transcript")
        observation = receive_type(socket, "observation")["observation"]
        assert observation["at"] == transcript["segment"]["received_at"]
        clock["now"] += 2
        # Flush after model completion plus grace: the announcement is now older than 15s.
        assert flushed.wait(2)
        socket.send_json({"type": "ping"})
        receive_type(socket, "pong")
        assert client.get("/v1/state", headers=auth).json()["alerts"] == []
        socket.send_json({"type": "stop"})
        expect_closed(socket)
