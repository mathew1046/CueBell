"""Nonbillable latency experiments: wire contracts, correction ordering and teardown."""

import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from app import gnani
from app.config import Settings
from app.engine import Engine
from app.intelligence import OpenAIFallback
from app.main import OutboundCoverageGap, OutboundWriter, create_app
from app.models import EventExtraction, Extraction, MonitoringTask, StopListeningRequest
from app.prompts import EVENT_PROMPT, SETUP_PROMPT, VERBATIM_LOCATION_HINT
from app.validation import grounded_stop_request, validate_match
from tests.conftest import ACCESS_CODE, activate, make_event, make_intent, make_segment, pair
from tests.test_event_monitor import ANNOUNCEMENT, observation, task_intent
from tests.test_stream import CONSENT, FakePrisma, expect_closed, ready, receive_type


@pytest.fixture
def fallback(settings, monkeypatch):
    parse = AsyncMock(
        return_value=SimpleNamespace(status="completed", output_parsed=Extraction(events=[]))
    )
    monkeypatch.setattr(
        "app.intelligence.AsyncOpenAI",
        lambda **kwargs: SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    settings.openai_api_key, settings.openai_model = "dummy-test-key", "gpt-6-luna"
    return OpenAIFallback(settings), parse


async def test_latency_options_preserve_baseline_request_until_configured(fallback, settings):
    model, parse = fallback
    segment = make_segment()
    await model.extract([segment], [])
    baseline = parse.call_args.kwargs
    assert set(baseline) == {"model", "store", "input", "text_format", "max_output_tokens"}
    assert baseline["max_output_tokens"] == 2000
    assert baseline["input"][0]["role"] == "system"
    assert json.loads(baseline["input"][1]["content"])["segments"] == [segment.model_dump()]
    settings.openai_reasoning_effort = "none"
    settings.openai_service_tier = "fast"
    settings.openai_verbosity = "low"
    settings.openai_max_output_tokens = 800
    settings.openai_prompt_cache_mode = "implicit"
    await model.extract([segment], [])
    configured = parse.call_args.kwargs
    assert configured["reasoning"] == {"effort": "none"}
    assert configured["service_tier"] == "fast"
    assert configured["text"] == {"verbosity": "low"}
    assert configured["max_output_tokens"] == 800
    assert configured["prompt_cache_options"] == {"mode": "implicit"}
    assert configured["input"] == baseline["input"]


@pytest.mark.parametrize("method", ["observe", "extract", "intent"])
@pytest.mark.parametrize("cache_mode", [None, "explicit"])
async def test_verbatim_location_hint_only_changes_opted_in_extraction_prompt(
    fallback, settings, method, cache_mode
):
    model, parse = fallback
    settings.openai_prompt_cache_mode = cache_mode
    assert settings.openai_verbatim_location_hint is False

    async def payload():
        if method == "observe":
            await model.observe([make_segment()], [], task_intent().task)
        elif method == "extract":
            await model.extract([make_segment()], [])
        else:
            await model.intent("Alert me when train 14922 arrives.")
        return parse.call_args.kwargs

    def instructions(request):
        content = request["input"][0]["content"]
        return content[0]["text"] if cache_mode == "explicit" else content

    baseline = await payload()
    original = instructions(baseline)
    if method == "observe":
        assert original == EVENT_PROMPT
    elif method == "intent":
        assert original == SETUP_PROMPT
    assert VERBATIM_LOCATION_HINT not in original
    settings.openai_verbatim_location_hint = True
    enabled = await payload()
    expected = original if method == "intent" else original + VERBATIM_LOCATION_HINT
    assert instructions(enabled) == expected
    assert enabled["input"][1:] == baseline["input"][1:]
    assert enabled.keys() == baseline.keys()
    settings.openai_verbatim_location_hint = False
    assert await payload() == baseline


@pytest.mark.parametrize("hint", [False, True])
@pytest.mark.parametrize(
    "location,expected",
    [("കൗണ്ടർ രണ്ട്", "UNCERTAIN"), ("കൗണ്ടർ രണ്ടിലേക്ക്", "MATCH"), (None, "MATCH")],
)
async def test_location_hint_does_not_relax_or_repair_nonverbatim_model_output(
    fallback, settings, hint, location, expected
):
    model, parse = fallback
    settings.openai_verbatim_location_hint = hint
    text = "ടോക്കൺ നാനൂറ്റി നാല്പത്തി രണ്ട് കൗണ്ടർ രണ്ടിലേക്ക് വരൂ."
    task = MonitoringTask(
        subject="token 442",
        condition="is called",
        summary="Alert when token 442 is called.",
        request_evidence="Alert me when token 442 is called.",
        identifiers=[{"value": "442", "evidence_text": "442"}],
    )
    proposed = observation(
        summary=text,
        subject_evidence="ടോക്കൺ നാനൂറ്റി നാല്പത്തി രണ്ട്",
        condition_evidence="വരൂ",
        identifiers=[{"value": "442", "evidence_text": "നാനൂറ്റി നാല്പത്തി രണ്ട്"}],
        location=location,
        evidence_text=text,
    )
    parse.return_value = SimpleNamespace(
        status="completed", output_parsed=EventExtraction(events=[proposed])
    )
    segment = make_segment(text=text)
    result = await model.observe([segment], [], task)
    assert result.events[0].location == location
    engine = Engine(grace=0.2)
    engine.activate(
        make_intent(intent="monitor_event", task=task, token=None, target_evidence=None)
    )
    event = engine.ingest_match(result.events[0], [segment], 100)[0]["observation"]
    assert event["type"] == expected
    if expected == "UNCERTAIN":
        assert event["ambiguity_reason"] == "Location has no source evidence."
        assert engine.flush(101) == []
    else:
        assert engine.flush(101)[0]["alert"]["location"] == location


async def test_explicit_cache_prefix_is_stable_before_dynamic_speech(fallback, settings):
    model, parse = fallback
    settings.openai_prompt_cache_mode = "explicit"
    settings.openai_prompt_cache_ttl = "12h"
    task = task_intent().task
    await model.observe([make_segment(id="first")], [], task)
    first = parse.call_args.kwargs
    await model.observe([make_segment(id="second", text="Changed speech")], [], task)
    second = parse.call_args.kwargs
    assert first["input"][:2] == second["input"][:2]
    assert first["input"][2] != second["input"][2]
    assert first["prompt_cache_options"] == {"mode": "explicit", "ttl": "12h"}
    instructions, confirmed, dynamic = first["input"]
    assert instructions["role"] == "developer"
    assert confirmed["role"] == "user"
    for stable in (instructions, confirmed):
        assert stable["content"][0]["prompt_cache_breakpoint"] == {"mode": "explicit"}
    assert json.loads(confirmed["content"][0]["text"]) == {"confirmed_task": task.model_dump()}
    assert "confirmed_task" not in json.loads(dynamic["content"])
    assert "source_segment_ids" in instructions["content"][0]["text"]


async def test_current_sdk_serializes_flags_and_breakpoints_without_extra_body(
    settings, monkeypatch
):
    captured = []

    async def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_mock",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-6-luna",
                "output": [
                    {
                        "id": "msg_mock",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"events":[],"stop_request":null}',
                                "annotations": [],
                            }
                        ],
                    }
                ],
            },
        )

    async with AsyncOpenAI(
        api_key="dummy-test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as client:
        monkeypatch.setattr("app.intelligence.AsyncOpenAI", lambda **kwargs: client)
        settings.openai_api_key, settings.openai_model = "dummy-test-key", "gpt-6-luna"
        settings.openai_prompt_cache_mode = "explicit"
        settings.openai_prompt_cache_ttl = "30m"
        settings.openai_reasoning_effort = "low"
        settings.openai_service_tier = "priority"
        settings.openai_verbosity = "low"
        result = await OpenAIFallback(settings).observe(
            [make_segment(text=ANNOUNCEMENT)], [], task_intent().task
        )
    assert result == EventExtraction(events=[])
    payload = captured[0]
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["service_tier"] == "priority"
    assert payload["text"]["verbosity"] == "low"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
    assert payload["input"][0]["content"][0]["prompt_cache_breakpoint"] == {"mode": "explicit"}


@pytest.mark.parametrize("kind", ["MATCH", "CALL", "STOP"])
async def test_compact_aliases_expand_before_grounding_without_mutating_evidence(
    fallback, settings, kind
):
    model, parse = fallback
    settings.openai_compact_input = True
    segment = make_segment(id="opaque-connection:provider-id", text=ANNOUNCEMENT)
    recent = [
        {
            "id": "s1",
            "type": "MATCH",
            "source_segment_ids": [segment.id, "s2"],
            "evidence_text": ANNOUNCEMENT,
        }
    ]
    originals = json.dumps(recent)
    raw = None

    async def respond(**kwargs):
        nonlocal raw
        serialized = kwargs["input"][-1]["content"]
        assert '": ' not in serialized
        data = json.loads(serialized)
        assert data["segments"] == [{"id": "s3", "text": ANNOUNCEMENT}]
        assert data["recent_observations"][0]["id"] == "s1"
        assert data["recent_observations"][0]["source_segment_ids"] == ["s3", "s2"]
        if kind == "MATCH":
            raw = EventExtraction(
                events=[observation(source_segment_ids=["s3"], replaces_event_id="s1")]
            )
        elif kind == "CALL":
            raw = Extraction(events=[make_event(source_segment_ids=["s3"], replaces_event_id="s1")])
        else:
            raw = Extraction(
                events=[],
                stop_request=StopListeningRequest(
                    evidence_text=ANNOUNCEMENT, source_segment_ids=["s3"]
                ),
            )
        return SimpleNamespace(status="completed", output_parsed=raw)

    parse.side_effect = respond
    if kind == "MATCH":
        result = await model.observe([segment], recent, task_intent().task)
        assert validate_match(result.events[0], [segment], task_intent().task).type == "MATCH"
    else:
        result = await model.extract([segment], recent)
    if kind == "STOP":
        assert result.stop_request.source_segment_ids == [segment.id]
        assert raw.stop_request.source_segment_ids == ["s3"]
        assert grounded_stop_request(result.stop_request, [segment])
    else:
        assert result.events[0].source_segment_ids == [segment.id]
        assert result.events[0].replaces_event_id == "s1"
        assert raw.events[0].source_segment_ids == ["s3"]
    assert segment.received_at == 100
    assert json.dumps(recent) == originals


@pytest.mark.parametrize(
    ("field", "low", "high"),
    [
        ("gnani_min_silence_ms", 100, 2000),
        ("gnani_vad_threshold", 0, 1),
        ("gnani_min_speech_ms", 50, 2000),
        ("gnani_min_segment_ms", 100, 1000),
        ("gnani_max_speech_s", 5, 120),
    ],
)
def test_vad_settings_validate_provider_ranges(field, low, high):
    for value in (low, high):
        assert getattr(Settings(_env_file=None, **{field: value}), field) == value
    for value in (low - 1, high + 1):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{field: value})


