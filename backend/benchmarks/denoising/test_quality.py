"""Scorer invariants using unit-test signals/responses, never quality evidence.

Run with the optional DNSMOS numpy/soundfile environment on PYTHONPATH. These
tests do not download artifacts, run a device, or need the model. Real-model
equivalence is a separate cached-model smoke check.
"""

import argparse
import hashlib
import io
import json

import pytest

from benchmarks.denoising import quality

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")


class RecordingSession:
    """Inspect tensors; fixed unit-test outputs are not model predictions."""

    def __init__(self, responses=None):
        self.inputs = []
        self.responses = responses

    def run(self, output_names, inputs):
        assert output_names is None and set(inputs) == {"input_1"}
        self.inputs.append(inputs["input_1"].copy())
        if self.responses is None:
            return [np.array([[2, 3, 4]], dtype=np.float32)]
        response = self.responses[len(self.inputs) - 1]
        if isinstance(response, Exception):
            raise response
        return [np.asarray(response, dtype=np.float32)]


@pytest.mark.parametrize("count,factor,hops,tail", [
    (80000, 2, 1, 15840),
    (144160, 1, 1, 0),
    (160160, 1, 1, 16000),  # upstream does not evaluate the second otherwise-fitting window
    (176000, 1, 2, 15840),
    (192000, 1, 3, 15840),
])
def test_official_window_boundaries_repeat_doubling_and_tail(count, factor, hops, tail):
    signal = np.arange(count, dtype=np.float64) / (count * 3)
    original = signal.copy()
    session = RecordingSession()
    result = quality.score_audio(session, signal)
    assert result["repeat_factor"] == factor
    assert result["num_hops"] == result["evaluated_windows"] == hops
    assert result["evaluation_unscored_tail_samples"] == tail
    assert result["original_sample_count"] == count
    assert result["evaluation_sample_count"] == count * factor
    assert result["skipped_hops"] == []
    for index, tensor in enumerate(session.inputs):
        expected = np.tile(original, factor)[index * 16000:index * 16000 + 144160]
        assert tensor.dtype == np.float32
        np.testing.assert_array_equal(tensor, expected.astype(np.float32)[None, :])
    np.testing.assert_array_equal(signal, original)


def test_nonpersonal_polynomials_are_applied_per_window_before_averaging():
    session = RecordingSession([[[1, 2, 3]], [[3, 4, 5]]])
    result = quality.score_audio(session, np.zeros(176000))
    assert result["raw_scores"] == {"SIG": 2, "BAK": 3, "OVRL": 4}
    assert result["scores"] == pytest.approx({
        "SIG": 2.02705906, "BAK": 3.11473116, "OVRL": 3.35761596,
    }, abs=1e-8)
    # Calibrating the mean raw SIG would incorrectly give 2.11103184.
    assert abs(result["scores"]["SIG"] - 2.11103184) > 0.08


def test_full_file_metrics_rail_counts_hash_and_pcm_units(tmp_path):
    path = tmp_path / "rails.wav"
    source = np.array([0, 32767, -32768, 123, -1], dtype=np.int16)
    sf.write(path, source, 16000, subtype="PCM_16")
    saved = path.read_bytes()
    audio, metrics = quality.load_wav(path)
    np.testing.assert_array_equal(audio, source.astype(np.float64) / 32768)
    assert metrics["sha256"] == hashlib.sha256(saved).hexdigest()
    assert metrics["clipped_count"] == 2
    assert metrics["zero_count"] == 1
    assert metrics["peak_abs"] == 1.0
    assert metrics["rms"] == pytest.approx(float(np.sqrt(np.mean(audio ** 2))))
    assert metrics["sample_count"] == 5
    assert metrics["duration_s"] == 5 / 16000
    assert path.read_bytes() == saved


def test_float_wave_is_not_peak_normalized_or_clipped(tmp_path):
    path = tmp_path / "float.wav"
    samples = np.array([-1.25, 0.125, 1.5, 0], dtype=np.float32)
    sf.write(path, samples, 16000, subtype="FLOAT")
    audio, metrics = quality.load_wav(path)
    np.testing.assert_array_equal(audio, samples)
    assert metrics["clipped_count"] == 2 and metrics["peak_abs"] == 1.5


@pytest.mark.parametrize("problem,match", [
    ("rate", "Expected mono 16000 Hz"),
    ("stereo", "Expected mono 16000 Hz"),
    ("nan", "only finite samples"),
    ("inf", "only finite samples"),
    ("empty", "empty recording"),
    ("truncated", "RIFF byte length mismatch"),
    ("trailing", "RIFF byte length mismatch"),
    ("compressed", "Expected uncompressed"),
])
def test_invalid_audio_is_rejected_explicitly(tmp_path, problem, match):
    path = tmp_path / "bad.wav"
    samples = np.zeros((512, 2) if problem == "stereo" else 512)
    if problem in {"nan", "inf"}:
        samples[0] = float(problem)
    if problem == "empty":
        samples = np.array([])
    subtype = "ULAW" if problem == "compressed" else "FLOAT"
    sf.write(path, samples, 8000 if problem == "rate" else 16000, subtype=subtype)
    if problem == "truncated":
        path.write_bytes(path.read_bytes()[:-1])
    elif problem == "trailing":
        path.write_bytes(path.read_bytes() + b"extra")
    with pytest.raises(ValueError, match=match):
        quality.load_wav(path)


