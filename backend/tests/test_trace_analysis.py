import json

from benchmarks.analyze_traces import summarize


def test_failed_and_cancelled_attempts_are_not_reported_as_fast_successes(tmp_path):
    trace = tmp_path / "trace.jsonl"
    records = [
        {"event": "openai_request", "call_id": "returned"},
        {
            "event": "openai_response",
            "call_id": "returned",
            "elapsed_ms": 1000,
            "status": "completed",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 10,
                "input_tokens_details": {"cached_tokens": 80, "cache_write_tokens": 10},
            },
        },
        {"event": "openai_request", "call_id": "timed-out"},
        {
            "event": "openai_error",
            "call_id": "timed-out",
            "elapsed_ms": 12000,
            "error_type": "APITimeoutError",
        },
        {"event": "openai_request", "call_id": "cancelled"},
        {"event": "interpretation_end", "stage": "observe", "elapsed_ms": 1100},
        {"event": "interpretation_error", "stage": "observe", "elapsed_ms": 12100},
    ]
    trace.write_text("\n".join(json.dumps(row) for row in records) + "\n")
    summary = summarize(trace)
    assert summary["openai_requests_attempted"] == 3
    assert summary["openai_response_ms"]["p95"] == 1000
    assert summary["openai_terminated_attempt_ms"]["p95"] == 11450
    assert summary["openai_error_types"] == {"APITimeoutError": 1}
    assert [row["call_id"] for row in summary["openai_unfinished_requests"]] == ["cancelled"]
    assert summary["interpretation_terminated_attempt_ms"]["observe"]["p95"] == 11550
    assert summary["cached_input_share_of_recorded_responses"] == 0.8
