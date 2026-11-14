"""Paired, no-reference DNSMOS SIG/BAK/OVRL proxies on unchanged causal WAVs.

Requires numpy, onnxruntime and soundfile; no P808 model or resampling libraries.
Pairs exact filenames in two flat directories. Any failed pair produces a nonzero
CLI exit and explicit JSON errors; aggregates include successful pairs only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import statistics
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

SOURCE_COMMIT = "785ab12275d5cf9341c5e946b0eee9f8825ece3b"
BASE_URL = f"https://raw.githubusercontent.com/microsoft/DNS-Challenge/{SOURCE_COMMIT}"
ASSETS = {
    "sig_bak_ovr.onnx": {
        "url": BASE_URL + "/DNSMOS/DNSMOS/sig_bak_ovr.onnx",
        "sha256": "269fbebdb513aa23cddfbb593542ecc540284a91849ac50516870e1ac78f6edd",
    },
    "dnsmos_local.py": {
        "url": BASE_URL + "/DNSMOS/dnsmos_local.py",
        "sha256": "1ab566afe006daab32ac7073296a5d0ef99f8b82f91c7266f3ccf26113d7a28b",
    },
}
DEFAULT_CACHE = Path.home() / ".cache/cuebell/dnsmos"
SAMPLE_RATE = 16000
INPUT_SECONDS = 9.01
INPUT_SAMPLES = int(INPUT_SECONDS * SAMPLE_RATE)
METRICS = ("SIG", "BAK", "OVRL")
POLYNOMIALS = {
    "SIG": [-0.08397278, 1.22083953, 0.0052439],
    "BAK": [-0.13166888, 1.60915514, -0.39604546],
    "OVRL": [-0.06766283, 1.11546468, 0.04602535],
}
DEPENDENCIES = {"numpy": "2.3.4", "onnxruntime": "1.23.2", "soundfile": "0.13.1"}
LIMITATIONS = [
    "DNSMOS values are model predictions, not human listening MOS, intelligibility or ASR proof.",
    "No clean reference, speech transcription or real-provider latency is measured.",
    "RMS attenuation/noise suppression alone cannot establish preserved speech or success.",
    "Short audio is doubled in memory as in the official algorithm; repetition changes context.",
    "Official window/hop arithmetic can leave a trailing region unscored; coverage is reported.",
    "Full causal audio, including startup delay/padding, is retained without alignment/trimming.",
    "Rail/full-scale sample counts indicate possible clipping, not verified historical clipping.",
    "Aggregates are descriptive, equal-clip-weight proxies on successful pairs, not a ship gate.",
]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_assets(cache: Path, download: bool = False) -> dict:
    cache = cache.expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    for name, asset in ASSETS.items():
        path = cache / name
        if not path.exists():
            if not download:
                raise FileNotFoundError(f"Missing {path}; pass --download-model once")
            with urlopen(asset["url"], timeout=60) as response:
                data = response.read(16 * 1024 * 1024)
            if hashlib.sha256(data).hexdigest() != asset["sha256"]:
                raise ValueError(f"Downloaded official artifact SHA256 mismatch: {asset['url']}")
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            try:
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        if sha256(path) != asset["sha256"]:
            raise ValueError(f"Cached official artifact SHA256 mismatch: {path}")
    provenance = {"schema_version": 1, "repository": "https://github.com/microsoft/DNS-Challenge",
                  "source_commit": SOURCE_COMMIT, "assets": ASSETS,
                  "model_family": "non-personalized DNSMOS SIG/BAK/OVRL", "p808_used": False}
    metadata = cache / "provenance.json"
    if metadata.exists():
        if json.loads(metadata.read_text()) != provenance:
            raise ValueError(f"Cached provenance differs from pinned scorer: {metadata}")
    else:
        write_json(metadata, provenance)
    return {**provenance, "cache": str(cache), "metadata_sha256": sha256(metadata),
            "model_path": str(cache / "sig_bak_ovr.onnx"),
            "reference_source_path": str(cache / "dnsmos_local.py")}


def wave_data_bytes(data: bytes) -> int:
    """Reject incomplete RIFF files instead of libsndfile silently shortening PCM."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Expected a complete little-endian RIFF/WAVE file")
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ValueError("RIFF byte length mismatch (truncated or trailing data)")
    offset, sizes = 12, []
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        end = offset + 8 + size
        if end > len(data):
            raise ValueError("WAV chunk extends beyond the file")
        if data[offset:offset + 4] == b"data":
            sizes.append(size)
        offset = end + size % 2
    if offset != len(data) or len(sizes) != 1:
        raise ValueError("Expected exactly one complete WAV data chunk")
    return sizes[0]