async def test_vad_overrides_send_only_documented_headers(settings, monkeypatch):
    headers = {}

    @asynccontextmanager
    async def connect(url, **kwargs):
        headers.update(kwargs["additional_headers"])
        yield object()

    monkeypatch.setattr(gnani, "connect", connect)
    settings.gnani_api_key = "dummy-test-key"
    settings.gnani_min_silence_ms = 100
    settings.gnani_vad_threshold = 0.0
    settings.gnani_min_speech_ms = 50
    settings.gnani_min_segment_ms = 100
    settings.gnani_max_speech_s = 5
    async with gnani.prisma(settings):
        pass
    assert headers == {
        "x-api-key-id": "dummy-test-key",
        "model": "prisma-v3.0",
        "language_code": "indic-auto",
        "x-sample-rate": "16000",
        "format": "verbatim",
        "x-idle-timeout-sec": "900",
        "x-min-silence-ms": "100",
        "x-vad-threshold": "0.0",
        "x-min-speech-ms": "50",
        "x-min-segment-ms": "100",
        "x-max-speech-s": "5",
    }


class RecordingSocket:
    def __init__(self, blocked=False):
        self.sent = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        if not blocked:
            self.release.set()

    async def send_text(self, payload):
        self.started.set()
        await self.release.wait()
        self.sent.append(json.loads(payload))

    async def close(self, code, reason):
        self.sent.append({"closed": code, "reason": reason})


