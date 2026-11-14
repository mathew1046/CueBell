# CueBell's explicit sherpa-onnx FFT experiment

This is a **modified native build**, not an official sherpa binary. It replaces
only the streaming transform implementation in sherpa-onnx 2.0.1. Model weights,
model state, ONNX Runtime, windowing, overlap-add, hop size, Kotlin framing and the
32 ms fail-open policy remain the same. It is not a FastEnhancer model switch.

Upstream source commit: `af2d8d81dbfa61c4cea4c568da78f3982edca005`.
Source archive SHA-256:
`afcafe3c34bc2f15a363ad791fa1644a69bf0977a58c1b4f617468976c2faeb5`.
https://codeload.github.com/k2-fsa/sherpa-onnx/tar.gz/af2d8d81dbfa61c4cea4c568da78f3982edca005

Original STFT header SHA-256:
`5ec43424a1c5bf48c198dd7aaad3e19cc01d366e779fbc8196e8146f8514e124`.
The checked-in `upstream.patch` removes the old `StreamingDft` and includes
`streaming-dft.h`; it does not edit the surrounding streaming code. The custom
header is Apache-2.0, with upstream attribution for the retained fallback math.
Existing model/sherpa/ORT notices continue to ship as app assets.

## Why this change

The official online frontend performs a quadratic DFT: two forward and two
inverse transforms per 512-sample capture frame, **524,288 inner-loop terms**.
It stores four double trigonometric tables totaling **4,210,688 bytes** at N=512.

The replacement uses a portable complex radix-2 FFT with double intermediate
values, precomputed twiddles/bit reversal, and persistent scratch. At N=512 its
array payload is **14,336 bytes**, and the four transforms use **9,216 butterflies**.
There is no allocation in either transform call. Input/output retain upstream's
float format. The forward sign is negative; inverse scaling is exactly `1/N`.
Imaginary DC and Nyquist values are ignored on inverse, as upstream requires.

Non-power-of-two sizes >=2 use the original DFT arithmetic. That fallback retains
upstream's odd-size inverse convention, including omission of the highest
positive bin; it is not a claim that odd sizes are a supported GTCRN configuration.
Sizes <2 are rejected (the original inverse loop is invalid at N=1).
The FFT instance has mutable scratch and is **single-owner**, matching the
stateful denoiser. No global state, worker pool, affinity or governor change is
introduced.

## Build and integration

Linux prerequisites: Python >=3.12, C++17 host compiler, `patch`, Android SDK
NDK **27.1.12297006**, CMake **3.22.1** and Ninja. Allow about 4 GB for unstripped
build products/dependencies; a disk-backed work directory is preferable to tmpfs.
From the repository root:

```sh
python3 mobile/modules/queue-listener/android/native/sherpa-fft/build.py \
  --work-dir /home/mathew/.cache/cuebell/sherpa-fft-v1 --jobs 4
```

The script validates the source checksum, tests the transform against a class
extracted from the verified original, applies the exact patch, builds the full
JNI ABI for arm64-v8a, strips the result and writes `dist/provenance.json`.
The ONNX Runtime static archive remains pinned to **1.28.2**, SHA-256
`bc68410f35f13df82c260830bf476ee5565f5efd0ec7622297829a929613c6c0`:
https://github.com/csukuangfj/onnxruntime-libs/releases/download/v1.28.2/onnxruntime-android-arm64-v8a-static_lib-1.28.2.zip

The complete CMake invocation is in the provenance. Important flags: Release,
`-ffp-contract=off`, Android API 21, `c++_static`, `BUILD_SHARED_LIBS=OFF`, JNI/TTS/
speaker-diarization ON, binaries/C API/Python/PortAudio/WebSocket OFF. Upstream
retains 16 KiB ELF page alignment. No fast-math or hardware-specific CPU tuning is
added. The model SHA remains
`e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534`.

Gradle selects the reviewed experiment only with an explicit property:

```sh
./gradlew :queue-listener:testDebugUnitTest :queue-listener:assembleRelease \
  -PcuebellSherpaFftDir=/home/mathew/.cache/cuebell/sherpa-fft-v1/dist \
  --console=plain --max-workers=2
```

Run that command from the generated mobile Android build directory. Main owns
APK builds and device jobs. Use `-PreactNativeArchitectures=arm64-v8a` for an arm64
app experiment. Gradle verifies the binary, source/header/patch/build-script hashes
against **`artifact-lock.json`**, then overlays only arm64 JNI onto the verified
official AAR. Other ABIs remain official. Omit the property to return to the
official binary; this is a Gradle input, so cached FFT outputs are replaced.
The packaged `noise-reduction/runtime-provenance.json` records the selected build
and patched ABIs. Rebuilt binaries with a different hash require explicit review
and a lock update; a manifest alone cannot authorize arbitrary replacement.

