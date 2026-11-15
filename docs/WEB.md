# CueBell web app

The web app shares the Android screens, task setup, translations, live captions,
history, alert acknowledgment, themes and accessible controls. It connects to the
same relay and Gnani Prisma pipeline. Provider credentials stay on the backend.

## Build and preview

Use Node.js 24 or later. From `mobile`, run the following commands with the public
HTTPS relay origin configured in your environment or an ignored `.env` file.

```sh
npm ci
# Set EXPO_PUBLIC_API_URL=https://your-relay.example.com in your environment.
npm run build:web
npm run preview:web
```

Open http://127.0.0.1:4173. Localhost is a secure context for microphone access.
The public site and relay require HTTPS/WSS. For a local relay, use the explicit
development configuration below. `EXPO_PUBLIC_API_URL` is bundled at build time.
It contains the public service origin, with no trailing path or credentials.

### Run both services locally

Keep provider credentials in `backend/.env`. From `backend`, start the relay:

```sh
ALLOW_APP_SESSIONS=true ALLOW_INSECURE_LOCAL=true \
  WEB_ORIGINS='["http://127.0.0.1:4173","http://localhost:4173"]' \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 8192 --no-access-log
```

In another terminal, from `mobile`:

```sh
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 EXPO_PUBLIC_ALLOW_INSECURE_LOCAL=true npm run build:web
npm run preview:web
```

Open http://127.0.0.1:4173. The local HTTP/WS exception accepts only `localhost`,
`127.0.0.1`, or `[::1]`, and only with the explicit build-time opt-in. For hosting,
remove that opt-in and rebuild with the deployed HTTPS relay origin. Speech and
text processing still use the providers configured in the local backend.

## Deploy

1. Deploy the backend from this branch, retaining its existing provider and session
   configuration. Add each exact web origin to the backend environment as JSON.

   ```dotenv
   WEB_ORIGINS=["https://app.example.com"]
   ```

   Include `http://127.0.0.1:4173` or `http://localhost:8081` only when local access
   is needed. Wildcards, origin paths and unlisted preview URLs are rejected.
   Restart the relay after changing its environment.

2. Configure your static host with project root `mobile`, installation command
   `npm ci`, build command `npm run build:web`, and output directory `dist`.
   Set `EXPO_PUBLIC_API_URL` to the deployed relay's HTTPS origin before building.

3. Publish all of `mobile/dist` at the web origin's root. Preserve generated route
   HTML, fonts, `_expo`, icons, `audio`, the manifest and `sw.js`. The host should
   serve `/settings` from `settings.html`, and similarly for the other routes.
   Expo exports a separate HTML file for each route. Configure clean HTML URLs
   if your host requires it.

4. Serve `.js` and `.mjs` as JavaScript, `.wasm` as `application/wasm`, the manifest as
   `application/manifest+json`, and `sw.js` with revalidation. The supplied
   `_headers` file provides these security headers on hosts supporting that format.
   Apply equivalent headers on other hosts. Allow microphone and screen wake lock
   for the app's own origin. The app assumes deployment at `/`.

5. Verify consent, microphone permission, a spoken or typed task, listening status,
   captions, an alert, and Stop on the deployed origin. Add the app to your home
   screen through the browser menu or the Install CueBell control where offered.

The service worker handles notification clicks. It does not cache API responses,
audio, credentials or transcripts. The app requires an internet connection.
The existing backend admission and provider limits also apply to web clients.

When browser site storage is blocked or full, session credentials and preferences
remain usable in page memory. Reloading the page discards changes that could not
be persisted. Successful storage operations retain the usual tab-scoped bearer
and local preferences.

## Browser behavior

