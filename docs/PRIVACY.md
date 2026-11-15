# Privacy and data flow

These notes describe the source and preview behavior. They do not guarantee a
hosting operator's, operating system's or provider's retention practices.

## What leaves the device

| Data | Destination and purpose |
| --- | --- |
| Typed request | Relay, then the configured OpenAI text model for task interpretation. |
| Microphone audio | Android or browser client, through the relay to Gnani Prisma for transcription. The relay does not send audio to OpenAI. |
| Final transcripts | Relay and OpenAI for event and voice-stop interpretation; recent captions appear in the client. |
| Connection metadata | Relay session state and local client storage for an expiring session. Provider keys remain server-side. |

No session admission request is sent until the user acts after accepting processing.
Capture starts through a visible user action and microphone permission. Android
uses a foreground service with an ongoing notification. Browser listening stops
when the page becomes hidden; installation does not enable background capture.

Experimental [noise reduction](NOISE_REDUCTION.md) runs on the device before
processed audio is sent through the same relay/provider path. It does not make
recognition offline. Voice stop is not speaker authentication: nearby speech can
also pause a monitor.

## What is stored

| Location | Storage |
| --- | --- |
| Android | Encrypted SecureStore holds connection metadata, including origin, bearer, expiry and suppression flag, plus app preferences. The service keeps notification language/catalog data in private preferences. |
| Browser | The expiring bearer is in tab-scoped session storage; preferences use origin-local storage. If storage is unavailable, page-memory fallback is lost on reload. |
| Client and relay memory | Bounded recent transcripts, task state, observations and history. No intentional audio-recording or transcript files are written by the normal app/relay path. |
| Relay | No database. Sessions expire after four hours by default; restarts discard all in-memory state. |

The web service worker handles notification clicks. It does not cache audio,
transcripts, credentials or API responses. The bundled alarm is generated public
audio, not a user recording.

Gnani and OpenAI have separate terms and retention policies. OpenAI requests use
`store=false`; this is not a zero-retention guarantee. Hosts, reverse proxies,
monitoring tools, OS diagnostics, browser extensions and screenshots may create
additional records. Operators must avoid sensitive payload logging and disclose
any extra collection.

## User controls

- Decline processing consent or microphone/notification permissions if you do not want to proceed. A valid submitted task activates automatically after the required checks; there is no second confirmation tap.
- **Stop Listening** releases capture while retaining the task and recent history for review.
- **Settings → Stop** clears local session events and notifications and attempts remote cleanup. Failure is reported; unreachable sessions expire. A saved suppression flag prevents an uncleared old monitor from being restored.
- Use manual controls if voice stop fails. It depends on connectivity and model interpretation, not an offline kill switch. Android also offers a notification stop control.

Do not capture a real venue without permission. Use consenting speakers and
synthetic identifiers for reports, and redact personal information and credentials.
Report unintended disclosure [privately](../SECURITY.md).

See [architecture](ARCHITECTURE.md), [web behavior](WEB.md) and the
[documentation index](README.md).
