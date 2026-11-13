# Verification record

This is an evidence record, not an accuracy benchmark or a reliability guarantee.
Results are grouped by preview version; historical checks are labelled separately.

## 1.3.1-preview — 2026-11-14

### Automated checks

| Check | Result and scope |
| --- | --- |
| Backend | The included latency implementation passed 410 tests; lint and formatting passed. GitHub Actions also passed for implementation commit `09b7cf19ddecd4b6df2dab05ff35ee1be624aae0`. |
| Mobile | 43 tests passed with version 1.3.1 / code 6, including metadata consistency. TypeScript, lint and build-time service-origin validation passed. |
| Native Android | 14 JUnit tests passed, with no failures, errors or skips. ARM64 release compilation succeeded. |
| Expo Doctor | 19 of 20 checks passed. The dependency-version check recommends seven newer SDK 58 patch releases; the tested dependency versions are retained. |

The patch-version notice lists Expo 58.0.23 (recommended 58.0.25), Constants
58.0.15 (58.0.16), Font 58.0.11 (58.0.12), Linking 58.0.16 (58.0.17), Router
58.0.30 (58.0.31), SecureStore 58.0.2 (58.0.3) and StatusBar 58.0.4 (58.0.5).
Existing Node module-type and Starlette/httpx deprecation warnings are recorded
in the corresponding test output.

### Real-provider replay evidence

- 24 ElevenLabs fixtures in six languages; 22 experiment runs and 174 case attempts
  using real Gnani Prisma and GPT-6 Luna through a local backend.
- Fast/speech-aware spoken setup: six of six trials passed, median confirmation
  6.21 seconds; baseline six of six passed, median 10.75 seconds.
- Full monitoring: baseline 23 passed / 1 failed / 4 inconclusive; candidate
  22 / 2 / 4 after uniform label review. The target-and-counter quality gate was
  not met, so experimental latency controls remain opt-in.
- These are synthetic backend replays, not physical-phone microphone,
  notification, battery or real-venue accuracy measurements.

Results, failed cases, provider errors and reproducible evidence:
https://github.com/mathew1046/CueBell/blob/v1.3.1-preview/docs/LATENCY_BENCHMARK_2026-11-13.md

Implementation CI:
https://github.com/mathew1046/CueBell/actions/runs/43481314804

### Release artifact

- Package `app.cuebell.mobile`, version 1.3.1, Android version code 6;
  ARM64 only, minimum SDK 24, target SDK 36, compile SDK 37.
- APK signature and 16 KB ZIP alignment passed. The non-debuggable APK uses the
  same development signing certificate as 1.3.0 for in-place updates.
- Verified the compiled service origin, native microphone service and
  cleartext-traffic rejection. The bundled alarm bytes match the original.
- No environment/keystore files or configured private backend values were found
  in the APK; this is a targeted packaging check, not a comprehensive audit.
- APK size: 16,002,893 bytes. SHA-256:
  `cd76b8d6ef7c70069c59b167aa73ca9dd0c42bdb4908f52f8c3ea6c3cf321505`.

Release artifact and checksum:
https://github.com/mathew1046/CueBell/releases/tag/v1.3.1-preview

## 1.3.0-preview — 2026-11-08

### Automated checks

| Check | Result and scope |
| --- | --- |
| Backend | 280 tests passed, including general-task schemas, grounded matching, corrections, session admission and voice-stop routing. Ruff lint and formatting passed. The admission suite also passed after making its exact rate-limit boundary clock deterministic. |
| Mobile | 43 tests passed, including automatic activation/cancellation, general-task UI, 21 language catalogs, native alert configuration, sessions and stop recovery. TypeScript and lint passed. |
| Native Android | 14 JUnit tests passed: PCM framing, waveform levels, WebSocket rejection, bounded speech queuing and foreground-request handoff. |
| Toolchain | All 20 Expo Doctor checks passed. ARM64 release compilation succeeded. |

### Release artifact and service smoke checks

- Package `app.cuebell.mobile`, version 1.3.0, Android version code 5;
  ARM64 only, Android 7+ (minimum SDK 24), target SDK 36.
