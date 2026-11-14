# Native noise-reduction integration contract

This feature is opt-in. `NoiseReductionMode = 'off' | 'gtcrn'` is exported from
`index.ts`. The optional fourth argument to `QueueListener.start(url, token, mode,
options)` is `{ noiseReductionMode?: NoiseReductionMode }`; omitted means `off`.
The same options apply to request and monitor sessions. Selection is fixed for a
capture session; stop before changing it.

**Integration outcome (2026-11-14): experimental, not performance-qualified.**
The FFT variant passed a short shell-context phone test, but both original and FFT
builds failed the previous single-call 32 ms managed foreground-service gate.
The functional overload policy below now tolerates bounded transient overruns;
those earlier results do not validate this revised policy. Enabled-mode latency
and ASR non-regression have not been established; the default remains `off`.
Full results:
/home/mathew/Arrakis/CueBell/docs/NOISE_REDUCTION_BENCHMARK_2026-11-14.md

Subsequent sourced-recording tests found background-noise reduction but repeatable
Gnani language/script and word-error regressions. Recognition-preserving shipping
is not qualified by those results. Real-noise audio, observations, and the revised
policy's validation are recorded in:
/home/mathew/Arrakis/CueBell/docs/REAL_NOISE_DENOISING_2026-11-14.md

The native `snapshot()` JSON includes `noiseReductionMode` (selection) and
`noiseReduction` (the diagnostic snapshot). `onEvent` emits a
`{ type: "noise_reduction", ...diagnostics }` JSON event at initialization and on
fallback, never per PCM frame. Diagnostics in the service snapshot are updated
on initialization, fallback and capture completion. Fallback also updates the
foreground notification/status message. Request-to-monitor handoff creates a new
capture/engine with the supplied mode; an active recording cannot be hot-switched.

## Benchmark contract

Package: `expo.modules.queuelistener`.

```kotlin
interface PcmNoiseReducer : AutoCloseable {
  fun process(input: ShortArray, output: ShortArray)
  override fun close()
}
```

The concrete adapter is `GtcrnNoiseReducer(modelPath: String,
assetManager: android.content.res.AssetManager? = null)`. A filesystem path works
without an Android context. It consumes exactly 512 mono PCM16 samples at 16000 Hz
and writes exactly 512 samples into the supplied output, retaining inference
state between calls. Process and close from one owner thread. A fully initialized
instance can be transferred between threads before processing starts.
Construction/preload is outside the timed per-frame loop. `diagnostics` returns
`NoiseReductionDiagnostics` with `requestedMode`, `activeMode`, `sampleRate`,
`frameSamples`, `algorithmicDelaySamples`, `startupPaddingSamples`,
`initializationNanos`, `processedFrames`, `lastProcessNanos`, `maxProcessNanos`,
`overloadCount`, nullable `fallbackReason`, and the `Long` fields
`processingDebtNanos`, `maxProcessingDebtNanos`, `processingDebtLimitNanos`.
Read it before `close()` to retain
the active mode. `fallbackReason` is also available directly without allocating a
snapshot. Benchmarks should retain these diagnostics alongside external timings.
`algorithmicDelaySamples` reports output alignment while the processor is open:
256 for active GTCRN and for raw fallback after delayed output has been emitted,
zero for startup raw fallback. `activeMode` is `off` during either raw fallback;
the delay field distinguishes aligned raw output from zero-delay startup raw.
Before the first successful call, active GTCRN reports its configured 256-sample
delay. `startupPaddingSamples` counts padding actually emitted (zero before
processing or an immediate fallback, 256 after the first successful frame).
After `close()`, active mode is `off`, current delay is zero, and padding remains
historical. Read diagnostics before closing to record the final streaming state.

`GtcrnNoiseReducer.MODEL_ASSET` is `noise-reduction/gtcrn_simple.onnx`. Copy this
asset to a file for a filesystem benchmark, or pass an `AssetManager`. Only the
pinned SHA-256 model is accepted. Missing/mismatched models and unavailable JNI
libraries cause raw passthrough with a reason. This is intentional: it must be
possible to benchmark and diagnose a fallback rather than crash the listener.
Production uses `GtcrnNoiseReducer.fromAssets(assets, directory)` to copy the model
once into the app's private no-backup directory, then verify and load the file.
This uses upstream's exception-guarded file constructor. Initialization I/O errors
also fail open. The persisted file contains only model weights. Direct asset
construction remains supported for standalone callers. Recoverable JVM/linkage
errors are caught; fatal native aborts or process termination cannot be recovered
by Kotlin (upstream `run`/`reset` do not wrap all C++ exceptions).

