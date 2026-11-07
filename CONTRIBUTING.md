# Contributing to CueBell

Thank you for helping make audio-only queue announcements more accessible.
Useful contributions include reproducible bug reports, accessibility feedback,
documentation, tests and small, focused fixes.

## Before starting

- Search existing issues and open one before a large feature or architecture change.
- Read the product scope and repository instructions, including `mobile/AGENTS.md`
  for mobile work. Check the matching Expo SDK docs before changing native APIs.
- No project license has been selected. Clarify contribution/reuse terms with the
  maintainer before substantial work; do not assume an open-source license.
- Keep claims proportionate to evidence. A mocked test is not a live-language or
  accessibility-usability result.

Issues:
https://github.com/mathew1046/CueBell/issues

## Development checks

Use Python 3.12+, Node 24.3+ and npm. Java 17 and an SDK-compatible Android toolchain
are needed only for native builds/tests. Expo Go cannot load the native service.

From the repository root, backend checks are:

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/pytest -q
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
```

In a separate terminal, from the repository root:

```sh
cd mobile
npm ci
npm test
npm run typecheck
npm run lint
```

These automated checks use mocked providers and do not need real API keys or
microphone access. GitHub Actions runs the same backend/mobile checks. Native
JUnit tests, APK builds and physical-device checks are separate; follow:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md

## Pull request checklist

- Explain the user problem and keep the change focused.
- Add regression tests for behavior changes; run the relevant checks above.
- Keep generated `mobile/android/` and `mobile/ios/`, APKs, signing keys, `.env`
  files and provider credentials out of commits.
- Preserve explicit consent, visible start/stop controls, source-evidence checks,
  coverage-gap reporting and the separation between app and backend credentials.
- For interface work, check large text, contrast, screen-reader labels and both
  themes. For lifecycle changes, test denial, interruption and stop/restart.
- Say what was not tested. Never describe emulator-only or mocked checks as
  physical-phone, live-recognition or real-venue verification.

Use synthetic token numbers and consenting speakers. Redact screenshots/logs;
do not upload patient details, bearer tokens or unconsented venue audio.

Security issues must be reported privately:
https://github.com/mathew1046/CueBell/security/advisories/new
