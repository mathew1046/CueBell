# On-device noise reduction: implementation and validation

Date: 2026-11-14

Branch: `feat/on-device-denoising`, based on release commit
`6e1f32cc11b6a019c9a143d169af4043a6178c4d`.

Published baseline:
https://github.com/mathew1046/CueBell/releases/tag/v1.3.1-preview

## Follow-up: real recorded noise

The original latency-gated experiment below is retained as historical evidence.
The user subsequently deferred latency optimization and requested sourced real
noisy recordings, before/after audio, and conditional shipping. That follow-up
uses a revised 64 ms cumulative-processing-debt fallback policy and real Gnani
recognition. It found background-noise improvement alongside repeatable
recognition regressions; current observations and provider usage are recorded in:

/home/mathew/Arrakis/CueBell/docs/REAL_NOISE_DENOISING_2026-11-14.md

The 32 ms single-call fallback, test counts, and zero-additional-provider-usage
statements below describe the earlier experiment, not the current branch state.

## Original experiment outcome

**Experimental implementation complete; the performance acceptance gate failed.**
Noise reduction remains opt-in and off by default on `feat/on-device-denoising`.
The published 1.3.1 release remains the baseline. This experiment does not establish
latency-neutral noise reduction or improved Gnani/GPT-6 Luna recognition accuracy.

- The same-model FFT passed a short shell-context phone test: sustained p99
  **3.869 ms**, with all 1,095 frames enhanced and no fallback.
- Both Android-managed foreground-service tests failed. In the FFT trial, the
  first stress-frame call took **54.797 ms**, triggering the unchanged 32 ms guard;
  all 938 sustained frames were raw fallback, not successful enhancement.
- Enabled GTCRN also has a fixed **16 ms signal delay** and initialization cost.
  The disabled path does not initialize or run the denoiser.
- Final checks: **482 backend tests and 49 mobile tests passed**; backend Ruff,
  mobile lint, TypeScript and service-origin checks passed. The latest native
  build passed **28 JVM tests**.
- No additional paid provider or TTS calls were made. The planned paired ASR
  comparison was not run after the device gate failed.

Completion here means the branch implementation and its measured experimental
outcome are documented. Reliable enabled-mode performance, release-app microphone
timing, long-session/battery behavior and recognition non-regression remain
unproven. JNI startup overhead is a hypothesis, not an established root cause.

## Objective and implementation

Evaluate opt-in, native GTCRN enhancement before the existing Gnani → GPT-6 Luna
pipeline. Preserve the current raw path and measure the cost of enabling enhancement.
The setting defaults to **off**; this branch is separate from the published release.

Three subagents implemented the native streaming adapter, the settings/preference
flow, and the controlled device/recognition benchmark. The model is pinned by hash;
the engine uses sherpa-onnx 2.0.1 with one inference thread. The native module's
provenance, licensing and API contract are recorded in:

/home/mathew/Arrakis/CueBell/mobile/modules/queue-listener/NOISE_REDUCTION.md

The processing contract remains 16 kHz mono PCM16, 512 samples / 1024 bytes every
32 ms. The disabled path uses the original encoder. Enabling GTCRN introduces a
known **256-sample / 16 ms alignment delay**, plus separately measured initialization
and processing time. It cannot honestly be described as zero-overhead cancellation.
Initialization errors and processing calls of at least 32 ms trigger explicit raw
fallback; such output is excluded from successful-denoising comparisons.

## Predeclared evaluation

### Device processing

- Run the actual production Kotlin/JNI engine on the connected I2404 phone.
- Separate initialization, warm-up, sustained per-frame processing, scheduling
  lateness and fixed waveform alignment.
- Compare a sample-identical bypass path with the engine under paced 32 ms input.
- Record p50/p95/p99/max, process/thread CPU, RSS, reset reproducibility and every
  fallback. No silent removal of failed frames or faster-than-real-time-only claim.
- Initial performance gate: p99 processing below 8 ms and no 32 ms processing
  deadline violation or fallback. This is a conservative engineering budget, not
  a measured outcome or a guarantee about all phones.

### Recognition and end-to-end delivery

