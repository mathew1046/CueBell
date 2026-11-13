"""Offline benchmark-contract tests: no provider clients or provider credentials."""

import asyncio
import hashlib
import json
import math
import wave
from copy import deepcopy

import httpx
import pytest
from websockets.asyncio.server import serve

from benchmarks.run_pipeline import (
    FRAME_SECONDS,
    MIN_FRAME_SPACING_SECONDS,
    Options,
    SendProgress,
    assemble_audio,
    classify_result,
    load_manifest,
    pace_audio,
    quantile,
    run_case,
    select_cases,
    summarize,
)


def make_fixture(tmp_path, name="cue", samples=1024, speech_end_s=0.06):
    path = tmp_path / f"{name}.wav"
    pcm = b"\x23\x01" * samples
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(pcm)
    return {
        "id": name,
        "language": "hi",
        "text": "टोकन 442 काउंटर 3 पर आएं।",
        "audio_path": str(path),
        "speech_end_s": speech_end_s,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def make_case(**expected):
    return {
        "id": "case-hi",
        "language": "hi",
        "request": "Alert me when pharmacy token 442 is called.",
        "sequence": [{"fixture_id": "cue", "silence_after_s": 0.0}],
        "expected": {
            "alert": True,
            "token": "442",
            "location": "3",
            "voice_stop": False,
            "correction": False,
            **expected,
        },
    }


def envelope(kind, at=10.0, **fields):
    return {"t": at, "event": {"type": kind, **fields}}


def final_transcript(text="टोकन 442 काउंटर 3 पर आएं।", **fields):
    return envelope("transcript", mode="monitor", segment={"id": "s1", "text": text}, **fields)


def base_record(**expected):
    return {
        "mode": "monitor",
        "expected": make_case(**expected)["expected"],
        "events": [final_transcript()],
        "sender": {"full_window_sent": True},
        "source_speech_sent": True,
        "confirmation": {"type": "monitor.created"},
    }


def observation(identifier="442", location="counter 3", **fields):
    return {
        "id": "o1",
        "type": "MATCH",
        "state": "confirmed",
        "identifiers": [{"value": identifier, "evidence_text": identifier}],
        "location": location,
        "source_segment_ids": ["s1"],
        **fields,
    }


def alert(**fields):
    return {
        "id": "a1",
        "observation_id": "o1",
        "state": "unacknowledged",
        "token": None,
        "counter": None,
        "summary": "442 is called to counter 3",
        **fields,
    }


def test_audio_assembly_retains_files_silence_and_short_frame(tmp_path):
    first = make_fixture(tmp_path, samples=1001, speech_end_s=0.04)
    second = make_fixture(tmp_path, name="correction", samples=701, speech_end_s=0.03)
    case = make_case(correction=True, location_aliases=["काउंटर तीन"])
    case["mode"] = "monitor"
    case["sequence"] = [
        {"fixture_id": "cue", "silence_after_s": 0.017},
        {"fixture_id": "correction", "silence_after_s": 0.019},
    ]
    manifest = {"version": 1, "sample_rate": 16000, "fixtures": [first, second], "cases": [case]}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    assert load_manifest(manifest_path) == manifest
    plan = assemble_audio(case, {"cue": first, "correction": second}, 0.003, 0.021)
    expected = (
        b"\0\0" * 48
        + b"\x23\x01" * 1001
        + b"\0\0" * 272
        + b"\x23\x01" * 701
        + b"\0\0" * 304
        + b"\0\0" * 336
    )
    assert plan.pcm == expected + b"\0" * ((-len(expected)) % 1024)
    assert plan.sequence_end_sample == 2326
    assert plan.spans[-1]["speech_end_sample"] == 1801
    assert plan.spans[-1]["speech_end_sample"] != plan.sequence_end_sample
    assert plan.describe()["padding_samples"] == 410
    corrupted = {**first, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        assemble_audio(make_case(), {"cue": corrupted})
    with pytest.raises(ValueError, match="speech_end_s exceeds WAV duration"):
        assemble_audio(make_case(), {"cue": {**first, "speech_end_s": 20.0}})


@pytest.mark.asyncio
@pytest.mark.parametrize("stall_at,stall_seconds", [("send", 0.1), ("sleep", 0.1), ("sleep", 0.03)])
async def test_pacing_does_not_burst_or_lose_frames_after_a_stall(
    tmp_path,
    stall_at,
    stall_seconds,
):
    fixture = make_fixture(tmp_path, samples=1001, speech_end_s=0.04)
    plan = assemble_audio(make_case(), {"cue": fixture}, 0.032, 0.128)
    now = 50.0
    sent = []
    deadlines = []

    async def sleep(delay):
        nonlocal now
        now += delay
        if stall_at == "sleep" and len(deadlines) == 1:
            now += stall_seconds
        deadlines.append(now)

    async def send(frame):
        nonlocal now
        sent.append((now, frame))
        if stall_at == "send" and len(sent) == 2:
            now += stall_seconds

    progress = SendProgress()
    await pace_audio(send, plan, progress, lambda: False, clock=lambda: now, sleep=sleep)
    assert b"".join(frame for _, frame in sent) == plan.pcm
    assert all(len(frame) == 1024 for _, frame in sent)
    assert all(b[0] - a[0] >= MIN_FRAME_SPACING_SECONDS - 1e-10 for a, b in zip(sent, sent[1:]))
    assert deadlines[0] == pytest.approx(50.032)
    assert progress.complete
    assert progress.t_finished - sent[-1][0] == pytest.approx(FRAME_SECONDS)
    metrics = progress.describe()
    if stall_seconds > FRAME_SECONDS:
        assert metrics["rebase_count"] == 1
        assert metrics["schedule_shift_ms"] == pytest.approx(68 if stall_at == "send" else 100)
        assert metrics["lateness_ms"]["max"] >= 68.0 - 1e-8
        assert all(b[0] - a[0] >= FRAME_SECONDS - 1e-10 for a, b in zip(sent, sent[1:]))
        assert progress.scheduled_lateness_ms[3:] == pytest.approx([0] * (len(sent) - 3))
    else:
        assert metrics["rebase_count"] == 0
        assert metrics["lateness_ms"]["max"] == pytest.approx(30)
    assert progress.boundary_time(plan.spans[0]["speech_end_sample"]) == sent[2][0]
    assert progress.boundary_time(len(plan.pcm) // 2 + 1) is None


@pytest.mark.asyncio
async def test_regular_scheduler_oversleep_recovers_to_absolute_clock(tmp_path):
    fixture = make_fixture(tmp_path)
    plan = assemble_audio(make_case(), {"cue": fixture}, 0.032, 21.0)
    now = 50.0
    sleeps = 0
    sent = []

    async def sleep(delay):
        nonlocal now, sleeps
        # Realistic alternating 0.4/0.8ms oversleep must not accumulate over 21 seconds.
        sleeps += 1
        now += delay + (0.0004 if sleeps % 2 else 0.0008)

    async def send(frame):
        sent.append((now, frame))

    progress = SendProgress()
    await pace_audio(send, plan, progress, lambda: False, clock=lambda: now, sleep=sleep)
    assert b"".join(frame for _, frame in sent) == plan.pcm
    assert progress.complete
    assert progress.describe()["rebase_count"] == 0
    assert progress.describe()["lateness_ms"]["max"] <= 0.800001
    assert progress.describe()["lateness_ms"]["p95"] == pytest.approx(0.8)
    assert sent[-1][0] - (50.0 + (plan.frames - 1) * FRAME_SECONDS) <= 0.000800001
    assert all(b[0] - a[0] >= MIN_FRAME_SPACING_SECONDS - 1e-10 for a, b in zip(sent, sent[1:]))


def test_case_selection_respects_mode_and_explicit_overrides():
    cases = [
        {"id": "legacy"},
        {"id": "monitor", "mode": "monitor"},
        {"id": "hi-request", "mode": "request"},
        {"id": "ml-request", "mode": "request"},
    ]
    assert select_cases(cases, "monitor") == cases[:2]
    assert select_cases(cases, "request") == cases[2:]
    assert select_cases(cases[:2], "request") == cases[:2]  # Backwards-compatible old manifests.
    assert select_cases(cases, "monitor", ["ml-request", "hi-request"]) == cases[2:]
    assert select_cases(cases, "request", ["legacy"]) == cases[:1]
    with pytest.raises(ValueError, match="Unknown case IDs: missing"):
        select_cases(cases, "monitor", ["missing"])
    with pytest.raises(ValueError, match="No cases selected"):
        select_cases(cases[2:], "monitor")


def test_quantiles_and_summary_do_not_invent_missing_measurements():
    assert quantile([], 0.95) is None
    assert quantile([12.0], 0.95) == 12.0
    assert quantile([40.0, 10.0, 20.0, 30.0], 0.95) == pytest.approx(38.5)
    record = base_record(alert=False)
    result = classify_result(record)
    rows = [
        {
            **record,
            "result": result,
            "language": "hi",
            "status": "completed",
            "errors": [],
            "metrics": {"speech_end_to_transcript_ms": value, "speech_end_to_alert_ms": None},
            "usage": {"audio_stream_seconds": 4.0, "successful_intent_count": 1},
        }
        for value in (100.0, 300.0, None)
    ]
    summary = summarize(rows, {"label": "offline"})
    metrics = summary["per_language"]["hi"]["metrics"]
    assert metrics["speech_end_to_transcript_ms"]["median"] == 200.0
    assert metrics["speech_end_to_transcript_ms"]["p95"] == 290.0
    assert metrics["speech_end_to_transcript_ms"]["n"] == 2
    assert metrics["speech_end_to_transcript_ms"]["small_n"]
    assert metrics["speech_end_to_alert_ms"]["median"] is None
    assert metrics["speech_end_to_alert_ms"]["n"] == 0
    assert summary["usage_proxy"]["audio_stream_seconds"] == 12.0


def test_scoring_joins_identifiers_and_preserves_corrected_transient_alerts():
    record = base_record(correction=True)
    old = alert()
    new = alert(id="a2", observation_id="o2")
    record["events"] = [
        envelope("observation", observation=observation(location="counter 2")),
        envelope("alert", alert=old),
        envelope("alert.corrected", alert={**old, "state": "corrected"}),
        envelope(
            "observation",
            observation=observation(
                id="o2", identifier="४४२", type="CORRECT", replaces_event_id="o1"
            ),
        ),
        envelope("alert", alert=new),
        final_transcript(),
    ]
    result = classify_result(record)
    assert result["verdict"] == "pass"
    assert result["initial_alert"] == old
    assert result["initial_alert_evaluations"][0]["location"] is False
    assert result["terminal_active_alerts"] == [new]
    assert result["terminal_alert_states"][0]["state"] == "corrected"
    assert result["correction_observed"] and result["retraction_observed"]
    assert result["retracted_alert_ids"] == ["a1"]
    record["events"] = record["events"][:2] + [final_transcript()]
    record["events"][0]["event"]["observation"]["identifiers"][0]["value"] = "1442"
    record["expected"]["correction"] = False
    result = classify_result(record)
    assert result["checks"]["target"] is False  # Summary contains 442, identifier is 1442.
    assert result["checks"]["location"] is False
    assert result["verdict"] == "fail"
    assert result["false_positive_any"] and result["false_positive_terminal"]
    record["events"] = [envelope("alert", alert=old), final_transcript()]
    assert classify_result(record)["verdict"] == "inconclusive"  # No structured identifier.


def test_negative_degradation_and_early_voice_stop_need_explicit_coverage():
    negative = base_record(alert=False, correction=True)
    old = alert()
    negative["events"] = [
        envelope("alert", alert=old),
        envelope("alert.corrected", alert={**old, "state": "corrected"}),
        final_transcript(),
    ]
    result = classify_result(negative)
    assert result["verdict"] == "fail"
    assert result["terminal_checks_passed"]
    assert result["false_positive_any"] and not result["false_positive_terminal"]
    negative = base_record(alert=False)
    negative["sender"]["full_window_sent"] = False
    assert classify_result(negative)["verdict"] == "inconclusive"
    negative["sender"]["full_window_sent"] = True
    negative["events"] = [envelope("status", state="DEGRADED"), final_transcript()]
    assert classify_result(negative)["verdict"] == "inconclusive"
    stop = base_record(alert=False, voice_stop=True)
    stop["sender"]["full_window_sent"] = False
    stop["events"] = [envelope("monitor.pause", reason="voice"), final_transcript("stop listening")]
    assert classify_result(stop)["verdict"] == "pass"
    stop["source_speech_sent"] = False
    assert classify_result(stop)["verdict"] == "inconclusive"


def test_location_aliases_are_verbatim_structured_labels_not_digit_matches():
    record = base_record(location="counter 2", location_aliases=["काउंटर दो"])
    source = observation(location="काउंटर दो")
    record["events"] += [
        envelope("observation", observation=source),
        envelope("alert", alert=alert()),
    ]
    result = classify_result(record)
    assert result["verdict"] == "pass"
    evaluation = result["terminal_alert_evaluations"][0]
    assert evaluation["location"] is True
    assert evaluation["location_literal"] is False and evaluation["location_canonical"] is False
    assert evaluation["matched_location_alias"] == "काउंटर दो"
    for location in ("gate 2", "काउंटर दो और तीन", "काउंटर १२", "22", "counter 12"):
        source["location"] = location
        result = classify_result(record)
        assert result["verdict"] == "fail"
        assert result["checks"]["location"] is False
        assert result["terminal_alert_evaluations"][0]["matched_location_alias"] is None
    source["location"] = None
    record["events"][-1]["event"]["alert"]["summary"] = "442 called to काउंटर दो"
    assert classify_result(record)["checks"]["location"] is None  # Never inspect prose.
    source["location"] = "counter 2"
    assert classify_result(record)["terminal_alert_evaluations"][0]["location_literal"] is True


def test_suppressed_initial_correction_does_not_require_nonexistent_retraction():
    record = base_record(alert=False, correction=True)
    record["events"] += [envelope("observation", observation=observation(type="UNCERTAIN"))]
    result = classify_result(record)
    assert result["verdict"] == "pass"
    assert result["checks"]["correction"] and result["correction_outcome_satisfied"]
    assert not result["correction_observed"] and not result["retraction_observed"]
    assert result["initial_alerts"] == result["terminal_active_alerts"] == []
    assert result["retracted_alert_ids"] == result["confirmed_correction_observations"] == []
    assert result["interpretation_completion_verified"] is None
    # A surviving wrong call is still a correction-outcome failure.
    record["events"].append(envelope("alert", alert=alert()))
    result = classify_result(record)
    assert result["verdict"] == "fail"
    assert not result["checks"]["correction"]
    # Retracting an already-exposed false positive cannot erase that exposure.
    record["events"].append(envelope("alert.corrected", alert=alert(state="corrected")))
    result = classify_result(record)
    assert result["checks"]["correction"] and result["retraction_observed"]
    assert result["false_positive_any"] and result["verdict"] == "fail"


def test_negative_monitor_requires_a_nonempty_final_transcript():
    record = base_record(alert=False)
    for events in ([], [final_transcript("")], [final_transcript("unrelated", is_final=False)]):
        record["events"] = events
        result = classify_result(record)
        assert not result["checks"]["final_transcript_received"]
        assert not result["coverage_sufficient"]
        assert result["verdict"] == "inconclusive"
    record["events"] = [final_transcript("unrelated announcement")]
    assert classify_result(record)["verdict"] == "pass"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario", ["correction", "negative", "no_final", "request", "voice_stop", "degraded"]
)
async def test_client_protocol_full_tail_request_mode_and_cleanup(tmp_path, scenario):
    fixture = make_fixture(tmp_path)
    case = make_case(
        alert=scenario in {"correction", "request"},
        correction=scenario == "correction",
        voice_stop=scenario == "voice_stop",
    )
    token = "private-session-token-only-for-this-offline-test"
    access_code = "private-access-code-only-for-this-offline-test"
    received = []
    calls = []
    connected = False
    request_text = "Please notify me for pharmacy token 442."

    def handle_http(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/sessions":
            assert json.loads(request.content) == {"access_code": access_code}
            return httpx.Response(200, json={"token": token})
        assert request.headers["authorization"] == "Bearer " + token
        if request.url.path == "/v1/intent":
            assert not connected
            assert json.loads(request.content) == {
                "text": request_text if scenario == "request" else case["request"],
                "consent_to_text_processing": True,
            }
            return httpx.Response(
                200,
                json={
                    "status": "confirm",
                    "proposal_id": "proposal-1",
                    "intent": {"task": {"identifiers": [{"value": "442"}]}},
                },
            )
        if request.url.path == "/v1/confirm":
            assert json.loads(request.content) == {"proposal_id": "proposal-1"}
            return httpx.Response(200, json={"type": "monitor.created"})
        if request.url.path == "/v1/state":
            return httpx.Response(
                200,
                json={
                    "stream_connected": connected,
                    "alerts": [],
                    "note": token + " " + access_code,
                },
            )
        assert (request.method, request.url.path) == ("DELETE", "/v1/session")
        return httpx.Response(200, json={"deleted": True})

    async def socket_handler(socket):
        nonlocal connected
        connected = True
        assert socket.request.headers["authorization"] == "Bearer " + token
        assert socket.request.headers["x-processing-consent"] == "audio-gnani;text-openai"
        mode = "request" if scenario == "request" else "monitor"
        assert socket.request.path == "/v1/stream?mode=" + mode
        await socket.send(json.dumps({"type": "status", "state": "STARTING"}))
        # The client must not transmit source or leading silence until READY.
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(socket.recv(), timeout=0.02)
        await socket.send(json.dumps({"type": "status", "state": "READY"}))
        try:
            async for packet in socket:
                if isinstance(packet, str):
                    assert json.loads(packet) == {"type": "stop"}
                    break
                assert len(packet) == 1024
                received.append(packet)
                events = []
                if scenario == "negative" and len(received) == 3:
                    events = [final_transcript("Some unrelated announcement.")]
                if scenario == "correction" and len(received) == 2:
                    events = [
                        envelope("transcript", mode=mode, segment={"id": "s1", "text": "442"}),
                        envelope("observation", observation=observation(location="counter 2")),
                        envelope("alert", alert=alert()),
                    ]
                if scenario == "correction" and len(received) == 5:
                    events = [
                        envelope("alert.corrected", alert=alert(state="corrected")),
                        envelope(
                            "observation",
                            observation=observation(
                                id="o2", type="CORRECT", replaces_event_id="o1"
                            ),
                        ),
                        envelope("alert", alert=alert(id="a2", observation_id="o2")),
                    ]
                if scenario in {"request", "voice_stop", "degraded"} and len(received) == 3:
                    if scenario == "degraded":
                        events = [envelope("status", state="DEGRADED", message="offline failure")]
                    else:
                        events = [
                            envelope(
                                "transcript", mode=mode, segment={"id": "s1", "text": request_text}
                            )
                        ]
                        if scenario == "voice_stop":
                            events.append(envelope("monitor.pause", reason="voice"))
                for event in events:
                    await socket.send(json.dumps(event["event"]))
                if scenario in {"request", "voice_stop", "degraded"} and len(received) == 3:
                    await socket.close(code=1000)
                    break
        finally:
            connected = False

    async with serve(socket_handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        options = Options(
            base_url=f"http://127.0.0.1:{port}",
            mode="request" if scenario == "request" else "monitor",
            leading_silence=0.032,
            tail_silence=0.128,
            ready_timeout=1.0,
            close_timeout=1.0,
        )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle_http),
            base_url=options.base_url,
        ) as client:
            record = await run_case(
                client, case, {"cue": fixture}, options, access_code, run_id="offline", repetition=1
            )
    assert calls[-1] == ("DELETE", "/v1/session")
    assert record["cleanup"] == {"deleted": True}
    assert not record["errors"]
    assert token not in json.dumps(record) and access_code not in json.dumps(record)
    assert record["usage"]["successful_intent_count"] == 1
    assert record["usage"]["audio_stream_seconds"] == pytest.approx(len(received) * FRAME_SECONDS)
    assert record["metrics"]["connect_ready_ms"] >= 20
    assert record["source_speech_sent"]
    assert record["result"]["verdict"] == (
        "inconclusive" if scenario in {"degraded", "no_final"} else "pass"
    )
    if scenario in {"correction", "negative", "no_final"}:
        plan = assemble_audio(case, {"cue": fixture}, 0.032, 0.128)
        assert b"".join(received) == plan.pcm
        assert record["sender"]["full_window_sent"]
    if scenario == "correction":
        assert len(record["alerts"]) == 2
        assert record["result"]["initial_alert"]["id"] == "a1"
        assert record["result"]["terminal_active_alerts"][0]["id"] == "a2"
        assert record["metrics"]["source_transcript_to_alert_ms"] is not None
    if scenario == "request":
        assert record["spoken_request_text"] == request_text
        assert record["metrics"]["request_workflow_ms"] > 0
        assert record["metrics"]["speech_end_to_alert_ms"] is None
    if scenario in {"request", "voice_stop"}:
        assert record["stream"]["close_code"] == 1000
        assert not record["sender"]["full_window_sent"]
    if scenario == "degraded":
        assert record["status"] == "provider_degraded"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "timeout", "window_too_long"])