## Correctness checks

`build.py --math-only` checks:
- N=2/4/8/32/256/512/1024 and non-power-of-two 480/9;
- silence, impulses at multiple positions, DC, Nyquist, bin/non-bin sinusoids,
  deterministic noise, near-zero/denormal inputs and PCM16 endpoint patterns;
- arbitrary complex spectra, real-only DC/Nyquist, sign/scaling and round trips;
- 128 repeated forward/inverse pairs per size with an allocation counter;
- 160-hop periodic square-root-Hann overlap-add with a nontrivial spectral mask,
  256-sample first-output deficit and identical fresh/reused scratch results.

The host model regression compiles the **actual pinned native GTCRN + STFT code**
twice into one harness: original frontend and patched frontend, separate model
instances/states, the same Linux ORT 1.28.2. It compares two full input passes,
256/512 output framing, finite samples, flush and exact reset reproducibility.
Limits: max absolute float difference 2e-5 and at most one PCM16 LSB. Example:

```sh
python3 mobile/modules/queue-listener/android/native/sherpa-fft/host-regression.py \
  --work-dir /home/mathew/.cache/cuebell/sherpa-fft-v1 \
  --model mobile/modules/queue-listener/android/src/main/assets/noise-reduction/gtcrn_simple.onnx \
  --wav docs/benchmarks/denoising-2026-11-14/fixtures/audio/colored-snr-p10/hi-positive.wav
```

These verify numerical behavior, not Android tail latency. Device acceptance
still requires the same 32 ms paced workload, no fallback and p99 target below
8 ms, followed by the actual Gnani comparison. A smaller FFT workload cannot
guarantee scheduler availability; do not count raw fallback frames as successful
denoising measurements.

## Validated artifact (2026-11-14)

Built JNI: **24,145,240 bytes**, SHA-256
`59964bf7d9cf9520231d6cce3f6728b05f3c0ecac765bd9182bd9fc9d0539c65`.
All **134** exported sherpa JNI methods match the official arm64 library; the
eight `OnlineSpeechDenoiser` entry points are present. ELF LOAD alignment remains
`0x4000`. Dependencies remain only `libandroid`, `liblog`, `libm`, `libdl`, `libc`;
ORT and the C++ runtime are statically linked.

Available artifact:
/home/mathew/.cache/cuebell/sherpa-fft-v1-storage/dist/arm64-v8a/libsherpa-onnx-jni.so

Provenance (complete flags and hashes):
/home/mathew/.cache/cuebell/sherpa-fft-v1-storage/dist/provenance.json

This run used `/tmp/opencode/cuebell-denoising/fft` as its logical build directory;
bulky `_deps`, `lib` and `dist` directories were moved behind symlinks to the
disk-backed cache when tmpfs filled. Use the available `dist` above for the exact
locked artifact. Builds in other paths/toolchains can differ in embedded paths
and must be reviewed before changing the binary lock.

Observed checks:
- Transform/reference max absolute difference: **5.96046447754e-08** forward and
  inverse; masked window/overlap difference **2.91038304567e-11**. Allocation guard
  passed. The same tests passed Clang/GCC and Clang ASan+UBSan.
- Actual native GTCRN regression: Hindi + colored noise fixture SHA-256
  `c898a65eb4c965e5f42a2ae35fc50a3e4bd0dbf6cbb30073a8b03f5b82e5fa64`, **920 frames
  per pass**, two reset passes, **941,568** compared unprefixed native samples.
  Float and PCM16 differences were **zero**; 929,834 output PCM16 samples were
  nonzero (output RMS 0.0589267848833). Reset was exact and flush framing passed.
- FFT-selected `testDebugUnitTest` + `assembleRelease`: **25 tests, zero failures**.
  The resulting AAR contains the locked JNI, unchanged model SHA and explicit
  runtime provenance. Tampered provenance is rejected; FFT → official → FFT
  selection was checked for exact binary hashes and matching metadata.
- Mobile lint/typecheck and `git diff --check` passed.

Logs/results:
/tmp/opencode/cuebell-denoising/fft/math-tests/results.txt
/tmp/opencode/cuebell-denoising/fft/math-tests/sanitized-results.txt
/tmp/opencode/cuebell-denoising/fft/host-regression/results.txt
/tmp/opencode/cuebell-denoising/fft/host-regression/inputs.json
/tmp/opencode/cuebell-denoising/fft/module-check.log

The isolated host transform timing was 475.16 µs → 18.53 µs per equivalent
512-sample frame in one Clang run; this excludes model inference and scheduling,
and is not an Android performance result. No phone jobs or APK builds were run
for this native experiment.
