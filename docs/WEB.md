# Browser development and deployment

The browser shares Android's task screens, 21 UI languages, captions, history,
themes and alert acknowledgment. Gnani Prisma transcribes; OpenAI interprets text.
Provider keys stay on the relay.

**Keep the page visible.** Hiding it stops capture and requires explicit restart.
Installation does not add Android's background service. Sound, vibration,
notifications and installed voices depend on browser/OS support.

## Build and preview

Use Node 24.3+ and npm. From `mobile/`:

```sh
npm ci
EXPO_PUBLIC_API_URL=https://your-relay.example.com npm run build:web
npm run preview:web
```

Open `http://127.0.0.1:4173`, a microphone-compatible loopback secure context.
Allow that exact origin in relay `WEB_ORIGINS`. Public hosting needs HTTPS/WSS.
`EXPO_PUBLIC_API_URL` is a build-time public origin, without path or credentials;
never bundle secrets.

### Run both services locally

Install the [backend](../backend/README.md#install-and-test); configure ignored
`backend/.env` with provider credentials. Processing still uses potentially paid
providers. From `backend/`:

```sh
ALLOW_APP_SESSIONS=true ALLOW_INSECURE_LOCAL=true \
  WEB_ORIGINS='["http://127.0.0.1:4173","http://localhost:4173"]' \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 8192 --no-access-log
```

Separately, from `mobile/`:

```sh
npm ci
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 EXPO_PUBLIC_ALLOW_INSECURE_LOCAL=true npm run build:web
npm run preview:web
```

Open `http://127.0.0.1:4173`. The client HTTP/WS exception permits only `localhost`,
`127.0.0.1`, `[::1]` with explicit build-time opt-in. Remove it and rebuild for
public hosting; never enable backend insecure-local publicly.

## Deploy

1. Host a matching [single-worker relay](../backend/README.md#host-behind-tls) with TLS/admission safeguards. Set exact origin JSON, e.g. `WEB_ORIGINS=["https://app.example.com"]`, then restart. No paths/wildcards; previews need explicit entries.
2. Static host: root `mobile`, install `npm ci`, build `npm run build:web`, output `dist`. Set the relay HTTPS origin before building.
3. Publish all `mobile/dist` at `/`: route HTML, fonts, `_expo`, icons, `audio`, manifest, `sw.js`. Resolve `/settings` to exported `settings.html`.
4. Serve `.js`/`.mjs` as JavaScript, `.wasm` as `application/wasm`, manifest as `application/manifest+json`. Revalidate `sw.js`; apply `_headers` or equivalent security headers permitting same-origin microphone/screen wake lock.
5. Verify consent, permissions, typed/spoken setup, captions, a known alert, **Home → Stop Listening** (pause) and **Settings → Clear task** (reset). Older APKs may say Stop. Check installation/notifications and hidden-page capture stop.

The service worker handles notification clicks, not offline listening. It caches
no API responses, audio, credentials or transcripts. Provider/session limits remain.

## Capabilities and limits

- AudioWorklet converts one microphone stream to 16 kHz mono PCM16LE, 1024 bytes/frame. Waveform RMS shows activity, not recognition confidence.
- Shared relay handles automatic activation, source checks, corrections and duplicate suppression. Captions are final segments; history supports review without forced scrolling.
- Manual/recognized voice stop releases capture. Reconnect is bounded, warns of gaps and discards stale audio. Voice stop is not an offline guarantee.
- Visual alerts accompany three sound pulses when enabled and Web Audio is unlocked by listening. Vibration requires `navigator.vibrate` (unavailable in many browsers, including iOS Safari). Spoken alerts need local voices.
- Notifications need explicit permission/support, sometimes installation. Visible-screen wake lock is not hidden-page capture.
- Keyboard/semantic controls, live announcements, reduced motion and system themes need device/user review.
- Preferences use local storage, bearer uses tab-scoped session storage, history stays in memory. Blocked/full storage falls back to page memory, lost on reload.

UI translations need native-speaker review; 21 UI languages do not mean 21 speech
languages. Official announcements remain authoritative. WebSockets require allowed
Origin and bounded first-message authentication, never tokens in URLs; see the
[protocol](../backend/README.md#client-protocol).

## Experimental noise reduction

Off by default; change only before capture. Local GTCRN runs in a single-threaded
WASM worker using pinned ONNX Runtime Web 1.31.1, without cross-origin isolation.
`prepare:web-audio` runs for start/web/export, copying checksum-verified model/runtime
to ignored `public/audio/vendor`. Publish vendor assets and notices with `dist`.

Alignment delay is 256 samples/16 ms; relay packets remain 512 samples/32 ms.
Bounded queues and original packet deadlines prevent growing backlog. Initialization,
crashes or deadline misses trigger visible raw fallback. Stop/reconnect/hiding clears
state. Cold download/compilation adds separate startup time. For lowest latency,
leave it off. See [recognition trade-offs](NOISE_REDUCTION.md).

## Verify changes

From `mobile/`:

```sh
npm test
npm run typecheck
npm run lint
npx playwright install --with-deps chromium
EXPO_PUBLIC_API_URL=https://cuebell.mathewjoseph.xyz npm run test:web
```

The suite exports production and starts preview; `PORT` overrides 4173. Outside CI,
it can reuse previews: stop stale servers first. Run backend checks separately.
Synthetic Chromium microphone/mock relay tests, including some real local GTCRN,
do not establish live recognition, physical alerts or cross-browser accessibility.
**Two browser audio checks failed on this review host; no local all-pass claim.**
GitHub checks are separate evidence. See [verification](VERIFICATION.md) and
[privacy](PRIVACY.md).