async def test_failed_setup_still_deletes_session_and_preserves_references(tmp_path, failure):
    fixture = make_fixture(tmp_path)
    case = make_case()
    calls = []

    def handle_http(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"token": "offline-session-secret"})
        if request.url.path == "/v1/intent":
            if failure == "timeout":
                raise httpx.ReadTimeout("Offline timeout")
            return httpx.Response(503, json={"detail": "Offline provider failure"})
        assert (request.method, request.url.path) == ("DELETE", "/v1/session")
        return httpx.Response(200, json={"deleted": True})

    options = Options(max_stream_seconds=0.01 if failure == "window_too_long" else 180)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle_http), base_url=options.base_url
    ) as client:
        record = await run_case(
            client,
            deepcopy(case),
            {"cue": fixture},
            options,
            "offline-access-secret",
            run_id="offline",
            repetition=1,
        )
    assert record["result"]["verdict"] == "inconclusive"
    assert record["status"] == ("timeout" if failure == "timeout" else "error")
    assert record["references"] == [fixture]
    assert record["expected"] == case["expected"]
    assert record["metrics"]["speech_end_to_transcript_ms"] is None
    assert record["usage"]["successful_intent_count"] == 0
    assert record["usage"]["audio_stream_seconds"] == 0
    assert all(
        not isinstance(value, float) or math.isfinite(value) for value in record["metrics"].values()
    )
    if failure == "window_too_long":
        assert not calls  # Never buy setup or crop the source when the complete window cannot fit.
        assert "refusing to crop" in record["errors"][0]["message"]
    else:
        assert calls[-1] == ("DELETE", "/v1/session")
        assert record["usage"]["intent_attempt_count"] == 1
