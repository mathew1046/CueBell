"""Offline evidence joins, version pinning and outcome accounting regressions."""

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks import analyze_campaign as analysis


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def classifier(tmp_path):
    # Unit fixtures obey the same mandatory source-hash contract as archived runs.
    return analysis.load_classifier(
        {"client_sha256": digest(analysis.CURRENT_SCORER)}, tmp_path / "run.json"
    )[0]


def add_event(case, event, when):
    envelope = {"t": when, "event": event}
    case["events"].append(envelope)
    group = {
        "transcript": "transcripts",
        "observation": "observations",
        "alert": "alerts",
        "status": "statuses",
        "alert.corrected": "corrections",
    }.get(event["type"])
    if group:
        case.setdefault(group, []).append(envelope)
    if event["type"] == "alert" and case.get("t_first_alert") is None:
        case["t_first_alert"] = when
    return envelope


def replay(case_id="hi-correction"):
    case = {
        "case_id": case_id,
        "language": "hi",
        "mode": "monitor",
        "expected": {
            "alert": False,
            "token": "442",
            "location": None,
            "voice_stop": False,
            "correction": False,
        },
        "events": [],
        "transcripts": [],
        "observations": [],
        "alerts": [],
        "stream": {"t_finished": 10},
        "sender": {"full_window_sent": True},
        "source_speech_sent": True,
        "confirmation": {"type": "monitor.created"},
        "result": {"verdict": "pass", "checks": {}, "false_positive_any": False},
        "metrics": {},
        "errors": [],
        "t_start": 0,
        "t_end": 11,
        "t_speech_end": 3,
        "t_first_alert": None,
        "reference_text": "first last",
    }
    for text, when in [("first", 2), ("last", 4)]:
        add_event(
            case,
            {
                "type": "transcript",
                "segment": {"id": case_id + ":" + text, "text": text},
            },
            when,
        )
    return case


def inference(event, call_id, source, when, result=None):
    return {
        "event": event,
        "call_id": call_id,
        "source_ids": [source] if source else [],
        "monotonic_s": when,
        "result": result or {"events": []},
    }


def completed_trace(case, end=9):
    source = case["transcripts"][-1]["event"]["segment"]["id"]
    return [
        inference("interpretation_start", case["case_id"], source, 5),
        inference("interpretation_end", case["case_id"], source, end),
    ]


def add_alert(case, location, token="442"):
    case["expected"].update(alert=True, location="2")
    observation = {
        "id": case["case_id"] + "-observation",
        "type": "MATCH",
        "condition_met": True,
        "location": location,
        "source_segment_ids": [case["case_id"] + ":last"],
        "summary": "Token 442 called",
        "evidence_text": "source evidence",
        "state": "confirmed",
    }
    if token is not None:
        observation["identifiers"] = [{"value": token, "evidence_text": token}]
    add_event(case, {"type": "observation", "observation": observation}, 5)
    alert = {
        "id": case["case_id"] + "-alert",
        "observation_id": observation["id"],
        "state": "unacknowledged",
        "location": location,
        "summary": "Token 442 called",
    }
    add_event(case, {"type": "alert", "alert": alert}, 6)
    return alert


def write_run(tmp_path, cases, trace, monkeypatch):
    # Provider cost aggregation is owned/tested separately; this test is entirely offline.
    monkeypatch.setattr(analysis, "summarize", lambda path: {})
    manifest = tmp_path / "original-corpus.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": case["case_id"], "kind": "positive", "expected": {"token": "999"}}
                    for case in cases
                ]
            }
        )
    )
    for name, records in [("client.jsonl", cases), ("server.jsonl", trace)]:
        (tmp_path / name).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records))
    run = {
        "label": "offline",
        "configuration": {},
        "manifest": manifest.name,
        "manifest_sha256": digest(manifest),
        "client_sha256": digest(analysis.CURRENT_SCORER),
        "client_results": "client.jsonl",
        "server_trace": "server.jsonl",
    }
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run))
    return path


@pytest.mark.parametrize("end_time,expected", [(9, "pass"), (11, "inconclusive")])
def test_latest_interpretation_must_complete_inside_client_window(classifier, end_time, expected):
    case = replay()
    result = analysis.inspect_case(case, completed_trace(case, end_time), classifier=classifier)
    assert result["audited_verdict"] == expected
    assert result["client_verdict"] == "pass"


