"""Run the production denoiser through its Android app_process benchmark entry.

This uses a test APK as a DEX classpath, not an installed microphone service.
No microphone, provider request, or phone security-setting change is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import tempfile
import zipfile
from pathlib import Path

REFERENCE_JNI_SHA256 = "491b1b6e287fdfe5e0e1ffa918f5e5556299cb14bea7b7b8a0c19468f4156193"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fft_overlay(directory: Path, model: Path, lock_path: Path) -> tuple[Path, dict]:
    """Accept only the separately reviewed same-model native experiment."""
    lock = json.loads(lock_path.read_text())
    provenance = json.loads((directory / "provenance.json").read_text())
    if provenance.get("officialBinary") is not False:
        raise ValueError("FFT overlay must identify itself as a modified binary")
    for key, expected in lock.items():
        if provenance.get(key) != expected:
            raise ValueError(f"FFT provenance does not match the reviewed lock: {key}")
    library = directory / "arm64-v8a/libsherpa-onnx-jni.so"
    if digest(library) != lock["librarySha256"] or library.stat().st_size != lock["libraryBytes"]:
        raise ValueError("FFT binary does not match the reviewed lock")
    if digest(model) != lock["modelSha256"]:
        raise ValueError("FFT experiment requires the unchanged reviewed GTCRN model")
    return library, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device-root", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=int, default=30)
    parser.add_argument("--warmup-seconds", type=int, default=5)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--no-stress", action="store_true")
    parser.add_argument("--id", action="append", default=[])
    parser.add_argument(
        "--sherpa-fft-dir",
        type=Path,
        help="Explicit, locked arm64 JNI overlay; keeps the reference APK unchanged",
    )
    args = parser.parse_args()
    root = args.device_root.rstrip("/")
    if not root.startswith("/data/local/tmp/cuebell-denoising-") or ".." in root:
        parser.error("Use a unique /data/local/tmp/cuebell-denoising-* directory")
    if args.output.exists():
        parser.error("Refusing to overwrite local benchmark evidence")
    if not 1 <= args.duration_seconds <= 3600 or not 0 <= args.warmup_seconds <= 60:
        parser.error("Invalid duration")
    overlay_library = None
    overlay_provenance = None
    if args.sherpa_fft_dir:
        lock_path = (
            Path(__file__).resolve().parents[3]
            / "mobile/modules/queue-listener/android/native/sherpa-fft/artifact-lock.json"
        )
        overlay_library, overlay_provenance = fft_overlay(
            args.sherpa_fft_dir, args.model, lock_path
        )
    adb = [str(args.adb), "-s", args.serial]

    def command(*parts: str, timeout: float = 120, check: bool = True):
        return subprocess.run(
            [*adb, *parts], check=check, timeout=timeout, capture_output=True, text=True
        )

    if command("shell", f"test -e {shlex.quote(root)}", check=False).returncode == 0:
        parser.error("Device directory already exists; choose a new run ID")
    args.output.mkdir(parents=True)
    metadata = {
        "entry_point": "app_process64; production Kotlin/JNI through debug test APK",
        "serial": args.serial,
        "apk_sha256": digest(args.apk),
        "model_sha256": digest(args.model),
        "input_manifest_sha256": digest(args.fixtures / "device-inputs.json"),
        "device_root": root,
        "security_settings_changed": False,
        "native_overlay": overlay_provenance,
        "runtime_identity_source": "Actual deployed library hashes, not embedded APK provenance",
    }
    command("shell", f"mkdir -p {shlex.quote(root + '/lib')}")
    command("push", str(args.apk), root + "/benchmark.apk")
    command("push", str(args.fixtures), root + "/inputs")
    command("push", str(args.model), root + "/gtcrn_simple.onnx")
    with tempfile.TemporaryDirectory(prefix="cuebell-jni-", dir=args.output) as local:
        with zipfile.ZipFile(args.apk) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.startswith("lib/arm64-v8a/") and name.endswith(".so")
            ]
            if not any(name.endswith("libsherpa-onnx-jni.so") for name in members):
                raise ValueError("Test APK lacks the arm64 sherpa JNI library")
            metadata["native_sha256"] = {}
            for name in members:
                path = Path(local) / Path(name).name
                path.write_bytes(archive.read(name))
                if path.name == "libsherpa-onnx-jni.so" and overlay_library is not None:
                    if digest(path) != REFERENCE_JNI_SHA256:
                        raise ValueError("FFT overlay requires the pinned official reference JNI")
                    metadata["reference_jni_sha256"] = digest(path)
                    path.write_bytes(overlay_library.read_bytes())
                metadata["native_sha256"][path.name] = digest(path)
                command("push", str(path), root + "/lib/" + path.name)
                remote_hash = command(
                    "shell", "sha256sum " + shlex.quote(root + "/lib/" + path.name)
                ).stdout.split()[0]
                if remote_hash != digest(path):
                    raise ValueError(f"Device native-library hash mismatch: {path.name}")
    command("shell", f"chmod 444 {shlex.quote(root + '/benchmark.apk')}")
    options = {
        "inputDir": root + "/inputs",
        "outputDir": root + "/results",
        "modelPath": root + "/gtcrn_simple.onnx",
        "durationSeconds": str(args.duration_seconds),
        "warmupSeconds": str(args.warmup_seconds),
        "stress": str(not args.no_stress).lower(),
        "replay": str(args.replay).lower(),
        "apkSha256": metadata["apk_sha256"],
        "label": args.output.name,
    }
    if args.id:
        options["ids"] = ",".join(args.id)
    remote = " ".join(
        [
            "CLASSPATH=" + shlex.quote(root + "/benchmark.apk"),
            "LD_LIBRARY_PATH=" + shlex.quote(root + "/lib"),
            "/system/bin/app_process64",
            shlex.quote("-Djava.library.path=" + root + "/lib"),
            "/system/bin",
            "expo.modules.queuelistener.DenoisingBenchmarkMain",
            *(shlex.quote(f"{key}={value}") for key, value in options.items()),
        ]
    )
    metadata["command"] = remote
    inputs = json.loads((args.fixtures / "device-inputs.json").read_text())["inputs"]
    replay_seconds = sum(
        item["sample_count"] / 16000
        for item in inputs
        if not args.id or item["id"] in args.id
    ) * 2 if args.replay else 0
    stress_seconds = 2 * (args.duration_seconds + args.warmup_seconds) if not args.no_stress else 0
    timeout = replay_seconds + stress_seconds + 180
    try:
        with (args.output / "device.log").open("w") as log:
            result = subprocess.run(
                [*adb, "shell", remote], stdout=log, stderr=subprocess.STDOUT, timeout=timeout
            )
        metadata["exit_code"] = result.returncode
    finally:
        pulled = command("pull", root + "/results/.", str(args.output), check=False)
        metadata["pull_exit_code"] = pulled.returncode
        (args.output / "deployment.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "exit_code": metadata.get("exit_code")}))
    raise SystemExit(metadata.get("exit_code", 1))


if __name__ == "__main__":
    main()
