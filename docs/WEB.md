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

Open `http://127.0.0.1:4173`. Localhost is a secure context for microphone access.
The public site requires HTTPS. The relay must use HTTPS and WSS, including when
the web interface runs locally. `EXPO_PUBLIC_API_URL` is bundled at build time.
It contains the public service origin, with no trailing path or credentials.

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

4. Serve `.js` and `.mjs` as JavaScript, the manifest as
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
