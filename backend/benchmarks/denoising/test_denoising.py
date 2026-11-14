"""Offline benchmark invariants; no model downloads, provider calls, or device jobs."""

import copy
import csv
import hashlib
import json
import math
from array import array

import pytest

from benchmarks.denoising.analyze import (
    analyze_device,
    estimate_lag,
    percentile,
    similarity,
)
from benchmarks.denoising.audio import (
    FRAME_SAMPLES,
    REVERB_TAPS,
    SAMPLE_RATE,
    colored_noise,
    mix,
    noise_scale,
    pcm_bytes,
    read_wav,
    reverberate,
    sha256,
    write_wav,
)
from benchmarks.denoising.prepare import assemble_case, prepare, write_json
from benchmarks.denoising.register_outputs import register
from benchmarks.run_pipeline import assemble_audio, load_manifest


@pytest.fixture
def source(tmp_path):
    audio = tmp_path / "original-audio"
    fixtures = []
    for index, count in enumerate((1003, 2051)):
        name = f"cue-{index}"
        path = audio / f"{name}.wav"
        samples = [round(27000 * math.sin(i * (0.03 + index * 0.01))) for i in range(count)]
        write_wav(path, samples)
        fixtures.append({"id": name, "language": "hi", "text": f"टोकन {442 + index}।",
                         "english_gloss": f"Token {442 + index}.",
                         "audio_path": str(path), "sha256": sha256(path),
                         "speech_end_s": (count - 50) / SAMPLE_RATE})
    case = {"id": "hi-correction", "language": "hi", "kind": "correction",
            "request": "Tell me when 442 is called.", "mode": "monitor",
            "sequence": [{"fixture_id": "cue-0", "silence_after_s": 0.15},
                         {"fixture_id": "cue-1", "silence_after_s": 0.25}],
            "expected": {"alert": False, "token": "443", "location": "counter 2",
                         "location_aliases": ["काउंटर दो"], "voice_stop": False,
                         "correction": True}}
    corpus = {"version": 1, "sample_rate": SAMPLE_RATE, "fixtures": fixtures, "cases": [case],
              "metadata": {"corpus_type": "test-only-synthetic", "provenance": "offline unit test"}}
    path = tmp_path / "source-corpus.json"
    write_json(path, corpus)
    return path, audio, corpus


def test_deterministic_colored_noise_is_case_specific_and_has_no_frame_reset():
    a = colored_noise(16_000, "seed\0case-a")
    assert a == colored_noise(16_000, "seed\0case-a")
    assert a != colored_noise(16_000, "seed\0case-b")
    assert abs(sum(a)) < 1e-8
    covariance = sum(a[i] * a[i - 1] for i in range(1, len(a)))
    energy = sum(value * value for value in a)
    assert 0.85 < covariance / energy < 0.97  # the declared low-pass color
    assert list(a[:512]) != list(a[512:1024])


@pytest.mark.parametrize("target", [-10, 0, 10, 30])
def test_rms_snr_survives_headroom_scaling_without_clipping_or_retiming(target):
    signal = array("h", (round(30000 * math.sin(index * 0.043)) for index in range(64000)))
    noise = colored_noise(len(signal), "known-snr")
    spans = [(100, 32000), (33000, 63900)]
    scale = noise_scale(signal, noise, spans, target)
    peak = max(abs(s + n * scale) for s, n in zip(signal, noise))
    gain = min(1.0, 30000 / peak)
    output, measured = mix(signal, noise, scale, gain, spans)
    assert len(output) == len(signal)
    assert max(map(abs, output)) <= 30000
    assert measured["achieved_snr_db"] == pytest.approx(target, abs=0.01)
    # The actual mixture at each original sample, not a resampled or shifted signal.
    for index in (0, 511, 512, 8191, 63999):
        assert output[index] == round((signal[index] + noise[index] * scale) * gain)


def test_case_assembly_preserves_original_samples_and_harness_frame_boundaries(source):
    _, audio, corpus = source
    fixtures = {item["id"]: item for item in corpus["fixtures"]}
    case = corpus["cases"][0]
    samples, entry = assemble_case(case, fixtures, audio, 0.3, 1.0)
    plan = assemble_audio(case, fixtures, leading_silence=0.3, tail_silence=1.0)
    assert pcm_bytes(samples) == plan.pcm
    assert len(samples) % FRAME_SAMPLES == 0
    assert entry["source_assembled_pcm_sha256"] == hashlib.sha256(plan.pcm).hexdigest()
    assert entry["speech_end_sample"] == plan.spans[-1]["speech_end_sample"]
    for script in entry["scripts"]:
        start, end = script["start_sample"], script["source_end_sample"]
        assert samples[start:end] == read_wav(audio / f"{script['fixture_id']}.wav")


