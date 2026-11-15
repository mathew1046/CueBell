# Browser development and deployment

The web app shares Android screens, task setup, 21 UI languages, captions,
history, alert acknowledgment, themes and accessible controls. It uses the same
Gnani Prisma relay and OpenAI text interpretation, with provider keys on the server.

**Keep the page visible while listening.** Hiding it stops capture and requires
an explicit restart. Installing CueBell does not add Android's foreground service
or lock-screen capture. Browser/OS audio, vibration and notification support varies.

See [architecture](ARCHITECTURE.md), [privacy](PRIVACY.md) and the
[documentation index](README.md).

## Build and preview

Use Node 24.3+ and npm. From `mobile/`:

```sh
npm ci
EXPO_PUBLIC_API_URL=https://your-relay.example.com npm run build:web
npm run preview:web
```

Open `http://127.0.0.1:4173`. Loopback is a secure context for microphone access.
The relay must allow that exact origin in `WEB_ORIGINS`. Public deployments require
HTTPS/WSS. `EXPO_PUBLIC_API_URL` is a build-time public origin, without a trailing
path or credentials. Never put secrets in public build variables.

### Run both services locally

First install the [backend](../backend/README.md#install-and-test) and configure
provider credentials in ignored `backend/.env`. Speech/text processing still
uses those providers and may incur charges. The current client needs explicit
anonymous admission. From `backend/`:

```sh
ALLOW_APP_SESSIONS=true ALLOW_INSECURE_LOCAL=true \
  WEB_ORIGINS='["http://127.0.0.1:4173","http://localhost:4173"]' \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 8192 --no-access-log
```

In another terminal, from `mobile/`:

```sh
npm ci
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 EXPO_PUBLIC_ALLOW_INSECURE_LOCAL=true npm run build:web
npm run preview:web
```

Open `http://127.0.0.1:4173`. The client HTTP/WS exception accepts only loopback
hosts (`localhost`, `127.0.0.1`, `[::1]`) with the explicit build-time opt-in.
Remove that opt-in and rebuild for public HTTPS hosting. Do not enable the
backend's insecure-local setting on a public deployment.

## Deploy

1. Deploy the matching backend with one worker/instance, TLS and admission safeguards. Configure `WEB_ORIGINS` as a JSON array, for example `WEB_ORIGINS=["https://app.example.com"]`, then restart the relay. Origins must be exact, without paths or wildcards; unlisted preview URLs are rejected.
2. On the static host, use project root `mobile`, install command `npm ci`, build command `npm run build:web` and output `dist`. Set `EXPO_PUBLIC_API_URL` to the relay HTTPS origin before building.
3. Publish all of `mobile/dist` at `/`. Preserve route HTML, fonts, `_expo`, icons, `audio`, manifest and `sw.js`. Serve clean routes such as `/settings` from their exported `settings.html` files.
4. Serve `.js`/`.mjs` as JavaScript, `.wasm` as `application/wasm`, and the manifest as `application/manifest+json`. Revalidate `sw.js`. Apply the supplied `_headers` rules or equivalent security headers, allowing same-origin microphone and screen wake lock.
5. On the deployed origin, verify consent, microphone permission, typed/spoken setup, captions, a known alert and Stop. Test installation where offered, including notification permission and the hidden-page stop behavior.

The service worker handles notification clicks, not offline listening. It does
not cache API responses, audio, credentials or transcripts. Backend session,
admission and provider limits still apply. See [backend hosting](../backend/README.md#host-behind-tls).

## Browser capabilities and limits

| Feature | Browser behavior |
| --- | --- |
| Setup and matching | Typed/spoken requests, automatic task activation, source validation, corrections and duplicate suppression through the shared relay. |
| Audio | One microphone stream; AudioWorklet conversion to 16 kHz mono PCM16LE in 1024-byte frames. Waveform shows local RMS activity, not recognition confidence. |
| Captions/history | Finalized segments and selectable in-session history; automatic scroll respects review. |
| Controls/recovery | Manual and interpreted voice stop release capture. Bounded reconnect shows gaps and discards stale audio. Voice stop is not an offline guarantee. |
| Alerts | Full-screen/inline visual alerts and three sound pulses after a listening action unlocks Web Audio, when sound is requested. |
| Vibration | Only when requested and `navigator.vibrate` is supported; unavailable in many browsers, including iOS Safari. |
| Spoken alerts | Optional locally installed browser voices; language availability varies by device. |
| Notifications | Explicit permission and browser/OS support required; some mobile browsers require installation. Not a background microphone service. |
| Accessibility | Keyboard controls, semantic labels, live state announcements, reduced motion and system color preferences. Requires device/user review. |
| Storage | Preferences in local storage, expiring bearer in tab-scoped session storage, audio/transcript history in memory. If storage is blocked/full, page-memory fallback is lost on reload. |
| Screen/background | Hidden page stops listening. A supported wake lock may keep a visible screen awake but does not enable hidden-page capture. |

The 21 bundled UI languages are not a claim of 21-language speech recognition.
Translations need native-speaker review; Prisma's supported speech languages are
a separate limit. Use the official announcement source as the authority.

Browser WebSockets check the configured Origin, then authenticate in a bounded
first message. Bearers never appear in URLs. Android retains header authentication
and the same PCM protocol.

## Experimental noise reduction

Off by default. Enable it before capture; the saved setting is locked while
listening and applies to spoken setup and monitoring. GTCRN runs locally in a
WebAssembly worker using pinned ONNX Runtime Web 1.31.1. `prepare:web-audio` runs
for start, web and export, copying the checksum-verified model and runtime to
ignored `public/audio/vendor`. Publish them with `dist`, including license notices.
The single-threaded worker does not require cross-origin isolation headers.

The model adds 256 samples / 16 ms of causal delay; relay frames remain 512 samples /
32 ms. A bounded queue and original 32 ms packet deadlines prevent growing backlog.
Initialization, crashes or missed deadlines trigger raw-audio fallback with a
visible warning. Stop, reconnect and page hiding clear the worker state. Cold
model download/compilation is separate from steady-state latency. Turn it off for
the lowest capture latency. See [noise reduction and recognition trade-offs](NOISE_REDUCTION.md).

## Verify changes

From `mobile/`:

```sh
npm test
npm run typecheck
npm run lint
npx playwright install --with-deps chromium
EXPO_PUBLIC_API_URL=https://cuebell.mathewjoseph.xyz npm run test:web
```

The browser suite builds a production export and starts the preview server.
`PORT` changes the shared test/server port from 4173. Outside CI it may reuse an
existing preview; stop stale previews when testing a new build. Run backend
checks separately using its [setup guide](../backend/README.md#install-and-test).

Playwright uses Chromium's synthetic microphone and mock relay output. Some tests
exercise the real local GTCRN worker, not paid speech/text providers. These checks
do not establish live recognition accuracy, physical vibration, screen-reader
speech or cross-browser notification delivery. Two browser audio checks have
failed on the current review host; no all-pass browser result is claimed. Record
actual failures and environment details rather than treating every timing failure
as harmless. See [verification](VERIFICATION.md).
