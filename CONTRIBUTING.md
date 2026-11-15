# Contributing to CueBell

Focused fixes, tests, documentation and accessibility feedback are welcome.

## Start here

Read the [architecture](docs/ARCHITECTURE.md), search [issues](https://github.com/mathew1046/CueBell/issues) and discuss large changes first. No project license is selected; ask about contribution and reuse terms before substantial work.

Follow [mobile/AGENTS.md](mobile/AGENTS.md) and version-matched Expo documentation for mobile work. Put native changes in local modules or config plugins, not generated directories.

## Setup and checks

Use [backend setup](backend/README.md), [Android setup](mobile/README.md) or [web setup](docs/WEB.md). Requirements include Python 3.12+, Node 24.3+ and npm; Android also needs Java 17 and the SDK/NDK compatible with Expo SDK 58. Expo Go cannot load the native service.

With dependencies installed, run from the repository root:

```sh
(cd backend && .venv/bin/python -m pytest -q)
(cd backend && .venv/bin/python -m ruff check app tests)
(cd backend && .venv/bin/python -m ruff format --check app tests)
(cd mobile && npm test && npm run typecheck && npm run lint)
(cd mobile && npx playwright install --with-deps chromium)
(cd mobile && EXPO_PUBLIC_API_URL=https://cuebell.mathewjoseph.xyz npm run test:web)
```

These provider checks are mocked; browser tests use a synthetic microphone and mock relay. Native JUnit, APK and physical-device checks are separate. See [verification](docs/VERIFICATION.md).

## Pull requests

- Explain the user problem. Keep changes focused and add regression tests.
- Report commands, failures and untested behavior. Do not equate mocks or replays with venue reliability.
- Preserve consent, stop controls, source validation, gap warnings and server-only credentials.
- For UI changes, check large text, contrast, screen-reader labels and both themes. For lifecycle changes, test denied permissions, interruptions and stop/restart.
- Exclude generated native directories, APKs, signing keys and credentials. Use synthetic identifiers and consenting speakers; redact logs and screenshots.

Report vulnerabilities [privately](SECURITY.md).