def test_earlier_completed_segment_does_not_prove_later_correction_was_processed(classifier):
    case = replay()
    trace = [
        inference("interpretation_start", "a", "hi-correction:first", 2.1),
        inference("interpretation_end", "a", "hi-correction:first", 3),
        inference("interpretation_start", "b", "hi-correction:last", 4.1),
    ]
    result = analysis.inspect_case(case, trace, classifier=classifier)
    assert result["audited_verdict"] == "inconclusive"
    assert not result["latest_interpretation_completed_in_window"]


def test_observed_false_alert_overrides_missing_final_completion_and_stored_verdict(classifier):
    case = replay()
    add_alert(case, "2", "443")
    case["result"].update(verdict="pass", false_positive_any=False)
    result = analysis.inspect_case(case, [], classifier=classifier)
    assert result["audited_verdict"] == "fail"
    assert result["false_positive_any"]
    assert result["client_verdict"] == "pass"


def test_spoken_setup_keeps_combined_text_even_without_a_monitor_segment_id(classifier):
    case = replay()
    case.update(mode="request", events=[], transcripts=[], reference_text="काउंटर दो।")
    add_event(case, {"type": "transcript", "segment": {"text": "काउंटर दो"}}, 5)
    case["intent_response"] = {
        "status": "confirm",
        "intent": {"task": {"identifiers": [{"value": "442"}]}},
    }
    result = analysis.inspect_case(case, [], "request", classifier=classifier)
    assert result["audited_verdict"] == "pass"
    assert result["latest_interpretation_completed_in_window"] is None
    assert result["asr_text_errors"]["wer_percent"] == 0
    assert result["transcripts"] == ["काउंटर दो"]


def test_counter_defects_only_count_emitted_alerts_and_keep_unknown_targets(tmp_path, monkeypatch):
    absent = replay("absent")
    absent["expected"].update(alert=True, location="2")
    absent["status"] = "provider_degraded"
    add_event(absent, {"type": "status", "state": "DEGRADED"}, 8)
    wrong = replay("wrong")
    alert = add_alert(wrong, "3")
    add_event(wrong, {"type": "alert.corrected", "alert": {**alert, "state": "corrected"}}, 8)
    unknown = replay("unknown")
    add_alert(unknown, None, token=None)
    wrong_target = replay("wrong-target")
    add_alert(wrong_target, "2", token="443")
    cases = [absent, wrong, unknown, wrong_target]
    trace = [row for case in cases for row in completed_trace(case)]
    result = analysis.analyze_run(write_run(tmp_path, cases, trace, monkeypatch))
    assert result["wrong_location_cases"] == 1
    assert result["missing_location_cases"] == 1
    assert result["terminal_wrong_location_cases"] == 0
    assert result["terminal_missing_location_cases"] == 1
    assert result["unknown_target_cases"] == 1
    assert result["false_positive_cases"] == 1  # Wrong target, not wrong/missing counter.
    by_id = {case["case_id"]: case for case in result["cases"]}
    assert by_id["absent"]["checks"]["location"] is False
    assert not by_id["absent"]["counter_defects"]["initial"]["wrong_alert_ids"]
    assert by_id["unknown"]["initial_alert_evaluations"][0]["target"] is None
    assert not by_id["unknown"]["false_positive_any"]


@pytest.mark.parametrize(
    "case_id,end,observed,later,alert,expected_ms",
    [
        ("ta-burst", 2502.361994703, 2502.363433905, 2507.904514324, 2508.018985340, 5656.990637),
        ("en-burst", 2849.587982414, 2849.588526972, 2852.982923674, 2853.085389212, 3497.406798),
    ],
)
def test_burst_alert_latency_joins_its_extraction_not_later_empty_result(
    classifier,
    case_id,
    end,
    observed,
    later,
    alert,
    expected_ms,
):
    # Timings are frozen from completed full-v1-baseline; no campaign files/providers needed.
    case = replay(case_id)
    add_alert(case, "3" if case_id == "ta-burst" else None)
    case["observations"][0]["t"] = observed
    case["alerts"][0]["t"] = case["t_first_alert"] = alert
    case["stream"]["t_finished"] = alert + 1
    observation = case["observations"][0]["event"]["observation"]
    extracted = {key: value for key, value in observation.items() if key not in {"id", "state"}}
    source = observation["source_segment_ids"][0]
    trace = [
        inference("interpretation_start", "cause", source, end - 1),
        inference("interpretation_end", "cause", source, end, {"events": [extracted]}),
        inference("interpretation_start", "later", source, observed + 0.1),
        inference("interpretation_end", "later", source, later),
    ]
    result = analysis.inspect_case(case, trace, classifier=classifier)
    assert result["metrics"]["causal_model_end_to_first_alert_ms"] == pytest.approx(expected_ms)
    assert result["alert_model_completions"][0]["call_id"] == "cause"
    noncausal = result["metrics"]["last_completed_interpretation_to_first_alert_ms_noncausal"]
    assert noncausal == pytest.approx((alert - later) * 1000)
    assert noncausal < 115
    assert "last_model_end_to_first_alert_ms" not in result["metrics"]


