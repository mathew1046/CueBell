# Native noise reduction: implementation and device evidence

14 November 2026. **The FFT optimization passed a short shell-context phone test, but both managed foreground-service trials failed the original performance gate.** Noise reduction stayed experimental, opt-in and off by default. This study does not establish recognition improvement or latency-neutral enhancement.

## Method

The production Kotlin/JNI reducer used pinned GTCRN, sherpa-onnx 2.0.1 and one inference thread on an I2404 / MediaTek MT6878 phone, Android API 36. Input/output was mono PCM16 at 16 kHz, 512 samples every 32 ms. Enabled processing retains **256 samples / 16 ms signal delay**, plus initialization and computation. Disabled mode does not initialize the model.

The original policy permanently returned to raw audio after errors or any processing call ≥32 ms. Acceptance required sustained active p99 below 8 ms, no call ≥32 ms, no fallback and complete coverage. P99 means 99% of measured calls finish below that time. Fallback timings are not enhancement throughput.

A planned ten-case, six-language recognition comparison included clean and synthetic 10 dB colored-noise conditions, each raw and phone-enhanced. It retained state, alignment, gaps and identical provider settings. **No paid recognition output was registered after the device failures.** [Fixture manifest](benchmarks/denoising-2026-11-14/fixtures/manifest.json) and the full report retain registration rules. Fixtures already include leading/tail silence; replay needs `--leading-silence 0 --tail-silence 0`.

## Results

| Trial | Result and denominator |
|---|---|
| Original shell smoke | Initialization 97.418 ms. A 38.381 ms wall / 18.434 ms CPU call caused fallback; **0/938 sustained frames** enhanced. Short reset outputs matched, not sustained compliance |
| First instrumentation | No results before 240-second host timeout; all 18 threads later found frozen. Execution-context failure, not timing evidence |
| Patched FFT shell | **1,095/1,095 frames** active across 5 s warm-up and 30 s sustained replay. Sustained processing median/p99/max **3.119 / 3.869 / 4.968 ms**; no fallback/deadline misses |
| Managed service, DFT | Maximum internal processing **32.205 ms**, fallback after 137 invoked stress frames; **0/938 sustained frames** active |
| Managed service, FFT | Maximum internal processing **54.693 ms**, fallback on first stress frame; **0/938 sustained frames** active |

DFT is the original discrete Fourier transform; FFT computes the same transform more efficiently. The patched native frontend preserves the model, window, hop, normalization and signal alignment.

Host comparison found **zero float/PCM16 differences over 941,568 samples**, from two Hindi/noise-fixture passes. Transform tables/scratch shrank **4,210,688 → 14,336 bytes (99.66%)**, not total model/process memory. Both phone reset hashes matched the original binary.

The successful shell test used the same immutable APK/Kotlin code with only the arm64 JNI library overlaid. Initialization was **62.516 ms**, sustained CPU **9.98% of one core**, and sampled RSS change **+236 KiB**. These are short file-replay results on one fixture, not microphone, battery or recognition validation.

Managed trials used a test-only media-processing foreground service, partial wake lock and screen-off execution, not the release microphone service. DEX hashes matched; native libraries/provenance differed. Initial thermal statuses differed, so one run each cannot isolate a cause. FFT's failing call took **54.797 ms external wall / 28.194 ms CPU**. JNI startup remains a hypothesis, not a diagnosis.

## Evidence and historical checks

Canonical [campaign](benchmarks/denoising-2026-11-14/) retains APK/library locks, timings and original statuses:

- [Original shell analysis](benchmarks/denoising-2026-11-14/device-smoke-v1-analysis.json), [timeout recovery](benchmarks/denoising-2026-11-14/instrument-smoke-v1/timeout-recovery.json).
- [FFT shell analysis](benchmarks/denoising-2026-11-14/device-fft-smoke-v1-analysis.json), [managed DFT](benchmarks/denoising-2026-11-14/instrument-service-dft-v2-analysis.json), [managed FFT](benchmarks/denoising-2026-11-14/instrument-service-fft-v2-analysis.json), [artifact verification](benchmarks/denoising-2026-11-14/foreground-artifact-verification-v2.json).
- [Native contract/licenses](../mobile/modules/queue-listener/NOISE_REDUCTION.md), [FFT build/reproduction](../mobile/modules/queue-listener/android/native/sherpa-fft/README.md), [instrument launcher](../backend/benchmarks/denoising/instrument.py).

Android pretty-output parsing caused a separate launcher failure, fixed with `am instrument -r`; offline lifecycle validation did not erase the recorded status or processing failures. Historical checks included 482 backend, 49 mobile and 28 JVM tests; no new tests/device/provider runs accompanied this edit. No additional paid providers or TTS were used in this original study.

## Decision

Retain raw defaults. Reliable enabled-mode microphone performance, long sessions, energy cost and recognition preservation remain unproven. The [DNS5 follow-up](REAL_NOISE_DENOISING_2026-11-14.md) changes the fallback policy to cumulative debt and adds real recognition results; it does not retroactively pass this strict gate.

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/NOISE_REDUCTION_BENCHMARK_2026-11-14.md), including artifact identities and historical verification details.