The model uses 512-sample windows and 256-sample hops at 16 kHz. The verified
sherpa-onnx 2.0.1 implementation returns 256 samples on its first 512-sample call,
then 512 on subsequent calls. The adapter prepends **256 zeros once**. Output
therefore has **256 samples / 16 ms sample alignment delay**, with no extra
packet queue: it still emits 512 samples / 1024 bytes per 32 ms capture frame.
Initialization includes a zero-frame warm-up followed by `reset()`, so warm-up
does not leak state into the recording. Initialization time is reported separately
and is additional startup time before the microphone opens.

### Functional overload policy

Each inference attempt uses monotonic **wall time**, including normalization,
native inference, validation and conversion. The accounting interval remains
**32 ms**; a call at or above that interval increments `overloadCount`. A single
overrun does not necessarily disable enhancement:

```text
processingDebt = max(0, previousProcessingDebt + processingTime - 32 ms)
```

Debt starts at zero. Faster processing pays down existing debt but never banks
advance credit. Initialization/warm-up time is reported separately and is not
charged. Valid enhanced output is retained while debt is **below 64 ms**. At or
above **64 ms**, the current and subsequent frames permanently use raw fallback
with `fallbackReason = "processing_debt_exceeded"` for that capture. There is no
inference retry, model reset, extra warm-up, worker queue or additional audio
buffer. A 54.796847 ms call incurs 22.796847 ms debt; a following 3.119384 ms call
clears it. Eight consecutive 40 ms calls hit the limit on the eighth call.

Recoverable exceptions, malformed output and non-finite samples **always fail
open immediately**, regardless of debt. Their original error reason takes
precedence if the same call also exceeds the debt limit. Invalid results are
never emitted. `overloadCount` is a count of calls at or above 32 ms, not a count
of fallback transitions; it may be nonzero while `activeMode` is still `gtcrn`.

Diagnostic debt values describe the estimate after the **last inference attempt**:
- `processingDebtNanos`: current estimate; can exceed the limit on the triggering
  call because synchronous JNI cannot be preempted.
- `maxProcessingDebtNanos`: peak estimate for this processor instance.
- `processingDebtLimitNanos`: **64_000_000** for requested GTCRN, including fallback
  and closed snapshots; **0** for explicit `NoiseReductionDiagnostics.off()`.

Debt and peak remain historical after fallback/close; raw bypass does not update
them. A fresh instance starts with zero debt and peak. Arithmetic saturates only
at `Long.MAX_VALUE` to prevent overflow from falsely clearing debt.

This is a bounded **processing-debt policy**, not a microphone-age or hard
end-to-end latency measurement. AudioRecord capture pacing normally provides one
512-sample frame per 32 ms; faster calls can catch up queued microphone input.
The estimate excludes waits, scheduling between calls and transport work. A
single blocked JNI call can overshoot the limit before returning; capture-side
age/backlog and cancellation guards still govern whether returned PCM is sent.
No processor policy can undo that elapsed time or interrupt the native call.

Raw fallback preserves the input timeline:
- **Before any successful delayed output:** copy the current and subsequent raw
  frames bit-exactly with zero delay and no startup padding.
- **After delayed output begins:** retain the existing 256-sample / 16 ms delay.
  Each raw frame contains the preceding input frame's last 256 samples followed
  by the current input frame's first 256 samples. This includes the failing call;
  there is no repeated prefix, silence insertion, skipped interval or growing
  queue. The transition changes filtering, not sample positions. No additional
  buffering delay is introduced.

The adapter keeps one preallocated `ShortArray(256)` raw-input tail (512 bytes),
updated before writing caller output so aliased input/output buffers are safe.
It reuses the existing conversion buffer to stage fallback output. The raw tail
tracks input even while enhancement succeeds; failed or late native output is
never used to fill it. Inference is not retried after fallback.

Explicit capture stop still discards the final **256 pending samples / 16 ms**
whenever alignment was introduced, whether enhancement is active or raw fallback
is retaining that delay. There is no pending alignment tail for startup raw or
the original `off` path. `close()` releases the engine once, clears all adapter
buffers even if release throws, and produces no PCM; subsequent `process()` is
rejected. No silence, `flush()` output or saved audio is sent after explicit stop.
Steady-state native/JNI allocations still exist inside sherpa's `run()` API;
CueBell preallocates its PCM, normalization, conversion and network buffers.

No JavaScript per-frame audio, Android noise suppressor, AGC, VAD gate, resampling,
or near-speaker isolation is introduced. The microphone remains
`VOICE_RECOGNITION`. The raw `off` path does not construct or load the engine.

Android performance must be measured on Android; desktop real-time factors are
not acceptance evidence. The 16 ms alignment is source/model-derived and checked
against first-frame shape during preload; it is not an Android wall-clock result.

## Pinned artifacts

- sherpa-onnx 2.0.1, Apache-2.0, static ONNX Runtime AAR: **38,577,050 bytes**.
  SHA-256 `07e042d97f3a6bd5b7fe74d4eef0513dc01a714b16c15a903250095aba43a575`.
  https://github.com/k2-fsa/sherpa-onnx/releases/download/v2.0.1/sherpa-onnx-static-link-onnxruntime-2.0.1.aar