- Reuse existing ElevenLabs source recordings; generate no new paid speech.
- Ten cases: positive calls in Hindi, Malayalam, Tamil, Telugu, Marathi and Indian
  English; Hindi near-miss and correction; Malayalam stop; Tamil two-call burst.
- Compare clean and deterministic 10 dB stationary colored-noise input, each with
  sample-identical raw control and actual phone-processed GTCRN output.
- A shared per-case headroom gain prevents clipping and avoids a raw/processed
  loudness confound. Noise is synthetic AR(1), not a recording of a real venue.
- Preserve continuous state within each case, inter-cue gaps, scripts, expected
  identifiers/counters and source speech endpoints. Denoised output stays causal;
  do not trim away its 16 ms delay to improve the reported latency.
- Keep backend/model settings equal between conditions. Use real Gnani and Luna,
  with trace-audited coverage, raw and reviewed verdicts, provider-error counts and
  matched passing-case latency denominators.
- Require no observed regression on clean target/counter correctness before any
  recommendation to enable enhancement. A small corpus cannot establish general
  statistical noninferiority or real public-address performance.

Fixtures and provenance:
/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/fixtures/manifest.json

The fixture streams already include 0.3 seconds leading silence, their original
inter-cue gaps, and 24 seconds additional tail. Pipeline replay must use
`--leading-silence 0 --tail-silence 0` to avoid adding these twice.

## Budget

The prior campaign consumed 419 of 600 approved OpenAI attempts and 72.0804 of 120
approved Gnani connection minutes. This follow-up made no additional paid provider
calls, so those combined totals are unchanged. Existing source generation remains
1,250 submitted ElevenLabs characters; no additional TTS was generated.

## Validation status

Final full-suite verification: `backend/.venv/bin/pytest -q` passed 482 tests;
`npm test` in `mobile` passed 49 tests. Backend Ruff, mobile lint/typecheck and
service-origin validation passed. The latest native build passed 28 JVM tests,
including startup and midstream fail-open continuity. The published 1.3.1 APK was
confirmed installed on the phone (version code 6).

### First phone smoke test: performance gate failed

The experimental ARM64 application and the platform-instrumentation test APK built
successfully. The application APK is 25,160,445 bytes, an increase of 9,157,552 bytes
over the published release. Its signing certificate, bundled model hash and 16 KiB
alignment checks passed. This build result does not establish runtime performance.
This initial application artifact predates the later fail-open continuity fix;
it is not a final validated distribution candidate.

The first paced test executed the production Kotlin/JNI reducer through the test
APK's `app_process64` entry point on the I2404 / MediaTek MT6878, Android API 36.
Requested and actual thread priority were both `THREAD_PRIORITY_AUDIO` (-16).
This is a real-device processing test, but it is a shell-launched process rather
than the installed application's foreground microphone service.

| Measurement | Observed result |
| --- | --- |
| Fresh stress-engine initialization | 97.418 ms |
| First 12 invoked frames | 4.81–7.01 ms wall time |
| Next invoked frame | 22.023 ms wall / 15.923 ms thread CPU |
| Following invoked frame | 38.381 ms wall / 18.434 ms thread CPU |
| Result | `processing_deadline_exceeded`; permanent raw fallback |
| Active denoising frames in the 30-second sustained cohort | **0 of 938** |
| Separate bypass processing p50 / p99 | 0.0034 / 0.0108 ms |

Two earlier 32-frame reset checks kept enhancement active and produced identical
output hashes after recreating the engine. Their maximum processing times were
17.638 and 19.288 ms. This demonstrates repeatable state initialization for those
short checks, not sustained performance compliance.

The stress run's very low sustained processing times belong to **raw fallback**
and must not be reported as GTCRN speed. The runner completed successfully, but the
predeclared processing gate failed during warm-up. No output from this failed run
has been accepted as successfully denoised audio or sent for a paid ASR comparison.

The subsequent experiments below compare the installed test application's execution
context and avoidable transform overhead while keeping the 32 ms fallback guard.

Evidence:

/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/device-smoke-v1/results.json

/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/device-smoke-v1-analysis.json

/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/build.json

