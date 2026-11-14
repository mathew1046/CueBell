"""Validate actual Android replays and export plainly named before/after audio."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .audio import pcm_bytes, read_wav, sha256

MODEL_SHA256 = "e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534"


def export(recordings: Path, device_run: Path, output: Path,
           ids: set[str] | None = None) -> dict:
    recordings, device_run, output = recordings.resolve(), device_run.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Refusing to overwrite audio evidence")
    source = json.loads((recordings / "manifest.json").read_text())
    source_ids = {r["id"] for r in source["records"]}
    if ids is not None and (not ids or not ids.issubset(source_ids)):
        raise ValueError("Empty or unknown selected recording IDs")
    report_path = device_run / "results.json"
    report = json.loads(report_path.read_text())
    deployment = json.loads((device_run / "deployment.json").read_text())
    if report.get("status") != "completed" or deployment.get("exit_code") != 0:
        raise ValueError("An actually completed device run is required")
    if report.get("engine_class") != "expo.modules.queuelistener.GtcrnNoiseReducer":
        raise ValueError("Unexpected processing engine")
    if report.get("model", {}).get("sha256") != MODEL_SHA256:
        raise ValueError("Unexpected model identity")
    if report.get("input_manifest_sha256") != sha256(recordings / "device-inputs.json"):
        raise ValueError("Device input manifest mismatch")
    replays = {}
    for replay in report["replays"]:
        key = (replay["input_id"], replay["mode"])
        if key in replays:
            raise ValueError("Duplicate replay")
        replays[key] = replay
    expected = {(r["id"], mode) for r in source["records"] for mode in ("engine", "bypass")}
    if set(replays) != expected:
        raise ValueError("Missing or extra source/counterpart recordings")
    pairs = []
    for record in source["records"]:
        if ids is not None and record["id"] not in ids:
            continue
        before = (recordings / record["relative_path"]).resolve()
        if not before.is_relative_to(recordings) or sha256(before) != record["sha256"]:
            raise ValueError("Source audio changed")
        original = read_wav(before)
        for mode in ("engine", "bypass"):
            replay = replays[(record["id"], mode)]
            after = (device_run / replay["output_file"]).resolve()
            if not after.is_relative_to(device_run) or sha256(after) != replay["output_sha256"]:
                raise ValueError("Output path or hash mismatch")
            if replay["input_sha256"] != record["sha256"]:
                raise ValueError("Replay input identity mismatch")
            samples = read_wav(after)
            if len(samples) != len(original) or len(samples) != record["sample_count"]:
                raise ValueError("Sample count changed")
            if not replay.get("causal_unshifted") or replay.get("sample_zero_offset") != 0:
                raise ValueError("Output alignment was changed")
            if mode == "bypass" and pcm_bytes(samples) != pcm_bytes(original):
                raise ValueError("Bypass was not bit-identical")
            if mode == "engine":
                if not replay.get("all_engine_frames_active"):
                    raise ValueError(f"Fallback output is not fully denoised: {record['id']}")
                if replay.get("diagnostics", {}).get("fallback_reason"):
                    raise ValueError("Engine reported a fallback")
                pairs.append((record, before, after, replay))
    (output / "before").mkdir(parents=True)
    (output / "after").mkdir()
    records = []
    for record, before, after, replay in pairs:
        name = f"{record['id']}.wav"
        shutil.copyfile(before, output / "before" / name)
        shutil.copyfile(after, output / "after" / name)
        records.append({**record, "after_relative_path": f"after/{name}",
                        "after_sha256": replay["output_sha256"],
                        "all_engine_frames_active": True,
                        "algorithmic_delay_samples":
                            replay["diagnostics"]["algorithmic_delay_samples"]})
    manifest = {**source, "records": records,
                "source_recording_count": len(source_ids),
                "explicitly_excluded_ids": sorted(source_ids - {r["id"] for r in records}),
                "device_report_sha256": sha256(report_path), "model_sha256": MODEL_SHA256,
                "apk_sha256": deployment["apk_sha256"],
                "native_sha256": deployment["native_sha256"],
                "export_policy": ("Original amplitudes and lengths; causal delay retained; "
                                  "all frames enhanced; bit-identical bypass validated")}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings", type=Path, required=True)
    parser.add_argument("--device-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--id", action="append")
    args = parser.parse_args()
    manifest = export(args.recordings, args.device_run, args.output,
                      set(args.id) if args.id else None)
    print(json.dumps({"output": str(args.output), "validated_pairs": len(manifest["records"])}))


if __name__ == "__main__":
    main()
