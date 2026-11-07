# Verification record

This is an evidence record, not an accuracy benchmark or a reliability guarantee.
Results below refer to the 1.2.0 preview unless explicitly marked historical.

## Automated checks

| Check | Result and scope |
| --- | --- |
| Backend | 253 tests passed: schema/source evidence, confirmation, correction/repeat aliases, acknowledgment, stale results, coverage gaps, cleanup, authorization, automatic session admission and voice-stop routing. Ruff lint and formatting passed. |
| Mobile | 28 tests passed: session reuse/expiry/revocation, consent, configuration, branding and stop/storage/remote-cleanup recovery. TypeScript and lint passed. |
| Native Android | 12 JUnit tests passed: PCM16 framing, waveform boundaries, permanent/retryable WebSocket rejection and bounded initialization-time speech queuing. |
| Toolchain | All 20 Expo Doctor checks passed. ARM64 release compilation succeeded. |

Multilingual voice-stop tests mock model decisions and validate source grounding,
priority, pause state and cleanup. They do **not** measure live recognition or
semantic accuracy in those languages.

## Release artifact and service smoke checks

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
- Live voice-stop accuracy, locked-screen delivery and physical-phone behavior of
  the 1.2.0 APK.
- TalkBack usability, alert vibration/sound, OEM battery management and endurance.
- Fewer missed turns, reduced waiting time or successful venue deployments.

Automated tests, emulator captures and an accepted socket connection do not
establish real-world reliability. Use consenting speakers or staged recordings,
and follow the device checklist before a supervised demonstration:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md