@pytest.mark.parametrize(
    "problem",
    [
        "different_source",
        "different_extraction",
        "partial_extraction",
        "ambiguous",
    ],
)
def test_causal_join_does_not_guess_from_partial_or_ambiguous_matches(classifier, problem):
    case = replay()
    add_alert(case, "2")
    observation = case["observations"][0]["event"]["observation"]
    extracted = {key: value for key, value in observation.items() if key not in {"id", "state"}}
    source = observation["source_segment_ids"][0]
    if problem == "different_source":
        extracted["source_segment_ids"] = ["other:last"]
    elif problem == "different_extraction":
        extracted["identifiers"] = [{"value": "443", "evidence_text": "443"}]
    elif problem == "partial_extraction":
        extracted = {"type": "MATCH", "source_segment_ids": [source]}
    trace = [
        inference("interpretation_start", "a", source, 4.1),
        inference("interpretation_end", "a", source, 4.5, {"events": [extracted]}),
    ]
    if problem == "ambiguous":
        trace += [
            inference("interpretation_start", "b", source, 4.2),
            inference("interpretation_end", "b", source, 4.8, {"events": [extracted]}),
        ]
    result = analysis.inspect_case(case, trace, classifier=classifier)
    assert result["metrics"]["causal_model_end_to_first_alert_ms"] is None
    assert result["alert_model_completions"][0]["status"] == (
        "ambiguous" if problem == "ambiguous" else "unmatched"
    )


def test_error_totals_distinguish_degradation_interpretation_errors_and_client_timeouts(
    tmp_path,
    monkeypatch,
):
    provider = replay("provider")
    add_event(provider, {"type": "status", "state": "DEGRADED"}, 8)
    client = replay("client")
    client["status"] = "timeout"
    client["errors"] = [{"kind": "TimeoutError", "message": "stream deadline"}]
    setup = replay("setup")
    setup.update(
        mode="request",
        intent_response={},
        http=[
            {
                "path": "/v1/intent",
                "t_start": 5,
                "t_end": 8,
            }
        ],
    )
    trace = [
        inference("interpretation_start", "p", "provider:last", 5),
        inference("interpretation_error", "p", "provider:last", 7),
        {**inference("interpretation_start", "s", None, 6), "stage": "intent"},
        {**inference("interpretation_error", "s", None, 7), "stage": "intent"},
    ]
    path = write_run(tmp_path, [provider, client, setup], trace, monkeypatch)
    result = analysis.analyze_run(path)
    assert result["provider_degraded_case_count"] == 1
    assert result["interpretation_error_count"] == 2
    assert result["interpretation_error_case_count"] == 2
    assert result["client_exception_count"] == result["client_exception_case_count"] == 1
    assert result["client_timeout_count"] == result["client_timeout_case_count"] == 1
    assert result["cases"][0]["errors"] == []
    assert result["cases"][0]["interpretation_errors"]


