"""Real-provider, sequential CueBell client; never imports or instruments the relay.

Run with the backend virtualenv, for example::

    python benchmarks/run_pipeline.py --label baseline --output /absolute/baseline.jsonl
    python benchmarks/run_pipeline.py --mode request --case spoken-setup --label setup

Set CUEBELL_BENCH_ACCESS_CODE in the environment. The running relay owns all provider
credentials/configuration. --output is a JSONL file (one complete record per attempt);
the adjacent *.summary.json contains descriptive statistics and usage proxies.
Existing output files are not overwritten. No audio filtering, cropping, resampling,
silence removal, API generation, or automatic provider retries are performed here.

Time convention: all t_* values are client time.monotonic() seconds. Speech endpoints
come from the manifest, mapped to the actual send time of the frame containing that
sample boundary (32 ms packetization). Nominal file-clock endpoints are also retained.
These are synthetic replay measurements, not physical microphone/provider timings.
First-event offsets can be negative for multi-cue sequences; no alignment is inferred.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import statistics
import time
import unicodedata
import uuid
import wave
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512
FRAME_BYTES = 1024
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE
# Allow small clock jitter to recover, but never drain a backlog with rapid sends.
MIN_FRAME_SPACING_SECONDS = 0.028
REBASE_THRESHOLD_SECONDS = FRAME_SECONDS
CONSENT = "audio-gnani;text-openai"
HERE = Path(__file__).resolve().parent
LATENCY_KEYS = (
    "setup_ms",
    "connect_ready_ms",
    "intent_ms",
    "confirm_ms",
    "speech_end_to_transcript_ms",
    "speech_end_to_alert_ms",
    "speech_end_to_voice_stop_ms",
    "transcript_to_alert_ms",
    "source_transcript_to_alert_ms",
    "last_cue_to_correction_ms",
    "request_workflow_ms",
    "speech_end_to_confirmation_ms",
    "sender_lateness_p50_ms",
    "sender_lateness_p95_ms",
    "sender_lateness_max_ms",
)


class BenchmarkError(Exception):
    """An observed protocol/setup failure, saved with the case instead of crashing it."""


def quantile(values: Sequence[float], probability: float) -> float | None:
    """Linear interpolation (type 7); empty samples stay missing, never become zero."""
    if not 0 <= probability <= 1:
        raise ValueError("Quantile probability must be between zero and one.")
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def distribution(values: Sequence[float]) -> dict:
    return {
        "n": len(values),
        "median": statistics.median(values) if values else None,
        "p95": quantile(values, 0.95),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "small_n": len(values) < 20,
    }


def finite_nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite, nonnegative number.")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite, nonnegative number.")
    return float(value)


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or manifest.get("sample_rate") != SAMPLE_RATE:
        raise ValueError("Expected manifest version=1 and sample_rate=16000.")
    fixtures = manifest.get("fixtures")
    cases = manifest.get("cases")
    if not isinstance(fixtures, list) or not isinstance(cases, list) or not fixtures or not cases:
        raise ValueError("The manifest must contain nonempty fixtures and cases lists.")
    ids: set[str] = set()
    for fixture in fixtures:
        for key in ("id", "language", "text", "audio_path", "sha256"):
            if not isinstance(fixture.get(key), str) or not fixture[key].strip():
                raise ValueError(f"Every fixture needs a nonempty {key} string.")
        if fixture["id"] in ids:
            raise ValueError(f"Duplicate fixture ID: {fixture['id']}")
        ids.add(fixture["id"])
        if not Path(fixture["audio_path"]).is_absolute():
            raise ValueError(f"Fixture {fixture['id']} needs an absolute audio_path.")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", fixture["sha256"]):
            raise ValueError(f"Invalid SHA-256 for fixture {fixture['id']}.")
        finite_nonnegative(fixture.get("speech_end_s"), "speech_end_s")
    case_ids: set[str] = set()
    for case in cases:
        for key in ("id", "language", "request"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError(f"Every case needs a nonempty {key} string.")
        if case["id"] in case_ids:
            raise ValueError(f"Duplicate case ID: {case['id']}")
        case_ids.add(case["id"])
        if case.get("mode", "monitor") not in {"monitor", "request"}:
            raise ValueError(f"Case {case['id']} mode must be monitor or request.")
        if not isinstance(case.get("sequence"), list) or not case["sequence"]:
            raise ValueError(f"Case {case['id']} needs a nonempty sequence.")
        for item in case["sequence"]:
            if item.get("fixture_id") not in ids:
                raise ValueError(f"Unknown fixture in case {case['id']}: {item.get('fixture_id')}")
            finite_nonnegative(item.get("silence_after_s"), "silence_after_s")
        expected = case.get("expected", {})
        boolean_keys = ("alert", "voice_stop", "correction")
        if any(type(expected.get(key)) is not bool for key in boolean_keys):
            raise ValueError(f"Case {case['id']} needs alert/voice_stop/correction booleans.")
        for key in ("token", "location"):
            if key not in expected or not (
                expected[key] is None or isinstance(expected[key], str) and expected[key].strip()
            ):
                raise ValueError(f"Case {case['id']} needs {key} as a nonempty string or null.")
        aliases = expected.get("location_aliases", [])
        if not isinstance(aliases, list) or any(
            not isinstance(alias, str) or not alias.strip() for alias in aliases
        ):
            raise ValueError(
                f"Case {case['id']} location_aliases must be a list of nonempty strings."
            )
    return manifest


def select_cases(cases: list[dict], mode: str, case_ids: Sequence[str] = ()) -> list[dict]:
    """Explicit IDs override filtering; old manifests can still replay in request mode."""
    unknown = set(case_ids) - {case["id"] for case in cases}
    if unknown:
        raise ValueError("Unknown case IDs: " + ", ".join(sorted(unknown)))
    if case_ids:
        selected = [case for case in cases if case["id"] in case_ids]
    elif mode == "monitor":
        selected = [case for case in cases if case.get("mode", "monitor") == "monitor"]
    else:
        selected = [case for case in cases if case.get("mode") == "request"] or cases
    if not selected:
        raise ValueError(f"No cases selected for --mode {mode}; use explicit --case IDs if needed.")
    return selected


@dataclass
class AudioPlan:
    pcm: bytes
    spans: list[dict]
    sequence_end_sample: int
    unpadded_samples: int
    leading_samples: int
    tail_samples: int

    @property
    def frames(self) -> int:
        return len(self.pcm) // FRAME_BYTES

    @property
    def duration_s(self) -> float:
        return len(self.pcm) / (SAMPLE_RATE * 2)

    def describe(self) -> dict:
        return {
            "sample_rate": SAMPLE_RATE,
            "channels": 1,
            "sample_width_bytes": 2,
            "frame_bytes": FRAME_BYTES,
            "frame_duration_s": FRAME_SECONDS,
            "planned_frames": self.frames,
            "planned_bytes": len(self.pcm),
            "planned_duration_s": self.duration_s,
            "leading_silence_s": self.leading_samples / SAMPLE_RATE,
            "tail_silence_s": self.tail_samples / SAMPLE_RATE,
            "sequence_end_s": self.sequence_end_sample / SAMPLE_RATE,
            "last_cue_speech_end_s": self.spans[-1]["speech_end_sample"] / SAMPLE_RATE,
            "padding_samples": len(self.pcm) // 2 - self.unpadded_samples,
            "fixtures": self.spans,
            "processing": "unaltered source PCM; inserted silence; final-frame zero padding only",
        }


def assemble_audio(
    case: dict, fixtures: dict[str, dict], leading_silence: float = 0.3, tail_silence: float = 6.0
) -> AudioPlan:
    """Keep every source sample and every requested silence, including WAV trailing silence."""
    leading = round(finite_nonnegative(leading_silence, "leading_silence") * SAMPLE_RATE)
    tail = round(finite_nonnegative(tail_silence, "tail_silence") * SAMPLE_RATE)
    chunks = [b"\0\0" * leading]
    offset = leading
    spans = []
    for item in case["sequence"]:
        fixture = fixtures[item["fixture_id"]]
        path = Path(fixture["audio_path"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != fixture["sha256"].lower():
            raise ValueError(f"SHA-256 mismatch for fixture {fixture['id']}.")
        with wave.open(str(path), "rb") as audio:
            if (
                audio.getnchannels() != 1
                or audio.getsampwidth() != 2
                or audio.getframerate() != SAMPLE_RATE
                or audio.getcomptype() != "NONE"
            ):
                raise ValueError(f"Fixture {fixture['id']} must be mono 16 kHz PCM16 WAV.")
            samples = audio.getnframes()
            pcm = audio.readframes(samples)
        if len(pcm) != samples * 2 or samples == 0:
            raise ValueError(f"Fixture {fixture['id']} has empty or truncated PCM data.")
        speech_end_s = finite_nonnegative(fixture["speech_end_s"], "speech_end_s")
        if speech_end_s > samples / SAMPLE_RATE:
            raise ValueError(f"speech_end_s exceeds WAV duration for fixture {fixture['id']}.")
        after = round(finite_nonnegative(item["silence_after_s"], "silence_after_s") * SAMPLE_RATE)
        spans.append(
            {
                **fixture,
                "file_samples": samples,
                "file_duration_s": samples / SAMPLE_RATE,
                "start_sample": offset,
                "speech_end_sample": offset + round(speech_end_s * SAMPLE_RATE),
                "file_end_sample": offset + samples,
                "silence_after_samples": after,
            }
        )
        chunks.extend((pcm, b"\0\0" * after))
        offset += samples + after
    sequence_end = offset
    chunks.append(b"\0\0" * tail)
    unpadded = offset + tail
    padding = (-unpadded) % FRAME_SAMPLES
    chunks.append(b"\0\0" * padding)
    return AudioPlan(b"".join(chunks), spans, sequence_end, unpadded, leading, tail)


@dataclass
class SendProgress:
    t_audio_start: float | None = None
    t_finished: float | None = None
    frame_times: list[float] = field(default_factory=list)
    lateness_ms: list[float] = field(default_factory=list)
    scheduled_lateness_ms: list[float] = field(default_factory=list)
    rebases: list[dict] = field(default_factory=list)
    complete: bool = False

    def boundary_time(self, sample: int) -> float | None:
        # The whole frame is submitted at once; don't claim sub-frame microphone timing.
        index = max(0, math.ceil(sample / FRAME_SAMPLES) - 1)
        return self.frame_times[index] if index < len(self.frame_times) else None

    def describe(self) -> dict:
        return {
            "frames": len(self.frame_times),
            "bytes": len(self.frame_times) * FRAME_BYTES,
            "audio_duration_s": len(self.frame_times) * FRAME_SECONDS,
            "wall_duration_s": (
                self.t_finished - self.t_audio_start
                if self.t_finished is not None and self.t_audio_start is not None
                else None
            ),
            "full_window_sent": self.complete,
            "lateness_ms": distribution(self.lateness_ms),
            "lateness_reference": "ideal absolute 32 ms schedule from first frame",
            "scheduled_lateness_ms": distribution(self.scheduled_lateness_ms),
            "scheduled_lateness_reference": "active deadline before any rebase of this frame",
            "rebase_count": len(self.rebases),
            "schedule_shift_ms": self.rebases[-1]["cumulative_shift_ms"] if self.rebases else 0.0,
            "rebases": self.rebases,
            "minimum_spacing_ms": MIN_FRAME_SPACING_SECONDS * 1000,
            "rebase_threshold_ms": REBASE_THRESHOLD_SECONDS * 1000,
            "inter_frame_spacing_ms": distribution(
                [
                    (current - previous) * 1000
                    for previous, current in zip(self.frame_times, self.frame_times[1:])
                ]
            ),
            "pacing": "absolute 32 ms clock; jitter recovery with 28 ms minimum spacing; "
            "lateness over one frame rebases the schedule without dropping PCM",
        }


async def pace_audio(
    send: Callable[[bytes], Awaitable[None]],
    plan: AudioPlan,
    progress: SendProgress,
    stopped: Callable[[], bool],
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Recover ordinary jitter against absolute deadlines; rebase after real stalls.

    Lateness remains measured against the original ideal clock, so rebasing cannot
    hide stretched replay. Active-clock lateness and every rebase are saved separately.
    """
    origin = clock()
    schedule_shift = 0.0
    try:
        for index in range(plan.frames):
            ideal_deadline = origin + index * FRAME_SECONDS
            scheduled_deadline = ideal_deadline + schedule_shift
            deadline = scheduled_deadline
            if progress.frame_times:
                deadline = max(deadline, progress.frame_times[-1] + MIN_FRAME_SPACING_SECONDS)
            while clock() < deadline and not stopped():
                await sleep(deadline - clock())
            if stopped():
                return
            submitted = clock()
            scheduled_lateness = max(0.0, submitted - scheduled_deadline)
            if scheduled_lateness > REBASE_THRESHOLD_SECONDS:
                schedule_shift += scheduled_lateness
                progress.rebases.append(
                    {
                        "frame_index": index,
                        "t": submitted,
                        "ideal_deadline": ideal_deadline,
                        "previous_deadline": scheduled_deadline,
                        "new_deadline": submitted,
                        "shift_ms": scheduled_lateness * 1000,
                        "cumulative_shift_ms": schedule_shift * 1000,
                    }
                )
            if progress.t_audio_start is None:
                progress.t_audio_start = submitted
            frame = plan.pcm[index * FRAME_BYTES : (index + 1) * FRAME_BYTES]
            await send(frame)
            progress.frame_times.append(submitted)
            progress.lateness_ms.append(max(0.0, (submitted - ideal_deadline) * 1000))
            progress.scheduled_lateness_ms.append(scheduled_lateness * 1000)
        # Include the duration of the final packet in the negative observation window.
        end = progress.frame_times[-1] + FRAME_SECONDS
        while clock() < end and not stopped():
            await sleep(end - clock())
        progress.complete = not stopped()
    finally:
        progress.t_finished = clock()


