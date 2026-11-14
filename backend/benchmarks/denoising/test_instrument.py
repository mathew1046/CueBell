"""Offline transport/provenance tests. No adb, APK install, or benchmark job is run."""

import copy
import hashlib
import io
import json
import os
import shlex
import signal
import subprocess
import tarfile
import zipfile

import pytest

from benchmarks.denoising import instrument
from benchmarks.denoising.audio import FRAME_SAMPLES, sha256, write_wav

XML = f"""<manifest xmlns:android="http://schemas.android.com/apk/res/android"
package="{instrument.PACKAGE}">
<instrumentation android:name="{instrument.RUNNER}"
android:targetPackage="{instrument.PACKAGE}" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PROCESSING" />
<uses-permission android:name="android.permission.WAKE_LOCK" />
<application android:debuggable="true">
<activity android:name="{instrument.ACTIVITY}" android:exported="false" />
<service android:name="{instrument.SERVICE}" android:exported="false"
android:foregroundServiceType="mediaProcessing" />
</application></manifest>"""


@pytest.fixture
def fixture_tree(tmp_path):
    root = tmp_path / "fixtures"
    entries = []
    for variant in ("clean", "colored-snr-p0"):
        relative = f"audio/{variant}/en-positive.wav"
        path = root / relative
        write_wav(path, range(FRAME_SAMPLES))
        entries.append({"id": variant + "__en-positive", "case_id": "en-positive",
                        "variant": variant, "relative_path": relative, "sha256": sha256(path),
                        "sample_count": FRAME_SAMPLES, "sample_zero_offset": 0})
    manifest = {"schema_version": 1, "sample_rate": 16000,
                "frame_samples": FRAME_SAMPLES, "inputs": entries}
    (root / "device-inputs.json").write_text(json.dumps(manifest))
    return root, manifest


@pytest.mark.parametrize("before,after", [
    ('debuggable="true"', 'debuggable="false"'),
    (f'targetPackage="{instrument.PACKAGE}"', 'targetPackage="another.app"'),
    (f'package="{instrument.PACKAGE}"', 'package="another.app.test"'),
    (instrument.RUNNER, "some.other.Runner"),
])
def test_apk_identity_rejects_other_packages_targets_and_non_debuggable(before, after):
    assert instrument.apk_identity(XML)["package"] == instrument.PACKAGE
    with pytest.raises(ValueError):
        instrument.apk_identity(XML.replace(before, after))


def test_payload_preserves_all_bytes_and_hashes_when_selecting_subset(fixture_tree, tmp_path):
    root, data = fixture_tree
    selected_id = data["inputs"][1]["id"]
    _, files, selected = instrument.fixture_files(root, [selected_id], selected_id)
    assert [item["id"] for item in selected] == [selected_id]
    archive_path = tmp_path / "payload.tar"
    instrument.write_payload(archive_path, files)
    with tarfile.open(archive_path) as archive:
        assert set(archive.getnames()) == set(files)
        for member in archive.getmembers():
            raw = archive.extractfile(member).read()
            assert raw == files[member.name]["path"].read_bytes()
            assert hashlib.sha256(raw).hexdigest() == files[member.name]["sha256"]
            assert member.mode == 0o444
    manifest_bytes = (root / "device-inputs.json").read_bytes()
    assert json.loads(manifest_bytes) == data  # Selecting never rewrites the manifest.


@pytest.mark.parametrize("ids,stress", [
    (["unknown"], None), (["clean__en-positive"] * 2, None),
    (["clean__en-positive,colored-snr-p0__en-positive"], None),
    (["clean__en-positive"], "colored-snr-p0__en-positive"),
])
def test_id_lists_and_stress_input_are_unambiguous(fixture_tree, ids, stress):
    with pytest.raises(ValueError):
        instrument.fixture_files(fixture_tree[0], ids, stress)


@pytest.mark.parametrize("relative", ["../escape.wav", "/audio/a.wav", "audio/../a.wav",
                                      "audio//a.wav", "audio/$(id).wav"])
