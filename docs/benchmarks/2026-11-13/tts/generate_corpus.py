"""Approved audio-only utility. No paid calls in plan/validate; no automatic retries.

Run with OpenMontage's .venv/bin/python, from the toolkit root. Commands:
  generate_corpus.py plan
  generate_corpus.py sample
  generate_corpus.py batch
  generate_corpus.py revalidate
  generate_corpus.py validate

The approved provider/model/voice and both spend limits are immutable here.
CostTracker's actual_usd is reconciled conservatively to the tool ESTIMATE;
cost_status documents that this is not provider-confirmed monetary billing.
"""

from __future__ import annotations

import argparse
import array
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch
import wave


PROJECT = Path(__file__).resolve().parent
TOOLKIT = PROJECT.parent.parent
sys.path.insert(0, str(TOOLKIT))
from jsonschema import validate as validate_schema
from lib.checkpoint import init_project
from lib.config_model import BudgetMode
from tools.cost_tracker import CostTracker
from tools.tool_registry import registry

ARTIFACTS = PROJECT / "artifacts" / "audio"
SCRIPT = ARTIFACTS / "script.json"
STATE = ARTIFACTS / "generation_state.json"
MANIFEST = Path("/home/mathew/Arrakis/CueBell/backend/benchmarks/corpus.json")
TOOL = "elevenlabs_tts"
MODEL = "eleven_v3"
VOICE = "bajNon13EdhNMndG3z05"
MAX_CHARACTERS = 2000
MAX_COST_USD = 0.60
SAMPLE_ID = "hi-positive"
LANGUAGES = ("hi", "ml", "ta", "te", "mr", "en")
ALIGNMENT_OVERRUN_TOLERANCE_S = 0.005


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def safe(value):
    # Never persist credentials, request headers or raw HTTP bodies.
    serialized = json.dumps(value, ensure_ascii=False)
    secret = os.environ.get("ELEVENLABS_API_KEY")
    if secret:
        serialized = serialized.replace(secret, "[REDACTED]")
    return json.loads(serialized)


def tool_and_plan():
    registry.discover()
    tool = registry.get(TOOL)
    if tool is None or tool.provider != "elevenlabs":
        raise RuntimeError("Approved ElevenLabs tool unavailable; no substitution authorized")
    if tool.retry_policy.max_retries != 0:
        raise RuntimeError("Approved tool must have max_retries=0")
    script = read_json(SCRIPT)
    if STATE.exists():
        for extension in read_json(STATE).get("script_extensions", []):
            path = Path(extension["script_path"])
            assert extension["user_approved"] and digest(path) == extension["script_sha256"], "Locked extension script changed"
            plan = read_json(Path(extension["plan_path"]))
            assert plan["user_approved"] and plan["script_sha256"] == extension["script_sha256"]
            assert (plan["tool"], plan["model"], plan["voice_id"]) == (TOOL, MODEL, VOICE)
            script["fixtures"].extend(read_json(path)["fixtures"])
    rows = script["fixtures"]
    assert len({row["id"] for row in rows}) == len(rows)
    total = sum(len(row["text"]) for row in rows)
    cost = round(sum(tool.estimate_cost({"text": row["text"], "model_id": MODEL}) for row in rows), 4)
    if total > MAX_CHARACTERS or cost > MAX_COST_USD:
        raise RuntimeError("Full corpus exceeds approved character or estimated-dollar limit")
    if set(row["language"] for row in rows) != set(LANGUAGES):
        raise RuntimeError("The plan must cover all six approved languages")
    return tool, script, total, cost


def inputs_for(row):
    return {
        "text": row["text"], "voice_id": VOICE, "model_id": MODEL,
        "language_code": row["language"], "output_format": "pcm_16000",
        "with_timestamps": True, "stability": 0.5, "similarity_boost": 0.75,
        "style": 0.0, "speed": 1.0, "use_speaker_boost": True,
        "output_path": str(PROJECT / "assets" / "audio" / (row["id"] + ".wav")),
    }