def normalize_identifier(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in value)
    return " ".join(value.split()).strip(" .,:;!?")


def target_match(expected: str | None, *sources: dict) -> bool | None:
    if expected is None:
        return True
    values = []
    structured = False
    for source in sources:
        if "identifiers" in source:
            structured = True
            values.extend(
                i.get("value") for i in (source["identifiers"] or []) if isinstance(i, dict)
            )
        for key in ("token_normalized", "token"):
            if source.get(key) is not None:
                structured = True
                values.append(source[key])
    if not structured:
        return None
    # Never search a summary, evidence sentence, or task description for token substrings.
    wanted = normalize_identifier(expected)
    return any(isinstance(value, str) and normalize_identifier(value) == wanted for value in values)


def location_match(expected: str | None, *sources: dict) -> bool | None:
    if expected is None:
        return True
    values = [s[key] for s in sources for key in ("location", "counter") if s.get(key)]
    if not values:
        return None
    wanted = normalize_identifier(expected)
    for value in values:
        actual = normalize_identifier(str(value))
        if actual == wanted:
            return True

        # "3" and a structured location "counter 3" are equivalent, but not "13".
        # Do not guess translations or spoken-number semantics; retain them for review.
        def short(text):
            return re.sub(r"^(?:counter|platform|gate|desk|window)\s+", "", text)

        if (wanted.isdecimal() or actual.isdecimal()) and short(actual) == short(wanted):
            return True
    return False


