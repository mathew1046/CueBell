"""Acceptance reports must not mistake a fast raw fallback for successful DSP."""

import csv
import hashlib
import json

from .analyze import analyze_device


def device_run(tmp_path, frames, fallback=None):
    fields = [
        "phase", "process_ns", "thread_cpu_ns", "engine_active", "engine_invoked",
        "start_lateness_ns", "completion_lateness_ns",
    ]
    path = tmp_path / "frames.csv"
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for phase, nanos, active, invoked in frames:
            writer.writerow(dict(zip(fields, [
                phase, nanos, nanos, int(active), int(invoked), 0, nanos - 32_000_000,
            ], strict=True)))
    report = {
        "status": "completed",
        "stages": [{
            "mode": "engine", "frames_file": path.name, "frame_count": len(frames),
            "frames_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "fallback_reason": fallback,
        }],
    }
    (tmp_path / "results.json").write_text(json.dumps(report))
    return analyze_device(tmp_path)["stages"][0]


def test_fast_fallback_never_passes_processing_gate(tmp_path):
    stage = device_run(tmp_path, [
        ("warmup", 38_000_000, False, True),
        ("sustained", 8_000, False, False),
        ("sustained", 7_000, False, False),
    ], "processing_deadline_exceeded")
    assert stage["cohorts"]["sustained"]["process_ms"]["p99"] == 0.008
    assert stage["cohorts"]["sustained"]["active_engine_process_ms"]["count"] == 0
    assert not stage["processing_gate"]["passed"]
    assert "raw_fallback_observed" in stage["processing_gate"]["reasons"]


def test_processing_gate_keeps_inclusive_deadline_boundary(tmp_path):
    stage = device_run(tmp_path, [
        ("warmup", 32_000_000, True, True),
        ("sustained", 5_000_000, True, True),
    ])
    assert stage["cohorts"]["warmup"]["process_deadline_violations"] == 1
    assert not stage["processing_gate"]["passed"]


def test_active_processing_budget_is_strict_and_sustained(tmp_path):
    stage = device_run(tmp_path, [
        ("warmup", 17_000_000, True, True),
        ("sustained", 5_000_000, True, True),
        ("sustained", 7_900_000, True, True),
    ])
    assert stage["processing_gate"]["passed"]
    stage = device_run(tmp_path, [("sustained", 8_000_000, True, True)])
    assert not stage["processing_gate"]["passed"]
    assert stage["processing_gate"]["reasons"] == ["active_sustained_p99_not_below_8ms"]
