# Privacy and data flow

These notes describe source/preview behavior, not guarantees about hosts, operating
systems or provider retention.

## What leaves the device

| Data | Destination/purpose |
| --- | --- |
| Typed request | Relay, then configured OpenAI text model for interpretation. |
| Microphone audio | Relay, then Gnani Prisma for transcription; not OpenAI. |
| Final transcripts | Relay/OpenAI for event and voice-stop interpretation; recent captions appear locally. |
| Connection metadata | Relay session state and client storage for expiring sessions. Keys stay server-side. |

Admission waits for consent and user action. Capture needs visible user action
and microphone permission. Android displays a foreground notification. Browsers
stop when hidden; installation adds no background capture.

Optional local [denoising](NOISE_REDUCTION.md) precedes the same provider path,
not offline recognition. Voice stop has no speaker authentication; nearby speech
can pause listening.

## What is stored

| Location | Storage |
| --- | --- |
| Android | Encrypted SecureStore: origin, bearer, expiry, suppression flag and app preferences. Private preferences: service notification language/catalog. |
| Browser | Tab-scoped session storage: bearer. Origin-local storage: preferences. Unavailable storage falls back to page memory, lost on reload. |
| Client/relay memory | Bounded task, observations, recent transcripts/history. Normal operation intentionally writes no audio/transcript recording files. |
| Relay | No database; default four-hour expiry. Restart discards memory. |

The web service worker handles notification clicks, caching no audio, transcripts,
credentials or API responses. The bundled alarm is generated public audio.

Gnani/OpenAI terms govern provider retention. OpenAI `store=false` is not a
zero-retention guarantee. Hosts, proxies, monitoring, OS diagnostics, browser
extensions and screenshots can create records. Operators must avoid sensitive
payload logging and disclose extra collection.

## User controls

- Decline processing consent or microphone permission to prevent capture. Clear submitted tasks activate automatically after required checks, without another confirmation tap.
- **Home → Stop Listening** releases capture but retains task/history.
- **Settings → Clear task** clears local events/notifications and attempts remote cleanup. Older APKs may label it **Stop**. Failures are reported; unreachable sessions expire. Saved suppression prevents restoring an uncleared monitor. If suppression and session removal both fail, retry Clear task or clear app storage before closing.
- Voice stop depends on connectivity/interpretation, not an offline kill switch. Keep manual controls available; Android also has a notification stop control.

Obtain venue permission; use consenting speakers, synthetic identifiers and redacted
reports. Report unintended disclosure [privately](../SECURITY.md).
See [architecture](ARCHITECTURE.md), [web behavior](WEB.md) and the [index](README.md).