def test_reverb_has_declared_causal_taps_no_pre_echo_and_no_length_change():
    source = array("h", [0]) * 16_000
    source[300] = 10000
    output = reverberate(source)
    assert len(output) == len(source)
    assert not any(output[:300])
    assert [(index - 300, value / 10000) for index, value in enumerate(output) if value] == [
        (delay, gain) for delay, gain in REVERB_TAPS
    ]


def test_manifests_are_repeatable_match_labels_and_preserve_causal_latency_origin(source, tmp_path):
    path, audio, corpus = source
    source_hash = sha256(path)
    a = prepare(path, audio, tmp_path / "a", snrs=[10, 0], reverb=True, tail=1)
    b = prepare(path, audio, tmp_path / "b", snrs=[10, 0], reverb=True, tail=1)
    original_case = corpus["cases"][0]
    entry = a["cases"][0]
    assert sha256(path) == source_hash
    assert entry["source_case"] == original_case
    assert len(a["variants"]) == 5
    assert entry["common_gain"] < 1
    assert entry["scripts"][0]["text"] == corpus["fixtures"][0]["text"]
    for variant in a["variants"]:
        left, right = entry["counterparts"][variant], b["cases"][0]["counterparts"][variant]
        assert left["sha256"] == right["sha256"]
        assert left["sample_count"] == entry["sample_count"]
        assert left["frame_remainder"] == 0
        replay = load_manifest(tmp_path / "a" / a["pipeline_manifests"][variant]["relative_path"])
        assert replay["cases"][0]["expected"] == original_case["expected"]
        assert replay["cases"][0]["request"] == original_case["request"]
        fixture = replay["fixtures"][0]
        assert fixture["speech_end_s"] == entry["speech_end_sample"] / SAMPLE_RATE
        plan = assemble_audio(replay["cases"][0], {fixture["id"]: fixture}, 0, 0)
        assert plan.pcm == pcm_bytes(read_wav(tmp_path / "a" / left["relative_path"]))
        if variant != "clean":
            assert left["mix_measurement"]["common_gain"] == entry["common_gain"]
            assert left["mix_measurement"]["achieved_snr_db"] == pytest.approx(
                left["target_snr_db"], abs=0.01
            )
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        prepare(path, audio, tmp_path / "a", tail=1)