- Non-debuggable APK with a development signing certificate matching 1.2.0.
  APK signature verification and 16 KB ZIP alignment passed.
- Verified the hosted origin in the compiled bundle, native microphone service
  and permissions, and the named alarm resource with the original 2.4-second audio.
- No previous origin, environment/keystore files or configured private environment
  values were found in the APK. This is not a comprehensive security audit.
- Service health reported both providers configured. Temporary anonymous admission
  returned `monitoring_schema: speech-event-v1`; authenticated state and session
  deletion returned HTTP 200. No microphone or paid-model request was made.
- APK size: 16,002,897 bytes. SHA-256:
  `960a706317959c0023e0d279635acf4cbe00910c14af60157a85bd5cf4f35e3b`.

Release artifact and checksum:
https://github.com/mathew1046/CueBell/releases/tag/v1.3.0-preview

These checks do not establish real-phone speech, vibration, alarm audibility or
locked-screen reliability. No device microphone capture was performed for this release.

## 1.2.0-preview — 2026-11-07

### Automated checks

| Check | Result and scope |
| --- | --- |
| Backend | 253 tests passed: schema/source evidence, confirmation, correction/repeat aliases, acknowledgment, stale results, coverage gaps, cleanup, authorization, automatic session admission and voice-stop routing. Ruff lint and formatting passed. |
| Mobile | 28 tests passed: session reuse/expiry/revocation, consent, configuration, branding and stop/storage/remote-cleanup recovery. TypeScript and lint passed. |
| Native Android | 12 JUnit tests passed: PCM16 framing, waveform boundaries, permanent/retryable WebSocket rejection and bounded initialization-time speech queuing. |
| Toolchain | All 20 Expo Doctor checks passed. ARM64 release compilation succeeded. |

Multilingual voice-stop tests mock model decisions and validate source grounding,
priority, pause state and cleanup. They do **not** measure live recognition or
semantic accuracy in those languages.

### Release artifact and service smoke checks

- Package `app.cuebell.mobile`, version 1.2.0, Android version code 4; ARM64 only.
- Release APK is non-debuggable but uses a **development signing certificate**.
  Its certificate matches the 1.1.0 preview for in-place updates.
- Verified the configured origin in the compiled bundle, absence of the previous
  origin, native listener/pause handler, APK signature and 16 KB ZIP alignment.
- No environment/keystore files or configured private environment values were
  found in the APK. This is not a comprehensive security audit.
- Uploaded assets were downloaded again and checked against the SHA-256 file.
  The public APK download returned HTTP 200 with matching bytes/checksum.
- Service health reported both providers configured. Automatic session admission,
  authenticated state and deletion of the temporary session returned HTTP 200.
  No microphone capture or paid-model request was made for this check.

Published artifact and checksum:
https://github.com/mathew1046/CueBell/releases/tag/v1.2.0-preview

## Historical checks — not new-release device verification

- Earlier minimal-interface review launched on an Android 16 emulator and
  inspected light/dark themes and enlarged text.
- Version 1.1.0 installed on a physical phone, and its cold-launch request returned
  `Status: ok`. The phone was asleep, so no fresh visible-screen check or unlock
  was attempted. No phone microphone capture was started.
- Earlier hosted typed-intent checks returned expected token/preferences.
- Staged English/Malayalam text-model checks covered intent, calls, negation,
  injection abstention, corrections, HTTP lifecycle and leading zeroes using
  the account-enabled `gpt-6-luna` model.
- Gnani authentication/stream negotiation succeeded at 16 kHz / 512 samples.
  Forty-eight paced synthetic tone/silence frames produced no reported provider
  error. This was **not spoken-audio recognition testing**.

## Not established

- Real PA speech accuracy, false-alert/missed-call rates and end-to-end latency.
- Real-venue voice-stop accuracy, locked-screen delivery and sustained
  physical-phone microphone behavior of the current APK.
- TalkBack usability, alert vibration/sound, OEM battery management and endurance.
- Fewer missed turns, reduced waiting time or successful venue deployments.

Automated tests, emulator captures and an accepted socket connection do not
establish real-world reliability. Use consenting speakers or staged recordings,
and follow the device checklist before a supervised demonstration:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md