async def test_writer_snapshots_critical_events_and_drains_in_order():
    socket = RecordingSocket()
    writer = OutboundWriter(socket, 4)
    alert = {"type": "alert", "alert": {"state": "ACTIVE"}}
    writer.send({"type": "status", "state": "READY"})
    writer.send(alert)
    alert["alert"]["state"] = "REVOKED"
    writer.send({"type": "correction", "alert": alert["alert"]})
    writer.send({"type": "monitor.pause"})
    await writer.close()
    assert socket.sent == [
        {"type": "status", "state": "READY"},
        {"type": "alert", "alert": {"state": "ACTIVE"}},
        {"type": "correction", "alert": {"state": "REVOKED"}},
        {"type": "monitor.pause"},
        {"closed": 1000, "reason": ""},
    ]
    assert writer.task.done()


async def test_writer_overflow_closes_with_coverage_gap_and_bounded_cleanup():
    socket = RecordingSocket(blocked=True)
    writer = OutboundWriter(socket, 1)
    writer.send({"type": "alert"})
    await socket.started.wait()
    writer.send({"type": "correction"})
    with pytest.raises(OutboundCoverageGap, match="queue full"):
        writer.send({"type": "monitor.pause"})
    await asyncio.wait_for(writer.close(), timeout=1.8)
    assert socket.sent[-1]["closed"] == 1013
    assert "coverage lost" in socket.sent[-1]["reason"]
    assert writer.task.done()


