# Native noise reduction: implementation and device evidence

Date: 14 November 2026. Historical experiment on `feat/on-device-denoising`, based on `6e1f32cc11b6a019c9a143d169af4043a6178c4d`. Published baseline: [v1.3.1-preview](https://github.com/mathew1046/CueBell/releases/tag/v1.3.1-preview).

## Outcome

**The FFT optimization passed a short shell-context phone test, but the original performance acceptance gate failed in both managed foreground-service trials.** Noise reduction remained experimental, opt-in and off by default. This study does not demonstrate latency-neutral enhancement or improved Gnani/GPT-6 Luna recognition.

The later [real-recording study](REAL_NOISE_DENOISING_2026-11-14.md) used a revised 64 ms cumulative-processing-debt fallback policy and real Gnani recognition. The single-call 32 ms fallback, test counts and no-additional-provider-use statements here describe this earlier experiment only.

## Method and acceptance gate

- Three implementation workstreams covered native streaming, settings/preferences and controlled device/recognition evaluation. GTCRN is hash-pinned, using sherpa-onnx 2.0.1 and one inference thread. See the [native contract, licenses and provenance](../mobile/modules/queue-listener/NOISE_REDUCTION.md).
- Input/output: 16 kHz mono PCM16, 512 samples / 1,024 bytes every 32 ms. The disabled path retains the original encoder and does not initialize the model. Enabled output retains a **256-sample / 16 ms signal delay**, plus separate initialization and processing cost.
- In this original policy, initialization errors or processing calls of at least 32 ms trigger permanent raw fallback. Fallback is never counted as successful denoising.
- Run the production Kotlin/JNI engine on the connected I2404 phone, with sample-identical bypass, paced input and separate initialization, warm-up, sustained processing, scheduling and alignment measurements. Retain CPU, RSS, reset hashes and every fallback.
- Predeclared processing gate: sustained active p99 below 8 ms, no call at or above 32 ms, no fallback and complete active coverage. This is an engineering budget, not a guarantee for all phones. The executable gate has three regression tests for fallback masking and threshold boundaries; all 26 fixture/device-gate tests passed.

### Recognition comparison prepared, not executed

The plan covered ten cases across Hindi, Malayalam, Tamil, Telugu, Marathi and Indian English: positive calls, Hindi near-miss/correction, Malayalam stop and a Tamil two-call burst. Existing ElevenLabs speech would be tested clean and with deterministic 10 dB stationary AR(1) colored noise, each raw and phone-enhanced, giving four acoustic conditions with shuffled within-case order. This is synthetic noise, not a venue recording.

The plan retained continuous state, gaps, scripts, expected identifiers/counters, endpoints and the causal delay. Shared per-case headroom prevented clipping/loudness confounds. Real Gnani and Luna settings were to remain equal, with trace-audited coverage, raw/reviewed verdicts, provider errors and matched passing-case latency denominators. Registration rejects changed labels, scripts, lengths, endpoints, fallback, removed delay or nonidentical bypass. Clean correctness non-regression was required, without claiming statistical noninferiority from a small corpus.

[Fixtures and provenance](benchmarks/denoising-2026-11-14/fixtures/manifest.json) include 0.3 seconds leading silence, original gaps and 24 seconds tail. Replay requires `--leading-silence 0 --tail-silence 0` to avoid doubling those intervals. **No output was registered for the paid comparison after the device failures.**

## Device results

### 1. Original shell smoke test: failed

Device: I2404 / MediaTek MT6878, Android API 36. Production Kotlin/JNI ran through the test APK's `app_process64` entry point, not the installed foreground microphone service. Requested and actual audio thread priority were both -16.

| Measurement | Result |
| --- | ---: |
| Fresh stress-engine initialization | 97.418 ms |
| First 12 invoked frames | 4.81–7.01 ms wall |
| Next frame | 22.023 ms wall / 15.923 ms thread CPU |
| Following frame | 38.381 ms wall / 18.434 ms thread CPU |
| Result | `processing_deadline_exceeded`, permanent raw fallback |
| Active sustained denoising | 0 / 938 frames over 30 seconds |
| Bypass p50 / p99 | 0.0034 / 0.0108 ms |

Two earlier 32-frame reset checks stayed active and produced identical output hashes; their maxima were 17.638 and 19.288 ms. That validates short reset reproducibility, not sustained compliance. The failed frame spent about 19.95 ms off-CPU, so transform cost cannot explain its entire wall time. Low sustained fallback timings are **not GTCRN throughput**. No failed output was accepted as denoised or submitted for paid ASR.

Evidence: [results](benchmarks/denoising-2026-11-14/device-smoke-v1/results.json), [analysis](benchmarks/denoising-2026-11-14/device-smoke-v1-analysis.json), [gate analysis](benchmarks/denoising-2026-11-14/device-smoke-v1-gate-analysis.json).

### 2. First managed instrumentation trial: inconclusive

The original test APK and deployed input hashes were verified, but no results arrived before the host's 240-second timeout. All 18 process threads were later found in `do_freezer_trap`, under UID 10392, CPU cgroup `/foreground` and cpuset `/l-foreground`. This is an execution-context failure, not a denoiser timing result. Only the dedicated test package was stopped.

The inner timeout was 250 seconds, longer than the host limit. Interim deployment metadata still says `running`; [timeout recovery](benchmarks/denoising-2026-11-14/instrument-smoke-v1/timeout-recovery.json) records the final outcome. See [thread waits](benchmarks/denoising-2026-11-14/instrument-smoke-v1/timeout-thread-waits.txt). Later trials used a normal test-only foreground media-processing service and bounded cleanup without changing global power/security settings. Launcher: [`instrument.py`](../backend/benchmarks/denoising/instrument.py).

### 3. Same-model FFT: short phone gate passed

[Upstream sherpa-onnx 2.0.1 source](https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v2.0.1/sherpa-onnx/csrc/online-speech-denoiser-stft-impl.h) uses a quadratic DFT frontend. The patched native runtime replaces it with preallocated double-precision FFT tables/scratch, preserving the GTCRN checkpoint, window, hop, normalization, 512-sample packet, 256-sample alignment and 32 ms guard.

Host comparison of the actual native implementations found **zero float or PCM16 differences across 941,568 samples**, from two Hindi/noise-fixture passes. Transform tables/scratch fell from **4,210,688 to 14,336 bytes (99.66% less)**. This is not total model/process memory.

The phone comparison retained the same immutable v1 APK and Kotlin code, overlaying only its standalone arm64 JNI library for `app_process`. Artifact locks and uploaded library hashes identify what ran; working-tree snapshots are not substituted for build provenance. APK SHA-256: `77d648eefa38ed66c78f95684a1cafb7f142a8622caac5c58ccb807ce79c79e4`. Loaded JNI SHA-256: `59964bf7d9cf9520231d6cce3f6728b05f3c0ecac765bd9182bd9fc9d0539c65`.

| Short FFT test | Result |
| --- | ---: |
| Warm-up / sustained | 157 / 938 frames, 5 / 30 seconds |
| Active denoising | 1,095 / 1,095 frames |
| Sustained processing p50 / p99 / max | 3.119 / 3.869 / 4.968 ms |
| Warm-up maximum | 6.896 ms |
| Calls ≥32 ms / completion misses / fallback | 0 / 0 / 0 |
| Sustained process CPU, one-core equivalent | 9.98% |
| Sustained sampled RSS change | +236 KiB |
| Engine initialization, before paced frames | 62.516 ms |
| Fixed signal alignment | 256 samples / 16 ms |

Both reset hashes matched the original binary. **This is a short shell-context success on one fixture**, not evidence of microphone-service behavior, long-session/battery performance, recognition quality or unchanged end-to-end latency.

Evidence: [phone artifacts](benchmarks/denoising-2026-11-14/device-fft-smoke-v1/), [analysis](benchmarks/denoising-2026-11-14/device-fft-smoke-v1-analysis.json), [native implementation and reproducibility](../mobile/modules/queue-listener/android/native/sherpa-fft/README.md).

### 4. Foreground-service comparison: both failed

A visible test activity started a `mediaProcessing` foreground service, then moved to `service-only` mode. A bounded partial wake lock avoided freezing; both runs completed and released it. Neither used the microphone or kept the screen on. These were debug instrumentation APKs, not the release microphone service.

The two APKs had identical hashes for all 20 DEX files; the arm64 library and packaged provenance distinguished DFT/FFT. Both used UID 10392, thread priority -16, `/foreground` and `/l-foreground`. Phase-level ART GC counters were outside processing timers. One run per context cannot isolate a root cause.

| Managed test | Original DFT | Patched FFT |
| --- | ---: | ---: |
| Stress-engine initialization, internal timer | 91.011 ms | 675.204 ms |
| Invoked stress frames before fallback | 137 | 1 |
| Maximum internal processing | 32.205 ms | 54.693 ms |
| Active sustained frames | 0 / 938 | 0 / 938 |
| Reset checks all enhanced | No | No |
| Processing acceptance | Failed | Failed |

The FFT failing call was **54.797 ms external wall / 28.194 ms thread CPU**. Its preliminary resets fell back after 11 and 24 calls, with internal maxima 35.350 and 41.833 ms. Initial thermal status was 3 for DFT and 2 for FFT, so this is not a controlled thermal comparison. Shell success does not override these failures.

The DFT launcher also reported failure because Android pretty output hid the result code. `am instrument -r` fixed that launcher issue; 41 launcher tests passed. DFT completion/lifecycle were independently validated offline, preserving the original failed deployment status and not inventing a missing result code. Both processing gates still failed.

Evidence: [DFT analysis](benchmarks/denoising-2026-11-14/instrument-service-dft-v2-analysis.json), [FFT analysis](benchmarks/denoising-2026-11-14/instrument-service-fft-v2-analysis.json), [artifact verification](benchmarks/denoising-2026-11-14/foreground-artifact-verification-v2.json), [native validation](benchmarks/denoising-2026-11-14/native-validation/).

## Build, verification and usage record

- Experimental application and test APKs built. Initial app APK: **25,160,445 bytes**, **9,157,552 bytes larger** than the published release. Signing certificate, model hash and 16 KiB alignment passed. This APK predates the later fail-open continuity fix and is not a final validated distribution.
- Historical full checks: **482 backend tests, 49 mobile tests and 28 JVM tests passed**, including startup/midstream fallback continuity. Backend Ruff, mobile lint/TypeScript and service-origin checks passed. Published 1.3.1 APK, version code 6, was confirmed installed.
- [Build evidence](benchmarks/denoising-2026-11-14/build.json). This documentation audit did not rerun those suites or the phone tests.
- No additional paid provider or TTS calls. Prior cumulative usage stayed **419/600 OpenAI attempts**, **72.0804/120 Gnani connection minutes**, and **1,250 submitted ElevenLabs characters**.

## Decision

Retain the raw default. The implementation and measured experiment are complete, but reliable enabled-mode performance, release microphone timing, long sessions, battery cost and recognition non-regression are unproven. JNI startup overhead is a hypothesis, not an established root cause. A useful next profile separates initialization, native inference, JNI/allocation and off-CPU time on the actual microphone path. Later policy and recognition findings belong to the [real-noise follow-up](REAL_NOISE_DENOISING_2026-11-14.md), not this original gate.
