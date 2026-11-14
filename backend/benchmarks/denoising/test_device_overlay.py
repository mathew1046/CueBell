import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.denoising.device import fft_overlay


def overlay_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    directory = tmp_path / "overlay"
    library = directory / "arm64-v8a/libsherpa-onnx-jni.so"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"reviewed native test payload")
    model = tmp_path / "model.onnx"
    model.write_bytes(b"unchanged test model")
    lock = {
        "variant": "reviewed-test-variant",
        "librarySha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "libraryBytes": library.stat().st_size,
        "modelSha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    }
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(lock))
    (directory / "provenance.json").write_text(json.dumps({**lock, "officialBinary": False}))
    return directory, model, lock_path


def test_overlay_rejects_changed_binary_despite_unchanged_provenance(tmp_path: Path):
    directory, model, lock_path = overlay_fixture(tmp_path)
    library, _ = fft_overlay(directory, model, lock_path)
    library.write_bytes(b"different native test payload")
    with pytest.raises(ValueError, match="FFT binary does not match"):
        fft_overlay(directory, model, lock_path)


def test_overlay_rejects_model_substitution(tmp_path: Path):
    directory, model, lock_path = overlay_fixture(tmp_path)
    model.write_bytes(b"another model")
    with pytest.raises(ValueError, match="unchanged reviewed GTCRN model"):
        fft_overlay(directory, model, lock_path)