async def test_cancelled_writer_drain_cleans_up_network_task():
    socket = RecordingSocket(blocked=True)
    writer = OutboundWriter(socket, 2)
    writer.send({"type": "monitor.pause"})
    await socket.started.wait()
    closer = asyncio.create_task(writer.close())
    await asyncio.sleep(0)
    closer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await closer
    assert writer.task.done()
    assert writer.closed
    assert socket.sent[-1]["closed"] == 1013


@pytest.fixture
def latency_relay(settings, intelligence, monkeypatch):
    settings.gnani_api_key = "dummy-test-key"
    settings.optimized_scheduling = True
    settings.outbound_writer = True
    providers = []

    @asynccontextmanager
    async def provider(settings):
        fake = FakePrisma()
        providers.append(fake)
        yield fake

    monkeypatch.setattr("app.main.prisma", provider)
    with TestClient(create_app(settings, intelligence)) as client:
        yield client, providers


def hold_health_poll(monkeypatch):
    # Disable only the old 200ms health poll; deadlines/idle transitions must suffice.
    async def sleep(delay):
        if delay == 0.2:
            await asyncio.Event().wait()
        else:
            await asyncio.sleep(delay)

    proxy = SimpleNamespace(**vars(asyncio))
    proxy.sleep = sleep
    monkeypatch.setattr("app.main.asyncio", proxy)


@pytest.mark.parametrize("already_due", [False, True])
@pytest.mark.parametrize("writer_enabled", [False, True])
def test_idle_and_deadline_flush_do_not_depend_on_health_poll(
    latency_relay, intelligence, settings, monkeypatch, already_due, writer_enabled
):
    client, _ = latency_relay
    settings.outbound_writer = writer_enabled
    hold_health_poll(monkeypatch)
    original = intelligence.extract
    clock = {"offset": 0}
    monkeypatch.setattr(
        "app.main.time",
        SimpleNamespace(time=lambda: time.time() + clock["offset"], monotonic=time.monotonic),
    )

    async def extract(window, recent):
        if already_due:
            clock["offset"] = 1
        return await original(window, recent)

    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        assert receive_type(socket, "observation")["observation"]["type"] == "CALL"
        assert receive_type(socket, "alert")["alert"]["token"] == "P042"
        socket.send_json({"type": "stop"})
        expect_closed(socket)


