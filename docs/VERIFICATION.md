# Verification record

This is an evidence record, not an accuracy benchmark or reliability guarantee.
Historical release checks below are not fresh results for the current checkout.
Use the [documentation index](README.md) for study reports and
[Android](../mobile/README.md) / [browser](WEB.md) guides for repeatable checks.

## How to read the evidence

| Check | What it can establish | What it cannot establish |
| --- | --- | --- |
| Backend/mobile unit tests | Logic against controlled inputs and mocked provider decisions. | Live speech/model accuracy. |
| Browser tests | UI, synthetic microphone framing, mock relay handling; some real local GTCRN worker checks. | Real microphone acoustics, all browsers, physical vibration or screen-reader speech. |
| Provider connection/health | Configuration presence or successful authentication/negotiation, depending on the check. | Recognition quality or a complete alert. |
| Real-provider audio replay | Behavior on the stated recordings and labels through actual providers. | General accuracy, live venue performance or phone microphone reliability. |
| APK build/signature | Packaging, compilation and stated artifact properties. | Physical-device lifecycle, audibility or usability. |

**Browser review status:** two repeatable browser audio checks failed on the
current review host. This record does not claim that the browser suite passes
in full. Review timing, fallback and environment evidence before release; do not
substitute unit-test success for a passing browser audio check.

## Documentation review | 15 November 2026

The documentation refactor was checked against application source at `af0173d` and the saved benchmark artifacts. Only Markdown changed; raw benchmark data, source snapshots, models, application code and historical release files were left intact.

- Backend: **508 tests passed**, one optional module skipped; Ruff lint and formatting passed.
- Client: **81 unit tests passed**; TypeScript and lint passed.
- Headline setup, enhancement availability, background-quality and word-error figures were recalculated from saved JSON/JSONL evidence. This did not make new paid-provider calls or rerun phone benchmarks.
- Local documentation links and heading anchors were checked. Release-specific checks below remain historical.

## 1.4.0-preview | 14 November 2026

### Recorded checks

| Check | Historical result |
| --- | --- |
| Backend | 487 tests passed; one optional numerical-module test module skipped. Ruff lint and formatting passed. |
| Mobile | 49 tests passed, including version 1.4.0 / code 7 metadata. TypeScript, lint and service-origin validation passed. |
| Android | 33 JUnit tests passed, with no failures/errors/skips. ARM64 release build succeeded with the pinned FFT runtime. |
| DNSMOS tooling | 25 numerical tests passed separately in the pinned scoring environment. |
| Targeted source review | Whitespace checks passed, with original upstream/evidence whitespace retained. A scan of 500 staged text files found no configured private backend values; this was not a comprehensive audit. |

All 16 selected DNS5 clips and five complete station-PA recordings completed
phone replay with the bounded-debt FFT implementation. All 5,883 station processing
frames were enhanced without fallback, retaining the 16 ms causal delay. These
were replay checks, not live-microphone or long-session measurements. Estimated
background quality improved, but actual Gnani and GPT-6 Luna checks found
recognition regressions. Noise reduction remains experimental and off by default.

