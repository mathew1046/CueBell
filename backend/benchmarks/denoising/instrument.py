"""Run the installed debug test APK through platform Android instrumentation.

Installation is opt-in (--install), user 0 only. Inputs are copied unchanged into
the test package's private files/denoising/<label>; existing labels are refused.
Repeat --id / --mode for lists (never comma-separated). A successful command means
evidence was collected, NOT that every frame was denoised. Registration is separate.
Android API 35+ is required. Unlock the device normally for the visible test host.
The default bounded partial wake lock covers both arms; the screen is not kept on.
Allow the reported generous outer timeout, including at least 35s SIGTERM grace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from .audio import FRAME_SAMPLES, SAMPLE_RATE, read_wav, sha256

PACKAGE = "expo.modules.queuelistener.test"
RUNNER = "expo.modules.queuelistener.DenoisingBenchmarkInstrumentation"
ACTIVITY = "expo.modules.queuelistener.DenoisingBenchmarkActivity"
SERVICE = "expo.modules.queuelistener.DenoisingBenchmarkService"
CLEANUP_SECONDS = 30
ANDROID = "{http://schemas.android.com/apk/res/android}"
ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / "mobile/modules/queue-listener/android"
SOURCES = [
    Path(__file__), Path(__file__).with_name("audio.py"), NATIVE / "build.gradle",
    NATIVE / "src/androidTest/AndroidManifest.xml",
    *sorted((NATIVE / "src/androidTest/java/expo/modules/queuelistener").glob("*.kt")),
    *(NATIVE / "src/main/java/expo/modules/queuelistener" / name for name in (
        "PcmNoiseReducer.kt", "NoiseReductionDiagnostics.kt", "StreamingNoiseReducer.kt",
        "GtcrnNoiseReducer.kt",
    )),
]


def now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class TerminationRequested(BaseException):
    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(signal.Signals(signum).name)


@contextmanager
def termination_signals():
    state = {"received": [], "cleanup": False}

    def handle(signum, _frame):
        state["received"].append(signum)
        # A second signal must not interrupt own-package cleanup. SIGKILL cannot be caught.
        if len(state["received"]) == 1 and not state["cleanup"]:
            raise TerminationRequested(signum)

    previous = {sig: signal.signal(sig, handle) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield state
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value):
        raise ValueError(f"Unsafe identifier (repeat flags instead of commas): {value!r}")
    return value


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Empty relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or not re.fullmatch(r"[a-zA-Z0-9_.-]+", part)
           for part in parts):
        raise ValueError(f"Unsafe relative path: {value!r}")
    return value


def apk_identity(xml: str) -> dict:
    manifest = ET.fromstring(xml)
    package = manifest.get("package")
    application = manifest.find("application")
    runners = manifest.findall("instrumentation")
    if package != PACKAGE or application is None or len(runners) != 1:
        raise ValueError(f"Expected the single-runner {PACKAGE} test APK")
    runner = runners[0]
    name = runner.get(ANDROID + "name", "")
    if name.startswith("."):
        name = package + name
    elif "." not in name:
        name = package + "." + name
    if name != RUNNER or runner.get(ANDROID + "targetPackage") != package:
        raise ValueError("Only the self-targeting denoising test instrumentation is supported")
    if application.get(ANDROID + "debuggable") != "true":
        raise ValueError("Test APK must be debuggable for private run-as deployment")
    permissions = sorted(node.get(ANDROID + "name", "")
                         for node in manifest.findall("uses-permission"))
    activity = next((node for node in application.findall("activity")
                     if node.get(ANDROID + "name") == ACTIVITY), None)
    service = next((node for node in application.findall("service")
                    if node.get(ANDROID + "name") == SERVICE), None)
    service_type = service.get(ANDROID + "foregroundServiceType", "") if service is not None else ""
    return {"package": package, "runner": name, "target_package": package, "debuggable": True,
            "permissions": permissions,
            "foreground_host": {
                "activity": ACTIVITY if activity is not None else None,
                "activity_exported": activity.get(ANDROID + "exported")
                if activity is not None else None,
                "service": SERVICE if service is not None else None,
                "service_exported": service.get(ANDROID + "exported")
                if service is not None else None,
                "service_type": service_type,
            }}


def require_foreground_host(identity: dict) -> None:
    host = identity["foreground_host"]
    service_type = host["service_type"]
    media_only = service_type == "mediaProcessing"
    if re.fullmatch(r"0x[0-9a-fA-F]+|[0-9]+", service_type):
        media_only = int(service_type, 0) == 8192
    required = {"android.permission." + name for name in (
        "FOREGROUND_SERVICE", "FOREGROUND_SERVICE_MEDIA_PROCESSING", "WAKE_LOCK",
    )}
    forbidden = {"android.permission." + name for name in (
        "RECORD_AUDIO", "FOREGROUND_SERVICE_MICROPHONE",
    )}
    if (host["activity"] != ACTIVITY or host["service"] != SERVICE or not media_only
            or host["activity_exported"] != "false" or host["service_exported"] != "false"
            or not required.issubset(identity["permissions"])
            or forbidden.intersection(identity["permissions"])):
        raise ValueError("APK lacks the private fixture-only mediaProcessing foreground host; "
                         "build the new test sources and preserve the frozen v1 APK separately")


def inspect_apk(apk: Path, apkanalyzer: Path) -> tuple[dict, str]:
    result = subprocess.run([str(apkanalyzer), "manifest", "print", str(apk)],
                            check=True, capture_output=True, text=True, timeout=120)
    identity = apk_identity(result.stdout)
    with zipfile.ZipFile(apk) as archive:
        hashes = {}
        for name in sorted(archive.namelist()):
            if re.fullmatch(r"lib/[^/]+/[^/]+\.so", name):
                with archive.open(name) as stream:
                    hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        if not any(name.endswith("/libsherpa-onnx-jni.so") for name in hashes):
            raise ValueError("Test APK is missing the real sherpa JNI library")
        provenance = "assets/noise-reduction/runtime-provenance.json"
        identity["runtime_provenance"] = None
        if provenance in archive.namelist():
            raw = archive.read(provenance)
            identity["runtime_provenance"] = {
                "asset_path": provenance, "sha256": hashlib.sha256(raw).hexdigest(),
                "content": json.loads(raw),
            }
    identity["native_sha256"] = hashes
    return identity, result.stdout


def fixture_files(root: Path, ids: list[str], stress_input: str | None) -> tuple[dict, dict, list]:
    root = root.resolve()
    manifest = root / "device-inputs.json"
    data = json.loads(manifest.read_text())
    if (data.get("schema_version"), data.get("sample_rate"), data.get("frame_samples")) != (
        1, SAMPLE_RATE, FRAME_SAMPLES,
    ):
        raise ValueError("Expected device-inputs schema 1, mono PCM16 16000 Hz / 512 samples")
    inputs = data.get("inputs", [])
    if not inputs or not isinstance(inputs, list):
        raise ValueError("Empty input manifest")
    files = {"inputs/device-inputs.json": {"path": manifest, "sha256": sha256(manifest)}}
    seen = set()
    for item in inputs:
        name = identifier(item["id"])
        if name in seen:
            raise ValueError(f"Duplicate input ID: {name}")
        seen.add(name)
        identifier(item["case_id"])
        identifier(item["variant"])
        relative = relative_path(item["relative_path"])
        if not relative.startswith("audio/") or not relative.endswith(".wav"):
            raise ValueError("Fixture paths must be WAVs under audio/")
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Input path escaped fixture root or is missing: {relative}")
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Input SHA256 mismatch: {relative}")
        samples = read_wav(path)
        if (not samples or len(samples) != item["sample_count"]
                or len(samples) % FRAME_SAMPLES or item.get("sample_zero_offset") != 0):
            raise ValueError(f"Input count/framing/alignment mismatch: {relative}")
        target = "inputs/" + relative
        if target in files:
            raise ValueError(f"Duplicate input path: {relative}")
        files[target] = {"path": path, "sha256": item["sha256"]}
    if len(ids) != len(set(ids)) or any(identifier(name) not in seen for name in ids):
        raise ValueError("Unknown or duplicate --id")
    selected = [item for item in inputs if not ids or item["id"] in ids]
    if stress_input is not None and identifier(stress_input) not in {
        item["id"] for item in selected
    }:
        raise ValueError("--stress-input must be one of the selected IDs")
    return data, files, selected


def write_payload(path: Path, files: dict) -> None:
    # Explicit regular members only; never recursively archive a fixture directory.
    with tarfile.open(path, "w") as archive:
        for name, source in sorted(files.items()):
            relative_path(name)
            item = tarfile.TarInfo(name)
            item.size = source["path"].stat().st_size
            item.mode = 0o444
            with source["path"].open("rb") as stream:
                archive.addfile(item, stream)


def extract_results(path: Path, output: Path) -> None:
    # Runner files are flat. Validate the entire archive before writing any file.
    with tarfile.open(path) as archive:
        members = []
        seen = set()
        for member in archive.getmembers():
            if member.isdir() and member.name in (".", "./"):
                continue
            name = member.name.removeprefix("./")
            if (not member.isfile() or not re.fullmatch(
                r"results\.json|(?:stress|replay)-[a-zA-Z0-9_-]+\.(?:frames\.csv|wav)", name,
            ) or name in seen or (output / name).exists() or (output / name).is_symlink()):
                raise ValueError(f"Unsafe/duplicate/existing result archive member: {member.name}")
            seen.add(name)
            members.append((member, name))
        for member, name in members:
            with archive.extractfile(member) as source, (output / name).open("xb") as target:
                shutil.copyfileobj(source, target)


def verify_hashes(text: str, expected: dict[str, str]) -> None:
    observed = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(.+)", line)
        if not match or match[2] in observed:
            raise ValueError("Malformed/duplicate device sha256sum output")
        observed[match[2]] = match[1].lower()
    if observed != expected:
        raise ValueError("Device file hashes differ from immutable local inputs/APK")


def verify_report(output: Path, metadata: dict) -> dict:
    report = json.loads((output / "results.json").read_text())
    env = report.get("environment", {})
    if (report.get("schema_version") != 1 or report.get("status") != "completed"
            or env.get("entry_point") != "instrumentation"
            or env.get("test_apk_sha256") != metadata["apk_sha256"]
            or report.get("model", {}).get("sha256") != metadata["model_sha256"]
            or report.get("input_manifest_sha256") != metadata["input_manifest_sha256"]
            or report.get("options") != metadata["options"]):
        raise ValueError("Incomplete or mismatched instrumentation report; "
                         "retained as failed evidence")
    host = json.loads((output / "foreground-host.json").read_text())
    options = metadata["options"]
    initial = env.get("foreground_host", {})
    final = report.get("foreground_host_at_finish", {})
    wake_lock = options["wakeLock"] == "true"
    wake_lock_ms = int(options["lifecycleTimeoutSeconds"]) * 1000
    if (host.get("schema_version") != 1 or host.get("status") != "completed"
            or host.get("options") != options or host.get("service_destroyed") is not True
            or host.get("host_mode") != options["hostMode"]
            or host.get("service_type") != "mediaProcessing"
            or host.get("microphone_used") is not False or host.get("screen_kept_on") is not False
            or host.get("activity_finish_requested") is not True):
        raise ValueError("Incomplete or mismatched foreground lifecycle evidence")
    for snapshot in (initial, final):
        if (snapshot.get("service_type") != "mediaProcessing"
                or snapshot.get("service_component") != SERVICE
                or snapshot.get("host_mode") != options["hostMode"]
                or snapshot.get("foreground_requested") is not True
                or snapshot.get("wake_lock_requested") is not wake_lock
                or snapshot.get("wake_lock_held") is not wake_lock
                or snapshot.get("wake_lock_timeout_ms") != wake_lock_ms
                or snapshot.get("microphone_used") is not False
                or snapshot.get("screen_kept_on") is not False):
            raise ValueError("Mismatched foreground execution context")
    events = host.get("events", [])
    names = [event["event"] for event in events]
    if "service_ready" not in names or "starting_processing" not in names:
        raise ValueError("Missing foreground service startup evidence")
    if names.index("service_ready") > names.index("starting_processing"):
        raise ValueError("Processing started before foreground service was ready")
    if options["hostMode"] == "service-only" and (
        "activity_stopped" not in names
        or names.index("activity_stopped") > names.index("starting_processing")
    ):
        raise ValueError("Service-only work started before Activity stopped")
    destroyed = [event["details"] for event in events if event["event"] == "service_destroyed"]
    if not destroyed or destroyed[-1].get("wake_lock_held") is not False:
        raise ValueError("Service cleanup/wake-lock release was not confirmed")
    for entry in report.get("stages", []) + report.get("replays", []):
        key = "frames" if "frames_file" in entry else "output"
        name = relative_path(entry[f"{key}_file"])
        if len(PurePosixPath(name).parts) != 1 or sha256(output / name) != entry[f"{key}_sha256"]:
            raise ValueError(f"Result hash/path mismatch: {name}")
    return {
        "benchmark_completed": True,
        "fallback_stage_ids": [s["id"] for s in report.get("stages", [])
                               if s.get("fallback_reason") is not None
                               or s.get("first_fallback_frame") is not None],
        "inactive_engine_replay_ids": [r["input_id"] for r in report.get("replays", [])
                                       if r.get("mode") == "engine"
                                       and r.get("all_engine_frames_active") is not True],
        "reset_all_engine_frames_active": report.get("reset_check", {}).get(
            "all_engine_frames_active"),
        "thread_priority": report.get("thread_priority"),
        "environment": env,
        "foreground_lifecycle": host,
        "registration_performed": False,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    for name in ("adb", "apkanalyzer", "apk", "fixtures", "model", "output"):
        result.add_argument("--" + name, type=Path, required=True)
    result.add_argument("--serial", required=True)
    result.add_argument("--label", required=True, help="Fresh private directory label")
    result.add_argument("--install", action="store_true", help="Explicit test APK install/replace")
    result.add_argument("--duration-seconds", type=int, default=30)
    result.add_argument("--warmup-seconds", type=int, default=5)
    result.add_argument("--replay", action="store_true")
    result.add_argument("--no-stress", action="store_true")
    result.add_argument("--id", action="append", default=[], help="One ID; repeat for multiple")
    result.add_argument("--mode", action="append", choices=("engine", "bypass"),
                        help="One mode; repeat to set order. Default: engine then bypass")
    result.add_argument("--stress-input", help="ID from the selected inputs")
    result.add_argument("--host-mode", choices=("activity-and-service", "service-only"),
                        default="activity-and-service")
    result.add_argument("--wake-lock", action=argparse.BooleanOptionalAction, default=True,
                        help="Bounded partial CPU wake lock, identical for both arms (default on)")
    result.add_argument("--timeout-seconds", type=int,
                        help="Instrumentation deadline; default planned audio + 60s")
    return result


def run(args: argparse.Namespace) -> dict:
    with termination_signals() as signals:
        return _run(args, signals)


def _run(args: argparse.Namespace, signals: dict) -> dict:
    identifier(args.label)
    modes = args.mode or ["engine", "bypass"]
    if len(set(modes)) != len(modes):
        raise ValueError("Duplicate --mode")
    if not 1 <= args.duration_seconds <= 3600 or not 0 <= args.warmup_seconds <= 60:
        raise ValueError("duration-seconds must be 1..3600; warmup-seconds must be 0..60")
    if args.no_stress and not args.replay:
        raise ValueError("Select stress and/or --replay")
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite local benchmark evidence")
    args.output = args.output.resolve()
    args.apk, args.model = args.apk.resolve(strict=True), args.model.resolve(strict=True)
    _, files, selected = fixture_files(args.fixtures, args.id, args.stress_input)
    apk_sha256 = sha256(args.apk)
    identity, xml = inspect_apk(args.apk, args.apkanalyzer)
    require_foreground_host(identity)
    if sha256(args.apk) != apk_sha256:
        raise ValueError("APK changed during inspection; retry after the build finishes")
    files["gtcrn_simple.onnx"] = {"path": args.model, "sha256": sha256(args.model)}
    planned = len(modes) * (
        (0 if args.no_stress else args.duration_seconds + args.warmup_seconds)
        + (sum(item["sample_count"] / SAMPLE_RATE for item in selected) if args.replay else 0)
    )
    timeout = args.timeout_seconds if args.timeout_seconds is not None else math.ceil(planned) + 60
    if not max(15, math.ceil(planned) + 10) <= timeout <= 18000:
        raise ValueError("timeout-seconds must allow planned audio + 10s, within 15..18000")
    metadata = {
        "schema_version": 1, "status": "preparing", "started_utc": now(), "user_id": 0,
        "entry_point": "installed platform instrumentation", "serial": args.serial,
        "test_apk": {**identity, "path": str(args.apk)}, "apk_sha256": apk_sha256,
        "model_sha256": files["gtcrn_simple.onnx"]["sha256"],
        "input_manifest_sha256": files["inputs/device-inputs.json"]["sha256"],
        "files": {name: {**info, "path": str(info["path"])} for name, info in files.items()},
        "installation_requested": args.install, "security_settings_changed": False,
        "host_python": platform.python_version(), "commands": [], "sources": [],
        "host_pid": os.getpid(), "microphone_used": False,
        "timing": {"planned_audio_s": planned, "instrumentation_timeout_s": timeout,
                   "cleanup_command_budget_s": CLEANUP_SECONDS,
                   "recommended_outer_timeout_s": timeout + 300 + (180 if args.install else 0),
                   "recommended_sigterm_grace_s": CLEANUP_SECONDS + 5},
        "source_snapshot_scope": "working tree at launch; APK hash is build identity; "
                                 "source snapshots alone do not establish APK build provenance",
    }
    args.output.mkdir(parents=True)
    def save() -> None:
        atomic_json(args.output / "deployment.json", metadata)

    save()
    evidence = args.output / "deployment"
    (evidence / "commands").mkdir(parents=True)
    (evidence / "apk-manifest.xml").write_text(xml)
    shutil.copyfile(args.fixtures / "device-inputs.json", evidence / "device-inputs.json")
    snapshots = [*SOURCES, args.apk.with_name("output-metadata.json")]
    for source in snapshots:
        if source.is_file():
            relative = (source.relative_to(ROOT) if source.is_relative_to(ROOT)
                        else Path("external") / source.name)
            dest = evidence / "source" / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            metadata["sources"].append({"path": str(source), "sha256": sha256(dest),
                                        "snapshot": str(dest.relative_to(args.output))})
    adb = [str(args.adb), "-s", args.serial]
    package = identity["package"]
    cleanup_deadline = None

    def command(parts: list[str], name: str, *, timeout: float = 120,
                check: bool = True, stdin: Path | None = None,
                stdout: Path | None = None, binary: bool = False) -> str:
        base = evidence / "commands" / f"{len(metadata['commands']):03d}-{name}"
        out = stdout or base.with_suffix(".stdout")
        err = base.with_suffix(".stderr")
        if cleanup_deadline is not None:
            timeout = min(timeout, max(0, cleanup_deadline - time.monotonic()))
        record = {"argv": [*adb, *parts], "started_utc": now(), "timeout_s": timeout,
                  "status": "running", "started_monotonic_ns": time.monotonic_ns(),
                  "stdout": str(out), "stderr": str(err)}
        if stdin:
            record["stdin_sha256"] = sha256(stdin)
        if binary:
            record["stdout_is_temporary_archive"] = True
        metadata["commands"].append(record)
        save()  # Persist the inflight command before blocking in adb (even SIGKILL leaves this).
        source = stdin.open("rb") if stdin else subprocess.DEVNULL
        try:
            if timeout <= 0:
                record["status"] = "skipped"
                raise TimeoutError(f"Cleanup command budget exhausted; skipped {name}")
            with out.open("wb") as output, err.open("wb") as error:
                completed = subprocess.run(record["argv"], stdin=source, stdout=output,
                                           stderr=error, timeout=timeout)
            record["exit_code"] = completed.returncode
            record["status"] = "completed" if completed.returncode == 0 else "failed"
            if binary:
                record["stdout_sha256"] = sha256(out)
            if check and completed.returncode != 0:
                raise RuntimeError(f"{name} failed ({completed.returncode}); see {err} and {out}")
            return "" if binary else out.read_text(errors="replace")
        except BaseException as error:
            if record["status"] != "skipped":
                record["status"] = "failed"
            record["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            if stdin:
                source.close()
            record["ended_utc"] = now()
            save()

    def shell(parts: list[str], name: str, **kwargs) -> str:
        return command(["shell", "-T", shlex.join(parts)], name, **kwargs)

    def own(parts: list[str], name: str, **kwargs) -> str:
        return shell(["run-as", package, *parts], name, **kwargs)

    def best_effort(operation, name: str) -> None:
        try:
            operation()
        except Exception as error:
            metadata.setdefault("collection_errors", []).append(f"{name}: {error}")
            save()

    remote = None
    uid = None
    device_start = None
    instrumentation_may_be_running = False
    try:
        command(["version"], "adb-version")
        sdk = shell(["getprop", "ro.build.version.sdk"], "android-api").strip()
        if not sdk.isdecimal() or int(sdk) < 35:
            raise ValueError("mediaProcessing foreground benchmark requires Android API 35+")
        metadata["device_sdk_int"] = int(sdk)
        if args.install:
            command(["install", "--user", "0", "-r", "-t", str(args.apk)], "install", timeout=180)
        paths = shell(["pm", "path", "--user", "0", package], "installed-apk").splitlines()
        if len(paths) != 1 or not paths[0].startswith("package:/"):
            raise ValueError("Install the exact monolithic debug test APK first, or pass --install")
        installed = paths[0].removeprefix("package:")
        verify_hashes(own(["sha256sum", installed], "installed-apk-hash"),
                      {installed: metadata["apk_sha256"]})
        metadata["installed_apk_path"] = installed
        shell(["dumpsys", "package", package], "installed-package", check=False)
        home = own(["pwd"], "package-home").strip()
        if home not in (f"/data/user/0/{package}", f"/data/data/{package}"):
            raise ValueError(f"Unexpected user-0 private package directory: {home!r}")
        uid = own(["id", "-u"], "package-uid").strip()
        if not uid.isdecimal():
            raise ValueError("Cannot determine test package UID")
        metadata["package_uid"] = int(uid)
        # mkdir without -p on the final label atomically refuses reuse. Reject parent symlinks.
        relative = "files/denoising/" + args.label
        own(["sh", "-c", "set -eu; test ! -L files; mkdir -p files; "
             "test ! -L files/denoising; mkdir -p files/denoising; mkdir " + relative],
            "create-private-root")
        remote = home + "/" + relative
        metadata["device_root"] = remote
        with tempfile.TemporaryDirectory(prefix="cuebell-instrument-", dir="/tmp/opencode") as temp:
            payload = Path(temp) / "inputs.tar"
            write_payload(payload, files)
            own(["tar", "-xf", "-", "-C", remote], "deploy-inputs", stdin=payload)
        expected = {remote + "/" + name: info["sha256"] for name, info in files.items()}
        verify_hashes(own(["sha256sum", *expected], "input-hashes-before"), expected)
        metadata["input_hashes_verified_before"] = True
        options = {
            "inputDir": remote + "/inputs", "outputDir": remote + "/results",
            "modelPath": remote + "/gtcrn_simple.onnx", "label": args.label,
            "durationSeconds": str(args.duration_seconds),
            "warmupSeconds": str(args.warmup_seconds), "modes": ",".join(modes),
            "stress": str(not args.no_stress).lower(), "replay": str(args.replay).lower(),
            "apkSha256": metadata["apk_sha256"],
            "hostMode": args.host_mode, "wakeLock": str(args.wake_lock).lower(),
            "lifecycleTimeoutSeconds": str(timeout),
        }
        if args.id:
            options["ids"] = ",".join(args.id)
        if args.stress_input:
            options["stressInput"] = args.stress_input
        metadata["options"] = options
        metadata["status"] = "running"
        save()
        print(f"Instrumentation deadline {timeout}s; cleanup command budget {CLEANUP_SECONDS}s; "
              f"recommended outer timeout {metadata['timing']['recommended_outer_timeout_s']}s "
              f"with {CLEANUP_SECONDS + 5}s SIGTERM grace.", file=sys.stderr)
        shell(["getprop"], "device-properties")
        for service in ("battery", "thermalservice", "power"):
            shell(["dumpsys", service], service + "-before", check=False)
        device_start = shell(["date", "+%m-%d %H:%M:%S.000"], "device-start").strip()
        # Raw mode preserves the result code even when the runner returns a stream.
        invocation = ["am", "instrument", "--user", "0", "-w", "-r"]
        for key, value in options.items():
            invocation.extend(["-e", key, value])
        invocation.append(package + "/" + identity["runner"])
        instrumentation_may_be_running = True
        log = shell(invocation, "instrument", timeout=timeout, stdout=args.output / "device.log")
        codes = re.findall(r"^INSTRUMENTATION_CODE:\s*(-?\d+)\s*$", log, re.MULTILINE)
        metadata["instrumentation_codes"] = codes
        if codes != ["-1"] or "INSTRUMENTATION_FAILED" in log:
            raise RuntimeError("Instrumentation did not finish RESULT_OK (-1); see device.log")
        instrumentation_may_be_running = False
        verify_hashes(own(["sha256sum", *expected], "input-hashes-after"), expected)
        metadata["input_hashes_verified_after"] = True
        metadata["status"] = "collected"
    except BaseException as error:
        metadata["status"] = "failed"
        metadata["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        signals["cleanup"] = True
        cleanup_deadline = time.monotonic() + CLEANUP_SECONDS
        metadata["cleanup_started_utc"] = now()
        save()
        if instrumentation_may_be_running:
            # Terminating host adb need not stop Android. Cancel only this test package first.
            best_effort(lambda: shell(["am", "force-stop", "--user", "0", package],
                                      "cancel-instrumentation", timeout=10),
                        "cancel-instrumentation")

        def collect_results() -> None:
            with tempfile.TemporaryDirectory(prefix="cuebell-result-", dir="/tmp/opencode") as temp:
                archive = Path(temp) / "results.tar"
                command(["exec-out", shlex.join(["run-as", package, "tar", "-cf", "-",
                                                "-C", remote + "/results", "."])],
                        "pull-results", stdout=archive, binary=True)
                extract_results(archive, args.output)
        if remote is not None:
            best_effort(lambda: own(["cat", remote + "/foreground-host.json"], "foreground-host",
                                    stdout=args.output / "foreground-host.json", timeout=5),
                        "foreground-host")
            best_effort(collect_results, "pull-results")
            for service in ("battery", "thermalservice", "power"):
                best_effort(lambda service=service: shell(["dumpsys", service],
                            service + "-after", check=False, timeout=3), service + "-after")
        if uid is not None and device_start:
            best_effort(lambda: shell(["logcat", "-d", "-v", "threadtime", "--uid=" + uid,
                                      "-T", device_start], "app-logcat", check=False, timeout=3),
                        "app-logcat")
        if metadata["status"] == "collected":
            try:
                metadata["outcome"] = verify_report(args.output, metadata)
                metadata["status"] = "completed"
            except Exception as error:
                metadata["status"] = "failed"
                metadata["error"] = f"{type(error).__name__}: {error}"
        metadata["ended_utc"] = now()
        metadata["termination_signals"] = signals["received"]
        if signals["received"]:
            metadata["status"] = "failed"
            metadata.setdefault("error", f"TerminationRequested: "
                                f"{signal.Signals(signals['received'][0]).name}")
        save()
    if signals["received"]:
        raise TerminationRequested(signals["received"][0])
    if metadata["status"] != "completed":
        raise RuntimeError(metadata.get("error", "Unable to collect complete evidence"))
    return metadata


def main() -> None:
    args = parser().parse_args()
    try:
        metadata = run(args)
    except TerminationRequested as error:
        print(f"Instrumentation benchmark interrupted: {error}", file=sys.stderr)
        raise SystemExit(128 + error.signum) from error
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Instrumentation benchmark failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps({"output": str(args.output), "status": metadata["status"],
                      "outcome": metadata["outcome"]}, indent=2))


if __name__ == "__main__":
    main()