def test_busy_correction_suppresses_already_pending_due_alert(latency_relay, intelligence):
    client, providers = latency_relay
    original = intelligence.extract
    correcting = threading.Event()
    release = asyncio.Event()

    async def extract(window, recent):
        if len(window) == 1:
            return await original(window, recent)
        correcting.set()
        await release.wait()
        return Extraction(
            events=[
                make_event(
                    type="UNCERTAIN",
                    evidence_text=window[-1].text,
                    source_segment_ids=[window[-1].id],
                    ambiguity_reason="Unclear correction",
                )
            ]
        )

    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        receive_type(socket, "observation")
        socket.portal.call(
            providers[0].messages.put_nowait,
            json.dumps(
                {
                    "type": "transcript",
                    "text": "Correction unclear",
                    "segment_id": "p2",
                    "is_final": True,
                }
            ),
        )
        assert correcting.wait(2)
        time.sleep(0.3)
        assert client.get("/v1/state", headers=auth).json()["alerts"] == []
        socket.portal.call(release.set)
        for _ in range(10):
            event = socket.receive_json()
            assert event["type"] != "alert"
            if event["type"] == "observation" and event["observation"]["type"] == "UNCERTAIN":
                break
        else:
            pytest.fail("No correction")
        socket.send_json({"type": "stop"})
        expect_closed(socket)
    assert client.get("/v1/state", headers=auth).json()["alerts"] == []


def test_overdue_positive_waits_for_queued_correction(latency_relay, intelligence, monkeypatch):
    client, providers = latency_relay
    original = intelligence.extract
    clock = {"offset": 0}
    monkeypatch.setattr(
        "app.main.time",
        SimpleNamespace(time=lambda: time.time() + clock["offset"], monotonic=time.monotonic),
    )

    async def extract(window, recent):
        if len(window) == 1:
            # The first result is already past grace while the correction is still queued.
            clock["offset"] = 1
            return await original(window, recent)
        return Extraction(
            events=[
                make_event(
                    type="UNCERTAIN",
                    evidence_text=window[-1].text,
                    source_segment_ids=[window[-1].id],
                    ambiguity_reason="Unclear correction",
                )
            ]
        )

    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        providers[0].transcripts.append(
            {
                "type": "transcript",
                "text": "Correction unclear",
                "segment_id": "p2",
                "is_final": True,
            }
        )
        socket.send_bytes(b"\0" * 1024)
        for _ in range(10):
            event = socket.receive_json()
            assert event["type"] != "alert"
            if event["type"] == "observation" and event["observation"]["type"] == "UNCERTAIN":
                break
        else:
            pytest.fail("No correction")
        socket.send_json({"type": "stop"})
        expect_closed(socket)
    assert client.get("/v1/state", headers=auth).json()["alerts"] == []


def test_heartbeat_continues_during_busy_interpretation(latency_relay, intelligence):
    client, _ = latency_relay
    busy, cancelled, stop_audio = threading.Event(), threading.Event(), threading.Event()

    async def extract(window, recent):
        busy.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        assert busy.wait(2)

        def feed_audio():
            while not stop_audio.wait(0.1):
                socket.send_bytes(b"\0" * 1024)

        feeder = threading.Thread(target=feed_audio)
        feeder.start()
        try:
            heartbeat = receive_type(socket, "heartbeat")
            assert heartbeat["audio_age_ms"] < 1000
            assert not cancelled.is_set()
        finally:
            stop_audio.set()
            feeder.join(timeout=2)
        socket.send_json({"type": "stop"})
        expect_closed(socket)
    assert cancelled.wait(2)