def test_fixture_paths_cannot_escape_or_be_shell_syntax(fixture_tree, relative):
    root, data = fixture_tree
    data["inputs"][0]["relative_path"] = relative
    (root / "device-inputs.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        instrument.fixture_files(root, [], None)


def test_tampered_pcm_rejected_even_when_not_selected(fixture_tree):
    root, data = fixture_tree
    path = root / data["inputs"][0]["relative_path"]
    write_wav(path, [0] * FRAME_SAMPLES)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        instrument.fixture_files(root, [data["inputs"][1]["id"]], None)


@pytest.mark.parametrize("name,kind", [
    ("../escape", tarfile.REGTYPE), ("/tmp/escape", tarfile.REGTYPE),
    ("results.json", tarfile.SYMTYPE), ("results.json", tarfile.LNKTYPE),
    ("deployment.json", tarfile.REGTYPE), ("results.json", tarfile.REGTYPE),
])
def test_result_archive_rejects_traversal_links_reserved_names_and_duplicates(tmp_path, name, kind):
    output = tmp_path / "output"
    output.mkdir()
    path = tmp_path / "results.tar"
    with tarfile.open(path, "w") as archive:
        first = tarfile.TarInfo("results.json")
        archive.addfile(first, io.BytesIO())
        bad = tarfile.TarInfo(name)
        bad.type, bad.linkname = kind, "/tmp/escape"
        archive.addfile(bad, io.BytesIO())
    with pytest.raises(ValueError):
        instrument.extract_results(path, output)
    assert list(output.iterdir()) == []  # Entire archive validated before extraction.


class FakeAdb:
    """Byte-level private-storage transport with real hashes; never starts subprocesses."""

    def __init__(self, apk, *, instrumentation_code="-1", installed_hash=None, timeout=False):
        self.apk = apk
        self.instrumentation_code = instrumentation_code
        self.installed_hash = installed_hash or sha256(apk)
        self.timeout = timeout
        self.home = f"/data/user/0/{instrument.PACKAGE}"
        self.commands = []
        self.files = {}
        self.options = None
        self.result_bytes = None
        self.private_root_exists = False
        self.on_instrument = lambda: None
        self.on_cancel = lambda: None

    def __call__(self, args, *, stdin, stdout, stderr, timeout):
        assert args[:3] == ["/unused/adb", "-s", "TEST-SERIAL"]
        command = args[3:]
        self.commands.append(command)
        data = b""
        if command[0] in ("version", "install"):
            data = b"Success\n"
        elif command[0] == "exec-out":
            assert self.result_bytes is not None
            with tarfile.open(fileobj=stdout, mode="w") as archive:
                member = tarfile.TarInfo("./results.json")
                member.size = len(self.result_bytes)
                archive.addfile(member, io.BytesIO(self.result_bytes))
        else:
            assert command[:2] == ["shell", "-T"]
            remote = shlex.split(command[2])
            if remote[:3] == ["pm", "path", "--user"]:
                data = b"package:/data/app/own/base.apk\n"
            elif remote[:2] == ["run-as", instrument.PACKAGE]:
                operation = remote[2:]
                if operation == ["pwd"]:
                    data = (self.home + "\n").encode()
                elif operation == ["id", "-u"]:
                    data = b"10234\n"
                elif operation[0] == "sha256sum":
                    lines = []
                    for path in operation[1:]:
                        digest = (self.installed_hash if path == "/data/app/own/base.apk"
                                  else hashlib.sha256(self.files[path]).hexdigest())
                        lines.append(digest + "  " + path)
                    data = ("\n".join(lines) + "\n").encode()
                elif operation[:2] == ["tar", "-xf"]:
                    root = operation[-1]
                    with tarfile.open(fileobj=stdin) as archive:
                        for member in archive.getmembers():
                            raw = archive.extractfile(member).read()
                            self.files[root + "/" + member.name] = raw
                elif operation[0] == "cat":
                    data = json.dumps(self.host_report()).encode()
                elif operation[0] == "sh" and self.private_root_exists:
                    stderr.write(b"mkdir: File exists\n")
                    return subprocess.CompletedProcess(args, 1)
                elif operation[0] != "sh":
                    raise AssertionError(operation)
            elif remote[:2] == ["am", "instrument"]:
                self.options = {}
                for index, item in enumerate(remote):
                    if item == "-e":
                        self.options[remote[index + 1]] = remote[index + 2]
                self.result_bytes = json.dumps(self.report()).encode()
                self.on_instrument()
                if self.timeout:
                    raise subprocess.TimeoutExpired(args, timeout)
                # Android's pretty stream output omits the machine-readable code.
                data = (
                    f"INSTRUMENTATION_CODE: {self.instrumentation_code}\n".encode()
                    if "-r" in remote else b"Denoising benchmark written to results.json\n"
                )
            elif remote[0] == "date":
                data = b"11-14 09:01:02.000\n"
            elif remote == ["getprop", "ro.build.version.sdk"]:
                data = b"36\n"
            elif remote[:2] == ["am", "force-stop"]:
                self.on_cancel()
            elif remote[0] not in ("getprop", "dumpsys", "logcat", "am"):
                raise AssertionError(remote)
        stdout.write(data)
        return subprocess.CompletedProcess(args, 0)

    def report(self):
        options = self.options
        return {
            "schema_version": 1, "status": "completed", "options": options,
            "environment": {"entry_point": "instrumentation", "test_apk_sha256": sha256(self.apk),
                            "foreground_host": self.host_snapshot()},
            "foreground_host_at_finish": self.host_snapshot(),
            "input_manifest_sha256": hashlib.sha256(
                self.files[options["inputDir"] + "/device-inputs.json"]).hexdigest(),
            "model": {"sha256": hashlib.sha256(self.files[options["modelPath"]]).hexdigest()},
            "thread_priority": {"requested": -16, "actual": -16}, "stages": [], "replays": [],
            "reset_check": {"all_engine_frames_active": False},
        }

    def host_snapshot(self):
        return {"service_type": "mediaProcessing", "service_component": instrument.SERVICE,
                "host_mode": self.options["hostMode"], "foreground_requested": True,
                "wake_lock_requested": self.options["wakeLock"] == "true",
                "wake_lock_held": self.options["wakeLock"] == "true",
                "wake_lock_timeout_ms": int(self.options["lifecycleTimeoutSeconds"]) * 1000,
                "microphone_used": False, "screen_kept_on": False}

    def host_report(self):
        names = ["service_ready"]
        if self.options["hostMode"] == "service-only":
            names.append("activity_stopped")
        names.extend(["starting_processing", "service_destroyed", "cleanup_finished"])
        return {"schema_version": 1, "status": "completed", "options": self.options,
                "host_mode": self.options["hostMode"], "service_type": "mediaProcessing",
                "microphone_used": False, "screen_kept_on": False,
                "service_destroyed": True, "activity_finish_requested": True,
                "events": [{"event": name, "details": {"wake_lock_held": False}}
                           for name in names]}


@pytest.fixture
def simulated_run(tmp_path, fixture_tree, monkeypatch):
    apk, model = tmp_path / "test.apk", tmp_path / "model.onnx"
    apk.write_bytes(b"test-only APK identity")
    model.write_bytes(b"test-only model payload")
    monkeypatch.setattr(instrument, "inspect_apk",
                        lambda *args: (instrument.apk_identity(XML), XML))
    args = instrument.parser().parse_args([
        "--adb", "/unused/adb", "--apkanalyzer", "/unused/apkanalyzer", "--serial", "TEST-SERIAL",
        "--apk", str(apk), "--fixtures", str(fixture_tree[0]), "--model", str(model),
        "--output", str(tmp_path / "result"), "--label", "smoke-001",
        "--id", "colored-snr-p0__en-positive",
    ])
    fake = FakeAdb(apk)
    monkeypatch.setattr(instrument.subprocess, "run", fake)
    return args, fake


def test_complete_transport_is_private_hashed_and_does_not_call_fallback_denoised(simulated_run):
    args, fake = simulated_run
    result = instrument.run(args)
    assert result["status"] == "completed"
    assert result["outcome"]["reset_all_engine_frames_active"] is False
    assert result["outcome"]["registration_performed"] is False
    assert (args.output / "results.json").read_bytes() == fake.result_bytes
    assert all(path.startswith(fake.home + "/files/denoising/smoke-001/") for path in fake.files)
    assert not any(command[0] in ("install", "root", "push") for command in fake.commands)
    assert fake.options["modes"] == "engine,bypass"
    assert fake.options["ids"] == "colored-snr-p0__en-positive"
    assert fake.options["hostMode"] == "activity-and-service"
    assert fake.options["wakeLock"] == "true"
    assert fake.options["lifecycleTimeoutSeconds"] == "130"
    assert result["timing"]["recommended_outer_timeout_s"] == 430
    assert result["outcome"]["thread_priority"] == {"requested": -16, "actual": -16}
    with pytest.raises(ValueError, match="overwrite"):
        instrument.run(args)


def test_install_is_explicit_and_modes_have_preserved_order(simulated_run):
    args, fake = simulated_run
    args.install = True
    args.mode = ["bypass", "engine"]
    instrument.run(args)
    installs = [command for command in fake.commands if command[0] == "install"]
    assert installs == [["install", "--user", "0", "-r", "-t", str(args.apk)]]
    assert fake.options["modes"] == "bypass,engine"


def test_mismatched_installed_apk_aborts_before_private_deployment(simulated_run):
    args, fake = simulated_run
    fake.installed_hash = "a" * 64
    with pytest.raises(ValueError, match="hashes differ"):
        instrument.run(args)
    assert fake.files == {} and fake.options is None
    assert json.loads((args.output / "deployment.json").read_text())["status"] == "failed"


def test_existing_remote_label_is_not_overwritten_or_collected(simulated_run):
    args, fake = simulated_run
    fake.private_root_exists = True
    with pytest.raises(RuntimeError, match="create-private-root failed"):
        instrument.run(args)
    assert not fake.files and fake.options is None
    assert not any(command[0] == "exec-out" for command in fake.commands)


def test_unsafe_remote_label_rejected_before_any_adb(simulated_run):
    args, fake = simulated_run
    args.label = "../other-app"
    with pytest.raises(ValueError, match="Unsafe identifier"):
        instrument.run(args)
    assert fake.commands == [] and not args.output.exists()


def test_adb_exit_zero_does_not_hide_instrumentation_failure(simulated_run):
    args, fake = simulated_run
    fake.instrumentation_code = "0"
    with pytest.raises(RuntimeError, match="RESULT_OK"):
        instrument.run(args)
    report = json.loads((args.output / "deployment.json").read_text())
    assert report["status"] == "failed" and report["instrumentation_codes"] == ["0"]
    assert (args.output / "results.json").exists()  # Failed-job evidence still retrieved.


def test_timeout_cancels_only_own_test_package_and_keeps_evidence(simulated_run):
    args, fake = simulated_run
    fake.timeout = True
    with pytest.raises(subprocess.TimeoutExpired):
        instrument.run(args)
    stops = [shlex.split(command[2]) for command in fake.commands
             if command[0] == "shell" and "force-stop" in command[2]]
    assert stops == [["am", "force-stop", "--user", "0", instrument.PACKAGE]]
    assert (args.output / "results.json").exists()
    assert json.loads((args.output / "deployment.json").read_text())["status"] == "failed"


def test_report_identity_cannot_be_relabelled_as_instrumentation(simulated_run):
    args, fake = simulated_run
    metadata = instrument.run(args)
    report = json.loads((args.output / "results.json").read_text())
    for changes in ({"environment": {"entry_point": "app_process"}},
                    {"input_manifest_sha256": "a" * 64}, {"options": {}}):
        altered = copy.deepcopy(report)
        altered.update(changes)
        (args.output / "results.json").write_text(json.dumps(altered))
        with pytest.raises(ValueError, match="mismatched"):
            instrument.verify_report(args.output, metadata)


def test_fallback_waveform_remains_failure_evidence_in_outcome(simulated_run):
    args, fake = simulated_run
    metadata = instrument.run(args)
    report = json.loads((args.output / "results.json").read_text())
    csv = args.output / "stress-engine.frames.csv"
    csv.write_text("frame,engine_active\n0,0\n")
    wav = args.output / "replay-clean__en-positive-engine.wav"
    write_wav(wav, [0] * FRAME_SAMPLES)
    report["stages"] = [{"id": "stress-engine", "mode": "engine", "fallback_reason": "slow",
                         "frames_file": csv.name, "frames_sha256": sha256(csv)}]
    report["replays"] = [{"mode": "engine", "input_id": "clean__en-positive",
                          "all_engine_frames_active": False,
                          "output_file": wav.name, "output_sha256": sha256(wav)}]
    (args.output / "results.json").write_text(json.dumps(report))
    outcome = instrument.verify_report(args.output, metadata)
    assert outcome["fallback_stage_ids"] == ["stress-engine"]
    assert outcome["inactive_engine_replay_ids"] == ["clean__en-positive"]
    wav.write_bytes(b"changed in transfer")
    with pytest.raises(ValueError, match="hash/path mismatch"):
        instrument.verify_report(args.output, metadata)


@pytest.mark.parametrize("change", [
    lambda xml: xml.replace(instrument.ACTIVITY, "some.OtherActivity"),
    lambda xml: xml.replace('exported="false"', 'exported="true"'),
    lambda xml: xml.replace('foregroundServiceType="mediaProcessing"',
                            'foregroundServiceType="microphone"'),
    lambda xml: xml.replace('android.permission.WAKE_LOCK', 'android.permission.RECORD_AUDIO'),
    lambda xml: xml.replace('android.permission.FOREGROUND_SERVICE_MEDIA_PROCESSING',
                            'android.permission.FOREGROUND_SERVICE_MICROPHONE'),
])
def test_foreground_contract_rejects_wrong_component_permission_or_type(change):
    with pytest.raises(ValueError, match="foreground host"):
        instrument.require_foreground_host(instrument.apk_identity(change(XML)))


def test_numeric_manifest_service_type_and_exact_apk_provenance(tmp_path, monkeypatch):
    apk = tmp_path / "variant.apk"
    provenance = b'{"variant":"fft-test","officialBinary":false}'
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("lib/arm64-v8a/libsherpa-onnx-jni.so", b"fixture JNI bytes")
        archive.writestr("assets/noise-reduction/runtime-provenance.json", provenance)
    numeric_xml = XML.replace("mediaProcessing", "8192")
    monkeypatch.setattr(instrument.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args, 0, numeric_xml))
    identity, _ = instrument.inspect_apk(apk, tmp_path / "apkanalyzer")
    instrument.require_foreground_host(identity)
    assert identity["runtime_provenance"]["sha256"] == hashlib.sha256(provenance).hexdigest()
    assert identity["runtime_provenance"]["content"]["officialBinary"] is False
    assert identity["native_sha256"] == {
        "lib/arm64-v8a/libsherpa-onnx-jni.so": hashlib.sha256(b"fixture JNI bytes").hexdigest(),
    }


