#!/usr/bin/env python3
"""Signal and device timing metrics, never ASR scores or provider latency estimates.

Positive waveform lag means candidate output follows the clean reference. Lag is
estimated by correlation and can be ambiguous; no WAV or ground truth is shifted.
Use the existing real-provider campaign analyzer for transcript/alert accuracy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from .audio import SAMPLE_RATE, read_wav, rms, sha256
from .prepare import write_json


def percentile(values: list[float], percent: float) -> float | None:
    """Nearest rank; p99 cannot interpolate away a measured slow frame."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percent * len(ordered) / 100) - 1)]


def distribution(values: list[float]) -> dict:
    return {"count": len(values), "p50": percentile(values, 50),
            "p95": percentile(values, 95), "p99": percentile(values, 99),
            "max": max(values) if values else None,
            "mean": sum(values) / len(values) if values else None}


def similarity(reference, candidate, *, lag: int = 0,
               indices: list[int] | range | None = None) -> dict:
    indices = range(len(reference)) if indices is None else indices
    xx = yy = xy = error = 0.0
    count = 0
    for index in indices:
        other = index + lag
        if 0 <= other < len(candidate):
            x, y = reference[index], candidate[other]
            xx += x * x
            yy += y * y
            xy += x * y
            error += (x - y) ** 2
            count += 1
    if not count or xx <= 1e-20 or yy <= 1e-20:
        return {"sample_count": count, "correlation": None, "si_sdr_db": None,
                "reference_error_snr_db": None, "reference_gain_fit": None}
    projection = xy * xy / xx
    residual = max(0.0, yy - projection)
    return {
        "sample_count": count,
        "correlation": xy / math.sqrt(xx * yy),
        # Exact equality is flagged instead of emitting nonstandard Infinity JSON.
        "si_sdr_db": 10 * math.log10(projection / residual)
        if projection > 0 and residual > 1e-12 else None,
        "zero_projection_residual": residual <= 1e-12,
        "reference_error_snr_db": 10 * math.log10(xx / error) if error > 0 else None,
        "identical_samples": error == 0,
        "reference_gain_fit": xy / xx,
    }


