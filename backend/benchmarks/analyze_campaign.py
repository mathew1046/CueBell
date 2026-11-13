"""Join replay outcomes to provider traces without changing the raw evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

if __package__:
    from .analyze_traces import distribution, summarize
else:
    from analyze_traces import distribution, summarize


CURRENT_SCORER = Path(__file__).with_name("run_pipeline.py")
ARCHIVE_SUBDIRECTORY = Path("source/benchmark-harness-v1")
ARCHIVED_HARNESS = (
    Path(__file__).resolve().parents[2] / "docs/benchmarks/2026-11-13" / ARCHIVE_SUBDIRECTORY
)
Classifier = Callable[[dict], dict]


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def rows(content: bytes) -> list[dict]:
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def relative_to_run(value: str | Path, run_path: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else run_path.parent / path


def verified_source(
    candidates: Sequence[Path], expected: str | None, name: str
) -> tuple[bytes, dict]:
    """Read once, verify those exact bytes, and explain rejected archive candidates."""
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in expected)
    ):
        raise ValueError(f"Run metadata must provide a valid {name} SHA-256")
    expected = expected.lower()
    rejected = []
    for path in dict.fromkeys(path.resolve() for path in candidates):
        try:
            content = path.read_bytes()
        except OSError as exc:
            rejected.append({"path": str(path), "reason": str(exc)})
            continue
        actual = sha256(content)
        if actual != expected:
            rejected.append({"path": str(path), "sha256": actual, "reason": "SHA-256 mismatch"})
            continue
        return content, {
            "path": str(path),
            "sha256": actual,
            "expected_sha256": expected,
            "fallback_used": bool(rejected),
            "rejected_candidates": rejected,
        }
    raise ValueError(
        f"No verified {name} source for SHA-256 {expected}: "
        + "; ".join(f"{item['path']}: {item['reason']}" for item in rejected)
    )


def load_classifier(run: dict, run_path: Path) -> tuple[Classifier, dict]:
    content, metadata = verified_source(
        [
            CURRENT_SCORER,
            run_path.parent / ARCHIVE_SUBDIRECTORY / "run_pipeline.py",
            ARCHIVED_HARNESS / "run_pipeline.py",
        ],
        run.get("client_sha256"),
        "classifier",
    )
    name = "_cuebell_verified_classifier_" + metadata["sha256"]
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__file__ = metadata["path"]
        module.__package__ = ""
        # Dataclasses resolve their module during execution. Never execute a second,
        # unverified disk read, or run the client's __main__ campaign entry point.
        sys.modules[name] = module
        try:
            exec(compile(content, metadata["path"], "exec"), module.__dict__)
        except Exception as exc:
            sys.modules.pop(name, None)
            raise ValueError(f"Cannot load verified classifier {metadata['path']}: {exc}") from exc
    classifier = getattr(module, "classify_result", None)
    if not callable(classifier):
        raise ValueError(f"Verified classifier {metadata['path']} has no classify_result function")
    return classifier, metadata


def load_manifest(run: dict, run_path: Path) -> tuple[dict, dict]:
    primary = run.get("manifest") or run.get("summary", {}).get("manifest")
    primary_path = (
        relative_to_run(primary, run_path) if primary else CURRENT_SCORER.with_name("corpus.json")
    )
    content, metadata = verified_source(
        [
            primary_path,
            run_path.parent / "corpus.json",
            run_path.parent / ARCHIVE_SUBDIRECTORY / "corpus.json",
            ARCHIVED_HARNESS / "corpus.json",
        ],
        run.get("manifest_sha256"),
        "manifest",
    )
    return json.loads(content), metadata


def counter_defects(evaluations: list[dict], expected: dict) -> dict:
    """Counter evidence is independent of target evidence; unknown is never False."""
    return {
        "wrong_alert_ids": [
            item["id"]
            for item in evaluations
            if expected.get("location") is not None and item.get("location") is False
        ],
        "missing_alert_ids": [
            item["id"]
            for item in evaluations
            if expected.get("location") is not None and item.get("location") is None
        ],
        "unknown_target_alert_ids": [
            item["id"] for item in evaluations if item.get("target") is None
        ],
    }


def alert_model_completion(alert: dict, observations: list[dict], ended: list[dict]) -> dict:
    """Join the emitted observation to an exact extraction, never merely the latest call."""
    payload = alert["event"]["alert"]
    result = {
        "alert_id": payload.get("id"),
        "observation_id": payload.get("observation_id"),
        "alert_t": alert["t"],
        "status": "missing_observation",
        "source_segment_ids": [],
        "candidate_call_ids": [],
        "call_id": None,
        "model_end_t": None,
        "elapsed_ms": None,
    }
    observed = [
        item
        for item in observations
        if payload.get("observation_id") is not None
        and item["event"].get("observation", {}).get("id") == payload["observation_id"]
        and item["t"] <= alert["t"]
    ]
    if len(observed) != 1:
        if observed:
            result["status"] = "ambiguous_observation"
        return result
    observation = observed[0]["event"]["observation"]
    source_ids = observation.get("source_segment_ids")
    if not source_ids:
        result["status"] = "missing_source_ids"
        return result
    result["source_segment_ids"] = source_ids
    matches = []
    for row in ended:
        if row["monotonic_s"] > observed[0]["t"] or not set(source_ids).issubset(
            row.get("source_ids", [])
        ):
            continue
        for extracted in row.get("result", {}).get("events", []):
            if (
                extracted.get("source_segment_ids") != source_ids
                or not extracted.get("type")
                or extracted["type"] != observation.get("type")
                or (extracted.get("id") is not None and extracted["id"] != observation["id"])
            ):
                continue
            # The relay adds these fields after extraction. Everything else in the
            # event must agree in both directions, including identifiers and evidence.
            runtime_fields = {"id", "at", "state", "monitor_id"}
            extracted_fields = {
                key: value for key, value in extracted.items() if key not in runtime_fields
            }
            observed_fields = {
                key: value for key, value in observation.items() if key not in runtime_fields
            }
            if extracted_fields == observed_fields:
                matches.append(row)
                break
    result["candidate_call_ids"] = [row["call_id"] for row in matches]
    result["status"] = "matched" if len(matches) == 1 else "ambiguous" if matches else "unmatched"
    if len(matches) == 1:
        result.update(
            call_id=matches[0]["call_id"],
            model_end_t=matches[0]["monotonic_s"],
            elapsed_ms=(alert["t"] - matches[0]["monotonic_s"]) * 1000,
        )
    return result


def edit_distance(reference, hypothesis) -> int:
    previous = list(range(len(hypothesis) + 1))
    for index, expected in enumerate(reference, 1):
        current = [index]
        for position, observed in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[position] + 1,
                    previous[position - 1] + (expected != observed),
                )
            )
        previous = current
    return previous[-1]


def text_error_rates(reference: str, hypothesis: str) -> dict:
    def normalize(text):
        text = unicodedata.normalize("NFKC", text).casefold()
        return " ".join(
            "".join(c for c in text if not unicodedata.category(c).startswith("P")).split()
        )

    reference, hypothesis = normalize(reference), normalize(hypothesis)
    ref_words, hyp_words = reference.split(), hypothesis.split()
    ref_chars, hyp_chars = reference.replace(" ", ""), hypothesis.replace(" ", "")
    word_edits = edit_distance(ref_words, hyp_words)
    char_edits = edit_distance(ref_chars, hyp_chars)
    return {
        "reference_words": len(ref_words),
        "word_edits": word_edits,
        "wer_percent": 100 * word_edits / len(ref_words) if ref_words else None,
        "reference_characters": len(ref_chars),
        "character_edits": char_edits,
        "cer_percent": 100 * char_edits / len(ref_chars) if ref_chars else None,
    }


def inspect_case(
    case: dict,
    trace: list[dict],
    kind: str = "unclassified",
    adjudication: dict | None = None,
    *,
    classifier: Classifier,
) -> dict:
    finals = [
        envelope
        for envelope in case.get("transcripts", [])
        if isinstance(envelope["event"].get("segment", {}).get("text"), str)
        and envelope["event"].get("is_final") is not False
        and envelope["event"]["segment"].get("is_final") is not False
    ]
    source_ids = {
        item["event"]["segment"]["id"] for item in finals if item["event"]["segment"].get("id")
    }
    latest = finals[-1]["event"]["segment"].get("id") if finals else None
    starts = {
        row["call_id"]: row
        for row in trace
        if row["event"] == "interpretation_start"
        and source_ids.intersection(row.get("source_ids", []))
    }
    ended = [
        row for row in trace if row["event"] == "interpretation_end" and row["call_id"] in starts
    ]
    # Spoken/typed setup has no transcript source IDs. Associate its errors using
    # the recorded intent HTTP window, without mixing them into monitor completion.
    intent_windows = [
        item
        for item in case.get("http", [])
        if item.get("path") == "/v1/intent" and "t_start" in item and "t_end" in item
    ]
    intent_calls = {
        row["call_id"]
        for row in trace
        if row["event"] == "interpretation_start"
        and row.get("stage") == "intent"
        and any(item["t_start"] <= row["monotonic_s"] <= item["t_end"] for item in intent_windows)
    }
    errors = [
        row
        for row in trace
        if row["event"] == "interpretation_error" and row["call_id"] in starts.keys() | intent_calls
    ]
    finish = case.get("stream", {}).get("t_finished", float("inf"))
    completed_latest = (
        any(
            row.get("source_ids")
            and row["source_ids"][-1] == latest
            and row["monotonic_s"] <= finish
            for row in ended
        )
        if latest
        else False
    )
    expected = dict(case["expected"])
    if adjudication:
        expected["location_aliases"] = [
            *expected.get("location_aliases", []),
            *adjudication.get("location_aliases_add", []),
        ]
    # Every case uses the same hash-verified scorer, even without a label review.
    scored = classifier({**case, "expected": expected})
    verdict = scored["verdict"]
    if scored.get("false_positive_any"):
        verdict = "fail"  # An observed false alert is evidence even after a transport failure.
    elif case["mode"] == "monitor" and not completed_latest:
        verdict = "inconclusive"

    metrics = dict(case["metrics"])
    speech_end = case.get("t_speech_end")
    metrics["speech_end_to_last_final_ms"] = (
        (finals[-1]["t"] - speech_end) * 1000 if finals and speech_end is not None else None
    )
    # All these processes run on one Linux host and share CLOCK_MONOTONIC.
    # Do not apply this subtraction between a phone clock and a remote server clock.
    newest_start = next(
        (
            row
            for row in starts.values()
            if row.get("source_ids") and row["source_ids"][-1] == latest
        ),
        None,
    )
    provider_final = next(
        (
            row
            for row in trace
            if row["event"] == "gnani_message"
            and row.get("payload", {}).get("type") == "transcript"
            and latest
            and latest.endswith(":" + str(row["payload"].get("segment_id")))
            and case.get("t_start", float("-inf")) <= row["monotonic_s"] <= finals[-1]["t"]
        ),
        None,
    )
    metrics["latest_segment_queue_ms"] = (
        (newest_start["monotonic_s"] - provider_final["monotonic_s"]) * 1000
        if newest_start and provider_final
        else None
    )
    alert_time = case.get("t_first_alert")
    before_alert = [
        row for row in ended if alert_time is not None and row["monotonic_s"] <= alert_time
    ]
    metrics.pop("last_model_end_to_first_alert_ms", None)
    metrics["last_completed_interpretation_to_first_alert_ms_noncausal"] = (
        (alert_time - max(row["monotonic_s"] for row in before_alert)) * 1000
        if before_alert
        else None
    )
    alert_completions = [
        alert_model_completion(item, case.get("observations", []), ended)
        for item in case.get("alerts", [])
    ]
    metrics["causal_model_end_to_first_alert_ms"] = (
        alert_completions[0]["elapsed_ms"] if alert_completions else None
    )
    initial_evaluations = scored.get("initial_alert_evaluations", [])
    emitted_ids = {item["id"] for item in initial_evaluations}
    terminal_evaluations = [
        item for item in scored.get("terminal_alert_evaluations", []) if item["id"] in emitted_ids
    ]
    ambiguities = Counter(
        item["event"]["observation"]["ambiguity_reason"]
        for item in case.get("observations", [])
        if item["event"].get("observation", {}).get("ambiguity_reason")
    )
    return {
        "case_id": case["case_id"],
        "repetition": case.get("repetition", 1),
        "run_id": case.get("run_id"),
        "language": case["language"],
        "kind": kind,
        "mode": case["mode"],
        "expected": case["expected"],
        "evaluated_expected": expected,
        "client_verdict": case["result"]["verdict"],
        "rescored_verdict": scored["verdict"],
        "label_review_verdict": scored["verdict"],
        "label_review": adjudication,
        "audited_verdict": verdict,
        "latest_interpretation_completed_in_window": (
            completed_latest if case["mode"] == "monitor" else None
        ),
        "completed_interpretations": len(ended),
        "interpretation_errors": errors,
        "provider_degraded": bool(
            scored.get("degraded") or case.get("status") == "provider_degraded"
        ),
        "client_exception_count": len(case.get("errors", [])),
        "client_timeout_count": sum(
            "timeout" in str(error.get("kind", error.get("type", ""))).casefold()
            for error in case.get("errors", [])
        ),
        "status": case.get("status"),
        "checks": scored["checks"],
        "initial_alert_evaluations": initial_evaluations,
        "terminal_alert_evaluations": terminal_evaluations,
        "counter_defects": {
            "initial": counter_defects(initial_evaluations, expected),
            "terminal": counter_defects(terminal_evaluations, expected),
        },
        "alert_model_completions": alert_completions,
        "false_positive_any": scored.get("false_positive_any", False),
        "false_positive_terminal": scored.get("false_positive_terminal", False),
        "semantic_correction_observed": scored.get("correction_observed", False),
        "retraction_observed": scored.get("retraction_observed", False),
        "voice_stop_observed": scored.get("voice_stop_observed", False),
        "ambiguity_reasons": dict(ambiguities),
        "asr_text_errors": text_error_rates(
            case.get("reference_text", ""),
            " ".join(item["event"]["segment"]["text"] for item in finals),
        ),
        "metrics": metrics,
        "transcripts": [item["event"]["segment"]["text"] for item in finals],
        "errors": case.get("errors", []),
    }


def analyze_run(path: Path, adjudications: dict | None = None) -> dict:
    path = path.resolve()
    run_bytes = path.read_bytes()
    run = json.loads(run_bytes)
    classifier, scorer_metadata = load_classifier(run, path)
    manifest, manifest_metadata = load_manifest(run, path)
    # Expected labels always come from each captured replay, not the manifest.
    kind_by_case = {case["id"]: case.get("kind", "unclassified") for case in manifest["cases"]}
    trace_path = relative_to_run(run["server_trace"], path)
    trace_bytes = trace_path.read_bytes()
    client_bytes = relative_to_run(run["client_results"], path).read_bytes()
    trace = rows(trace_bytes)
    cases = [
        inspect_case(
            case,
            trace,
            kind_by_case.get(case["case_id"], "unclassified"),
            (adjudications or {}).get(case["case_id"]),
            classifier=classifier,
        )
        for case in rows(client_bytes)
    ]
    metrics = {}
    for kind in sorted({case["kind"] for case in cases}):
        cohort = [case for case in cases if case["kind"] == kind]
        successful = [case for case in cohort if case["audited_verdict"] == "pass"]
        metrics[kind] = {
            "count": len(cohort),
            "verdicts": dict(Counter(case["audited_verdict"] for case in cohort)),
            "passing_case_latencies_ms": {
                name: distribution(
                    [
                        case["metrics"][name]
                        for case in successful
                        if isinstance(case["metrics"].get(name), (int, float))
                    ]
                )
                for name in (
                    "speech_end_to_alert_ms",
                    "speech_end_to_last_final_ms",
                    "speech_end_to_voice_stop_ms",
                    "speech_end_to_confirmation_ms",
                    "latest_segment_queue_ms",
                    "causal_model_end_to_first_alert_ms",
                )
            },
        }
    return {
        "label": run["label"],
        "configuration": run["configuration"],
        "provenance": {
            "analysis": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256(Path(__file__).read_bytes()),
            },
            "scorer": scorer_metadata,
            "manifest": manifest_metadata,
            "run_metadata_sha256": sha256(run_bytes),
            "client_results_sha256": sha256(client_bytes),
            "server_trace_sha256": sha256(trace_bytes),
            "adjudications_sha256": sha256(
                json.dumps(adjudications or {}, sort_keys=True, ensure_ascii=False).encode()
            ),
        },
        "case_count": len(cases),
        "verdicts": dict(Counter(case["audited_verdict"] for case in cases)),
        "client_verdicts": dict(Counter(case["client_verdict"] for case in cases)),
        "false_positive_cases": sum(case["false_positive_any"] for case in cases),
        "terminal_false_positive_cases": sum(case["false_positive_terminal"] for case in cases),
        "wrong_location_cases": sum(
            bool(case["counter_defects"]["initial"]["wrong_alert_ids"]) for case in cases
        ),
        "missing_location_cases": sum(
            bool(case["counter_defects"]["initial"]["missing_alert_ids"]) for case in cases
        ),
        "terminal_wrong_location_cases": sum(
            bool(case["counter_defects"]["terminal"]["wrong_alert_ids"]) for case in cases
        ),
        "terminal_missing_location_cases": sum(
            bool(case["counter_defects"]["terminal"]["missing_alert_ids"]) for case in cases
        ),
        "unknown_target_cases": sum(
            bool(case["counter_defects"]["initial"]["unknown_target_alert_ids"]) for case in cases
        ),
        "terminal_unknown_target_cases": sum(
            bool(case["counter_defects"]["terminal"]["unknown_target_alert_ids"]) for case in cases
        ),
        "provider_degraded_case_count": sum(case["provider_degraded"] for case in cases),
        "interpretation_error_count": sum(row["event"] == "interpretation_error" for row in trace),
        "interpretation_error_case_count": sum(
            bool(case["interpretation_errors"]) for case in cases
        ),
        "client_exception_count": sum(case["client_exception_count"] for case in cases),
        "client_exception_case_count": sum(bool(case["client_exception_count"]) for case in cases),
        "client_timeout_count": sum(case["client_timeout_count"] for case in cases),
        "client_timeout_case_count": sum(
            bool(case["client_timeout_count"]) or case["status"] in {"timeout", "timed_out"}
            for case in cases
        ),
        "asr_text_errors": {
            field: sum(case["asr_text_errors"][field] for case in cases)
            for field in (
                "reference_words",
                "word_edits",
                "reference_characters",
                "character_edits",
            )
        },
        "by_kind": metrics,
        "provider": summarize(trace_path),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    adjudications = json.loads(args.adjudications.read_text()) if args.adjudications else {}
    try:
        runs = [analyze_run(path, adjudications.get("cases", {})) for path in args.runs]
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    result = {
        "runs": runs,
        "adjudications": adjudications,
        "method": (
            "Raw replay records are unchanged. Monitor passes additionally require the latest "
            "transcript's interpretation to finish before the replay observation window closes. "
            "Observed false-alert exposure always fails. Latency cohorts retain their denominators "
            "and include only passing cases; do not compare conditional speed without pass rates. "
            "Multi-utterance first-final timing is not pooled with single-announcement ASR latency."
            " WER/CER use NFKC, casefold, punctuation removal and whitespace normalization; "
            "number words are not converted to digits. CER counts Unicode code points excluding "
            "spaces, not grapheme clusters. Task-level target/counter accuracy remains primary."
            " Optional explicit label reviews are applied uniformly; original client verdicts "
            "and the review reasons remain in each case. Every case is re-scored with a classifier "
            "verified against the run's client SHA-256; manifest bytes are also hash-verified. "
            "Wrong/missing counters count emitted initial alerts, with terminal counts separate; "
            "no alert is not a counter defect. Unknown targets remain unknown, independently of "
            "counter defects and unexpected/wrong-target exposure. Causal model-to-alert latency "
            "requires an unambiguous observation/source-ID/extraction-result join. The separately "
            "named noncausal last-completion interval is excluded from latency cohorts. Provider "
            "degradation, interpretation errors and client exceptions/timeouts are separate counts."
        ),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for run in result["runs"]:
        positive = run["by_kind"].get("positive", {}).get("passing_case_latencies_ms", {})
        latency = positive.get("speech_end_to_alert_ms", {})
        print(
            json.dumps(
                {
                    "label": run["label"],
                    "cases": run["case_count"],
                    "verdicts": run["verdicts"],
                    "positive_alert_ms": latency,
                    "false_positive_cases": run["false_positive_cases"],
                }
            )
        )


if __name__ == "__main__":
    main()