| Feature | Web behavior |
| --- | --- |
| Typed and spoken task setup | Shared Android workflow, including automatic activation |
| Speech and matching | Existing Gnani relay, source validation, corrections and duplicate suppression |
| Microphone and waveform | One browser audio stream, AudioWorklet conversion to 16 kHz mono PCM16LE, 1,024-byte relay frames and local RMS visualization |
| Captions and history | Finalized relay segments, selectable text, reviewable in-session history and automatic scroll that respects review |
| Voice stop and controls | Relay pause/stop decisions release capture; Home and Settings controls remain available |
| Network recovery | Bounded reconnection with visible gaps, retained finalized captions and discarded stale audio |
| Visual alerts | Shared full-screen and inline alerts, including counter details and corrections |
| Vibration | Used when requested and the browser exposes `navigator.vibrate`; unavailable on many browsers, including iOS Safari |
| Alarm sound | Three audible pulses after a user listening action unlocks Web Audio, when sound was requested |
| Spoken alerts | Optional locally installed browser voices for the selected language; voice availability varies by device |
| Experimental GTCRN noise reduction | Opt-in under Settings → Noise reduction; same on-device model as Android, in a dedicated WebAssembly worker |
| System notifications | Optional explicit permission and supported browser/OS notification APIs; mobile browsers may require installation |
| Accessibility | Keyboard controls, semantic labels, live state announcements, text selection, reduced motion and system color preferences |
| Languages | The existing 21 UI languages and added browser guidance are bundled; new translations are machine-generated and need native-speaker review |
| Persistence | Preferences in origin-local storage; expiring bearer in tab-scoped session storage; audio and transcript history in memory |
| Locked screen and background | Listening stops when the page becomes hidden. Return and explicitly start again. A requested screen wake lock may keep the visible screen awake where supported |

Android's foreground microphone service, lock-screen controls and guaranteed
platform APIs cannot run inside a web page. Browser suspension, audio policies,
device settings and notification support constrain delivery. The app explains
the visible-page requirement before listening. Installing it does not grant
Android foreground-service capabilities. Check the official announcement source.

Browser audio authentication uses a bounded first WebSocket message after checking
the configured Origin. The token never appears in a URL or a service worker cache.
Native Android clients retain header authentication and the same audio protocol.

### Low-latency browser denoising

Noise reduction is off by default. Enable it before starting capture; the setting
is retained locally and locked while listening. Both spoken setup and monitoring
use it. The model and pinned ONNX Runtime Web 1.31.1 are served from the app's own
origin. Denoising runs locally; the existing relay receives the processed audio.

`prepare:web-audio` runs automatically for start, web and production export. It
copies the existing checksum-verified Android GTCRN model and installed runtime
into ignored `public/audio/vendor`. Publish these files with the rest of `dist`.
The MIT licenses and ONNX Runtime third-party notices are included under `audio`.
The worker uses one WASM thread; cross-origin isolation headers are not required.

GTCRN retains 256 samples (16 ms at 16 kHz) of algorithmic delay. The existing
512-sample (32 ms) relay packets are unchanged. There is one inference packet in
flight and room for one waiting packet when the browser delivers a burst. Each
packet keeps its original 32 ms arrival-to-output deadline, including waiting;
there is no extra batching delay or growing backlog. The worker warms up before
the relay connection opens, then resets its recurrent state. Cold-start model/runtime
download and compilation are separate from steady-state processing latency.

If initialization fails, the worker crashes, or a packet reaches its 32 ms
processing/round-trip deadline, listening continues with raw audio and a visible
localized warning. Fallback preserves the 256-sample alignment after denoising
has started; it never replays a whole packet or skips its pending samples.
Stopping, reconnecting or hiding the page terminates the worker and clears its
state. Devices that cannot sustain real time fall back rather than accumulate
latency. Switch noise reduction off for the lowest possible capture latency.

## Verify changes

```sh
cd mobile
npm test
npm run typecheck
npm run lint
# Configure EXPO_PUBLIC_API_URL first. Browser tests build their own production export.
npx playwright install chromium
npm run test:web

cd ../backend
python -m pytest -q
python -m ruff check app tests
python -m ruff format --check app tests
```

`npm run test:web` builds `dist` before starting its preview server, so it works
from a fresh checkout after dependencies and the public relay origin are configured.
Set `PORT` to use a different local port. Playwright and the preview server share
that value, defaulting to 4173. A separately running local preview can be reused.

Browser tests use Chromium's synthetic microphone and mock relay output. Backend
tests exercise the real authenticated relay with mocked provider output. They
verify the application paths and PCM framing, including Malayalam text delivery,
without establishing live provider accuracy, physical-device vibration, actual
screen-reader speech or every browser's notification behavior.