def event_groups(events: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {
        name: []
        for name in ("transcripts", "observations", "alerts", "corrections", "controls", "statuses")
    }
    for envelope in events:
        event = envelope["event"]
        if not isinstance(event, dict):
            continue
        kind = event.get("type", "")
        if not isinstance(kind, str):
            continue
        group = {
            "transcript": "transcripts",
            "observation": "observations",
            "alert": "alerts",
            "status": "statuses",
            "alert.corrected": "corrections",
        }.get(kind)
        if group:
            groups[group].append(envelope)
        if kind.startswith("monitor."):
            groups["controls"].append(envelope)
        if kind == "observation" and event.get("observation", {}).get("type") in {
            "CORRECT",
            "CANCEL",
        }:
            groups["corrections"].append(envelope)
    return groups


def classify_result(record: dict) -> dict:
    """Score observed outcomes without erasing transient mistakes or missing coverage."""
    expected = record["expected"]
    groups = event_groups(record["events"])
    observations = {
        e["event"]["observation"]["id"]: e["event"]["observation"]
        for e in groups["observations"]
        if e["event"].get("observation", {}).get("id")
    }
    initial = [e["event"]["alert"] for e in groups["alerts"]]
    latest = {a["id"]: a for a in initial}
    for envelope in record["events"]:
        event = envelope["event"]
        if isinstance(event, dict) and isinstance(event.get("alert"), dict):
            alert = event["alert"]
            if alert.get("id"):
                latest[alert["id"]] = alert
    terminal = [a for a in latest.values() if a.get("state") != "corrected"]

    def evaluate_alert(item: dict) -> dict:
        source = observations.get(item.get("observation_id"), {})
        locations = [
            value
            for obj in (item, source)
            for key in ("location", "counter")
            if isinstance(value := obj.get(key), str) and value
        ]
        canonical = location_match(expected["location"], item, source)
        # Aliases are verbatim, human-reviewed labels, never substrings or digit extraction.
        matched_alias = next(
            (alias for alias in expected.get("location_aliases", []) if alias in locations), None
        )
        literal = (
            True
            if expected["location"] is None
            else expected["location"] in locations
            if locations
            else None
        )
        return {
            "id": item["id"],
            "target": target_match(expected["token"], item, source),
            "location": True if matched_alias is not None else canonical,
            "location_literal": literal,
            "location_canonical": canonical,
            "matched_location_alias": matched_alias,
        }

    initial_evaluations = [evaluate_alert(item) for item in initial]
    terminal_evaluations = [evaluate_alert(item) for item in terminal]
    voice_stop = any(
        e["event"].get("reason") == "voice"
        and e["event"].get("type") in {"monitor.pause", "monitor.stop"}
        for e in groups["controls"]
    )
    retractions = [e for e in groups["corrections"] if e["event"].get("type") == "alert.corrected"]
    confirmed_corrections = [
        e["event"]["observation"]
        for e in groups["corrections"]
        if e["event"].get("observation", {}).get("state") == "confirmed"
        and e["event"]["observation"].get("replaces_event_id")
    ]
    correction = bool(retractions or confirmed_corrections)
    terminal_matches = (
        [item[key] for item in terminal_evaluations for key in ("target", "location")]
        if expected["alert"]
        else [not terminal]
    )
    no_surviving_wrong_alert = (
        False if False in terminal_matches else None if None in terminal_matches else True
    )
    final_transcript_received = any(
        isinstance(e["event"].get("segment", {}).get("text"), str)
        and e["event"]["segment"]["text"].strip()
        and e["event"].get("is_final") is not False
        and e["event"]["segment"].get("is_final") is not False
        for e in groups["transcripts"]
    )
    checks: dict[str, bool | None]
    if record["mode"] == "request":
        proposal = record.get("intent_response") or {}
        intent = proposal.get("intent", {})
        checks = {
            "combined_final_received": bool(groups["transcripts"]),
            "intent_confirmable": proposal.get("status") == "confirm",
            "monitor_confirmed": record.get("confirmation", {}).get("type") == "monitor.created",
            "target": target_match(expected["token"], intent, intent.get("task") or {}),
        }
        sufficient = record.get("source_speech_sent", False) and bool(groups["transcripts"])
    else:
        checks = {
            "terminal_alert": bool(terminal) == expected["alert"],
            "voice_stop": voice_stop == expected["voice_stop"],
            "correction": no_surviving_wrong_alert if expected["correction"] else not correction,
            "final_transcript_received": final_transcript_received,
            "target": True,
            "location": True,
        }
        if expected["alert"]:
            for key in ("target", "location"):
                matches = [item[key] for item in terminal_evaluations]
                checks[key] = (
                    False if not matches or False in matches else None if None in matches else True
                )
        sufficient = record.get("sender", {}).get("full_window_sent", False) or (
            expected["voice_stop"] and voice_stop and record.get("source_speech_sent", False)
        )
        sufficient = sufficient and final_transcript_received
    degraded = any(
        e["event"].get("state") in {"DEGRADED", "DISCONNECTED"} for e in groups["statuses"]
    )
    confirmed = record.get("confirmation", {}).get("type") == "monitor.created"
    setup_observed = (
        bool(record.get("intent_response")) if record["mode"] == "request" else confirmed
    )
    sufficient = bool(sufficient and not degraded and setup_observed)
    false_positive_any = record["mode"] == "monitor" and (
        bool(initial)
        and not expected["alert"]
        or any(item["target"] is False for item in initial_evaluations)
    )
    false_positive_terminal = record["mode"] == "monitor" and (
        bool(terminal)
        and not expected["alert"]
        or any(item["target"] is False for item in terminal_evaluations)
    )
    terminal_passed = all(value is True for value in checks.values())
    known_failure = False in checks.values() or false_positive_any
    verdict = (
        "fail"
        if sufficient and known_failure
        else "pass"
        if sufficient and terminal_passed
        else "inconclusive"
    )
    return {
        "verdict": verdict,
        "passed": verdict == "pass",
        "coverage_sufficient": sufficient,
        "interpretation_completion_verified": None,
        "coverage_note": "Client window/final-transcript coverage only. The websocket cannot "
        "prove every model call, including the latest interpretation, completed. "
        "Negative outcomes need an offline server-trace cross-check.",
        "checks": checks,
        "terminal_checks_passed": terminal_passed,
        "false_positive_any": false_positive_any,
        "false_positive_terminal": false_positive_terminal,
        "voice_stop_observed": voice_stop,
        "correction_observed": bool(correction),
        "correction_outcome_satisfied": (
            no_surviving_wrong_alert if expected["correction"] else None
        ),
        "retraction_observed": bool(retractions),
        "retracted_alert_ids": list(
            dict.fromkeys(
                e["event"]["alert"]["id"]
                for e in retractions
                if e["event"].get("alert", {}).get("id")
            )
        ),
        "confirmed_correction_observations": confirmed_corrections,
        "degraded": degraded,
        "initial_alert": initial[0] if initial else None,
        "initial_alerts": initial,
        "initial_alert_evaluations": initial_evaluations,
        "terminal_alert_states": list(latest.values()),
        "terminal_active_alerts": terminal,
        "terminal_alert_evaluations": terminal_evaluations,
        "snapshot_alerts": (record.get("state") or {}).get("alerts"),
        "scoring_note": (
            "Any alert on a negative case, or any wrong-target alert, counts as false-positive "
            "exposure even if later corrected; terminal checks are separate. "
            "Initial and terminal target/location checks use structured values only. "
            "Location aliases are an explicit verbatim whitelist; raw literal checks remain. "
            "Expected correction assesses terminal safety, not mandatory retraction of an "
            "alert that may never have been emitted; observed correction/retraction is separate. "
            "Request mode scores spoken setup/target, not monitor alert/location/control behavior."
        ),
    }


@dataclass
class Options:
    base_url: str = "http://127.0.0.1:8000"
    mode: str = "monitor"
    label: str = "benchmark"
    leading_silence: float = 0.3
    tail_silence: float = 6.0
    max_stream_seconds: float = 180.0
    ready_timeout: float = 30.0
    http_timeout: float = 45.0
    close_timeout: float = 3.0


class PairLimiter:
    """Stay below the baseline's 20 pairing attempts/minute, even on fast failures."""

    def __init__(self):
        self.last_attempt: float | None = None

    async def wait(self) -> float:
        start = time.monotonic()
        if self.last_attempt is not None:
            await asyncio.sleep(max(0.0, self.last_attempt + 3.1 - start))
        self.last_attempt = time.monotonic()
        return (self.last_attempt - start) * 1000


def add_error(record: dict, phase: str, error: Exception | str) -> None:
    record["errors"].append(
        {
            "t": time.monotonic(),
            "phase": phase,
            "kind": type(error).__name__ if isinstance(error, Exception) else "BenchmarkError",
            "message": str(error),
        }
    )


async def http_call(
    client: httpx.AsyncClient, record: dict, method: str, path: str, **kwargs
) -> dict:
    started = time.monotonic()
    if path == "/v1/intent":
        record["usage"]["intent_attempt_count"] += 1
    try:
        response = await client.request(method, path, **kwargs)
    except httpx.HTTPError as error:
        finished = time.monotonic()
        record["http"].append(
            {
                "method": method,
                "path": path,
                "t_start": started,
                "t_end": finished,
                "duration_ms": (finished - started) * 1000,
                "status_code": None,
                "error": {"kind": type(error).__name__, "message": str(error)},
            }
        )
        raise
    finished = time.monotonic()
    try:
        body = response.json()
    except ValueError:
        body = {"non_json_response": response.text}
    saved = body
    if path == "/v1/sessions" and isinstance(body, dict):
        saved = {key: value for key, value in body.items() if key != "token"}
    record["http"].append(
        {
            "method": method,
            "path": path,
            "t_start": started,
            "t_end": finished,
            "duration_ms": (finished - started) * 1000,
            "status_code": response.status_code,
            "response": saved,
        }
    )
    if path == "/v1/intent":
        if response.is_success:
            record["usage"]["successful_intent_count"] += 1
    if not response.is_success:
        raise BenchmarkError(f"{method} {path}: HTTP {response.status_code}; {saved}")
    if not isinstance(body, dict):
        raise BenchmarkError(f"{method} {path}: expected a JSON object.")
    return body


async def wait_session_idle(client: httpx.AsyncClient, record: dict, auth: dict) -> dict:
    for delay in (0, 0.1, 0.2, 0.4, 0.8, 1.6):
        if delay:
            await asyncio.sleep(delay)
        state = await http_call(client, record, "GET", "/v1/state", headers=auth)
        record["state"] = state
        if not state.get("stream_connected"):
            return state
    raise BenchmarkError("Relay stream cleanup did not finish before the next setup operation.")


def websocket_url(base_url: str, mode: str) -> str:
    parsed = urlsplit(base_url)
    return urlunsplit(
        (
            "wss" if parsed.scheme == "https" else "ws",
            parsed.netloc,
            parsed.path.rstrip("/") + "/v1/stream",
            "mode=" + mode,
            "",
        )
    )


async def stream_audio(record: dict, plan: AudioPlan, auth: dict, options: Options) -> SendProgress:
    progress = SendProgress()
    ready = asyncio.Event()
    stopped = asyncio.Event()
    stream = record["stream"]
    stream["t_connect"] = time.monotonic()
    receiver = None
    socket = None

    async def receive():
        try:
            async for raw in socket:
                arrived = time.monotonic()
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeError):
                    add_error(record, "receive", "Non-JSON websocket message: " + repr(raw))
                    continue
                record["events"].append(
                    {"t": arrived, "elapsed_s": arrived - record["t_start"], "event": payload}
                )
                if not isinstance(payload, dict):
                    continue
                if payload.get("type") == "status" and payload.get("state") == "READY":
                    stream.setdefault("t_ready", arrived)
                    ready.set()
                if (
                    payload.get("type") in {"monitor.pause", "monitor.stop"}
                    and payload.get("reason") == "voice"
                ):
                    stream["end_reason"] = "voice_stop"
                    stopped.set()
                if payload.get("type") == "transcript" and options.mode == "request":
                    stream["end_reason"] = "request_final"
                    stopped.set()
        except ConnectionClosed as error:
            if socket.close_code != 1000:
                add_error(record, "receive", error)
        except Exception as error:
            add_error(record, "receive", error)
        finally:
            stream["t_closed"] = time.monotonic()
            stream["close_code"] = socket.close_code
            stream["close_reason"] = socket.close_reason
            stopped.set()

    try:
        async with connect(
            websocket_url(options.base_url, options.mode),
            additional_headers={**auth, "x-processing-consent": CONSENT},
            open_timeout=options.ready_timeout,
            close_timeout=options.close_timeout,
            max_size=2**20,
            proxy=None,
        ) as socket:
            stream["t_connected"] = time.monotonic()
            # The receiver is running before readiness is awaited and before any audio is sent.
            receiver = asyncio.create_task(receive())
            waiter = asyncio.create_task(ready.wait())
            try:
                await asyncio.wait(
                    (receiver, waiter),
                    timeout=options.ready_timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not ready.is_set():
                    if receiver.done():
                        raise BenchmarkError("Websocket closed before READY.")
                    raise TimeoutError("Timed out waiting for READY.")
            finally:
                waiter.cancel()
                await asyncio.gather(waiter, return_exceptions=True)
            try:
                async with asyncio.timeout(options.max_stream_seconds):
                    await pace_audio(socket.send, plan, progress, stopped.is_set)
            except ConnectionClosed:
                # The receiver records the close and provider status. Voice stop is orderly.
                pass
            if progress.complete:
                stream["end_reason"] = "full_window"
                await socket.send(json.dumps({"type": "stop"}))
            try:
                await asyncio.wait_for(asyncio.shield(receiver), timeout=options.close_timeout)
            except TimeoutError:
                add_error(record, "close", "Server did not close within the close timeout.")
                await socket.close(code=1000, reason="Benchmark observation window ended")
    except Exception as error:
        add_error(record, "stream", error)
        stream["timed_out"] = isinstance(error, TimeoutError)
    finally:
        if receiver is not None:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        stream.setdefault("end_reason", "closed_or_failed")
        stream["t_finished"] = time.monotonic()
        if socket is not None:
            stream["close_code"] = socket.close_code
            stream["close_reason"] = socket.close_reason
    return progress


def finalize_measurements(record: dict, plan: AudioPlan | None, progress: SendProgress) -> None:
    record.update(event_groups(record["events"]))
    record["sender"] = progress.describe()
    record["t_audio_start"] = progress.t_audio_start
    record["t_speech_end"] = None
    record["t_sequence_end"] = None
    record["t_first_final"] = record["transcripts"][0]["t"] if record["transcripts"] else None
    record["t_first_alert"] = record["alerts"][0]["t"] if record["alerts"] else None
    if plan:
        record["fixture_boundaries"] = [
            {
                "fixture_id": span["id"],
                "t_speech_end": progress.boundary_time(span["speech_end_sample"]),
                "t_file_end": progress.boundary_time(span["file_end_sample"]),
                "t_speech_end_nominal": (
                    progress.t_audio_start + span["speech_end_sample"] / SAMPLE_RATE
                    if progress.t_audio_start is not None
                    else None
                ),
            }
            for span in plan.spans
        ]
        record["t_speech_end"] = record["fixture_boundaries"][-1]["t_speech_end"]
        record["t_sequence_end"] = progress.boundary_time(plan.sequence_end_sample)
    record["source_speech_sent"] = record["t_speech_end"] is not None
    record["t_last_cue_speech_end"] = record["t_speech_end"]

    def elapsed(end, start):
        return (end - start) * 1000 if end is not None and start is not None else None

    metrics = record["metrics"]
    metrics.update(
        setup_ms=elapsed(record.get("t_confirmed"), record["t_start"]),
        connect_ready_ms=elapsed(
            record["stream"].get("t_ready"), record["stream"].get("t_connect")
        ),
        speech_end_to_transcript_ms=elapsed(record["t_first_final"], record["t_speech_end"]),
        speech_end_to_alert_ms=elapsed(record["t_first_alert"], record["t_speech_end"]),
        speech_end_to_voice_stop_ms=elapsed(
            next(
                (
                    event["t"]
                    for event in record["controls"]
                    if event["event"].get("reason") == "voice"
                    and event["event"].get("type") in {"monitor.pause", "monitor.stop"}
                ),
                None,
            ),
            record["t_speech_end"],
        ),
        transcript_to_alert_ms=elapsed(record["t_first_alert"], record["t_first_final"]),
        source_transcript_to_alert_ms=None,
        last_cue_to_correction_ms=elapsed(
            record["corrections"][0]["t"] if record["corrections"] else None, record["t_speech_end"]
        ),
        request_workflow_ms=(
            elapsed(record.get("t_confirmed"), record["t_audio_start"])
            if record["mode"] == "request"
            else None
        ),
        speech_end_to_confirmation_ms=(
            elapsed(record.get("t_confirmed"), record["t_speech_end"])
            if record["mode"] == "request"
            else None
        ),
        sender_lateness_p50_ms=quantile(progress.lateness_ms, 0.5),
        sender_lateness_p95_ms=quantile(progress.lateness_ms, 0.95),
        sender_lateness_max_ms=max(progress.lateness_ms, default=None),
    )
    if record["alerts"]:
        observation_id = record["alerts"][0]["event"]["alert"].get("observation_id")
        sources = next(
            (
                e["event"]["observation"].get("source_segment_ids", [])
                for e in record["observations"]
                if e["event"]["observation"].get("id") == observation_id
            ),
            [],
        )
        source_times = [
            e["t"]
            for e in record["transcripts"]
            if e["event"].get("segment", {}).get("id") in sources
        ]
        metrics["source_transcript_to_alert_ms"] = elapsed(
            record["t_first_alert"], max(source_times, default=None)
        )
    for endpoint, key in (("/v1/intent", "intent_ms"), ("/v1/confirm", "confirm_ms")):
        metrics[key] = next(
            (e["duration_ms"] for e in record["http"] if e["path"] == endpoint), None
        )
    record["usage"].update(
        audio_stream_seconds=len(progress.frame_times) * FRAME_SECONDS,
        connection_open_seconds=(
            record["stream"]["t_finished"] - record["stream"]["t_connected"]
            if record["stream"].get("t_connected") is not None
            else 0.0
        ),
        observed_transcript_count=len(record["transcripts"]),
        confirmed_intent_count=int(record.get("confirmation", {}).get("type") == "monitor.created"),
    )
    record["result"] = classify_result(record)
    if record["stream"].get("timed_out") or record.get("timed_out"):
        record["status"] = "timeout"
    elif record["result"]["degraded"]:
        record["status"] = "provider_degraded"
    elif record["errors"]:
        record["status"] = "error"
    elif not record["result"]["coverage_sufficient"]:
        record["status"] = "incomplete"
    else:
        record["status"] = "completed"


def redact(value: Any, secrets: Sequence[str]) -> Any:
    """Remove only credential values, retaining semantic alert/intent 'token' fields."""
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    return value


async def run_case(
    client: httpx.AsyncClient,
    case: dict,
    fixtures: dict[str, dict],
    options: Options,
    access_code: str,
    *,
    run_id: str,
    repetition: int,
    limiter: PairLimiter | None = None,
) -> dict:
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "label": options.label,
        "case_id": case["id"],
        "repetition": repetition,
        "mode": options.mode,
        "language": case["language"],
        "request": case["request"],
        "sequence": case["sequence"],
        "source_ids": [s["fixture_id"] for s in case["sequence"]],
        "references": [fixtures[s["fixture_id"]] for s in case["sequence"]],
        "reference_text": " ".join(fixtures[s["fixture_id"]]["text"] for s in case["sequence"]),
        "expected": case["expected"],
        "started_at_utc": datetime.now(UTC).isoformat(),
        "t_start": time.monotonic(),
        "events": [],
        "http": [],
        "intents": [],
        "errors": [],
        "metrics": {},
        "stream": {},
        "usage": {"intent_attempt_count": 0, "successful_intent_count": 0},
    }
    plan = None
    progress = SendProgress()
    auth = None
    token = ""
    phase = "audio_preflight"
    try:
        plan = assemble_audio(case, fixtures, options.leading_silence, options.tail_silence)
        record["audio"] = plan.describe()
        if plan.duration_s > options.max_stream_seconds:
            raise BenchmarkError(
                f"Full audio window ({plan.duration_s:.3f}s) exceeds --max-stream-seconds "
                f"({options.max_stream_seconds:.3f}s); refusing to crop source evidence or silence."
            )
        phase = "pair"
        record["metrics"]["pair_wait_ms"] = await limiter.wait() if limiter else 0.0
        paired = await http_call(
            client, record, "POST", "/v1/sessions", json={"access_code": access_code}
        )
        token = paired.get("token", "")
        if not isinstance(token, str) or not token:
            raise BenchmarkError("Pairing response did not contain a session token.")
        auth = {"authorization": "Bearer " + token}
        request_text = case["request"]
        if options.mode == "request":
            phase = "request_stream"
            progress = await stream_audio(record, plan, auth, options)
            phase = "request_cleanup"
            await wait_session_idle(client, record, auth)
            transcripts = event_groups(record["events"])["transcripts"]
            if not transcripts:
                raise BenchmarkError("Request stream did not return a combined final transcript.")
            if len(transcripts) != 1:
                raise BenchmarkError(
                    "Request stream returned multiple combined finals; inspect events."
                )
            request_text = transcripts[0]["event"].get("segment", {}).get("text", "")
            record["spoken_request_text"] = request_text
            if not request_text.strip():
                raise BenchmarkError("Request stream returned an empty combined final transcript.")
        phase = "intent"
        record["intent_input"] = request_text
        proposal = await http_call(
            client,
            record,
            "POST",
            "/v1/intent",
            headers=auth,
            json={"text": request_text, "consent_to_text_processing": True},
        )
        record["intent_response"] = proposal
        record["intents"].append(proposal)
        if proposal.get("status") != "confirm" or not proposal.get("proposal_id"):
            raise BenchmarkError(
                "Intent did not produce a confirmable proposal; response retained."
            )
        phase = "confirm"
        record["confirmation"] = await http_call(
            client,
            record,
            "POST",
            "/v1/confirm",
            headers=auth,
            json={"proposal_id": proposal["proposal_id"]},
        )
        record["t_confirmed"] = time.monotonic()
        if record["confirmation"].get("type") != "monitor.created":
            raise BenchmarkError("Confirmation did not create a monitor.")
        if options.mode == "monitor":
            phase = "monitor_stream"
            progress = await stream_audio(record, plan, auth, options)
        phase = "state"
        await wait_session_idle(client, record, auth)
    except Exception as error:
        add_error(record, phase, error)
        if isinstance(error, (TimeoutError, httpx.TimeoutException)):
            record["timed_out"] = True
    finally:
        if auth is not None:
            try:
                # DELETE bypasses authenticated-request rate limits and frees the session cap.
                record["cleanup"] = await asyncio.shield(
                    http_call(client, record, "DELETE", "/v1/session", headers=auth)
                )
            except Exception as error:
                add_error(record, "delete_session", error)
        record["t_end"] = time.monotonic()
        finalize_measurements(record, plan, progress)
    return redact(record, (access_code, token))


