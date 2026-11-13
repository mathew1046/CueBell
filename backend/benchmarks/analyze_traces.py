"""Summarize the real-provider sidecars produced by benchmarks/serve.py."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {"count": 0}

    def percentile(fraction):
        position = (len(ordered) - 1) * fraction
        low, high = math.floor(position), math.ceil(position)
        return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)

    return {
        "count": len(ordered),
        "p50": percentile(0.5),
        "p95": percentile(0.95),
        "max": round(ordered[-1], 3),
    }


def summarize(path: Path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    requests = [row for row in rows if row["event"] == "openai_request"]
    responses = [row for row in rows if row["event"] == "openai_response"]
    errors = [row for row in rows if row["event"] == "openai_error"]
    terminated_ids = {row["call_id"] for row in [*responses, *errors]}
    unfinished = [row for row in requests if row["call_id"] not in terminated_ids]
    streams = [row for row in rows if row["event"] == "gnani_stream_end"]
    transcripts = [
        row
        for row in rows
        if row["event"] == "gnani_message" and row["payload"].get("type") == "transcript"
    ]
    tokens = Counter()
    reference_cost = 0.0
    for row in responses:
        usage = row.get("usage") or {}
        details = usage.get("input_tokens_details") or {}
        output_details = usage.get("output_tokens_details") or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cached = details.get("cached_tokens", 0)
        written = details.get("cache_write_tokens", 0)
        tokens.update(
            input=input_tokens,
            output=output_tokens,
            cached_input=cached,
            cache_written_input=written,
            reasoning_output=output_details.get("reasoning_tokens", 0),
        )
        tier_multiplier = 2 if row.get("service_tier") in {"fast", "priority"} else 1
        reference_cost += (
            tier_multiplier
            * (
                max(input_tokens - cached - written, 0) * 0.10
                + cached * 0.01
                + written * 0.125
                + output_tokens * 0.50
            )
            / 1_000_000
        )
    stages = defaultdict(list)
    stages_with_errors = defaultdict(list)
    for row in rows:
        if row["event"] == "interpretation_end":
            stages[row["stage"]].append(row["elapsed_ms"])
        if row["event"] in {"interpretation_end", "interpretation_error"}:
            stages_with_errors[row["stage"]].append(row["elapsed_ms"])
    startup = [row for row in rows if row["event"] == "server_start"]
    return {
        "trace": str(path.resolve()),
        "settings": startup[-1]["settings"] if startup else None,
        "openai_requests_attempted": len(requests),
        "openai_responses": len(responses),
        "openai_errors": errors,
        "openai_error_types": dict(Counter(row["error_type"] for row in errors)),
        "openai_unfinished_requests": unfinished,
        "openai_response_ms": distribution([row["elapsed_ms"] for row in responses]),
        "openai_terminated_attempt_ms": distribution(
            [row["elapsed_ms"] for row in [*responses, *errors]]
        ),
        "openai_error_ms": distribution([row["elapsed_ms"] for row in errors]),
        "openai_response_statuses": dict(Counter(row.get("status") for row in responses)),
        "latency_population_note": (
            "Response latency includes returned SDK responses only, not failed or cancelled calls. "
            "Terminated-attempt latency includes recorded error durations. Unfinished calls are "
            "counted separately; no zero duration or successful outcome is imputed to them. "
            "A returned response does not by itself establish a valid task decision."
        ),
        "interpretation_ms": {name: distribution(values) for name, values in stages.items()},
        "interpretation_terminated_attempt_ms": {
            name: distribution(values) for name, values in stages_with_errors.items()
        },
        "returned_service_tiers": dict(Counter(row.get("service_tier") for row in responses)),
        "returned_models": dict(Counter(row.get("model") for row in responses)),
        "tokens": dict(tokens),
        "cached_input_share_of_recorded_responses": (
            round(tokens["cached_input"] / tokens["input"], 6) if tokens["input"] else None
        ),
        "openai_reference_cost_usd": round(reference_cost, 6),
        "cost_status": (
            "Estimate from published Luna rates and returned token usage, not an invoice; "
            "failed and cancelled calls may be billable without recorded usage. Cache shares "
            "describe these responses, not an isolated cold-cache experiment."
        ),
        "gnani_streams": len(streams),
        "gnani_audio_seconds": round(sum(row["audio_seconds"] for row in streams), 3),
        "gnani_connection_seconds": round(sum(row["elapsed_ms"] for row in streams) / 1000, 3),
        "gnani_provider_latency_ms": distribution(
            [
                row["payload"]["latency"]
                for row in transcripts
                if isinstance(row["payload"].get("latency"), (int, float))
            ]
        ),
        "gnani_transcripts": len(transcripts),
        "gnani_send_max_ms": max((row["send_max_ms"] for row in streams), default=None),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    # A glob plus an explicit argument must not bill the same evidence twice.
    summaries = [summarize(path) for path in dict.fromkeys(p.resolve() for p in args.traces)]
    result = {
        "variants": summaries,
        "total_openai_requests_attempted": sum(
            row["openai_requests_attempted"] for row in summaries
        ),
        "total_openai_error_count": sum(len(row["openai_errors"]) for row in summaries),
        "total_openai_unfinished_count": sum(
            len(row["openai_unfinished_requests"]) for row in summaries
        ),
        "total_gnani_connection_minutes": round(
            sum(row["gnani_connection_seconds"] for row in summaries) / 60, 3
        ),
        "total_openai_reference_cost_usd": round(
            sum(row["openai_reference_cost_usd"] for row in summaries), 6
        ),
        "limits": {"openai_requests": 600, "gnani_connection_minutes": 120},
        "quantile_method": "linear interpolation; small-sample p95 is descriptive only",
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
