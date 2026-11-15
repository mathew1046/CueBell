# Contributing to CueBell

Help improve access to spoken announcements through focused fixes, tests,
documentation and accessibility feedback.

## Before you start

- Read the [documentation index](docs/README.md) and [architecture](docs/ARCHITECTURE.md).
- Search [existing issues](https://github.com/mathew1046/CueBell/issues). Discuss large changes before implementation.
- No project license has been selected. Ask the maintainer about contribution and reuse terms before substantial work.
- For mobile changes, follow [mobile/AGENTS.md](mobile/AGENTS.md) and the matching Expo SDK documentation. Keep native changes in the local module or config plugins, not generated Android/iOS directories.

## Local checks

Use Python 3.12+, Node 24.3+ and npm. Android builds also need Java 17 and an
Expo SDK 58-compatible Android SDK/NDK. Expo Go cannot load the native service.

From the repository root:

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
.venv/bin/python -m ruff format --check app tests
```

In a separate terminal, from the repository root:

```sh
cd mobile
npm ci
npm test
npm run typecheck
npm run lint
npx playwright install --with-deps chromium
EXPO_PUBLIC_API_URL=https://cuebell.mathewjoseph.xyz npm run test:web
```

These checks use mocked provider output, not live recognition. Browser tests use
a synthetic microphone and mock relay. GitHub Actions runs these backend, mobile
and browser checks; native JUnit, APK and physical-device checks are separate.
See [Android development](mobile/README.md), [web development](docs/WEB.md) and
the [verification record](docs/VERIFICATION.md) for scope and known limits.

## Pull request checklist

- Explain the user problem, keep the diff focused and add regression tests for behavior changes.
- Report commands run, failures and untested behavior. Do not present mock, emulator or replay results as real-venue reliability.
- Preserve consent, visible start/stop controls, source validation, coverage-gap warnings and server-only provider credentials.
- Check large text, contrast, screen-reader labels and both themes for UI changes. Test denied permissions, interruption and stop/restart for lifecycle changes.
- Keep generated native directories, APKs, signing keys, `.env` files and credentials out of commits.
- Use synthetic identifiers and consenting speakers. Redact screenshots/logs; do not upload patient details, bearer tokens or unconsented venue audio.

Report security issues [privately](SECURITY.md), not in public issues.