@pytest.mark.parametrize("scheduler_enabled", [False, True])
def test_slow_caption_does_not_block_interpretation_or_control_lock(
    latency_relay, intelligence, settings, monkeypatch, scheduler_enabled
):
    client, _ = latency_relay
    settings.optimized_scheduling = scheduler_enabled
    caption_blocked, interpreted = threading.Event(), threading.Event()
    release = asyncio.Event()
    original_send = WebSocket.send_text
    original_extract = intelligence.extract

    async def send_text(socket, text):
        if json.loads(text).get("type") == "transcript":
            caption_blocked.set()
            await release.wait()
        await original_send(socket, text)

    async def extract(window, recent):
        interpreted.set()
        return await original_extract(window, recent)

    monkeypatch.setattr(WebSocket, "send_text", send_text)
    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        assert caption_blocked.wait(2)
        assert interpreted.wait(0.5)
        # State reflects the reducer while its outbound caption is still blocked.
        state = client.get("/v1/state", headers=auth).json()
        assert any(event["type"] == "observation" for event in state["history"])
        control = socket.portal.start_task_soon(
            # An HTTP request on the same ASGI loop exercises the shared session lock.
            pause_over_http,
            client.app,
            auth,
        )
        for _ in range(20):
            state = client.get("/v1/state", headers=auth).json()
            if state["rule"]["status"] == "PAUSED":
                break
            time.sleep(0.01)
        assert state["rule"]["status"] == "PAUSED"
        socket.portal.call(release.set)
        assert control.result(timeout=2).status_code == 200
        event = receive_type(socket, "monitor.pause")
        assert event["rule"]["status"] == "PAUSED"
        expect_closed(socket)


async def pause_over_http(app, auth):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.post("/v1/control", headers=auth, json={"action": "pause"})


@pytest.mark.parametrize(
    "error,state", [(RuntimeError("model"), "DISCONNECTED"), (Exception("model"), "DEGRADED")]
)
def test_model_error_status_is_drained_before_close(latency_relay, intelligence, error, state):
    client, _ = latency_relay

    async def extract(window, recent):
        raise error

    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        socket.send_bytes(b"\0" * 1024)
        for _ in range(10):
            event = socket.receive_json()
            if event.get("state") == state:
                break
        else:
            pytest.fail("Missing model-error status")
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
        assert closed.value.code == 1000
    assert not client.get("/v1/state", headers=auth).json()["stream_connected"]


@pytest.mark.parametrize("writer_enabled", [False, True])
def test_watchdog_clears_pending_alert_before_slow_provider_shutdown(
    settings, intelligence, monkeypatch, writer_enabled
):
    settings.gnani_api_key = "dummy-test-key"
    settings.optimized_scheduling = True
    settings.outbound_writer = writer_enabled
    settings.correction_grace_seconds = 4.5
    failures, exited = [], []

    @asynccontextmanager
    async def provider(settings):
        try:
            yield FakePrisma()
        except BaseException as error:
            failures.append((time.time(), error))
            raise
        finally:
            # The 4s audio watchdog fires before 4.5s grace; provider close crosses grace.
            await asyncio.sleep(1)
            exited.append(time.time())

    monkeypatch.setattr("app.main.prisma", provider)
    with TestClient(create_app(settings, intelligence)) as client:
        auth = pair(client)
        activate(client, auth)
        messages = []
        with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
            ready(socket)
            socket.send_bytes(b"\0" * 1024)
            transcript = receive_type(socket, "transcript")
            assert receive_type(socket, "observation")["observation"]["type"] == "CALL"
            with pytest.raises(WebSocketDisconnect):
                while True:
                    messages.append(socket.receive_json())
        assert len(failures) == 1
        failed_at, error = failures[0]
        assert isinstance(error, TimeoutError)
        assert str(error) == "Audio stopped arriving. Calls may have been missed."
        due = transcript["segment"]["received_at"] + 4.5
        assert failed_at < due < exited[0]
        assert not any(message["type"] == "alert" for message in messages)
        assert messages[-1]["state"] == "DISCONNECTED"
        state = client.get("/v1/state", headers=auth).json()
        assert state["alerts"] == []
        assert not state["stream_connected"]