def summarize(records: list[dict], metadata: dict) -> dict:
    counts = Counter(record["result"]["verdict"] for record in records)
    languages = sorted({record["language"] for record in records})
    per_language = {}
    for language in languages:
        subset = [record for record in records if record["language"] == language]
        per_language[language] = {
            "cases": len(subset),
            "verdicts": dict(Counter(record["result"]["verdict"] for record in subset)),
            "metrics": {
                key: distribution(
                    [r["metrics"][key] for r in subset if r["metrics"].get(key) is not None]
                )
                for key in LATENCY_KEYS
            },
        }
    return {
        "schema_version": 1,
        **metadata,
        "counts": {
            "attempts": len(records),
            "pass": counts["pass"],
            "fail": counts["fail"],
            "inconclusive": counts["inconclusive"],
            "statuses": dict(Counter(record["status"] for record in records)),
            "with_errors": sum(bool(record["errors"]) for record in records),
            "false_positive_any": sum(r["result"]["false_positive_any"] for r in records),
            "false_positive_terminal": sum(r["result"]["false_positive_terminal"] for r in records),
            "voice_stops": sum(r["result"]["voice_stop_observed"] for r in records),
            "corrections": sum(r["result"]["correction_observed"] for r in records),
        },
        "usage_proxy": {
            key: sum(record["usage"].get(key, 0) for record in records)
            for key in (
                "audio_stream_seconds",
                "connection_open_seconds",
                "intent_attempt_count",
                "successful_intent_count",
                "confirmed_intent_count",
                "observed_transcript_count",
            )
        },
        "per_language": per_language,
        "notes": [
            "Medians/p95 use only observed values, including failed cases; "
            "missing values stay null.",
            "p95 uses linear interpolation. n<20 is flagged; small samples are descriptive only.",
            "Times are monotonic client arrivals and manifest speech boundaries at 32 ms packet "
            "submission granularity, not physical microphone or separately measured "
            "STT/model delays.",
            "t_speech_end is the LAST cue speech endpoint, distinct from the full sequence end. "
            "First-event offsets can be negative for multi-cue/correction sequences.",
            "Request workflow is first audio frame through confirmation; setup includes pairing. "
            "No TTS generation time is included.",
            "Usage is a proxy, not provider billing: submitted PCM seconds, websocket-open "
            "seconds, HTTP-2xx intent responses (including clarify), "
            "and observed final transcripts. "
            "Unobserved upstream calls/retries and request-mode intermediate finals are unknown.",
            "Exact structured identifiers are scored. Location aliases, if supplied, are explicit "
            "verbatim ground truth; raw literal location checks remain recorded. "
            "References and all websocket events remain in JSONL for manual review.",
            "Monitor coverage requires a final transcript and the full window (or expected voice "
            "stop). This cannot prove all model calls or the latest interpretation completed; "
            "negative outcomes require an offline server-trace cross-check.",
            "Expected correction scores absence of surviving wrong alerts. Safe suppression "
            "does not imply a semantic correction or retraction was observed; those are separate.",
        ],
    }


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    cli.add_argument("--base-url", default="http://127.0.0.1:8000")
    cli.add_argument("--manifest", type=Path, default=HERE / "corpus.json")
    cli.add_argument(
        "--output", type=Path, help="New JSONL file; also writes an adjacent summary JSON"
    )
    cli.add_argument("--label", default="benchmark")
    cli.add_argument("--mode", choices=("monitor", "request"), default="monitor")
    cli.add_argument("--repeat", type=int, default=1)
    cli.add_argument(
        "--case",
        action="append",
        default=[],
        help="Exact case ID; repeatable; overrides automatic case.mode filtering",
    )
    cli.add_argument("--max-cases", type=int, help="Cap TOTAL attempts across repetitions")
    cli.add_argument("--leading-silence", type=float, default=0.3)
    cli.add_argument("--tail-silence", type=float, default=6.0)
    cli.add_argument("--max-stream-seconds", type=float, default=180.0)
    cli.add_argument("--ready-timeout", type=float, default=30.0)
    cli.add_argument("--http-timeout", type=float, default=45.0)
    cli.add_argument("--close-timeout", type=float, default=3.0)
    return cli


