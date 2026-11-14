# Changelog

Changes to downloadable Android previews are recorded here. Release assets and
checksums are authoritative for each published build; historical APKs are not renamed.

## 1.4.0-preview — 2026-11-14

### Added

- Experimental on-device GTCRN noise reduction in Settings → Listening. It is off
  by default, persists across launches, and applies to spoken setup and monitoring.
- ARM64 preview uses the tested, checksum-pinned FFT runtime with the same GTCRN
  model. Processing preserves 16 kHz PCM framing and its 16 ms causal delay.
- Bounded processing-debt fallback, continuous raw-audio handoff, and visible
  fallback status; selection is locked during a listening session.
- Reproducible Android replay, sourced-noise, station-PA, Gnani and GPT-6 Luna
  benchmark tools, observations, and before/after evidence.

### Evaluation

- All five actual station recordings were fully enhanced on the phone without
  fallback. Estimated background quality improved, but recognition of a platform
  and service time regressed reproducibly. This preview exposes the experimental
  feature for hands-on testing; it is not an accuracy-qualified default.
- Stop listening before changing the Noise reduction setting.

### Distribution

- Android version 1.4.0 / version code 7; ARM64, development-signed preview.
- Uses the same signing identity and configured backend as 1.3.1.

Release notes, APK and checksum:
https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview

## 1.3.1-preview — 2026-11-14

### Added

- Opt-in backend controls for correction-aware alert scheduling, ordered outbound
  delivery, OpenAI reasoning/service tier/prompt options and Gnani endpointing.
- Speech-aware spoken-request completion that tracks outstanding utterances before
  applying a shorter quiet period, available as an opt-in server setting.
- A reproducible real-provider benchmark: 24 ElevenLabs fixtures in six languages,
  22 experiment runs and 174 case attempts, with frozen sources, traces and results.

### Fixed

- Stream teardown invalidates pending interpretations and cancels workers before
  provider shutdown, preventing a delayed alert during failed-stream cleanup.

### Evaluation

- The tested Fast/speech-aware setup profile reduced median confirmation time from
  10.75 to 6.21 seconds, with six successful trials in each arm.
- Full monitoring validation did not meet the target-and-counter accuracy gate:
  baseline 23 passed / 1 failed / 4 inconclusive; candidate 22 / 2 / 4. Experimental
  latency settings therefore remain opt-in with baseline defaults retained.
- Measurements use paced synthetic audio through real Gnani and GPT-6 Luna APIs;
  they are not physical-microphone, real-venue or notification-latency measurements.

### Distribution

- Android version 1.3.1 / version code 6; ARM64, development-signed preview.
- Preconfigured for https://cuebell.mathewjoseph.xyz with `speech-event-v1` support.

Benchmark report:
https://github.com/mathew1046/CueBell/blob/main/docs/LATENCY_BENCHMARK_2026-11-13.md

Release notes, APK and checksum:
https://github.com/mathew1046/CueBell/releases/tag/v1.3.1-preview

## 1.3.0-preview — 2026-11-08

### Added

- General listening tasks for spoken events such as train arrivals, names being
  called, boarding and queue calls. Alerts show the event, location when heard
  and verbatim source speech.
- Bundled interface translations for English and 20 Indian languages, a language
  dropdown and localized native notifications.
- An original three-pulse alarm for sound-enabled alerts, preserving silent and
  vibration-only preferences.
- A short, plain-English solution pitch at the top of the project README.

### Changed

- Valid spoken or typed requests start monitoring automatically after consent and
  Android permission checks; no second confirmation tap is required.
- The existing foreground service stays alive during spoken-request interpretation
  with its microphone off, allowing the pending task to continue in the background.
  Fresh microphone starts still require the app to be visible.

### Fixed

- Stop/cancel during task activation prevents a late microphone restart.
- Stabilized the rate-limit boundary test and kept operational service names out
  of the application-branding check.

### Distribution

- Android version 1.3.0 / version code 5; ARM64, development-signed.
- Signing certificate matches 1.2.0 for in-place updates.
- Preconfigured for https://cuebell.mathewjoseph.xyz with `speech-event-v1` support.
- Internet is required. Real-world speech accuracy and locked-screen alert
  reliability have not been established for this build.

Release notes, APK and checksum:
https://github.com/mathew1046/CueBell/releases/tag/v1.3.0-preview

## 1.2.0-preview — 2026-11-07

### Added

- Inline spoken/typed requests, token confirmation and listening controls.
- Finalized live captions, microphone waveform and optional offline spoken alerts.
- Semantic, source-grounded voice-stop handling with native microphone shutdown
  and explicit restart, preserving the current token/history.

### Fixed

- Local stop no longer depends on restoring a backend connection.
- Storage and remote-cleanup failures are reported independently, with a fallback
  to removing stale saved credentials.
- Distinct spoken alerts queued during speech-engine initialization play in order.

### Distribution

- Updated the preconfigured service routing.
- Android version 1.2.0 / version code 4; ARM64, development-signed.
- Signing certificate matches 1.1.0 for in-place updates. Older-deployment sessions
  are not reused; submit your request again after updating.

Release notes, APK and checksum:
https://github.com/mathew1046/CueBell/releases/tag/v1.2.0-preview

Earlier previews and their original notes:
https://github.com/mathew1046/CueBell/releases
