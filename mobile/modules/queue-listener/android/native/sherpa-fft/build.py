#!/usr/bin/env python3
"""Build CueBell's explicitly modified sherpa JNI; no phone or Gradle actions.

Python >= 3.12, Linux, NDK 27.1.12297006, CMake 3.22.1, Ninja required.
Upstream's transitive FetchContent inputs retain their pinned URL_HASH checks.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
COMMIT = "af2d8d81dbfa61c4cea4c568da78f3982edca005"
SOURCE_SHA = "afcafe3c34bc2f15a363ad791fa1644a69bf0977a58c1b4f617468976c2faeb5"
STFT = "sherpa-onnx/csrc/online-speech-denoiser-stft-impl.h"
STFT_SHA = "5ec43424a1c5bf48c198dd7aaad3e19cc01d366e779fbc8196e8146f8514e124"
NDK_VERSION = "27.1.12297006"


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(*args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def source(work):
    archive = work / "sherpa-onnx-2.0.1.tar.gz"
    url = f"https://codeload.github.com/k2-fsa/sherpa-onnx/tar.gz/{COMMIT}"
    if not archive.exists():
        partial = archive.with_suffix(".partial")
        urllib.request.urlretrieve(url, partial)
        if digest(partial) != SOURCE_SHA:
            raise RuntimeError("sherpa source archive checksum mismatch")
        partial.replace(archive)
    if digest(archive) != SOURCE_SHA:
        raise RuntimeError("sherpa source archive checksum mismatch")
    upstream = work / f"sherpa-onnx-{COMMIT}"
    with tarfile.open(archive) as tar:
        # The upstream archive has unrelated absolute Go symlinks. Native build
        # inputs are regular files; never follow/extract those symlinks.
        if not (upstream / ".cuebell-extracted").exists():
            tar.extractall(work, members=[m for m in tar if m.isfile() or m.isdir()], filter="data")
            (upstream / ".cuebell-extracted").touch()
        original = tar.extractfile(f"sherpa-onnx-{COMMIT}/{STFT}").read()
    if hashlib.sha256(original).hexdigest() != STFT_SHA:
        raise RuntimeError("unexpected original streaming frontend")
    return upstream, original, url


def math_tests(work, original):
    test_dir = work / "math-tests"
    test_dir.mkdir(exist_ok=True)
    text = original.decode()
    reference = text[text.index("class StreamingDft {"):text.index("class OnlineSpeechDenoiserStftImpl {")]
    reference = reference.replace("StreamingDft", "ReferenceDft")
    (test_dir / "reference-dft.h").write_text("#include <cmath>\n#include <cstdint>\n#include <vector>\n" + reference)
    binary = test_dir / "test-streaming-dft"
    run(os.environ.get("CXX", "c++"), "-std=c++17", "-O3", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror",
        "-I", HERE, "-I", test_dir, HERE / "test-streaming-dft.cc", "-o", binary)
    with (test_dir / "results.txt").open("w") as output:
        run(binary, stdout=output)
    print((test_dir / "results.txt").read_text(), end="")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=Path.home() / ".cache/cuebell/sherpa-fft-v1")
    parser.add_argument("--math-only", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    upstream, original, url = source(work)
    math_tests(work, original)
    if args.math_only:
        return
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
    ndk = sdk / "ndk" / NDK_VERSION
    cmake = sdk / "cmake/3.22.1/bin/cmake"
    ninja = sdk / "cmake/3.22.1/bin/ninja"
    if not (ndk / "build/cmake/android.toolchain.cmake").is_file() or not cmake.is_file():
        raise RuntimeError(f"Install NDK {NDK_VERSION} and CMake 3.22.1 in {sdk}")
    # Restore the verified original before applying the auditable one-file patch.
    (upstream / STFT).write_bytes(original)
    run("patch", "--batch", "--fuzz=0", "-p1", "-i", HERE / "upstream.patch", cwd=upstream)
    shutil.copyfile(HERE / "streaming-dft.h", upstream / "sherpa-onnx/csrc/cuebell-streaming-dft.h")
    build = work / "android-arm64"
    flags = [
        "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_TOOLCHAIN_FILE={ndk}/build/cmake/android.toolchain.cmake",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_FLAGS=-ffp-contract=off",
        "-DANDROID_ABI=arm64-v8a", "-DANDROID_PLATFORM=android-21", "-DANDROID_STL=c++_static",
        "-DBUILD_SHARED_LIBS=OFF", "-DSHERPA_ONNX_ENABLE_JNI=ON",
        "-DSHERPA_ONNX_ENABLE_TTS=ON", "-DSHERPA_ONNX_ENABLE_SPEAKER_DIARIZATION=ON",
        "-DSHERPA_ONNX_ENABLE_BINARY=OFF", "-DSHERPA_ONNX_ENABLE_C_API=OFF",
        "-DSHERPA_ONNX_BUILD_C_API_EXAMPLES=OFF", "-DSHERPA_ONNX_ENABLE_WEBSOCKET=OFF",
        "-DSHERPA_ONNX_ENABLE_PYTHON=OFF", "-DSHERPA_ONNX_ENABLE_TESTS=OFF",
        "-DSHERPA_ONNX_ENABLE_CHECK=OFF", "-DSHERPA_ONNX_ENABLE_PORTAUDIO=OFF",
        "-DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=OFF",
    ]
    env = os.environ.copy()
    # Pin date-sensitive compiler behavior. Upstream's own version.cc remains
    # untouched; the separate provenance identifies this modified binary.
    env["SOURCE_DATE_EPOCH"] = "1794614400"
    run(cmake, "-S", upstream, "-B", build, *flags, env=env)
    run(cmake, "--build", build, "--target", "sherpa-onnx-jni", "--parallel", args.jobs, env=env)
    output = work / "dist/arm64-v8a"
    output.mkdir(parents=True, exist_ok=True)
    library = output / "libsherpa-onnx-jni.so"
    toolchain = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    partial = output / "libsherpa-onnx-jni.so.partial"
    run(toolchain / "llvm-strip", "--strip-unneeded", "-o", partial, build / "lib/libsherpa-onnx-jni.so")
    partial.replace(library)
    manifest = {
        "variant": "cuebell-sherpa-2.0.1-double-fft-v1", "officialBinary": False,
        "upstreamCommit": COMMIT, "sourceUrl": url, "sourceSha256": SOURCE_SHA,
        "originalStftSha256": STFT_SHA,
        "patchSha256": digest(HERE / "upstream.patch"), "fftHeaderSha256": digest(HERE / "streaming-dft.h"),
        "buildScriptSha256": digest(__file__), "ndkVersion": NDK_VERSION, "cmakeVersion": "3.22.1",
        "cmakeFlags": flags, "sourceDateEpoch": env["SOURCE_DATE_EPOCH"],
        "librarySha256": digest(library), "libraryBytes": library.stat().st_size,
        "modelSha256": "e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534",
        "onnxruntimeVersion": "1.28.2",
        "onnxruntimeArchiveSha256": "bc68410f35f13df82c260830bf476ee5565f5efd0ec7622297829a929613c6c0",
        "originalAarSha256": "07e042d97f3a6bd5b7fe74d4eef0513dc01a714b16c15a903250095aba43a575",
    }
    (output.parent / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    print("Artifact:", library)


if __name__ == "__main__":
    main()
