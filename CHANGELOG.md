# Changelog

Changes to downloadable Android previews are recorded here. Release assets and
checksums are authoritative for each published build; historical APKs are not renamed.

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