def test_service_only_without_wake_lock_is_explicit_and_verified(simulated_run):
    args, fake = simulated_run
    args.host_mode, args.wake_lock, args.timeout_seconds = "service-only", False, 115
    metadata = instrument.run(args)
    assert fake.options["hostMode"] == "service-only"
    assert fake.options["wakeLock"] == "false"
    assert fake.options["lifecycleTimeoutSeconds"] == "115"
    path = args.output / "foreground-host.json"
    host = json.loads(path.read_text())
    host["events"] = [event for event in host["events"] if event["event"] != "activity_stopped"]
    path.write_text(json.dumps(host))
    with pytest.raises(ValueError, match="before Activity stopped"):
        instrument.verify_report(args.output, metadata)


def test_missing_cleanup_or_expired_wake_lock_is_not_a_completed_foreground_run(simulated_run):
    args, _ = simulated_run
    metadata = instrument.run(args)
    path = args.output / "foreground-host.json"
    host = json.loads(path.read_text())
    host["service_destroyed"] = False
    path.write_text(json.dumps(host))
    with pytest.raises(ValueError, match="lifecycle"):
        instrument.verify_report(args.output, metadata)
    host["service_destroyed"] = True
    path.write_text(json.dumps(host))
    path = args.output / "results.json"
    report = json.loads(path.read_text())
    report["foreground_host_at_finish"]["wake_lock_held"] = False
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="execution context"):
        instrument.verify_report(args.output, metadata)


