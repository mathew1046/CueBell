"""Offline audit of saved corpus, approval/budget ledger, and provider evidence.

Run with the OpenMontage .venv Python. This script performs no network calls,
does not modify media, and writes artifacts/audio/audit_report.json.
"""

import hashlib
import json
from pathlib import Path
import wave


PROJECT = Path(__file__).resolve().parent
ARTIFACTS = PROJECT / "artifacts/audio"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = read(ARTIFACTS / "generation_plan.json")
    state = read(ARTIFACTS / "generation_state.json")
    manifest = read(ARTIFACTS / "corpus.json")
    summary = read(ARTIFACTS / "summary.json")
    costs = read(PROJECT / "cost_log.json")
    decisions = read(PROJECT / "decision_log.json")
    source = read(ARTIFACTS / "script.json")
    planned_characters = plan["planned_characters"]
    planned_cost = plan["planned_cost_usd"]
    preserved_baselines = []
    for extension in state.get("script_extensions", []):
        extension_script = Path(extension["script_path"])
        extension_plan = read(Path(extension["plan_path"]))
        assert extension["user_approved"] and extension_plan["user_approved"]
        assert sha256(extension_script) == extension["script_sha256"] == extension_plan["script_sha256"]
        assert extension_plan["model"] == "eleven_v3" and extension_plan["voice_id"] == "bajNon13EdhNMndG3z05"
        source["fixtures"].extend(read(extension_script)["fixtures"])
        planned_characters += extension_plan["planned_characters"]
        planned_cost = round(planned_cost + extension_plan["planned_cost_usd"], 4)
        baseline = Path(extension_plan["baseline_directory"])
        for snapshot in read(baseline / "index.json")["files"]:
            assert sha256(Path(snapshot["snapshot"])) == snapshot["sha256"]
        prior = read(baseline / "corpus.json")
        assert sha256(baseline / "corpus.json") == extension_plan["baseline_manifest_sha256"]
        assert manifest["fixtures"][:len(prior["fixtures"])] == prior["fixtures"]
        assert manifest["cases"][:len(prior["cases"])] == prior["cases"]
        previous_attempts = read(baseline / "generation_state.json")["attempts"]
        previous_costs = read(baseline / "cost_log.json")["entries"]
        previous_decisions = read(baseline / "decision_log.json")["decisions"]
        assert state["attempts"][:len(previous_attempts)] == previous_attempts
        assert costs["entries"][:len(previous_costs)] == previous_costs
        assert decisions["decisions"][:len(previous_decisions)] == previous_decisions
        preserved_baselines.append({"directory": str(baseline), "fixtures_unchanged": len(prior["fixtures"]), "cases_unchanged": len(prior["cases"])})
    actual_manifest = Path(summary["manifest_path"])
    assert sha256(actual_manifest) == summary["manifest_sha256"]
    assert actual_manifest.read_bytes() == (ARTIFACTS / "corpus.json").read_bytes()
    assert sha256(ARTIFACTS / "script.json") == plan["script_sha256"] == state["script_sha256"]
    assert plan["user_approved"] is True
    assert all(decision["user_approved"] is True for decision in decisions["decisions"])
    assert any(decision["category"] == "approval_policy" for decision in decisions["decisions"])
    assert plan["model"] == "eleven_v3" and plan["voice_id"] == "bajNon13EdhNMndG3z05"
    assert manifest["version"] == 1 and manifest["sample_rate"] == 16000
    attempts = state["attempts"]
    assert len({attempt["id"] for attempt in attempts}) == len(attempts), "Duplicate paid submission"
    assert {row["id"] for row in source["fixtures"]} == {row["id"] for row in manifest["fixtures"]} == {row["id"] for row in attempts}
    assert attempts[0]["id"] == "hi-positive", "Hindi sample must precede batch"
    characters = sum(attempt["characters"] for attempt in attempts)
    estimates = round(sum(attempt["estimated_cost_usd"] for attempt in attempts), 4)
    assert characters <= 2000 and estimates <= 0.60
    assert characters == planned_characters == summary["submitted_characters"]
    assert estimates == planned_cost == costs["budget_spent_usd"]
    assert costs["budget_reserved_usd"] == 0 and len(costs["entries"]) == len(attempts)
    by_id = {attempt["id"]: attempt for attempt in attempts}
    inputs = {row["id"]: row for row in source["fixtures"]}
    case_ids = set()
    provider_character_cost = []
    audio_seconds = 0
    for fixture in manifest["fixtures"]:
        attempt = by_id[fixture["id"]]
        assert attempt["status"] == "validated"
        assert attempt["characters"] == len(fixture["text"])
        assert attempt["inputs"]["text"] == fixture["text"] == inputs[fixture["id"]]["text"]
        assert attempt["inputs"]["model_id"] == "eleven_v3"
        assert attempt["inputs"]["voice_id"] == "bajNon13EdhNMndG3z05"
        assert attempt["tool_result"]["success"] is True
        assert attempt["tool_result"]["data"]["cost_status"] == "estimated"
        assert len(attempt["http"]) == 1 and attempt["http"][0]["status_code"] == 200
        if "character-cost" in attempt["http"][0]:
            provider_character_cost.append(attempt["http"][0]["character-cost"])
        audio = Path(fixture["audio_path"])
        assert audio.is_absolute() and audio.is_relative_to(PROJECT / "assets/audio")
        assert sha256(audio) == fixture["sha256"]
        with wave.open(str(audio), "rb") as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
            duration = wav.getnframes() / 16000
        assert 0 < fixture["speech_end_s"] <= duration
        audio_seconds += duration
        alignment_path = Path(fixture["alignment_path"])
        assert sha256(alignment_path) == fixture["alignment_sha256"]
        alignment = read(alignment_path)["alignment"]
        last = max(i for i, character in enumerate(alignment["characters"]) if character.strip())
        raw_end = alignment["character_end_times_seconds"][last]
        assert fixture["speech_end_raw_alignment_s"] == raw_end
        assert raw_end <= duration + 0.005
        assert fixture["speech_end_s"] == min(raw_end, duration)
        qa = read(Path(fixture["qa_path"]))
        assert qa["sha256"] == fixture["sha256"] and qa["status"] == "passed"
        assert qa["full_scale_fraction"] < 0.01
    for case in manifest["cases"]:
        assert case["id"] not in case_ids
        case_ids.add(case["id"])
        assert isinstance(case["request"], str) and case["request"]
        assert set(case["expected"]) == {"alert", "token", "location", "voice_stop", "correction"}
        assert all(isinstance(case["expected"][field], bool) for field in ("alert", "voice_stop", "correction"))
        assert all(step["fixture_id"] in by_id and step["silence_after_s"] >= 0 for step in case["sequence"])
        if case["kind"] in {"positive", "burst"}:
            assert case["expected"]["alert"] and case["expected"]["token"] == "442" and case["expected"]["location"] == "counter 2"
        elif case["kind"] == "request":
            assert case["id"] in {"hi-request", "ml-request"} and case["mode"] == "request"
            assert case["sequence"] == [{"fixture_id": case["id"], "silence_after_s": 2.0}]
            assert case["expected"] == {"alert": False, "token": "442", "location": None, "voice_stop": False, "correction": False}
        else:
            assert not case["expected"]["alert"] and case["expected"]["token"] is None and case["expected"]["location"] is None
    for language in ("hi", "ml", "ta", "te", "mr", "en"):
        assert {"positive", "near-miss", "voice-stop", "burst"} <= {case["kind"] for case in manifest["cases"] if case["language"] == language}
    report = {
        "status": "passed", "network_calls": 0, "fixtures": len(manifest["fixtures"]), "cases": len(manifest["cases"]),
        "submitted_unicode_characters": characters, "estimated_cost_usd": estimates, "cost_status": "estimated",
        "total_audio_duration_s": round(audio_seconds, 6), "http_200_responses": len(attempts),
        "provider_character_cost_header_count": len(provider_character_cost),
        "provider_character_cost_header_sum": sum(provider_character_cost),
        "provider_character_cost_note": "Exact response header values only; distinct from submitted Unicode count and not a USD invoice or remaining-quota measurement",
        "provider_confirmed_remaining_quota": None,
        "preserved_baselines": preserved_baselines,
        "request_cases": [case["id"] for case in manifest["cases"] if case["kind"] == "request"],
        "checks": ["manifest contract and case coverage", "source prompts unchanged", "approval decisions", "hard submission and estimated-cost caps", "no duplicate paid calls", "zero reserved budget", "approved model and voice in every attempt", "one HTTP 200 response per attempt", "WAV PCM format and duration", "SHA-256 audio and alignment integrity", "speech_end equals last non-whitespace aligned character bounded to WAV end within 5ms tolerance", "QA ledger consistency"],
        "listening_or_native_speaker_review": "not performed",
        "audit_script_path": str(Path(__file__).resolve()), "audit_script_sha256": sha256(Path(__file__)),
        "manifest_path": str(actual_manifest), "manifest_sha256": sha256(actual_manifest),
    }
    (ARTIFACTS / "audit_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