def test_source_tampering_is_rejected_before_creating_output(source, tmp_path):
    path, audio, _ = source
    write_wav(audio / "cue-0.wav", [1, 2, 3])
    with pytest.raises(ValueError, match="Source SHA256 mismatch"):
        prepare(path, audio, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("delay", [-123, 0, 257, 511])
def test_correlation_reports_sample_delay_including_sign_without_changing_input(delay):
    # Broadband colored excitation avoids the ambiguous periodic peaks of a pure tone.
    reference = [value * 12000 for value in colored_noise(20_000, "alignment")]
    candidate = [0.0] * len(reference)
    for index, value in enumerate(reference):
        if 0 <= index + delay < len(candidate):
            candidate[index + delay] = value * 0.3
    before = candidate.copy()
    estimated = estimate_lag(reference, candidate, [(1000, 18000)], max_lag=512)
    assert estimated["samples"] == delay
    assert estimated["milliseconds"] == delay / 16
    assert estimated["correlation"] == pytest.approx(1)
    assert candidate == before


def test_silence_has_no_defined_delay_and_attenuation_is_not_accuracy():
    noise = colored_noise(4096, "attenuation")
    signal = [math.sin(index * 0.07) for index in range(len(noise))]
    candidate = [signal[index] + noise[index] for index in range(len(signal))]
    first = similarity(signal, candidate)
    quieter = similarity(signal, [sample * 0.01 for sample in candidate])
    assert quieter["si_sdr_db"] == pytest.approx(first["si_sdr_db"])
    assert quieter["reference_gain_fit"] < 0.02
    assert similarity(signal, [0] * len(signal))["si_sdr_db"] is None
    estimated = estimate_lag(signal, [0] * len(signal), [(0, 4096)], max_lag=256)
    assert estimated["samples"] is None
    assert not estimated["reliable_heuristic"]


def fake_run(campaign, manifest, run_dir):
    """A labelled test-only report for importer validation, not benchmark evidence."""
    case = manifest["cases"][0]
    variant = manifest["variants"][1]
    source = case["counterparts"][variant]
    output = run_dir / "output.wav"
    samples = read_wav(campaign / source["relative_path"])
    write_wav(output, samples)
    report = {"schema_version": 1, "status": "completed", "engine_class": "unit-test-only",
              "model": {"sha256": "0" * 64}, "replays": [{
                  "input_id": f"{variant}__{case['case_id']}",
                  "case_id": case["case_id"], "variant": variant,
                  "mode": "engine", "input_sha256": source["sha256"],
                  "output_file": output.name, "output_sha256": sha256(output),
                  "causal_unshifted": True, "sample_zero_offset": 0,
                  "state_policy": "fresh-engine-per-case",
                  "all_engine_frames_active": True,
              }], "input_manifest_sha256": sha256(campaign / "device-inputs.json")}
    report["replays"].append({**report["replays"][0], "mode": "bypass"})
    write_json(run_dir / "results.json", report)
    return report


def test_device_registration_keeps_original_manifest_and_provider_labels(source, tmp_path):
    path, audio, _ = source
    campaign, run_dir = tmp_path / "campaign", tmp_path / "run"
    manifest = prepare(path, audio, campaign, snrs=[0], tail=1)
    original_hash = sha256(campaign / "manifest.json")
    fake_run(campaign, manifest, run_dir)
    registered = json.loads(register(campaign, run_dir, "unit-test-only").read_text())
    assert sha256(campaign / "manifest.json") == original_hash
    variant = "denoised-colored-snr-p0"
    case = registered["cases"][0]
    assert case["source_case"] == manifest["cases"][0]["source_case"]
    assert case["counterparts"][variant]["source_speech_end_sample"] == case["speech_end_sample"]
    replay_path = campaign / registered["pipeline_manifests"][variant]["relative_path"]
    replay = load_manifest(replay_path)
    assert replay["cases"][0]["expected"] == case["source_case"]["expected"]


@pytest.mark.parametrize(
    "problem", ["short", "shifted", "tamper", "fallback", "input", "no-bypass"]
)
def test_registration_rejects_changed_or_fail_open_audio(source, tmp_path, problem):
    path, audio, _ = source
    campaign, run_dir = tmp_path / "campaign", tmp_path / "run"
    manifest = prepare(path, audio, campaign, snrs=[0], tail=1)
    report = fake_run(campaign, manifest, run_dir)
    row = report["replays"][0]
    if problem == "short":
        write_wav(run_dir / row["output_file"], [0] * FRAME_SAMPLES)
        row["output_sha256"] = sha256(run_dir / row["output_file"])
    elif problem == "shifted":
        row["sample_zero_offset"] = 256
    elif problem == "tamper":
        row["output_sha256"] = "1" * 64
    elif problem == "fallback":
        row["all_engine_frames_active"] = False
    elif problem == "no-bypass":
        report["replays"] = report["replays"][:1]
    else:
        row["input_sha256"] = "2" * 64
    write_json(run_dir / "results.json", report)
    with pytest.raises(ValueError):
        register(campaign, run_dir, "bad")
    assert not (campaign / "paired-bad.json").exists()


def test_device_metrics_keep_warmup_deadlines_and_worker_cpu_distinct(tmp_path):
    frames = tmp_path / "frames.csv"
    fields = ["phase", "process_ns", "thread_cpu_ns", "start_lateness_ns",
              "completion_lateness_ns", "engine_active"]
    with frames.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(dict(zip(fields, ["warmup", 40_000_000, 20_000_000, 1, 8_000_000, 1])))
        writer.writerow(dict(zip(fields, ["sustained", 10_000_000, 5_000_000, 0, -22_000_000, 1])))
        writer.writerow(dict(zip(fields, ["sustained", 1_000, 1_000, 40_000_000, 8_001_000, 0])))
    report = {"status": "completed", "stages": [{"frames_file": frames.name,
              "frames_sha256": sha256(frames), "frame_count": 3, "mode": "engine",
              "resources_sustained_start": {"monotonic_ns": 100_000_000,
                                             "process_cpu_ms": 10, "rss_kb": 100},
              "resources_sustained_end": {"monotonic_ns": 200_000_000,
                                           "process_cpu_ms": 60, "rss_kb": 150}}]}
    write_json(tmp_path / "results.json", report)
    result = analyze_device(tmp_path)["stages"][0]["cohorts"]
    assert result["warmup"]["process_over_32ms"] == 1
    assert result["sustained"]["process_over_32ms"] == 0
    assert result["sustained"]["completion_deadline_misses"] == 1
    assert result["sustained"]["active_engine_frames"] == 1
    assert result["sustained"]["fail_open_frames"] == 1
    assert result["sustained"]["active_engine_process_ms"]["p50"] == 10
    resources = analyze_device(tmp_path)["stages"][0]["resource_cohorts"]["sustained"]
    assert resources["process_cpu_percent_one_core"] == 50
    assert resources["rss_delta_kb"] == 50
    assert percentile([1, 2, 3, 100], 99) == 100
    report["stages"][0]["frame_count"] = 4
    write_json(tmp_path / "results.json", report)
    with pytest.raises(ValueError, match="Missing device frame rows"):
        analyze_device(tmp_path)


def test_invalid_preparation_parameters_are_rejected(source, tmp_path):
    path, audio, _ = source
    for options in ({"snrs": [math.nan]}, {"snrs": [0, 0]}, {"tail": 0},
                    {"headroom": 1}, {"selected": ["absent"]}):
        with pytest.raises(ValueError):
            prepare(path, audio, tmp_path / "invalid", **copy.deepcopy(options))