@pytest.mark.parametrize("optimized", [False, True])
@pytest.mark.parametrize("ending", ["stop", "gap", "provider_error", "disconnect"])
@pytest.mark.parametrize("late_control", [False, True])
def test_partial_interpretation_is_invalidated_and_stopped_before_provider_exit(
    settings, intelligence, monkeypatch, optimized, ending, late_control
):
    settings.gnani_api_key = "dummy-test-key"
    settings.optimized_scheduling = optimized
    settings.outbound_writer = optimized
    started, cancelled, exited = threading.Event(), threading.Event(), threading.Event()
    release = asyncio.Event()
    providers, cancelled_at_exit, calls = [], [], []

    async def extract(window, recent):
        calls.append(window)
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            # A provider may finish a response concurrently with cancellation.
        newest = window[-1]
        if late_control:
            return Extraction(
                events=[],
                stop_request=StopListeningRequest(
                    evidence_text=newest.text, source_segment_ids=[newest.id]
                ),
            )
        return Extraction(events=[make_event(source_segment_ids=[newest.id])])

    @asynccontextmanager
    async def provider(settings):
        fake = FakePrisma()
        fake.transcripts.append({**fake.transcripts[0], "segment_id": "queued"})
        providers.append(fake)
        try:
            yield fake
        finally:
            cancelled_at_exit.append(cancelled.is_set())
            release.set()
            await asyncio.sleep(0.05)
            exited.set()

    intelligence.extract = extract
    monkeypatch.setattr("app.main.prisma", provider)
    with TestClient(create_app(settings, intelligence)) as client:
        auth = pair(client)
        activate(client, auth)
        with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
            ready(socket)
            socket.send_bytes(b"\0" * 1024)
            assert started.wait(2)
            before = client.get("/v1/state", headers=auth).json()
            if ending == "provider_error":
                socket.portal.call(providers[0].messages.put_nowait, json.dumps({"type": "error"}))
            elif ending == "disconnect":
                socket.close()
            else:
                socket.send_json({"type": ending})
            if ending == "disconnect":
                assert exited.wait(2)
            else:
                expect_closed(socket)
        assert cancelled_at_exit == [True]
        assert len(calls) == 1  # No queued segment can start a fresh post-gap interpretation.
        after = client.get("/v1/state", headers=auth).json()
        for field in ("rule", "history", "alerts"):
            assert after[field] == before[field]
        assert not after["stream_connected"]


@pytest.mark.parametrize("action,status", [("pause", "PAUSED"), ("stop", "STOPPED")])
def test_http_control_during_writer_drain_cannot_restart_queued_interpretation(
    latency_relay, intelligence, monkeypatch, action, status
):
    client, providers = latency_relay
    caption_blocked, started, returned = threading.Event(), threading.Event(), threading.Event()
    release_writer, release_model = asyncio.Event(), asyncio.Event()
    original_send = WebSocket.send_text
    calls = []

    async def send_text(socket, text):
        if json.loads(text).get("type") == "transcript":
            caption_blocked.set()
            await release_writer.wait()
        await original_send(socket, text)

    async def extract(window, recent):
        calls.append(window)
        started.set()
        await release_model.wait()
        returned.set()
        return Extraction(
            events=[],
            stop_request=StopListeningRequest(
                evidence_text=window[-1].text, source_segment_ids=[window[-1].id]
            ),
        )

    async def control_over_http():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app), base_url="http://testserver"
        ) as http:
            return await http.post("/v1/control", headers=auth, json={"action": action})

    monkeypatch.setattr(WebSocket, "send_text", send_text)
    intelligence.extract = extract
    auth = pair(client)
    activate(client, auth)
    with client.websocket_connect("/v1/stream", headers={**auth, **CONSENT}) as socket:
        ready(socket)
        providers[0].transcripts.append({**providers[0].transcripts[0], "segment_id": "queued"})
        socket.send_bytes(b"\0" * 1024)
        assert started.wait(2) and caption_blocked.wait(2)
        control = socket.portal.start_task_soon(control_over_http)
        try:
            for _ in range(20):
                state = client.get("/v1/state", headers=auth).json()
                if state["rule"]["status"] == status:
                    break
                time.sleep(0.01)
            assert state["rule"]["status"] == status
            socket.portal.call(release_model.set)
            assert returned.wait(0.5)
        finally:
            socket.portal.call(release_writer.set)
        assert control.result(timeout=2).status_code == 200
        event = receive_type(socket, "monitor." + action)
        assert event["rule"]["status"] == status
        expect_closed(socket)
    assert len(calls) == 1
    state = client.get("/v1/state", headers=auth).json()
    assert state["rule"]["status"] == status
    assert not state["alerts"]
    assert not any(event["type"] == "observation" for event in state["history"])