def estimate_lag(reference, candidate, spans: list[tuple[int, int]],
                 max_lag: int = 4096) -> dict:
    """Bounded two-resolution correlation. Pure Python; no guessed model delay.

    The coarse pass uses 16-sample box averages to reduce aliasing. The fine pass
    uses unsmoothed PCM at sample resolution within ±32 of the coarse peak. Known
    speech spans prevent long guard silences dominating the estimate. Confidence
    and the searched bound are retained; this is not an acoustic ground truth.
    """
    if max_lag < 0 or max_lag >= min(len(reference), len(candidate)):
        raise ValueError("max_lag must be nonnegative and shorter than both signals")
    block = 16

    def smooth(pcm):
        return [sum(pcm[start:start + block]) / block
                for start in range(0, len(pcm) - block + 1, block)]

    left, right = smooth(reference), smooth(candidate)
    coarse_indices = [i for start, end in spans for i in range(
        math.ceil(start / block), min(end // block, len(left))
    )]
    # Bound work independently of full campaign length.
    coarse_indices = coarse_indices[::max(1, len(coarse_indices) // 2000)]

    def score(a, b, indices, lag):
        metric = similarity(a, b, lag=lag, indices=indices)
        value = metric["correlation"]
        if value is None or metric["sample_count"] < len(indices) * 0.75:
            return -2.0
        return value

    coarse_bound = max_lag // block
    coarse = max(range(-coarse_bound, coarse_bound + 1),
                 key=lambda lag: (score(left, right, coarse_indices, lag), -abs(lag)))
    step = max(1, sum(end - start for start, end in spans) // 12_000)
    indices = [i for start, end in spans for i in range(start, end, step)]
    center = coarse * block
    lag = max(range(max(-max_lag, center - 32), min(max_lag, center + 32) + 1),
              key=lambda offset: (score(reference, candidate, indices, offset), -abs(offset)))
    correlation = score(reference, candidate, indices, lag)
    defined = correlation > -2
    return {
        "samples": lag if defined else None,
        "milliseconds": lag / SAMPLE_RATE * 1000 if defined else None,
        "correlation": correlation if defined else None,
        "reliable_heuristic": defined and correlation >= 0.3 and abs(lag) < max_lag,
        "at_search_boundary": defined and abs(lag) == max_lag,
        "search_bound_samples": max_lag,
        "method": "16-sample box coarse correlation, full-resolution local refinement",
        "sign_convention": "positive means candidate is later than clean",
        "provider_latency": False,
    }


def analyze_signals(manifest_path: Path, max_lag: int = 4096) -> dict:
    root = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text())
    results = []
    for case in manifest["cases"]:
        audio = {}
        for variant, reference in case["counterparts"].items():
            path = (root / reference["relative_path"]).resolve()
            if not path.is_relative_to(root) or sha256(path) != reference["sha256"]:
                raise ValueError(f"Invalid path or SHA256 for {path}")
            samples = read_wav(path)
            if len(samples) != case["sample_count"]:
                raise ValueError(f"Sample-count/alignment mismatch: {path}")
            if reference.get("sample_zero_offset") != 0:
                raise ValueError(f"Refusing silently shifted waveform: {path}")
            audio[variant] = samples
        reference = audio["clean"]
        spans = [(item["start_sample"], item["speech_end_sample"]) for item in case["scripts"]]
        indices = [i for start, end in spans for i in range(start, end)]
        for variant, samples in audio.items():
            if variant == "clean":
                continue
            delay = estimate_lag(reference, samples, spans, max_lag)
            row = {
                "case_id": case["case_id"], "variant": variant,
                "sample_count": len(samples), "source_speech_end_sample": case["speech_end_sample"],
                "waveform_delay_estimate": delay,
                "unaligned": similarity(reference, samples, indices=indices),
                "aligned_diagnostic_only": similarity(reference, samples,
                                                       lag=delay["samples"] or 0, indices=indices),
                "rms_pcm": rms(samples),
                "rms_ratio_to_clean": rms(samples) / rms(reference),
                "peak_abs_pcm": max(map(abs, samples), default=0),
                "saturated_sample_count": sum(abs(value) >= 32767 for value in samples),
                "tail_last_second_rms_pcm": rms(samples[-SAMPLE_RATE:]),
            }
            # The reference may include synthetic reverb; do not pool room/no-room cohorts.
            row["synthetic_reverb"] = case["counterparts"][variant].get("synthetic_reverb", False)
            results.append(row)
    return {
        "manifest_sha256": sha256(manifest_path),
        "scope": "offline waveform diagnostics; not ASR accuracy or real-provider latency",
        "rms_warning": "RMS, SNR, SI-SDR, and correlation are not transcript/alert accuracy.",
        "ground_truth_policy": "No alignment compensation applied to WAVs or speech endpoints.",
        "results": results,
    }


def analyze_device(run_dir: Path) -> dict:
    """Recompute distributions from all frame rows, keeping warmup and sustained separate."""
    report_path = run_dir / "results.json"
    report = json.loads(report_path.read_text())
    if report.get("status") != "completed":
        raise ValueError("Device run incomplete; cannot summarize as success")
    stages = []
    for stage in report["stages"]:
        path = (run_dir / stage["frames_file"]).resolve()
        if not path.is_relative_to(run_dir.resolve()) or sha256(path) != stage["frames_sha256"]:
            raise ValueError(f"Device frame log SHA/path mismatch: {path}")
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != stage["frame_count"]:
            raise ValueError(f"Missing device frame rows: {path}")
        cohorts = {}
        for phase in ("warmup", "sustained"):
            selected = [row for row in rows if row["phase"] == phase]
            durations = [int(row["process_ns"]) / 1e6 for row in selected]
            active = [row for row in selected if row["engine_active"] == "1"]
            invoked = [row for row in selected if row.get("engine_invoked") == "1"]
            cohorts[phase] = {
                "process_ms": distribution(durations),
                "thread_cpu_ms": distribution([
                    int(row["thread_cpu_ns"]) / 1e6 for row in selected
                ]),
                "start_lateness_ms": distribution([int(row["start_lateness_ns"]) / 1e6
                                                    for row in selected]),
                "completion_lateness_ms": distribution([int(row["completion_lateness_ns"]) / 1e6
                                                         for row in selected]),
                "process_over_32ms": sum(value > 32 for value in durations),
                "completion_deadline_misses": sum(int(row["completion_lateness_ns"]) > 0
                                                  for row in selected),
                "active_engine_frames": len(active),
                "fail_open_frames": len(selected) - len(active) if stage["mode"] == "engine" else 0,
                "active_engine_process_ms": distribution([
                    int(row["process_ns"]) / 1e6 for row in active
                ]),
                # Includes the transition frame that ran inference but exceeded its deadline.
                "invoked_engine_process_ms": distribution([
                    int(row["process_ns"]) / 1e6 for row in invoked
                ]),
            }
        resource_cohorts = {}
        for phase, start_key, end_key in (
            ("warmup", "resources_after_initialization", "resources_sustained_start"),
            ("sustained", "resources_sustained_start", "resources_sustained_end"),
        ):
            start, end = stage.get(start_key), stage.get(end_key)
            if not start or not end:
                continue
            elapsed_ms = (end["monotonic_ns"] - start["monotonic_ns"]) / 1e6
            cpu_ms = end["process_cpu_ms"] - start["process_cpu_ms"]
            rss = [item["rss_kb"] for item in [start, end, *stage.get("resource_samples", [])]
                   if item.get("rss_kb") is not None and item.get("phase", phase) == phase]
            resource_cohorts[phase] = {
                "elapsed_ms": elapsed_ms,
                "process_cpu_ms": cpu_ms,
                "process_cpu_percent_one_core": (
                    cpu_ms / elapsed_ms * 100 if elapsed_ms > 0 else None
                ),
                "rss_start_kb": start.get("rss_kb"), "rss_end_kb": end.get("rss_kb"),
                "rss_max_sampled_kb": max(rss) if rss else None,
                "rss_delta_kb": end["rss_kb"] - start["rss_kb"]
                if start.get("rss_kb") is not None and end.get("rss_kb") is not None else None,
            }
        stages.append({**stage, "cohorts": cohorts, "resource_cohorts": resource_cohorts})
    return {"results_sha256": sha256(report_path), "environment": report.get("environment"),
            "model": report.get("model"), "reset_check": report.get("reset_check"),
            "clock_policy": report.get("clock_policy"), "stages": stages,
            "scope": "device DSP cost/scheduling only; no microphone/relay/ASR/classifier latency",
            "cpu_policy": "process CPU includes runtime worker threads; per-frame thread CPU is "
                          "the calling thread only; CPU clocks exclude sleep"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--device-run", type=Path)
    parser.add_argument("--max-lag-samples", type=int, default=4096)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.manifest and not args.device_run:
        parser.error("--manifest and/or --device-run is required")
    if args.output.exists():
        parser.error("Refusing to overwrite an existing report")
    result = {"schema_version": 1}
    if args.manifest:
        result["signal"] = analyze_signals(args.manifest, args.max_lag_samples)
    if args.device_run:
        result["device"] = analyze_device(args.device_run)
    write_json(args.output, result)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