### Follow-up experiment: execution context and transform implementation

Source inspection identified a concrete optimization target: sherpa-onnx 2.0.1's
streaming frontend computes a quadratic DFT rather than an FFT. The first failed
frame also spent approximately 19.95 ms off-CPU, so transform cost alone cannot
explain its entire wall time.

Source:
https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v2.0.1/sherpa-onnx/csrc/online-speech-denoiser-stft-impl.h

The follow-up keeps two comparisons separate:

1. Execute the same original test APK through Android-managed instrumentation.
   Its SHA256 is
   `77d648eefa38ed66c78f95684a1cafb7f142a8622caac5c58ccb807ce79c79e4`.
   This checks the effect of the execution context without changing the model or
   native binary. Installation of this dedicated test package succeeded; it is
   separate from the installed CueBell release.
2. Build a version-pinned native FFT frontend with persistent plans and scratch
   buffers. Keep the GTCRN checkpoint, window, hop, normalization and alignment
   unchanged. Validate transform/output equivalence before device timing and ASR
   comparisons. Compilation or a faster desktop transform is not a phone result.

The managed-app launcher records installed-APK identity, deployed input hashes,
runtime results and test-package logs. Working-tree source snapshots are explicitly
distinguished from proof of which source built an APK. Later runner builds also
record cgroup/UID/TID and phase-level ART GC counters outside processing timers.

An executable processing gate now rejects incomplete active-engine coverage,
fallback, any measured processing call at or above 32 ms, or sustained active p99
at or above 8 ms. Three regression tests cover fallback masking and both threshold
boundaries; all 26 fixture/device-gate tests passed. Scheduling, fixed alignment,
recognition accuracy and device generalization remain separate measurements.

Launcher:
/home/mathew/Arrakis/CueBell/backend/benchmarks/denoising/instrument.py

Original-run gate report:
/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/device-smoke-v1-gate-analysis.json

### Managed trial: frozen process, no timing result

The first instrumentation launch verified the installed APK and deployed input
hashes, but produced no result files before the host command's 240-second timeout.
Post-timeout inspection found all 18 test-process threads in `do_freezer_trap`.
The process had UID 10392, CPU cgroup `/foreground` and cpuset `/l-foreground`.
This is an **inconclusive execution-context failure**, not a measurement of GTCRN
processing time. Only the dedicated test package was stopped after diagnostics.

The launcher had a 250-second inner instrumentation timeout, longer than its host
command's limit. Its interim deployment metadata therefore still says `running`;
the separate recovery record below records the final outcome. Future launch limits
must allow the runner to perform its own bounded cleanup.

The later managed trials used a test-only host and an ordinary foreground
media-processing service, with recorded lifecycle and cleanup. This provided a
runnable app context without changing global phone power or security settings.
Its context is still distinct from microphone capture.

Recovery record:
/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/instrument-smoke-v1/timeout-recovery.json

Thread-state evidence:
/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/instrument-smoke-v1/timeout-thread-waits.txt

### Same-model FFT: short phone processing gate passed

The rebuilt native library replaces the quadratic transform with preallocated
double-precision FFT scratch. The reviewed model, 512-sample packet, 256-sample
alignment and 32 ms overload guard remain unchanged. Host comparison of the actual
native GTCRN implementations found zero float or PCM16 differences across 941,568
samples from two passes of the Hindi/noise fixture. Transform tables/scratch fell
from 4,210,688 to 14,336 bytes; that is not total model or process memory.

The first phone comparison used the **same immutable v1 benchmark APK and Kotlin
code**, with only its standalone arm64 JNI library overlaid for `app_process`.
The launcher verifies the reviewed artifact lock and the uploaded library hashes.
Its deployment record, rather than the reference APK's embedded metadata, identifies
the loaded-library selection.

| Short FFT test | Result |
|---|---:|
| Warmup / sustained | 157 / 938 frames, 5 / 30 seconds |
| Active denoising | 1,095 / 1,095 frames |
| Sustained processing p50 / p99 / maximum | 3.119 / 3.869 / 4.968 ms |
| Warmup maximum processing | 6.896 ms |
| Processing ≥32 ms / completion deadline misses / fallback | 0 / 0 / 0 |
| Sustained process CPU, one-core equivalent | 9.98% |
| Sustained sampled RSS change | +236 KiB |
| Engine initialization | 62.516 ms, before paced frames |
| Fixed signal alignment | 256 samples = 16 ms |

