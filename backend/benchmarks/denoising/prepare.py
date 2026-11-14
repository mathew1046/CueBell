#!/usr/bin/env python3
"""Create synthetic noisy *case streams* without invoking paid services.

Run from backend: python -m benchmarks.denoising.prepare --help
Replay generated pipeline manifests with --leading-silence 0 --tail-silence 0:
their silence, inter-cue gaps, and final 512-sample padding are already included.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import re
import shutil
from array import array
from pathlib import Path

from .audio import (
    FRAME_SAMPLES,
    NOISE_POLE,
    NOISE_WARMUP,
    REVERB_TAPS,
    SAMPLE_RATE,
    audio_reference,
    colored_noise,
    mix,
    noise_scale,
    pcm_bytes,
    quantize,
    read_wav,
    reverberate,
    sha256,
    write_wav,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "docs/benchmarks/denoising-2026-11-14"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def assemble_case(case: dict, fixtures: dict[str, dict], audio_dir: Path,
                  leading: float, tail: float) -> tuple[array, dict]:
    """Match run_pipeline.assemble_audio; retain every original WAV sample."""
    samples = array("h", [0]) * round(leading * SAMPLE_RATE)
    spans = []
    for segment in case["sequence"]:
        fixture = fixtures[segment["fixture_id"]]
        source = audio_dir / f"{fixture['id']}.wav"
        if sha256(source) != fixture["sha256"]:
            raise ValueError(f"Source SHA256 mismatch: {source}")
        pcm = read_wav(source)
        speech_count = round(fixture["speech_end_s"] * SAMPLE_RATE)
        if not 0 < speech_count <= len(pcm):
            raise ValueError(f"Invalid source speech endpoint: {fixture['id']}")
        start = len(samples)
        samples.extend(pcm)
        spans.append({
            "fixture_id": fixture["id"],
            "text": fixture["text"],
            "english_gloss": fixture.get("english_gloss"),
            "source_wav_sha256": fixture["sha256"],
            "start_sample": start,
            "source_end_sample": start + len(pcm),
            "speech_end_sample": start + speech_count,
            "source_sample_count": len(pcm),
            "silence_after_s": segment.get("silence_after_s", 0),
        })
        samples.extend(array("h", [0]) * round(segment.get("silence_after_s", 0) * SAMPLE_RATE))
    samples.extend(array("h", [0]) * round(tail * SAMPLE_RATE))
    padding = -len(samples) % FRAME_SAMPLES
    samples.extend(array("h", [0]) * padding)
    return samples, {
        "scripts": spans,
        "source_assembled_pcm_sha256": hashlib.sha256(pcm_bytes(samples)).hexdigest(),
        "speech_end_sample": spans[-1]["speech_end_sample"],
        "sample_count": len(samples),
        "duration_s": len(samples) / SAMPLE_RATE,
        "final_padding_samples": padding,
        "leading_silence_s": leading,
        "tail_silence_s": tail,
    }


def variant_name(snr: float, reverb: bool) -> str:
    number = f"{abs(snr):g}".replace(".", "d")
    return f"{'synthetic-reverb-' if reverb else ''}colored-snr-{'m' if snr < 0 else 'p'}{number}"


def pipeline_manifest(source: dict, cases: list[dict], variant: str, root: Path) -> dict:
    fixtures = []
    replay_cases = []
    for entry in cases:
        reference = entry["counterparts"][variant]
        original = entry["source_case"]
        fixtures.append({
            "id": original["id"],
            "language": original["language"],
            "text": " ".join(item["text"] for item in entry["scripts"]),
            "audio_path": str(root / reference["relative_path"]),
            "sha256": reference["sha256"],
            "speech_end_s": entry["speech_end_sample"] / SAMPLE_RATE,
            "duration_s": entry["duration_s"],
            "source_scripts": copy.deepcopy(entry["scripts"]),
        })
        case = copy.deepcopy(original)
        case["sequence"] = [{"fixture_id": original["id"], "silence_after_s": 0}]
        replay_cases.append(case)
    return {
        "version": 1,
        "sample_rate": SAMPLE_RATE,
        "fixtures": fixtures,
        "cases": replay_cases,
        "metadata": {
            **copy.deepcopy(source.get("metadata", {})),
            "corpus_type": "synthetic-stock-voice-continuous-case-stream",
            "audio_processing": variant,
            "source_metadata": copy.deepcopy(source.get("metadata", {})),
            "source_corpus_sha256": sha256(root / "source/corpus.json"),
            "continuous_case_stream": True,
            "required_replay_flags": {"leading_silence": 0, "tail_silence": 0},
            "ground_truth": "Source scripts and expected labels unchanged; source speech endpoints "
                            "remain the latency origin, including for causal denoised output.",
        },
    }


def prepare(corpus_path: Path, audio_dir: Path, output: Path, *,
            selected: list[str] | None = None, snrs: list[float] | None = None,
            seed: str = "cuebell-denoising-2026-11-14-v1", reverb: bool = False,
            leading: float = 0.3, tail: float = 6.0, headroom: float = 0.97) -> dict:
    snrs = [10.0, 0.0] if snrs is None else snrs
    if not snrs or any(not math.isfinite(snr) or not -30 <= snr <= 60 for snr in snrs):
        raise ValueError("Provide finite SNRs in [-30, 60] dB")
    if len(set(snrs)) != len(snrs):
        raise ValueError("Duplicate SNR")
    conditions = [(snr, room) for room in ([False, True] if reverb else [False]) for snr in snrs]
    variants = ["clean", *(variant_name(snr, room) for snr, room in conditions)]
    if len(set(variants)) != len(variants):
        raise ValueError("SNR values produce identical six-significant-digit variant labels")
    if not 0 < headroom < 1 or not math.isfinite(headroom):
        raise ValueError("headroom must be strictly between 0 and 1")
    if not math.isfinite(leading) or not math.isfinite(tail) or leading < 0 or tail < 1:
        raise ValueError("leading must be >= 0; tail must be >= 1 second to retain delayed speech")
    output = output.resolve()
    source = json.loads(corpus_path.read_text())
    if source.get("version") != 1 or source.get("sample_rate") != SAMPLE_RATE:
        raise ValueError("Expected source corpus version 1 at 16000 Hz")
    fixtures = {fixture["id"]: fixture for fixture in source["fixtures"]}
    if len(fixtures) != len(source["fixtures"]):
        raise ValueError("Duplicate source fixture ID")
    cases = [case for case in source["cases"] if not selected or case["id"] in selected]
    if selected and set(selected) != {case["id"] for case in cases}:
        raise ValueError("Unknown or missing selected case ID")
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Cases must be nonempty with unique IDs")
    for identifier in [*fixtures, *(case["id"] for case in cases)]:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", identifier):
            raise ValueError(f"Unsafe source ID: {identifier}")
    # Fail before creating artifacts if any source is invalid.
    for case in cases:
        if not case["sequence"]:
            raise ValueError("Empty case sequence")
        for segment in case["sequence"]:
            gap = segment.get("silence_after_s", 0)
            if not math.isfinite(gap) or gap < 0:
                raise ValueError("Source silence_after_s must be finite and nonnegative")
        assemble_case(case, fixtures, audio_dir, leading, tail)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Refusing to overwrite nonempty output directory: {output}")
    (output / "source").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(corpus_path, output / "source/corpus.json")
    scripts = []
    for script in sorted(Path(__file__).parent.glob("*.py")):
        dest = output / "source" / script.name
        shutil.copyfile(script, dest)
        scripts.append({"path": str(script), "snapshot": str(dest.relative_to(output)),
                        "sha256": sha256(script)})
    manifest = {
        "schema_version": 1,
        "kind": "synthetic-denoising-case-streams",
        "sample_rate": SAMPLE_RATE,
        "frame_samples": FRAME_SAMPLES,
        "source_corpus": {"path": str(corpus_path.resolve()), "sha256": sha256(corpus_path),
                          "snapshot": "source/corpus.json"},
        "source_audio_directory": str(audio_dir.resolve()),
        "generator": {"scripts": scripts, "python": platform.python_version(), "seed": seed,
                      "leading_silence_s": leading, "tail_silence_s": tail,
                      "peak_headroom": headroom},
        "noise": {"kind": "synthetic stationary colored AR(1)", "pole": NOISE_POLE,
                  "startup_discard_samples": NOISE_WARMUP, "excitation": "SHAKE256 uint32 uniform",
                  "snr_reference": "RMS from fixture start through annotated speech endpoint; "
                                   "includes intrinsic pauses; no threshold-based VAD",
                  "not_real_venue_audio": True},
        "optional_reverb": {"enabled": reverb, "kind": "separately-labelled synthetic causal FIR",
                            "taps_sample_gain": REVERB_TAPS},
        "alignment": {"sample_zero_offset": 0, "time_stretch": False,
                      "endpoint_policy": "source speech endpoints unchanged for denoising/reverb",
                      "denoiser_tail_guard_s": tail},
        "variants": variants,
        "cases": [],
        "pipeline_manifests": {},
    }
    device_inputs = []
    for case in cases:
        clean, entry = assemble_case(case, fixtures, audio_dir, leading, tail)
        entry.update({"case_id": case["id"], "source_case": copy.deepcopy(case),
                      "counterparts": {}})
        spans = [(item["start_sample"], item["speech_end_sample"]) for item in entry["scripts"]]
        noise_seed = f"{seed}\0{case['id']}"
        noise = colored_noise(len(clean), noise_seed)
        wet = reverberate(clean) if reverb else None
        mixes = []
        peak = max(map(abs, clean))
        for snr, room in conditions:
            signal = wet if room else clean
            scale = noise_scale(signal, noise, spans, snr)
            peak = max(peak, max(abs(s + scale * n) for s, n in zip(signal, noise)))
            mixes.append((variant_name(snr, room), signal, scale, snr, room))
        # One gain per case, shared by clean and ALL selected conditions: no level confound.
        gain = min(1.0, math.floor(32767 * headroom) / peak)
        entry["common_gain"] = gain
        entry["gain_policy"] = "shared across clean and all noise/reverb conditions for this case"
        clean_path = output / "audio/clean" / f"{case['id']}.wav"
        write_wav(clean_path, quantize(clean, gain))
        entry["counterparts"]["clean"] = audio_reference(clean_path, output)
        for name, signal, scale, snr, room in mixes:
            mixed, measurement = mix(signal, noise, scale, gain, spans)
            path = output / "audio" / name / f"{case['id']}.wav"
            write_wav(path, mixed)
            entry["counterparts"][name] = {
                **audio_reference(path, output),
                "synthetic_reverb": room,
                "target_snr_db": snr,
                "snr_signal": "reverberant speech" if room else "dry speech",
                "noise_seed": noise_seed,
                "mix_measurement": measurement,
                "denoised_counterpart": None,
            }
        for variant, reference in entry["counterparts"].items():
            device_inputs.append({
                "id": f"{variant}__{case['id']}", "case_id": case["id"], "variant": variant,
                **reference,
            })
        manifest["cases"].append(entry)
    for variant in variants:
        path = output / "pipeline" / f"{variant}.json"
        write_json(path, pipeline_manifest(source, manifest["cases"], variant, output))
        manifest["pipeline_manifests"][variant] = {
            "relative_path": path.relative_to(output).as_posix(), "sha256": sha256(path),
        }
    device_path = output / "device-inputs.json"
    write_json(device_path, {"schema_version": 1, "sample_rate": SAMPLE_RATE,
                            "frame_samples": FRAME_SAMPLES, "inputs": device_inputs})
    manifest["device_inputs_sha256"] = sha256(device_path)
    write_json(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "backend/benchmarks/corpus.json")
    parser.add_argument("--audio-dir", type=Path, default=ROOT / "docs/benchmarks/2026-11-13/audio")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--snr-db", type=float, nargs="+", default=[10.0, 0.0])
    parser.add_argument("--seed", default="cuebell-denoising-2026-11-14-v1")
    parser.add_argument("--synthetic-reverb", action="store_true")
    parser.add_argument("--leading-silence", type=float, default=0.3)
    parser.add_argument("--tail-silence", type=float, default=6.0)
    args = parser.parse_args()
    manifest = prepare(args.corpus, args.audio_dir, args.output, selected=args.cases,
                       snrs=args.snr_db, seed=args.seed, reverb=args.synthetic_reverb,
                       leading=args.leading_silence, tail=args.tail_silence)
    print(json.dumps({"manifest": str(args.output.resolve() / "manifest.json"),
                      "cases": len(manifest["cases"]), "variants": manifest["variants"]}))


if __name__ == "__main__":
    main()
