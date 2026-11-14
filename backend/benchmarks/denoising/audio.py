"""PCM helpers. Standard library only; no model or provider is called here."""

from __future__ import annotations

import hashlib
import math
import struct
import sys
import wave
from array import array
from pathlib import Path
from typing import Iterable

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 512
NOISE_WARMUP = 4096
NOISE_POLE = 0.92
# A deliberately simple synthetic room, not a measured venue impulse response.
REVERB_TAPS = ((0, 1.0), (577, 0.25), (1489, -0.16), (3001, 0.10), (5711, 0.05))


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pcm_bytes(samples: Iterable[int]) -> bytes:
    pcm = array("h", samples)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm.tobytes()


def read_wav(path: Path) -> array:
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
            1, 2, SAMPLE_RATE, "NONE"
        ):
            raise ValueError(f"{path}: expected uncompressed mono PCM16 at 16000 Hz")
        count = wav.getnframes()
        data = wav.readframes(count)
    if len(data) != count * 2:
        raise ValueError(f"{path}: truncated PCM")
    pcm = array("h")
    pcm.frombytes(data)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm


def write_wav(path: Path, samples: Iterable[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm_bytes(samples))


def rms(samples: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in samples:
        total += value * value
        count += 1
    return math.sqrt(total / count) if count else 0.0


def span_rms(samples: Iterable[float], spans: list[tuple[int, int]]) -> float:
    return rms(samples[i] for start, end in spans for i in range(start, end))


def colored_noise(count: int, seed: str) -> array:
    """SHAKE256 uniform excitation, AR(1) low-pass, with a discarded startup.

    No time-varying envelope, speech modulation, or block resets. The finite
    deterministic realization approximates stationary colored background noise;
    it is not pink noise, crowd speech, a venue recording, or a learned model.
    """
    data = hashlib.shake_256(seed.encode("utf-8")).digest((count + NOISE_WARMUP) * 4)
    output = array("d")
    state = 0.0
    for index, (word,) in enumerate(struct.iter_unpack("<I", data)):
        white = (word + 0.5) / 2**31 - 1.0
        state = NOISE_POLE * state + (1.0 - NOISE_POLE) * white
        if index >= NOISE_WARMUP:
            output.append(state)
    # Remove the realization's tiny finite-sample DC offset once, globally.
    mean = sum(output) / len(output) if output else 0.0
    return array("d", (value - mean for value in output))


def reverberate(samples: Iterable[float]) -> array:
    """Causal fixed FIR; onset unchanged, length unchanged, tail must fit guard silence."""
    output = array("d", samples)
    for delay, gain in REVERB_TAPS[1:]:
        for index in range(delay, len(output)):
            output[index] += gain * samples[index - delay]
    return output


def noise_scale(signal: Iterable[float], noise: Iterable[float],
                spans: list[tuple[int, int]], snr_db: float) -> float:
    signal_rms = span_rms(signal, spans)
    noise_rms = span_rms(noise, spans)
    if not signal_rms or not noise_rms:
        raise ValueError("SNR requires nonzero signal and noise in the reference speech spans")
    return signal_rms / (10 ** (snr_db / 20) * noise_rms)


def quantize(samples: Iterable[float], gain: float = 1.0) -> array:
    values = array("h")
    for value in samples:
        value = round(value * gain)
        if not -32767 <= value <= 32767:
            raise ValueError("Headroom calculation failed; refusing to clip PCM")
        values.append(value)
    return values


def mix(signal: Iterable[float], noise: Iterable[float], scale: float,
        gain: float, spans: list[tuple[int, int]]) -> tuple[array, dict]:
    if len(signal) != len(noise):
        raise ValueError("Signal/noise sample counts differ")
    output = quantize((s + n * scale for s, n in zip(signal, noise)), gain)
    signal_rms = span_rms(signal, spans) * gain
    residual_rms = rms(
        output[i] - signal[i] * gain for start, end in spans for i in range(start, end)
    )
    return output, {
        "speech_rms_pcm": signal_rms,
        "noise_plus_quantization_rms_pcm": residual_rms,
        "achieved_snr_db": 20 * math.log10(signal_rms / residual_rms),
        "peak_abs_pcm": max(map(abs, output), default=0),
        "noise_scale": scale,
        "common_gain": gain,
    }


def audio_reference(path: Path, root: Path) -> dict:
    samples = read_wav(path)
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "sha256": sha256(path),
        "pcm_sha256": hashlib.sha256(pcm_bytes(samples)).hexdigest(),
        "sample_count": len(samples),
        "duration_s": len(samples) / SAMPLE_RATE,
        "frame_samples": FRAME_SAMPLES,
        "frame_remainder": len(samples) % FRAME_SAMPLES,
        "sample_zero_offset": 0,
        "alignment_policy": "causal-unshifted; no samples trimmed or time shifted",
    }