Both short reset-pass output hashes also exactly matched the original binary's
hash. The short processing gate passed. This result is limited to shell execution
and one fixture: it does not establish foreground-service behavior, long-session
tails, battery cost, recognition quality or unchanged end-to-end latency. In
particular, the 16 ms signal delay and processing time have not disappeared.

Locked JNI SHA-256:
`59964bf7d9cf9520231d6cce3f6728b05f3c0ecac765bd9182bd9fc9d0539c65`

Phone evidence:
/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/device-fft-smoke-v1/

Gate analysis:
/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/device-fft-smoke-v1-analysis.json

Native implementation and reproducibility:
/home/mathew/Arrakis/CueBell/mobile/modules/queue-listener/android/native/sherpa-fft/README.md

### Foreground-service comparison: both processing gates failed

The second-generation test host used a visible activity to start a normal
`mediaProcessing` foreground service, then backgrounded the activity before
processing (`service-only`). A bounded partial wake lock prevented the earlier
freezer problem. Both runs completed and released the service and wake lock.
Neither run used the microphone or kept the screen on.

Both APKs had identical hashes for all 20 DEX files. The selected arm64 native
library and packaged provenance distinguished the original DFT and patched FFT
builds. Both ran as UID 10392 with thread priority -16, CPU cgroup `/foreground`
and cpuset `/l-foreground`. These were debug instrumentation APKs, not the release
microphone service; a single result in each context cannot isolate a root cause.

| Managed test | Original DFT | Patched FFT |
| --- | ---: | ---: |
| Stress-engine initialization | 91.011 ms | 675.204 ms |
| Invoked stress frames before permanent fallback | 137 | 1 |
| Maximum internal timed processing | 32.205 ms | 54.693 ms |
| Active frames in the sustained cohort | 0 / 938 | 0 / 938 |
| Reset checks all enhanced | No | No |
| Processing acceptance | Failed | Failed |

The FFT failing call measured **54.797 ms externally / 28.194 ms thread CPU**;
the remainder was not on that worker's CPU. Its two preliminary reset passes also
fell back, after 11 and 24 calls, with internal maxima of 35.350 and 41.833 ms.
Initial thermal status was 3 for DFT and 2 for FFT; these runs are not a controlled
thermal comparison. The short shell-context success does not override these failures.
Low sustained raw-fallback timings must not be interpreted as denoising throughput.

The original DFT launcher also reported an instrumentation failure because Android's
pretty output hid the result code. Adding `am instrument -r` fixed the launcher;
41 launcher tests passed. The DFT report and foreground lifecycle independently
showed completion, and were validated offline without modifying the original
failed deployment status or inventing a missing result code. Its processing gate
still failed. The FFT launcher completed normally and its processing gate failed.

Evidence:

/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/instrument-service-dft-v2-analysis.json

/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/instrument-service-fft-v2-analysis.json

/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/foreground-artifact-verification-v2.json

/home/mathew/Arrakis/CueBell/docs/benchmarks/denoising-2026-11-14/native-validation/

### Recognition comparison: prepared, not executed

The paired-condition combiner and fixtures are ready for ten cases across six
languages, using four acoustic conditions and shuffled within-case order. It
rejects changed labels, scripts, durations or source endpoints. Output registration
rejects fallback, altered length, removed causal delay and nonidentical bypass.
No waveform was registered as successful denoising and no new Gnani/Luna study
was launched after the foreground processing failures. Recognition improvement,
clean-speech non-regression and end-to-end latency therefore have no result in
this denoising campaign.

The next decision requires a bounded profile of the actual release microphone
path, separating initialization, native inference, JNI/allocation and off-CPU
time. Retain the 32 ms fallback guard and the existing raw default. Only after a
representative device gate passes should the prepared real-provider comparison
be used to decide whether enabling enhancement helps CueBell.