async def test_handler_cancellation_stops_model_before_provider_exit_and_drains_writer(
    settings, intelligence, monkeypatch
):
    settings.gnani_api_key = "dummy-test-key"
    settings.optimized_scheduling = True
    settings.outbound_writer = True
    started, cancelled, exiting = asyncio.Event(), asyncio.Event(), asyncio.Event()
    release_exit = asyncio.Event()
    incoming, outgoing, writers = asyncio.Queue(), [], []
    ready_event = asyncio.Event()

    async def extract(window, recent):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
        return Extraction(events=[make_event(source_segment_ids=[window[-1].id])])

    @asynccontextmanager
    async def provider(settings):
        try:
            yield FakePrisma()
        finally:
            exiting.set()
            await release_exit.wait()

    def writer(socket, capacity):
        instance = OutboundWriter(socket, capacity)
        writers.append(instance)
        return instance

    async def send(message):
        outgoing.append(message)
        if message["type"] == "websocket.send":
            if json.loads(message["text"]).get("state") == "READY":
                ready_event.set()

    intelligence.extract = extract
    monkeypatch.setattr("app.main.prisma", provider)
    monkeypatch.setattr("app.main.OutboundWriter", writer)
    app = create_app(settings, intelligence)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await client.post("/v1/sessions", json={"access_code": ACCESS_CODE})
        auth = {"Authorization": "Bearer " + session.json()["token"]}
        proposal = await client.post(
            "/v1/intent",
            headers=auth,
            json={"text": "Vibrate for P042", "consent_to_text_processing": True},
        )
        confirmed = await client.post(
            "/v1/confirm", headers=auth, json={"proposal_id": proposal.json()["proposal_id"]}
        )
        assert confirmed.status_code == 200
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "scheme": "ws",
            "path": "/v1/stream",
            "raw_path": b"/v1/stream",
            "root_path": "",
            "query_string": b"mode=monitor",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "subprotocols": [],
            "headers": [
                (key.lower().encode(), value.encode()) for key, value in {**auth, **CONSENT}.items()
            ],
        }
        incoming.put_nowait({"type": "websocket.connect"})
        handler = asyncio.create_task(app(scope, incoming.get, send))
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=2)
            incoming.put_nowait({"type": "websocket.receive", "bytes": b"\0" * 1024})
            await asyncio.wait_for(started.wait(), timeout=2)
            before = (await client.get("/v1/state", headers=auth)).json()
            handler.cancel()
            await asyncio.wait_for(exiting.wait(), timeout=2)
            assert cancelled.is_set()
        finally:
            release_exit.set()
            if not handler.cancelling():
                handler.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(handler, timeout=2)
        assert writers[0].closed and writers[0].task.done()
        assert outgoing[-1]["type"] == "websocket.close"
        state = (await client.get("/v1/state", headers=auth)).json()
        for field in ("rule", "history", "alerts"):
            assert state[field] == before[field]
        assert not state["stream_connected"]
