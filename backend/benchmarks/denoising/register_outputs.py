#!/usr/bin/env python3
"""Validate and register real-device causal WAVs as matched provider-replay inputs.

The original fixture manifest is immutable. A new paired manifest and one replay
manifest per completed denoised variant are written under the campaign directory.
Partial runs, altered inputs, changed lengths, and shifted outputs are rejected.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
from pathlib import Path

from .audio import FRAME_SAMPLES, audio_reference, pcm_bytes, read_wav, sha256
from .prepare import pipeline_manifest, write_json


def register(campaign: Path, run_dir: Path, label: str) -> Path:
    campaign, run_dir = campaign.resolve(), run_dir.resolve()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", label):
        raise ValueError("label must contain only letters, digits, underscores, and hyphens")
    original_path = campaign / "manifest.json"
    manifest = json.loads(original_path.read_text())
    if sha256(campaign / "source/corpus.json") != manifest["source_corpus"]["sha256"]:
        raise ValueError("Archived source corpus was modified")
    report_path = run_dir / "results.json"
    report = json.loads(report_path.read_text())
    if report.get("status") != "completed" or report.get("schema_version") != 1:
        raise ValueError("A completed schema-version-1 device run is required")
    if sha256(campaign / "device-inputs.json") != report.get("input_manifest_sha256"):
        raise ValueError("Device input manifest differs from this campaign")
    if not report.get("engine_class") or not re.fullmatch(
        r"[0-9a-f]{64}", report.get("model", {}).get("sha256", "")
    ):
        raise ValueError("Missing production engine/model identity")
    destination = campaign / "device" / label
    paired_path = campaign / f"paired-{label}.json"
    if destination.exists() or paired_path.exists():
        raise ValueError("Run label already registered")
    cases = {entry["case_id"]: entry for entry in manifest["cases"]}
    accepted = []
    seen = set()
    bypassed = set()
    for replay in report.get("replays", []):
        case_id, variant = replay["case_id"], replay["variant"]
        source = cases[case_id]["counterparts"][variant]
        if replay["input_id"] != f"{variant}__{case_id}":
            raise ValueError("Input identity does not match case and variant")
        if replay["input_sha256"] != source["sha256"]:
            raise ValueError(f"Input SHA mismatch for {replay['input_id']}")
        input_path = campaign / source["relative_path"]
        if sha256(input_path) != source["sha256"]:
            raise ValueError(f"Campaign input was modified: {input_path}")
        path = (run_dir / replay["output_file"]).resolve()
        if not path.is_relative_to(run_dir) or sha256(path) != replay["output_sha256"]:
            raise ValueError(f"Output path/SHA mismatch: {path}")
        samples = read_wav(path)
        if len(samples) != source["sample_count"] or len(samples) % FRAME_SAMPLES:
            raise ValueError(f"Output sample count or PCM framing changed: {path}")
        if not replay.get("causal_unshifted") or replay.get("sample_zero_offset") != 0:
            raise ValueError(f"Refusing shifted output: {path}")
        if replay["mode"] == "bypass":
            if pcm_bytes(samples) != pcm_bytes(read_wav(input_path)):
                raise ValueError(f"Bypass changed PCM: {path}")
            bypassed.add((case_id, variant))
            continue
        if replay["mode"] != "engine":
            raise ValueError("Unknown replay mode")
        if replay.get("all_engine_frames_active") is not True:
            raise ValueError(f"Engine fell back to bypass; not denoised evidence: {path}")
        key = (case_id, variant)
        if key in seen:
            raise ValueError(f"Duplicate denoised output: {key}")
        seen.add(key)
        accepted.append((cases[case_id], variant, replay, path))
    if not accepted:
        raise ValueError("No real-engine replay WAVs; stress-only runs cannot populate ASR inputs")
    if not seen.issubset(bypassed):
        raise ValueError("Every engine WAV needs a validated, sample-identical bypass control")
    new_variants = {f"denoised-{variant}" for _, variant, _, _ in accepted}
    for variant in new_variants:
        path = campaign / "pipeline" / f"{label}-{variant}.json"
        if path.exists():
            raise ValueError(f"Replay manifest already exists: {path}")
    shutil.copytree(run_dir, destination)
    manifest["base_manifest_sha256"] = sha256(original_path)
    manifest["device_run"] = {"relative_path": f"device/{label}/results.json",
                              "sha256": sha256(report_path)}
    for case, variant, replay, path in accepted:
        name = f"denoised-{variant}"
        copied = destination / path.relative_to(run_dir)
        reference = {
            **audio_reference(copied, campaign),
            "parent_variant": variant,
            "synthetic_reverb": case["counterparts"][variant].get("synthetic_reverb", False),
            "engine_class": report["engine_class"],
            "model_sha256": report["model"]["sha256"],
            "state_policy": replay["state_policy"],
            "source_speech_end_sample": case["speech_end_sample"],
        }
        case["counterparts"][name] = reference
        case["counterparts"][variant]["denoised_counterpart"] = name
    source = json.loads((campaign / "source/corpus.json").read_text())
    for variant in sorted(new_variants):
        selected = [case for case in manifest["cases"] if variant in case["counterparts"]]
        path = campaign / "pipeline" / f"{label}-{variant}.json"
        replay_manifest = pipeline_manifest(source, selected, variant, campaign)
        replay_manifest["metadata"]["device_run"] = copy.deepcopy(manifest["device_run"])
        write_json(path, replay_manifest)
        manifest["pipeline_manifests"][variant] = {
            "relative_path": path.relative_to(campaign).as_posix(), "sha256": sha256(path),
        }
    manifest["variants"].extend(sorted(new_variants))
    write_json(paired_path, manifest)
    return paired_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--device-run", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    print(register(args.campaign, args.device_run, args.label))


if __name__ == "__main__":
    main()