- GTCRN `gtcrn_simple.onnx`, MIT (Rong Xiaobin): **535,638 bytes**.
  SHA-256 `e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534`.
  https://github.com/k2-fsa/sherpa-onnx/releases/download/speech-enhancement-models/gtcrn_simple.onnx
  The model's embedded metadata names its upstream model:
  https://github.com/Xiaobin-Rong/gtcrn/blob/main/stream/onnx_models/gtcrn_simple.onnx
- The arm64 library statically includes ONNX Runtime **1.28.2**, MIT.
  https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v2.0.1/cmake/onnxruntime-android-aarch64-static.cmake

Gradle's `prepareSherpaOnnx` downloads the AAR into the Gradle user cache, checks
its SHA-256, then extracts only `classes.jar` and `jni/**/*.so` into this module's
build directory. There are no checked-in native binaries or edits to generated
`mobile/android`. The model and license notices are packaged as Android assets.
`verifyGtcrnModel` checks the bundled model at build time; the adapter checks again
before loading. Offline builds can seed
`/home/mathew/.gradle/caches/cuebell-denoising/sherpa-onnx-static-link-onnxruntime-2.0.1.aar`
(or the corresponding Gradle user-home cache on another machine).

Uncompressed AAR payload: Kotlin `classes.jar` **245,045 B**; arm64-v8a JNI
**24,177,488 B**; armeabi-v7a JNI **16,498,184 B**; x86_64 JNI **27,371,968 B**;
x86 JNI **5,414,252 B** plus shared ONNX Runtime **26,491,148 B**. ABI filtering
belongs to the app build. Arm64's compressed AAR JNI entry is **8,961,888 B**;
actual APK growth must be measured in the final build.
Arm64 ELF load segments have 16 KiB alignment (`0x4000`).

### Explicit FFT experiment

The pinned official online frontend uses a quadratic DFT. An opt-in, same-model
arm64 build replaces it with a preallocated double-precision radix-2 FFT; see
`android/native/sherpa-fft/README.md`, the auditable `upstream.patch` and
`artifact-lock.json`. Gradle requires `-PcuebellSherpaFftDir=/absolute/path/to/dist`
and verifies the reviewed binary plus source/provenance hashes. Normal builds
continue to use the official AAR. Every build packages
`noise-reduction/runtime-provenance.json`; the modified build is explicitly marked
unofficial and names the patched ABI. No runtime mode or Kotlin contract changes.

Bundled license sources (the local copies ship as assets):
https://raw.githubusercontent.com/Xiaobin-Rong/gtcrn/main/LICENSE
https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v2.0.1/LICENSE
https://raw.githubusercontent.com/microsoft/onnxruntime/v1.28.2/LICENSE
https://raw.githubusercontent.com/microsoft/onnxruntime/v1.28.2/ThirdPartyNotices.txt

Inspected API and streaming implementation:
https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v2.0.1/sherpa-onnx/kotlin-api/OnlineSpeechDenoiser.kt
https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v2.0.1/sherpa-onnx/csrc/online-speech-denoiser-stft-impl.h

## Verification

Module checks (working directory `/home/mathew/Arrakis/CueBell/mobile/android`):

```sh
./gradlew :queue-listener:testDebugUnitTest --console=plain --max-workers=2
```

Passed: **33 JVM tests**, including **17 streaming-policy tests**, with the locked
FFT artifact selected. Log:
/tmp/opencode/cuebell-denoising/processing-debt-jvm.log

The checks cover
ordered state/framing, exact raw PCM with silence/extremes,
missing/corrupt models before JNI, and numbered-sample continuity through short
or oversized results, NaN/infinities, JVM/native-linkage errors and cumulative
processing-debt fallback. Startup and midstream failures are checked with separate
and aliased buffers. Reset, no replay at close, use-after-close rejection and
idempotent/error-safe release are covered. Successful enhanced output is also
checked against a non-identity engine to verify that fallback uses original raw
history and rejects debt-limit-exceeding enhanced candidates. Debt tests cover
observed transient overruns and recovery, sustained overload, exact boundaries,
no advance credit, initialization exclusion, error precedence, snapshots/reset
and overflow protection.
Previous library packaging checks
inspected model, notices, Kotlin dependency classes and all four JNI ABIs.

Mobile checks (working directory `/home/mathew/Arrakis/CueBell/mobile`):

```sh
npm run lint
npm run typecheck
npm run check:service
```

These passed. The integration report above records the completed short device
experiments and failed foreground processing gates. Long-session thermals, battery
cost, actual release-microphone timing and paired recognition remain unproven;
passing module checks does not establish those outcomes.