async def run_campaign(args: argparse.Namespace, access_code: str) -> int:
    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    fixtures = {fixture["id"]: fixture for fixture in manifest["fixtures"]}
    cases = select_cases(manifest["cases"], args.mode, args.case)
    options = Options(**{key: getattr(args, key) for key in Options.__dataclass_fields__})
    run_id = uuid.uuid4().hex
    label = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.label).strip(".-") or "benchmark"
    output = (args.output or HERE / "results" / f"{label}-{run_id}.jsonl").resolve()
    summary_path = output.with_suffix(".summary.json")
    if output == summary_path or output.exists() or summary_path.exists():
        raise ValueError(
            "Choose new output and summary paths; existing results are never overwritten."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "run_id": run_id,
        "label": args.label,
        "mode": args.mode,
        "base_url": args.base_url,
        "manifest": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "output": str(output),
        "options": {key: getattr(options, key) for key in Options.__dataclass_fields__},
        "repeat": args.repeat,
        "selected_cases": [case["id"] for case in cases],
        "max_cases": args.max_cases,
    }
    records = []
    limiter = PairLimiter()
    with output.open("x", encoding="utf-8") as handle:
        try:
            async with httpx.AsyncClient(
                base_url=args.base_url.rstrip("/") + "/",
                timeout=options.http_timeout,
                trust_env=False,
            ) as client:
                for repetition in range(1, args.repeat + 1):
                    for case in cases:
                        if args.max_cases is not None and len(records) >= args.max_cases:
                            break
                        record = await run_case(
                            client,
                            case,
                            fixtures,
                            options,
                            access_code,
                            run_id=run_id,
                            repetition=repetition,
                            limiter=limiter,
                        )
                        records.append(record)
                        handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                        handle.flush()
                        print(
                            f"{len(records)}: {case['id']} [{case['language']}] "
                            f"{record['result']['verdict']} / {record['status']}",
                            flush=True,
                        )
                    if args.max_cases is not None and len(records) >= args.max_cases:
                        break
        finally:
            summary = redact(summarize(records, metadata), (access_code,))
            with summary_path.open("x", encoding="utf-8") as summary_file:
                json.dump(summary, summary_file, ensure_ascii=False, indent=2, allow_nan=False)
                summary_file.write("\n")
            print(str(output), flush=True)
            print(str(summary_path), flush=True)
    return int(
        any(
            record["result"]["verdict"] != "pass" or record["status"] != "completed"
            for record in records
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    parsed = urlsplit(args.base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        cli.error("--base-url must be an HTTP(S) URL without credentials, query, or fragment.")
    if args.repeat < 1 or args.max_cases is not None and args.max_cases < 1:
        cli.error("--repeat and --max-cases must be positive integers.")
    for name in (
        "leading_silence",
        "tail_silence",
        "max_stream_seconds",
        "ready_timeout",
        "http_timeout",
        "close_timeout",
    ):
        value = getattr(args, name)
        positive = name.endswith("timeout") or name == "max_stream_seconds"
        if not math.isfinite(value) or value < 0 or positive and value == 0:
            requirement = "positive" if positive else "nonnegative"
            cli.error(f"--{name.replace('_', '-')} must be finite and {requirement}.")
    access_code = os.environ.get("CUEBELL_BENCH_ACCESS_CODE", "")
    if not access_code:
        cli.error("Set CUEBELL_BENCH_ACCESS_CODE in the environment (it is never saved).")
    try:
        return asyncio.run(run_campaign(args, access_code))
    except (OSError, ValueError) as error:
        cli.error(str(error))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
