#!/usr/bin/env python3
"""Compare actual native GTCRN + original/patched STFT on Linux, not Android timing."""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.request
import wave
import zipfile

sys.dont_write_bytecode = True
from build import HERE, STFT, digest, run, source

ORT_NAME = "onnxruntime-linux-x64-glibc2_17-Release-1.28.2"
ORT_SHA = "c4f8994d56191d9d2c92a961b39fe790459f2c5d155f912b239506ea31359534"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--work-dir", type=Path, required=True)
parser.add_argument("--model", type=Path, required=True)
inputs = parser.add_mutually_exclusive_group(required=True)
inputs.add_argument("--pcm", type=Path)
inputs.add_argument("--wav", type=Path)
parser.add_argument("--jobs", type=int, default=4)
args = parser.parse_args()
work = args.work_dir.resolve()
if digest(args.model) != "e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534":
    raise RuntimeError("model checksum mismatch")
upstream, original, _ = source(work)
if "cuebell-streaming-dft.h" not in (upstream / STFT).read_text():
    raise RuntimeError("Run build.py first to apply the pinned FFT patch")
host = work / "host-regression"
host.mkdir(exist_ok=True)
pcm = args.pcm
if args.wav:
    with wave.open(str(args.wav), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise RuntimeError("expected 16 kHz mono PCM16 WAV")
        data = audio.readframes(audio.getnframes())
    pcm = host / "input.pcm"
    pcm.write_bytes(data + bytes((-len(data)) % 1024))
reference = original.decode()
for old, new in [
    ("SHERPA_ONNX_CSRC_ONLINE_SPEECH_DENOISER_STFT_IMPL_H_", "CUEBELL_REFERENCE_STFT_H_"),
    ("StreamingDft", "ReferenceDft"),
    ("OnlineSpeechDenoiserStftImpl", "ReferenceStft"),
    ("OnlineSpeechDenoiserStftConfig", "ReferenceStftConfig"),
    ("MakeOnlineSpeechDenoiserWindow", "MakeReferenceWindow"),
]:
    reference = reference.replace(old, new)
(host / "reference-stft.h").write_text(reference)
reference_gtcrn = (upstream / "sherpa-onnx/csrc/online-speech-denoiser-gtcrn-impl.h").read_text()
for old, new in [
    ("SHERPA_ONNX_CSRC_ONLINE_SPEECH_DENOISER_GTCRN_IMPL_H_", "CUEBELL_REFERENCE_GTCRN_H_"),
    (STFT, "reference-stft.h"),
    ("OnlineSpeechDenoiserGtcrnImpl", "ReferenceGtcrn"),
    ("OnlineSpeechDenoiserStftImpl", "ReferenceStft"),
    ("OnlineSpeechDenoiserStftConfig", "ReferenceStftConfig"),
]:
    reference_gtcrn = reference_gtcrn.replace(old, new)
(host / "reference-gtcrn.h").write_text(reference_gtcrn)
archive = host / f"{ORT_NAME}.zip"
if not archive.exists():
    urllib.request.urlretrieve(f"https://github.com/csukuangfj/onnxruntime-libs/releases/download/v1.28.2/{ORT_NAME}.zip", archive)
if digest(archive) != ORT_SHA:
    raise RuntimeError("host ONNX Runtime checksum mismatch")
if not (host / ORT_NAME).exists():
    with zipfile.ZipFile(archive) as zip_file:
        zip_file.extractall(host)
env = os.environ.copy()
env.update(SHERPA_ONNXRUNTIME_INCLUDE_DIR=str(host / ORT_NAME / "include"),
           SHERPA_ONNXRUNTIME_LIB_DIR=str(host / ORT_NAME / "lib"), SOURCE_DATE_EPOCH="1794614400")
sdk = Path(env.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
cmake = sdk / "cmake/3.22.1/bin/cmake"
run(cmake, "-S", HERE / "host-tests", "-B", host / "build", "-G", "Ninja",
    "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_FLAGS=-ffp-contract=off",
    f"-DCUEBELL_SHERPA_SOURCE={upstream}", f"-DCUEBELL_REFERENCE_HEADERS={host}", env=env)
run(cmake, "--build", host / "build", "--target", "gtcrn-fft-regression", "--parallel", args.jobs, env=env)
with (host / "results.txt").open("w") as output:
    run(host / "build/gtcrn-fft-regression", args.model.resolve(), pcm.resolve(), stdout=output, env=env)
print((host / "results.txt").read_text())
(host / "inputs.json").write_text(json.dumps({"modelSha256": digest(args.model), "pcmSha256": digest(pcm),
    "sourceSha256": digest(args.wav or args.pcm), "paddedToWhole512SampleFrames": True,
    "onnxruntimeSha256": ORT_SHA, "boundary": "host native math/model correctness; not Android timing acceptance"}, indent=2) + "\n")
