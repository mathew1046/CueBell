# Changelog

Changes to downloadable Android previews are recorded here. Release assets and
checksums are authoritative for each published build; historical APKs are not renamed.

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