Source reports:
[station PA](https://github.com/mathew1046/CueBell/blob/v1.4.0-preview/docs/STATION_PA_DENOISING_2026-11-14.md),
[recorded noise](https://github.com/mathew1046/CueBell/blob/v1.4.0-preview/docs/REAL_NOISE_DENOISING_2026-11-14.md).
See also [noise reduction](NOISE_REDUCTION.md).

### Published artifact

[Release and checksum](https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview).
Package `app.cuebell.mobile`, version 1.4.0 / code 7, ARM64 only. The APK was
non-debuggable, with a development certificate matching 1.3.1 for in-place updates.
Signature and 16 KB ZIP alignment checks passed. Compiled origin, microphone
foreground service, cleartext rejection and unchanged alarm bytes were checked.
No configured private backend values, environment files or keystores were found
in the APK by targeted packaging checks, not an independent audit.

| Artifact | Recorded SHA-256 |
| --- | --- |
| APK, 25,167,101 bytes | `99c6700e865951a20f250bea49fb8e3b5a072814c336d8b3e7563bb2f6c192e9` |
| FFT JNI | `59964bf7d9cf9520231d6cce3f6728b05f3c0ecac765bd9182bd9fc9d0539c65` |
| GTCRN model | `e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534` |

## 1.3.1-preview | 14 November 2026

- Backend: 410 tests, lint and formatting passed. [Implementation CI](https://github.com/mathew1046/CueBell/actions/runs/43481314804) passed for `09b7cf19ddecd4b6df2dab05ff35ee1be624aae0`.
- Mobile: 43 tests, TypeScript, lint and service-origin checks passed, including version 1.3.1 / code 6 metadata.
- Android: 14 JUnit tests passed with no failures/errors/skips; ARM64 release compiled.
- Expo Doctor: 19/20 checks passed. The remaining check recommended seven newer SDK 58 package patches; tested versions were retained. Node module-type and Starlette/httpx deprecation warnings were recorded in test output.

Real-provider replay used 24 ElevenLabs fixtures in six languages, 22 runs and
174 case attempts through local Gnani Prisma and GPT-6 Luna. Fast/speech-aware
setup passed 6/6, median 6.21 s; baseline passed 6/6, median 10.75 s. Monitoring
baseline was 23 passed / 1 failed / 4 inconclusive; candidate was 22 / 2 / 4 after
uniform label review. The target-and-counter quality gate failed, so latency
settings remain opt-in. These synthetic replays do not measure physical-phone
microphones, battery, notifications or real-venue accuracy.

[Full latency evidence](https://github.com/mathew1046/CueBell/blob/v1.3.1-preview/docs/LATENCY_BENCHMARK_2026-11-13.md)
and [pipeline optimization](PIPELINE_OPTIMIZATION.md).

[Published release](https://github.com/mathew1046/CueBell/releases/tag/v1.3.1-preview):
`app.cuebell.mobile`, version 1.3.1 / code 6, ARM64, minimum SDK 24, target 36,
compile 37. Non-debuggable APK, development certificate matching 1.3.0; signature,
16 KB alignment, origin, service, cleartext rejection and original alarm checked.
Targeted scans found no configured private values or environment/keystore files.
APK: 16,002,893 bytes; SHA-256:
`cd76b8d6ef7c70069c59b167aa73ca9dd0c42bdb4908f52f8c3ea6c3cf321505`.

## Earlier previews

| Release | Recorded automated checks | Artifact |
| --- | --- | --- |
| [1.3.0, 8 November 2026](https://github.com/mathew1046/CueBell/releases/tag/v1.3.0-preview) | Backend 280, mobile 43, Android JUnit 14 passed; lint/types passed; Expo Doctor 20/20; ARM64 compiled. | Version code 5, ARM64, minimum SDK 24, target 36. Non-debuggable, development certificate matching 1.2.0. Signature, 16 KB alignment, origin, permissions, foreground service and original 2.4-second alarm checked. |
| [1.2.0, 7 November 2026](https://github.com/mathew1046/CueBell/releases/tag/v1.2.0-preview) | Backend 253, mobile 28, Android JUnit 12 passed; lint/types passed; Expo Doctor 20/20; ARM64 compiled. | Version code 4, ARM64. Non-debuggable, development certificate matching 1.1.0. Signature, 16 KB alignment, origin, listener/pause handler and downloaded checksum checked. |

Both releases had targeted packaging scans with no configured private values or
environment/keystore files found. Hosted health, anonymous admission, authenticated
state and temporary-session deletion succeeded. These smoke checks made no
microphone capture or paid-model request; health flags meant configured, not
provider-validated. Version 1.3.0 advertised `speech-event-v1`.

The 1.3.0 APK was 16,002,897 bytes, SHA-256:
`960a706317959c0023e0d279635acf4cbe00910c14af60157a85bd5cf4f35e3b`.
Multilingual voice-stop unit tests injected model decisions and checked grounding,
priority, state and cleanup, not live semantic accuracy.

### Older checks, not current-device verification

- An Android 16 emulator review inspected light/dark themes and enlarged text.
- Version 1.1.0 installed on a phone and cold launch returned `Status: ok`. The phone was asleep; no unlock, visible-screen review or microphone capture was performed.
- Hosted typed-intent probes and staged English/Malayalam text checks covered intent, calls, negation, injection abstention, corrections, lifecycle and leading zeroes using `gpt-6-luna`.
- Gnani authentication and negotiation succeeded at 16 kHz / 512 samples. Forty-eight paced tone/silence frames reported no provider error. This was not spoken-audio recognition testing.

## Still not established

- General real-venue accuracy, false/missed-alert rates or end-to-end latency.
- Current-APK sustained microphone capture, real-venue voice stop and locked-screen delivery.
- TalkBack usability, physical vibration/alarm audibility, OEM battery behavior and endurance.
- Fewer missed turns, shorter waits or successful venue deployments.

Use consenting speakers or staged recordings and the [device checklist](../mobile/README.md#physical-device-checklist)
before a supervised demonstration. Tests, emulator views and accepted sockets do
not establish real-world reliability.