def test_uniform_rescoring_uses_embedded_labels_and_records_reproduction_hashes(
    tmp_path,
    monkeypatch,
):
    plain = replay("plain")
    plain["result"]["verdict"] = "fail"  # Historical result is deliberately stale.
    reviewed = replay("te-positive")
    add_alert(reviewed, "కౌంటర్. రెండుకు")
    reviewed["result"]["verdict"] = "fail"
    trace = completed_trace(plain) + completed_trace(reviewed)
    path = write_run(tmp_path, [plain, reviewed], trace, monkeypatch)
    original_bytes = (tmp_path / "client.jsonl").read_bytes()
    review = {"te-positive": {"location_aliases_add": ["కౌంటర్. రెండుకు"]}}
    result = analysis.analyze_run(path, review)
    assert result["verdicts"] == {"pass": 2}
    assert result["client_verdicts"] == {"fail": 2}
    assert result["cases"][0]["rescored_verdict"] == "pass"
    assert result["cases"][1]["expected"]["token"] == "442"  # Manifest's 999 is ignored.
    assert "location_aliases" not in result["cases"][1]["expected"]
    assert result["cases"][1]["evaluated_expected"]["location_aliases"] == ["కౌంటర్. రెండుకు"]
    provenance = result["provenance"]
    assert provenance["scorer"]["sha256"] == digest(analysis.CURRENT_SCORER)
    assert provenance["manifest"]["sha256"] == digest(tmp_path / "original-corpus.json")
    assert provenance["analysis"]["sha256"] == digest(Path(analysis.__file__))
    assert provenance["client_results_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert (tmp_path / "client.jsonl").read_bytes() == original_bytes
    cohort = result["by_kind"]["positive"]["passing_case_latencies_ms"]
    assert "causal_model_end_to_first_alert_ms" in cohort
    assert "last_completed_interpretation_to_first_alert_ms_noncausal" not in cohort


@pytest.mark.parametrize("primary_state", ["missing", "changed"])
def test_manifest_fallback_requires_matching_captured_bytes(tmp_path, monkeypatch, primary_state):
    case = replay()
    path = write_run(tmp_path, [case], completed_trace(case), monkeypatch)
    primary = tmp_path / "original-corpus.json"
    captured = tmp_path / "corpus.json"
    captured.write_bytes(primary.read_bytes())
    if primary_state == "missing":
        primary.unlink()
    else:
        primary.write_text('{"cases": []}')
    result = analysis.analyze_run(path)
    assert result["provenance"]["manifest"]["path"] == str(captured)
    assert result["provenance"]["manifest"]["fallback_used"]
    captured.write_text("{}")
    with pytest.raises(ValueError, match="No verified manifest source"):
        analysis.analyze_run(path)


def test_classifier_falls_back_to_verified_archive_and_never_trusts_stale_cache(
    tmp_path,
    monkeypatch,
):
    live = tmp_path / "live.py"
    live.write_text("raise AssertionError('unverified source must not execute')\n")
    monkeypatch.setattr(analysis, "CURRENT_SCORER", live)
    monkeypatch.setattr(analysis, "ARCHIVED_HARNESS", tmp_path / "unavailable")
    pinned = tmp_path / "source/benchmark-harness-v1/run_pipeline.py"
    pinned.parent.mkdir(parents=True)
    pinned.write_text('def classify_result(record):\n    return {"verdict": "archived"}\n')
    run = {"client_sha256": digest(pinned)}
    classifier, metadata = analysis.load_classifier(run, tmp_path / "run.json")
    assert classifier({}) == {"verdict": "archived"}
    assert metadata["path"] == str(pinned)
    assert metadata["fallback_used"]
    pinned.write_text("# changed after loading\n")
    with pytest.raises(ValueError, match="No verified classifier source"):
        analysis.load_classifier(run, tmp_path / "run.json")


@pytest.mark.parametrize("field", ["manifest_sha256", "client_sha256"])
def test_missing_source_hashes_are_rejected_even_for_small_runs(tmp_path, monkeypatch, field):
    case = replay()
    path = write_run(tmp_path, [case], completed_trace(case), monkeypatch)
    run = json.loads(path.read_text())
    del run[field]
    path.write_text(json.dumps(run))
    with pytest.raises(ValueError, match="Run metadata must provide a valid .* SHA-256"):
        analysis.analyze_run(path)


def test_transcription_metrics_preserve_number_word_differences():
    result = analysis.text_error_rates("Token forty two, counter 2.", "token 42 counter 2")
    assert result["reference_words"] == 5
    assert result["word_edits"] == 2
    assert result["wer_percent"] == 40


def test_unicode_transcription_and_missing_speech():
    assert analysis.text_error_rates("काउंटर दो।", "काउंटर दो")["wer_percent"] == 0
    assert analysis.text_error_rates("é", "e\u0301")["cer_percent"] == 0
    result = analysis.text_error_rates("കൗണ്ടർ രണ്ടിലേക്ക്", "")
    assert result["wer_percent"] == 100
    assert result["cer_percent"] == 100