def test_causal_delay_survives_pair_loading_and_model_input(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    raw = np.zeros(144160, dtype=np.int16)
    raw[1:5] = [1024, 3072, -4096, 32767]
    delayed = np.zeros_like(raw)
    delayed[256:] = raw[:-256]
    sf.write(before / "clip.wav", raw, 16000)
    sf.write(after / "clip.wav", delayed, 16000)
    session = RecordingSession()
    clips = quality.score_pairs(before, after, session)
    assert clips[0]["status"] == "completed"
    assert clips[0]["before"]["sample_zero_offset"] == 0
    assert clips[0]["after"]["sample_zero_offset"] == 0
    np.testing.assert_array_equal(session.inputs[0][0], raw.astype(np.float32) / 32768)
    np.testing.assert_array_equal(session.inputs[1][0], delayed.astype(np.float32) / 32768)
    assert np.flatnonzero(session.inputs[1][0])[0] == 257


def test_pair_errors_are_not_dropped_or_counted_in_aggregates(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    for root in (before, after):
        sf.write(root / "ok.wav", np.zeros(144160), 16000)
        sf.write(root / "length.wav", np.zeros(512 if root == before else 768), 16000)
    sf.write(before / "missing.wav", np.zeros(512), 16000)
    sf.write(after / "extra.wav", np.zeros(512), 16000)
    session = RecordingSession()
    clips = quality.score_pairs(before, after, session)
    summary = quality.aggregate(clips)
    assert summary["total_pairs"] == 4
    assert summary["scored_pairs"] == 1 and summary["failed_pairs"] == 3
    assert summary["metrics"]["SIG"]["delta_mean"] == 0.0
    assert len(session.inputs) == 2  # invalid pairs never reach the model
    by_name = {clip["filename"]: clip for clip in clips}
    assert by_name["length.wav"]["errors"][0]["stage"] == "pair.validation"
    assert by_name["missing.wav"]["errors"][0]["exception_type"] == "FileNotFoundError"
    assert by_name["extra.wav"]["errors"][0]["stage"] == "before.validation"
    json.dumps(clips, allow_nan=False)


@pytest.mark.parametrize("response,match", [
    ([[float("nan"), 2, 3]], "three finite model outputs"),
    ([[1, 2]], "three finite model outputs"),
    (RuntimeError("inference test failure"), "inference test failure"),
])
def test_model_failures_are_explicit(response, match):
    with pytest.raises((ValueError, RuntimeError), match=match):
        quality.score_audio(RecordingSession([response]), np.zeros(144160))


def test_inference_error_remains_in_pair_and_empty_aggregate_is_null(tmp_path):
    sf.write(tmp_path / "clip.wav", np.zeros(144160), 16000)
    session = RecordingSession([RuntimeError("test inference exception"), [[2, 3, 4]]])
    clips = quality.score_pairs(tmp_path, tmp_path, session)
    assert clips[0]["status"] == "failed"
    assert clips[0]["errors"] == [{"stage": "before.inference",
                                   "exception_type": "RuntimeError",
                                   "message": "test inference exception"}]
    assert quality.aggregate(clips)["metrics"]["SIG"]["delta_mean"] is None


@pytest.fixture
def tiny_assets(monkeypatch):
    payloads = {"sig_bak_ovr.onnx": b"unit-test-model-bytes", "dnsmos_local.py": b"source bytes"}
    assets = {name: {"url": f"https://unit.test/{name}",
                     "sha256": hashlib.sha256(data).hexdigest()}
              for name, data in payloads.items()}
    monkeypatch.setattr(quality, "ASSETS", assets)
    return payloads


def test_asset_cache_download_is_pinned_reusable_and_detects_tampering(
    tmp_path, tiny_assets, monkeypatch,
):
    calls = []

    def download(url, timeout):
        calls.append(url)
        assert timeout == 60
        return io.BytesIO(tiny_assets[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(quality, "urlopen", download)
    with pytest.raises(FileNotFoundError, match="--download-model once"):
        quality.prepare_assets(tmp_path)
    first = quality.prepare_assets(tmp_path, download=True)
    assert len(calls) == 2 and all("p808" not in url.lower() for url in calls)
    assert first == quality.prepare_assets(tmp_path, download=True)
    assert len(calls) == 2
    assert first["source_commit"] == quality.SOURCE_COMMIT
    assert first["p808_used"] is False
    (tmp_path / "sig_bak_ovr.onnx").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Cached official artifact SHA256 mismatch"):
        quality.prepare_assets(tmp_path, download=True)
    assert len(calls) == 2  # do not silently replace a mutated cached model


def test_wrong_download_hash_is_never_cached(tmp_path, tiny_assets, monkeypatch):
    monkeypatch.setattr(quality, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"wrong"))
    with pytest.raises(ValueError, match="Downloaded official artifact SHA256 mismatch"):
        quality.prepare_assets(tmp_path, download=True)
    assert not (tmp_path / "sig_bak_ovr.onnx").exists()


def test_setup_exception_writes_explicit_failure_and_does_not_overwrite(tmp_path):
    args = argparse.Namespace(output=tmp_path / "report.json", before=tmp_path, after=tmp_path,
                              threads=1, cache=tmp_path / "missing-model", download_model=False)
    report = quality.run(args)
    assert report["status"] == "failed"
    assert report["errors"][0]["exception_type"] == "FileNotFoundError"
    assert report["aggregate"]["metrics"]["OVRL"]["before_mean"] is None
    saved = args.output.read_bytes()
    assert json.loads(saved) == report
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        quality.run(args)
    assert args.output.read_bytes() == saved