def load_wav(path: Path):
    import numpy as np
    import soundfile as sf

    # Hash the exact bytes decoded, even if the pathname is replaced concurrently.
    data = path.read_bytes()
    data_bytes = wave_data_bytes(data)
    bits_by_subtype = {"PCM_U8": 8, "PCM_16": 16, "PCM_24": 24, "PCM_32": 32,
                       "FLOAT": 32, "DOUBLE": 64}
    with sf.SoundFile(io.BytesIO(data)) as stream:
        if stream.samplerate != SAMPLE_RATE or stream.channels != 1:
            raise ValueError(f"Expected mono 16000 Hz, got {stream.channels} channels "
                             f"at {stream.samplerate} Hz; resampling/downmixing is disabled")
        if stream.subtype not in bits_by_subtype:
            raise ValueError(f"Expected uncompressed PCM/IEEE-float WAV, got {stream.subtype}")
        subtype, frames = stream.subtype, stream.frames
        audio = stream.read(dtype="float64", always_2d=False)
    if (not len(audio) or len(audio) != frames
            or data_bytes != frames * (bits_by_subtype[subtype] // 8)):
        raise ValueError("WAV sample/byte length mismatch or empty recording")
    if audio.ndim != 1 or not np.isfinite(audio).all():
        raise ValueError("Audio must be mono and contain only finite samples")
    peak = float(np.max(np.abs(audio)))
    rms = peak * math.sqrt(float(np.mean((audio / peak) ** 2))) if peak else 0.0
    positive_rail = 1.0
    if subtype.startswith("PCM_"):
        positive_rail -= 2.0 ** (1 - bits_by_subtype[subtype])
    return audio, {
        "path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
        "sample_rate": SAMPLE_RATE, "channels": 1, "subtype": subtype,
        "sample_count": frames, "duration_s": frames / SAMPLE_RATE,
        "rms": rms, "rms_dbfs": 20 * math.log10(rms) if rms else None,
        "peak_abs": peak, "minimum": float(np.min(audio)), "maximum": float(np.max(audio)),
        "clipped_count": int(np.count_nonzero((audio <= -1.0) | (audio >= positive_rail))),
        "clipping_thresholds": {"negative": -1.0, "positive": positive_rail},
        "zero_count": int(np.count_nonzero(audio == 0.0)),
        "sample_zero_offset": 0,
    }


def score_audio(session, audio) -> dict:
    import numpy as np

    audio = np.asarray(audio)
    if audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise ValueError("DNSMOS requires nonempty, finite, mono audio")
    original_count, doublings = len(audio), 0
    while len(audio) < INPUT_SAMPLES:
        audio = np.append(audio, audio)
        doublings += 1
    # Deliberately preserve upstream's floor-before-subtraction and int truncation.
    num_hops = int(np.floor(len(audio) / SAMPLE_RATE) - INPUT_SECONDS) + 1
    windows, skipped = [], []
    for index in range(num_hops):
        start = int(index * SAMPLE_RATE)
        end = int((index + INPUT_SECONDS) * SAMPLE_RATE)
        segment = audio[start:end]
        if len(segment) < INPUT_SAMPLES:
            skipped.append(index)
            continue
        with np.errstate(over="ignore", invalid="ignore"):
            features = np.array(segment).astype("float32")[np.newaxis, :]
        if not np.isfinite(features).all():
            raise ValueError(f"Window {index} is not representable as finite float32")
        prediction = np.asarray(session.run(None, {"input_1": features})[0])
        if prediction.shape != (1, 3) or not np.isfinite(prediction).all():
            raise ValueError(f"Window {index}: expected three finite model outputs; "
                             f"got shape {prediction.shape}")
        raw = dict(zip(METRICS, map(float, prediction[0]), strict=True))
        calibrated = {key: float(np.poly1d(POLYNOMIALS[key])(prediction[0, column]))
                      for column, key in enumerate(METRICS)}
        if not all(math.isfinite(value) for value in calibrated.values()):
            raise ValueError(f"Window {index}: non-finite polynomial-calibrated score")
        windows.append({"index": index, "start_sample": start, "end_sample": end,
                        "raw": raw, "scores": calibrated})
    if not windows:
        raise ValueError("Official DNSMOS segmentation produced no complete windows")
    covered = windows[-1]["end_sample"]
    return {
        "scores": {key: float(np.mean([row["scores"][key] for row in windows])) for key in METRICS},
        "raw_scores": {key: float(np.mean(np.array([row["raw"][key] for row in windows],
                                                   dtype=np.float32))) for key in METRICS},
        "original_sample_count": original_count, "evaluation_sample_count": len(audio),
        "repeat_doublings": doublings, "repeat_factor": 2 ** doublings,
        "num_hops": num_hops, "evaluated_windows": len(windows), "skipped_hops": skipped,
        "evaluation_unscored_tail_samples": len(audio) - covered,
        "original_unscored_tail_samples": max(0, original_count - covered),
        "windows": windows,
    }


def failure(stage: str, error: Exception) -> dict:
    return {"stage": stage, "exception_type": type(error).__name__, "message": str(error)}


def aggregate(clips: list[dict]) -> dict:
    good = [clip for clip in clips if clip["status"] == "completed"]
    result = {"total_pairs": len(clips), "scored_pairs": len(good),
              "failed_pairs": len(clips) - len(good), "weighting": "equal weight per scored clip",
              "metrics": {}}
    for key in METRICS:
        deltas = [clip["delta"][key] for clip in good]
        result["metrics"][key] = {
            "before_mean": statistics.mean(clip["before"]["dnsmos"]["scores"][key]
                                           for clip in good) if good else None,
            "after_mean": statistics.mean(clip["after"]["dnsmos"]["scores"][key]
                                          for clip in good) if good else None,
            "delta_mean": statistics.mean(deltas) if deltas else None,
            "delta_median": statistics.median(deltas) if deltas else None,
            "delta_min": min(deltas) if deltas else None,
            "delta_max": max(deltas) if deltas else None,
            "positive_delta_pairs": sum(delta > 0 for delta in deltas),
            "negative_delta_pairs": sum(delta < 0 for delta in deltas),
            "zero_delta_pairs": sum(delta == 0 for delta in deltas),
        }
    return result


def score_pairs(before: Path, after: Path, session) -> list[dict]:
    directories = {"before": before.resolve(strict=True), "after": after.resolve(strict=True)}
    names = set()
    for root in directories.values():
        names.update(path.name for path in root.iterdir() if path.suffix.lower() == ".wav")
    if not names:
        raise ValueError("No WAV filenames found in the two flat directories")
    clips = []
    for name in sorted(names):
        clip = {"filename": name, "status": "failed", "errors": []}
        signals = {}
        for side, root in directories.items():
            try:
                signals[side], clip[side] = load_wav(root / name)
            except Exception as error:
                clip["errors"].append(failure(side + ".validation", error))
        if len(signals) == 2 and len(signals["before"]) != len(signals["after"]):
            clip["errors"].append(failure("pair.validation", ValueError(
                f"Sample count mismatch: before={len(signals['before'])}, "
                f"after={len(signals['after'])}; no trimming/alignment is permitted")))
        if not clip["errors"]:
            for side in directories:
                try:
                    clip[side]["dnsmos"] = score_audio(session, signals[side])
                except Exception as error:
                    clip["errors"].append(failure(side + ".inference", error))
        if not clip["errors"]:
            clip["status"] = "completed"
            clip["delta"] = {key: clip["after"]["dnsmos"]["scores"][key]
                             - clip["before"]["dnsmos"]["scores"][key] for key in METRICS}
        clips.append(clip)
    return clips


def run(args: argparse.Namespace) -> dict:
    if args.output.exists() or args.output.is_symlink():
        raise ValueError(f"Refusing to overwrite quality evidence: {args.output}")
    report = {
        "schema_version": 1, "status": "failed", "started_utc": datetime.now(UTC).isoformat(),
        "before_directory": str(args.before.resolve()),
        "after_directory": str(args.after.resolve()),
        "scorer": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__))},
        "algorithm": {"source_commit": SOURCE_COMMIT, "sample_rate": SAMPLE_RATE,
                      "window_seconds": INPUT_SECONDS, "window_samples": INPUT_SAMPLES,
                      "hop_seconds": 1, "nonpersonal_polynomials": POLYNOMIALS,
                      "alignment": "causal-unshifted", "normalization": False,
                      "resampling": False, "trimming": False, "p808_used": False,
                      "delta_direction": "after minus before; higher proxy scores are better"},
        "limitations": LIMITATIONS, "clips": [], "errors": [],
    }
    try:
        if not 1 <= args.threads <= 32:
            raise ValueError("--threads must be 1..32")
        provenance = prepare_assets(args.cache, args.download_model)
        report["provenance"] = provenance
        try:
            import onnxruntime as ort
            import soundfile as sf

            versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
        except ImportError as error:
            pins = " ".join(f"{name}=={version}" for name, version in DEPENDENCIES.items())
            raise RuntimeError(f"DNSMOS dependencies missing; install {pins}") from error
        options = ort.SessionOptions()
        options.intra_op_num_threads = args.threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(provenance["model_path"], sess_options=options,
                                       providers=["CPUExecutionProvider"])
        inputs = session.get_inputs()
        if (len(inputs) != 1 or inputs[0].name != "input_1" or inputs[0].type != "tensor(float)"
                or inputs[0].shape[1:] != [INPUT_SAMPLES]):
            raise ValueError("Unexpected official DNSMOS model input contract")
        report["runtime"] = {"python": platform.python_version(), "platform": platform.platform(),
                             "packages": versions, "libsndfile": sf.__libsndfile_version__,
                             "providers": session.get_providers(), "intra_op_threads": args.threads,
                             "inter_op_threads": 1, "execution_mode": "ORT_SEQUENTIAL"}
        report["clips"] = score_pairs(args.before, args.after, session)
        report["errors"] = [{"filename": clip["filename"], **error}
                            for clip in report["clips"] for error in clip["errors"]]
    except Exception as error:
        report["errors"].append(failure("setup_or_scoring", error))
    report["aggregate"] = aggregate(report["clips"])
    if report["aggregate"]["scored_pairs"]:
        report["status"] = "partial" if report["errors"] else "completed"
    report["ended_utc"] = datetime.now(UTC).isoformat()
    write_json(args.output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh JSON report path")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--download-model", action="store_true",
                        help="Fetch missing pinned official model/source into the reusable cache")
    parser.add_argument("--threads", type=int, default=1, help="Offline CPU scoring threads")
    args = parser.parse_args()
    try:
        report = run(args)
    except (OSError, ValueError) as error:
        print(f"DNSMOS scoring failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps({"output": str(args.output.resolve()), "status": report["status"],
                      "aggregate": report["aggregate"], "errors": report["errors"]}, indent=2))
    if report["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