def test_real_sigterm_records_inflight_command_then_cleans_only_own_package(simulated_run):
    args, fake = simulated_run
    previous = signal.getsignal(signal.SIGTERM)

    def interrupt():
        durable = json.loads((args.output / "deployment.json").read_text())
        assert durable["status"] == "running"
        assert durable["commands"][-1]["status"] == "running"
        assert "am instrument" in durable["commands"][-1]["argv"][-1]
        assert durable["commands"][-1]["timeout_s"] == 130
        os.kill(os.getpid(), signal.SIGTERM)

    fake.on_instrument = interrupt
    # A second SIGTERM during cleanup cannot abort the own-package force-stop/pull.
    fake.on_cancel = lambda: os.kill(os.getpid(), signal.SIGTERM)
    with pytest.raises(instrument.TerminationRequested) as failure:
        instrument.run(args)
    assert failure.value.signum == signal.SIGTERM
    assert signal.getsignal(signal.SIGTERM) == previous
    durable = json.loads((args.output / "deployment.json").read_text())
    assert durable["status"] == "failed"
    assert durable["termination_signals"] == [signal.SIGTERM, signal.SIGTERM]
    commands = durable["commands"]
    interrupted = next(i for i, row in enumerate(commands) if "am instrument" in row["argv"][-1])
    assert commands[interrupted]["error"] == "TerminationRequested: SIGTERM"
    assert "force-stop --user 0 " + instrument.PACKAGE in commands[interrupted + 1]["argv"][-1]
    assert commands[interrupted + 1]["timeout_s"] <= 10
    assert (args.output / "results.json").exists()


def test_cleanup_commands_share_one_deadline_instead_of_repeated_long_timeouts(
    simulated_run, monkeypatch,
):
    args, fake = simulated_run
    fake.timeout = True
    clock = [100.0]
    monkeypatch.setattr(instrument.time, "monotonic", lambda: clock[0])
    fake.on_cancel = lambda: clock.__setitem__(0, clock[0] + instrument.CLEANUP_SECONDS)
    with pytest.raises(subprocess.TimeoutExpired):
        instrument.run(args)
    durable = json.loads((args.output / "deployment.json").read_text())
    assert durable["status"] == "failed"
    assert not any(command[0] == "exec-out" for command in fake.commands)
    skipped = [command for command in durable["commands"] if command["status"] == "skipped"]
    assert skipped and all(command["timeout_s"] == 0 for command in skipped)
    assert "budget exhausted" in " ".join(durable["collection_errors"])


def test_too_short_inner_timeout_is_rejected_before_device_commands(simulated_run):
    args, fake = simulated_run
    args.timeout_seconds = 70
    with pytest.raises(ValueError, match="planned audio"):
        instrument.run(args)
    assert not fake.commands