def prepare(tool, script, characters, cost):
    init_project(PROJECT.name, title="CueBell multilingual speech benchmark corpus",
                 pipeline_type="audio-fixtures", pipeline_dir=PROJECT.parent)
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is required before paid generation")
    if STATE.exists():
        state = read_json(STATE)
        if state["script_sha256"] != digest(SCRIPT):
            raise RuntimeError("Do not change the script after plan locking")
        return state
    decisions = []

    def decision(category, subject, selected, label, reason):
        decisions.append({
            "decision_id": f"audio-{len(decisions) + 1:03d}", "stage": "audio-fixtures",
            "category": category, "subject": subject, "selected": selected,
            "options_considered": [{"option_id": selected, "label": label, "score": 1.0, "reason": reason}],
            "reason": reason, "user_visible": True, "user_approved": True,
        })

    decision("approval_policy", "Full speech corpus approval", "sample-and-batch",
             "Explicitly approved Hindi sample and remaining batch",
             "Parent session records explicit approval of the full audio run, including sample then batch, up to 2000 total submitted Unicode characters including failures and retakes and estimated USD 0.60. No automatic retries, provider/model substitutions, quota extensions, or large model downloads are approved.")
    decision("pipeline_selection", "Benchmark asset utility", "audio-fixtures", "Audio-only benchmark fixtures",
             "This utility initializes an OpenMontage project and records assets, costs and decisions; no video production or executed video manifest/gated stages are claimed. Localization-dub and framework-smoke video manifests do not fit.")
    decision("provider_selection", "Speech corpus provider and model", "elevenlabs-v3", "OpenMontage elevenlabs_tts / ElevenLabs eleven_v3",
             "Explicit user selection. Parent preflight verified all six languages with /v1/models; eleven_v4 requires a separate price quote and is not approved.")
    decision("voice_selection", "Speech corpus stock voice", VOICE, "Viraj — Indian male stock voice",
             "Explicit approved voice ID bajNon13EdhNMndG3z05. Parent preflight verified Indian accent and hi/ta/en support; ml/te/mr are model-supported but voice-native quality is not verified.")
    decision("budget_tradeoff", "Speech corpus submission and quota budget", "capped", "2000 total Unicode characters; estimated USD 0.60",
             f"Planned {characters} characters across {len(script['fixtures'])} fixtures, estimated USD {cost:.4f} at tool reference USD 0.0003/character. Parent read-only account preflight: 7794/10000 used, 2206 left, no extension. CostTracker uses cap mode with explicit approved tool; all submissions, even failed ones, consume the local cap.")
    log = {"version": "1.0", "project_id": PROJECT.name, "decisions": decisions}
    validate_schema(log, read_json(TOOLKIT / "schemas/artifacts/decision_log.schema.json"))
    if (PROJECT / "decision_log.json").exists():
        raise RuntimeError("Existing decision log requires investigation before initialization")
    write_json(PROJECT / "decision_log.json", log)
    plan = {
        "created_at": now(), "user_approved": True, "tool": TOOL, "tool_version": tool.version,
        "provider": "elevenlabs", "model": MODEL, "voice_id": VOICE, "voice_name": "Viraj",
        "language_codes": list(LANGUAGES), "planned_characters": characters,
        "planned_cost_usd": cost, "cost_status": "estimated", "character_count_method": "Python len(text): Unicode code points, including spaces, punctuation and combining marks",
        "max_submitted_characters_including_failures": MAX_CHARACTERS, "max_estimated_cost_usd": MAX_COST_USD,
        "quota_preflight": {"used": 7794, "limit": 10000, "remaining": 2206, "provenance": "Parent-session read-only provider preflight; not re-fetched by this utility", "extension_approved": False},
        "format": {"provider_output": "pcm_16000", "container": "WAV", "sample_rate": 16000, "channels": 1, "sample_width_bytes": 2},
        "format_provenance": "Inspected OpenMontage tool wraps provider raw signed 16-bit mono PCM in a WAV container without DSP",
        "retry_policy": {"max_retries": 0, "retakes": "Not scheduled; any failed attempt blocks batch continuation"},
        "audio_processing": "None beyond WAV container wrapping; no denoising, gain normalization, resampling, trimming, speed change or added noise",
        "quality_scope": "Synthetic stock-voice benchmark; PCM/file/alignment integrity checks only. No independent listening or native-speaker quality validation is claimed.",
        "script_path": str(SCRIPT), "script_sha256": digest(SCRIPT),
        "generator_path": str(Path(__file__).resolve()),
        "tool_source_path": str(TOOLKIT / "tools/audio/elevenlabs_tts.py"),
        "tool_source_sha256": digest(TOOLKIT / "tools/audio/elevenlabs_tts.py"),
        "fixtures": [{"id": row["id"], "characters": len(row["text"]), "estimated_cost_usd": tool.estimate_cost(inputs_for(row)), "inputs": inputs_for(row)} for row in script["fixtures"]],
    }
    write_json(ARTIFACTS / "generation_plan.json", plan)
    state = {"version": 1, "created_at": now(), "script_sha256": digest(SCRIPT), "attempts": []}
    write_json(STATE, state)
    return state


def validate_audio(row):
    path = Path(inputs_for(row)["output_path"])
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    ffprobe = json.loads(probe.stdout)
    with wave.open(str(path), "rb") as handle:
        channels, width, rate, frames = handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.getnframes()
        raw = handle.readframes(frames)
    assert (channels, width, rate) == (1, 2, 16000), "Expected mono 16 kHz signed PCM16 WAV"
    assert len(raw) == frames * 2 and frames > 1600, "Truncated or empty PCM data"
    assert ffprobe["streams"][0]["codec_name"] == "pcm_s16le"
    samples = array.array("h", raw)
    if sys.byteorder != "little":
        samples.byteswap()
    duration = frames / rate
    peak = max(abs(sample) for sample in samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    clipping = sum(abs(sample) >= 32760 for sample in samples) / len(samples)
    assert rms > 1 and peak > 100, "No usable non-silent waveform"
    assert clipping < 0.01, "Excessive full-scale PCM samples"
    alignment_path = path.with_name(path.name + ".alignment.json")
    alignment = read_json(alignment_path)["alignment"]
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    assert len(chars) == len(starts) == len(ends) and chars, "Invalid alignment array lengths"
    assert all(math.isfinite(s) and math.isfinite(e) and 0 <= s <= e for s, e in zip(starts, ends)), "Invalid character timing"
    assert all(a <= b for a, b in zip(starts, starts[1:])), "Non-monotonic alignment starts"
    assert all(a <= b for a, b in zip(ends, ends[1:])), "Non-monotonic alignment ends"
    speech_index = max(i for i, char in enumerate(chars) if char.strip())
    raw_speech_end = ends[speech_index]
    assert 0 < raw_speech_end <= duration + ALIGNMENT_OVERRUN_TOLERANCE_S, "Last nonspace character ends outside the WAV tolerance"
    assert max(ends) <= duration + ALIGNMENT_OVERRUN_TOLERANCE_S, "Alignment duration exceeds WAV by more than 5 ms"
    speech_end = min(raw_speech_end, duration)
    provenance = "ElevenLabs with-timestamps alignment: last non-whitespace character end (includes punctuation); not independent forced alignment or measured human speech offset"
    if raw_speech_end > duration:
        provenance += "; bounded to WAV duration for a sub-5ms provider timestamp overrun; raw alignment retained unchanged"
    qa = {
        "id": row["id"], "checked_at": now(), "status": "passed", "audio_path": str(path),
        "sha256": digest(path), "byte_count": path.stat().st_size, "duration_s": duration,
        "sample_rate": rate, "channels": channels, "sample_width_bytes": width, "frames": frames,
        "peak_pcm16": peak, "rms_pcm16": round(rms, 6), "rms_dbfs": round(20 * math.log10(rms / 32768), 3),
        "full_scale_fraction": clipping, "speech_end_s": speech_end,
        "speech_end_provenance": provenance,
        "speech_end_raw_alignment_s": raw_speech_end,
        "speech_end_boundary_adjustment_s": round(raw_speech_end - speech_end, 9),
        "alignment_overrun_tolerance_s": ALIGNMENT_OVERRUN_TOLERANCE_S,
        "last_nonspace_character": chars[speech_index], "alignment_max_end_s": max(ends),
        "alignment_matches_text": "".join(chars) == row["text"],
        "alignment_path": str(alignment_path), "alignment_sha256": digest(alignment_path),
        "trailing_after_speech_end_s": round(duration - speech_end, 6),
        "quality_scope": "Container/PCM/timing checks; pronunciation and listening quality not independently established",
        "ffprobe": ffprobe,
    }
    write_json(ARTIFACTS / (row["id"] + ".qa.json"), qa)
    return qa


def generate_one(tool, row, state, tracker):
    if any(attempt["id"] == row["id"] for attempt in state["attempts"]):
        raise RuntimeError(f"Refusing repeat submission for {row['id']}")
    inputs = inputs_for(row)
    validate_schema(inputs, tool.input_schema)
    count = len(inputs["text"])
    estimate = tool.estimate_cost(inputs)
    if sum(attempt["characters"] for attempt in state["attempts"]) + count > MAX_CHARACTERS:
        raise RuntimeError("Submitted-character cap would be exceeded")
    if round(sum(attempt["estimated_cost_usd"] for attempt in state["attempts"]) + estimate, 4) > MAX_COST_USD:
        raise RuntimeError("Estimated-dollar cap would be exceeded")
    if Path(inputs["output_path"]).exists():
        raise RuntimeError("Unexpected existing audio; refusing to overwrite or submit")
    entry_id = tracker.estimate(TOOL, row["id"], estimate)
    tracker.entries[-1].update({"user_approved": True, "cost_status": "estimated", "reconciliation_basis": "Tool cost estimate conservatively charged against cap; actual provider bill unknown"})
    tracker.reserve(entry_id)
    attempt = {"id": row["id"], "started_at": now(), "characters": count, "estimated_cost_usd": estimate,
               "cost_status": "estimated", "cost_entry_id": entry_id, "status": "submitted", "generator_sha256": digest(Path(__file__)), "inputs": inputs}
    state["attempts"].append(attempt)
    write_json(STATE, state)  # Persist before the network call; an interrupted attempt cannot be replayed.
    import requests
    original_send = requests.sessions.Session.send
    http = []

    def observe_send(session, request, **kwargs):
        # Observe the tool's real transport, never recreate its API request.
        if request.method != "POST" or not request.url.startswith(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?"):
            raise RuntimeError("Unexpected provider transport; no substitute authorized")
        if http:
            raise RuntimeError("More than one HTTP request for a fixture is not authorized")
        response = original_send(session, request, **kwargs)
        observed = {"status_code": response.status_code, "request_id": response.headers.get("request-id")}
        for name in ("character-cost", "x-character-count", "x-characters-remaining"):
            value = response.headers.get(name)
            if value is not None and value.strip().isdigit():
                observed[name] = int(value)
        if not response.ok:
            try:
                detail = response.json().get("detail", {})
                if isinstance(detail, dict):
                    observed["provider_error"] = {key: detail[key] for key in ("status", "message") if key in detail}
            except (ValueError, AttributeError):
                pass
        http.append(safe(observed))
        return response

    started = time.monotonic()
    with patch("requests.sessions.Session.send", observe_send):
        result = tool.execute(inputs)
    elapsed = time.monotonic() - started
    tracker.reconcile(entry_id, estimate, success=result.success)
    attempt.update({"finished_at": now(), "generation_duration_s": round(elapsed, 6), "http": http,
                    "tool_result": safe(asdict(result)), "status": "generated" if result.success else "failed"})
    write_json(ARTIFACTS / (row["id"] + ".result.json"), attempt)
    write_json(STATE, state)
    if not result.success:
        raise RuntimeError(f"Provider/tool failure for {row['id']}: {safe(result.error)}; no retry or fallback performed")
    try:
        qa = validate_audio(row)
    except Exception as exc:
        attempt.update({"status": "validation_failed", "validation_error": str(exc)})
        write_json(STATE, state)
        raise
    attempt["status"] = "validated"
    write_json(STATE, state)
    print(json.dumps({"id": row["id"], "characters": count, "estimated_cost_usd": estimate, "duration_s": qa["duration_s"], "speech_end_s": qa["speech_end_s"], "generation_duration_s": round(elapsed, 3), "http": http}, ensure_ascii=False), flush=True)


def make_cases(script):
    cases = []

    def case(identifier, language, kind, fixtures, alert=False, voice_stop=False, correction=False):
        cases.append({
            "id": identifier, "language": language, "request": script["request"], "kind": kind,
            "sequence": [{"fixture_id": fixture, "silence_after_s": (0.15 if i < len(fixtures) - 1 else 2.0)} for i, fixture in enumerate(fixtures)],
            "expected": {"alert": alert, "token": "442" if alert else None, "location": "counter 2" if alert else None, "voice_stop": voice_stop, "correction": correction},
        })

    for language in LANGUAGES:
        case(language + "-positive", language, "positive", [language + "-positive"], alert=True)
        case(language + "-near-miss", language, "near-miss", [language + "-near-miss"])
        case(language + "-voice-stop", language, "voice-stop", [language + "-voice-stop"], voice_stop=True)
        case(language + "-burst", language, "burst", [language + "-near-miss", language + "-positive"], alert=True)
    for language in ("hi", "ml"):
        case(language + "-correction", language, "correction", [language + "-positive", language + "-correction"], correction=True)
        case(language + "-cancellation", language, "cancellation", [language + "-positive", language + "-cancellation"], correction=True)
    for row in script["fixtures"]:
        if row["kind"] == "request":
            cases.append({"id": row["id"], "language": row["language"], "kind": "request", "mode": "request",
                          "request": script["request"], "sequence": [{"fixture_id": row["id"], "silence_after_s": 2.0}],
                          "expected": {"alert": False, "token": "442", "location": None, "voice_stop": False, "correction": False}})
    return cases


def publish(script, state):
    if len(state["attempts"]) != len(script["fixtures"]) or any(a["status"] != "validated" for a in state["attempts"]):
        raise RuntimeError("All fixtures must validate before publishing the runner manifest")
    fixtures = []
    durations = []
    for row in script["fixtures"]:
        qa = read_json(ARTIFACTS / (row["id"] + ".qa.json"))
        assert qa["status"] == "passed" and qa["sha256"] == digest(Path(qa["audio_path"]))
        assert qa["alignment_sha256"] == digest(Path(qa["alignment_path"]))
        durations.append(qa["duration_s"])
        fixtures.append({**row, "audio_path": qa["audio_path"], "speech_end_s": qa["speech_end_s"], "sha256": qa["sha256"],
                         "duration_s": qa["duration_s"], "speech_end_provenance": qa["speech_end_provenance"],
                         "speech_end_raw_alignment_s": qa["speech_end_raw_alignment_s"], "speech_end_boundary_adjustment_s": qa["speech_end_boundary_adjustment_s"],
                         "alignment_path": qa["alignment_path"], "alignment_sha256": qa["alignment_sha256"],
                         "qa_path": str(ARTIFACTS / (row["id"] + ".qa.json")),
                         "generation_result_path": str(ARTIFACTS / (row["id"] + ".result.json"))})
    cases = make_cases(script)
    manifest = {"version": 1, "sample_rate": 16000, "fixtures": fixtures, "cases": cases,
                "metadata": {"project_path": str(PROJECT), "generation_plan_path": str(ARTIFACTS / "generation_plan.json"),
                             "provider": "elevenlabs", "tool": TOOL, "model": MODEL, "voice_id": VOICE, "voice_name": "Viraj",
                             "corpus_type": "synthetic-stock-voice", "translation_provenance": script["translation_provenance"],
                             "quality_scope": "Automated file/PCM/alignment validation; manual listening and native-speaker evaluation not performed",
                             "audio_processing": "Provider PCM wrapped in WAV only; no denoising or DSP",
                             "expected_location_semantics": "counter 2 is a canonical English ground-truth label for native-script counter two; returned evidence locations may be verbatim native text",
                             "correction_semantics": "Expected final alert is false once the initial 442 call is explicitly replaced by 443 or cancelled; transient earlier alerts must be separately recorded. correction=true includes explicit cancellation.",
                             "sequence_gap_note": "silence_after_s adds silence after the complete untrimmed WAV; intrinsic provider trailing silence also contributes to the effective gap",
                             "cost_status": "estimated", "estimated_cost_usd": round(sum(a["estimated_cost_usd"] for a in state["attempts"]), 4),
                             "submitted_characters_including_failures": sum(a["characters"] for a in state["attempts"])}}
    if MANIFEST.exists() and read_json(MANIFEST).get("metadata", {}).get("project_path") != str(PROJECT):
        raise RuntimeError("Existing corpus manifest belongs to another producer; refusing overwrite")
    if MANIFEST.exists():
        previous = read_json(MANIFEST)
        assert fixtures[:len(previous["fixtures"])] == previous["fixtures"], "Existing fixtures must remain unchanged"
        assert cases[:len(previous["cases"])] == previous["cases"], "Existing cases must remain unchanged"
    if state.get("script_extensions"):
        manifest["metadata"]["script_extensions"] = state["script_extensions"]
        manifest["metadata"]["request_case_selection"] = "Select hi-request and ml-request explicitly with --mode request; exclude kind=request cases from monitor-mode runs"
        manifest["metadata"]["request_translation_provenance"] = "Parent-supplied Hindi and Malayalam requests, fixed before synthesis; native pronunciation not independently verified"
    write_json(MANIFEST, manifest)
    write_json(ARTIFACTS / "corpus.json", manifest)
    summary = {"finished_at": now(), "status": "completed", "fixtures": len(fixtures), "cases": len(cases),
               "languages": list(LANGUAGES), "submitted_characters": sum(a["characters"] for a in state["attempts"]),
               "estimated_cost_usd": round(sum(a["estimated_cost_usd"] for a in state["attempts"]), 4), "cost_status": "estimated",
               "generation_duration_s": round(sum(a["generation_duration_s"] for a in state["attempts"]), 6),
               "total_audio_duration_s": round(sum(durations), 6), "min_audio_duration_s": min(durations), "max_audio_duration_s": max(durations),
               "failed_submissions": sum(a["status"] != "validated" for a in state["attempts"]), "automatic_retries": 0,
               "manifest_path": str(MANIFEST), "manifest_sha256": digest(MANIFEST), "audio_directory": str(PROJECT / "assets/audio"),
               "evidence_directory": str(ARTIFACTS), "provider_confirmed_remaining_quota": None,
               "quota_note": "Post-run remaining quota is unavailable in ToolResult/observed response metadata; do not present arithmetic remainder as provider-confirmed.",
               "approved_submitted_character_budget_remaining": MAX_CHARACTERS - sum(a["characters"] for a in state["attempts"])}
    if state.get("script_extensions"):
        summary["script_extension_plans"] = [item["plan_path"] for item in state["script_extensions"]]
        summary["request_cases"] = [case["id"] for case in cases if case["kind"] == "request"]
    write_json(ARTIFACTS / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "sample", "batch", "revalidate", "validate"))
    args = parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with (ARTIFACTS / ".generation.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        tool, script, characters, cost = tool_and_plan()
        state = prepare(tool, script, characters, cost)
        if args.command == "plan":
            print(json.dumps({"fixtures": len(script["fixtures"]), "cases": len(make_cases(script)), "planned_characters": characters, "estimated_cost_usd": cost, "sample_characters": len(script["fixtures"][0]["text"]), "plan": str(ARTIFACTS / "generation_plan.json")}, indent=2))
            return
        if args.command == "validate":
            publish(script, state)
            return
        if args.command == "revalidate":
            by_id = {row["id"]: row for row in script["fixtures"]}
            resolutions = []
            for attempt in state["attempts"]:
                if not attempt.get("tool_result", {}).get("success"):
                    raise RuntimeError("A provider/tool failure cannot be resolved by local audio validation")
                old_status = attempt["status"]
                qa = validate_audio(by_id[attempt["id"]])
                if old_status != "validated":
                    resolution = {"id": attempt["id"], "previous_status": old_status,
                                  "original_error": attempt.get("validation_error"), "resolved_at": now(),
                                  "raw_alignment_s": qa["speech_end_raw_alignment_s"], "speech_end_s": qa["speech_end_s"],
                                  "boundary_adjustment_s": qa["speech_end_boundary_adjustment_s"],
                                  "resolution": "Existing WAV passed local validation with documented 5ms timestamp-overrun tolerance; no media bytes changed or regenerated", "network_calls": 0}
                    attempt.setdefault("validation_history", []).append(resolution)
                    resolutions.append(resolution)
                attempt["status"] = "validated"
            write_json(STATE, state)
            write_json(ARTIFACTS / "local_revalidation.json", {"timestamp": now(), "network_calls": 0, "resolutions": resolutions})
            print(json.dumps({"locally_validated": len(state["attempts"]), "network_calls": 0, "resolutions": resolutions}, ensure_ascii=False, indent=2))
            return
        if tool.get_status().value != "available":
            raise RuntimeError("Approved provider unavailable; no substitute authorized")
        if any(a["status"] != "validated" for a in state["attempts"]):
            raise RuntimeError("An earlier attempt failed or was interrupted; do not resubmit automatically")
        tracker = CostTracker(budget_total_usd=MAX_COST_USD, reserve_pct=0, mode=BudgetMode.CAP,
                              single_action_approval_usd=MAX_COST_USD, cost_log_path=PROJECT / "cost_log.json")
        tracker.approve_tool(TOOL)
        if args.command == "sample":
            generate_one(tool, next(row for row in script["fixtures"] if row["id"] == SAMPLE_ID), state, tracker)
            return
        if not any(a["id"] == SAMPLE_ID and a["status"] == "validated" for a in state["attempts"]):
            raise RuntimeError("Hindi sample must pass validation before the approved batch")
        completed = {a["id"] for a in state["attempts"]}
        for row in script["fixtures"]:
            if row["id"] not in completed:
                generate_one(tool, row, state, tracker)
        publish(script, state)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write_json(ARTIFACTS / "blocker.json", {"timestamp": now(), "error": safe(str(error)), "automatic_retry": False, "substitution_performed": False})
        raise
