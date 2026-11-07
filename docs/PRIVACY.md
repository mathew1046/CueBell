# Privacy and data flow

These notes describe the current source and preview, not a guarantee about a
hosting operator, Android diagnostics or a third-party provider's retention.

## What is processed

| Data | Destination / purpose |
| --- | --- |
| Typed monitoring request | Backend, then the configured OpenAI text model for intent extraction. |
| Microphone audio | Native app → backend relay → Gnani Prisma for speech recognition. Audio is not sent to OpenAI by this relay. |
| Final speech transcripts | Backend and configured OpenAI text model for announcement/voice-stop interpretation; recent captions can appear in the app. |
| Session connection metadata | Encrypted Android SecureStore: routing origin, expiring bearer token, expiry and local suppression flag. |

No admission request is sent until the user acts after accepting processing.
Audio capture starts through a visible user action and a native Android foreground
service; it has an ongoing microphone notification. Provider credentials remain
server-side. Voice-stop interpretation is not speaker authentication: nearby speech
can also pause the monitor.

## Storage and retention

The app and relay do not intentionally write audio recordings or transcripts to
disk. Recent events/transcripts use bounded memory. The relay has no database;
sessions expire (four hours by default), and process restarts lose in-memory state.
Connection metadata is stored separately so the app can restore its session.

Cloud speech/text providers have their own terms and retention policies. OpenAI
requests use `store=False`, but this is not a promise of zero provider retention.
Hosts, reverse proxies, monitoring tools, OS diagnostics and screenshots can
introduce additional records. Operators must prevent sensitive payload logging
and explain any additional collection to users.

## User controls and limitations

- Review the target before confirming; deny microphone/notification permissions
  or processing consent if you do not want to proceed.
- **Stop Listening** pauses capture and keeps the token/history for review.
- **Settings → Stop** clears local session events and notifications and attempts
  remote cleanup. Failed cleanup is reported; unreachable sessions expire.
- Manual and notification stop controls remain important: voice stopping depends
  on connectivity, recognition and model interpretation, not an offline kill switch.

Do not use CueBell to record a real venue without permission. Bug reports should
contain synthetic tokens and redacted logs, never patient details or live credentials.

Security or unintended disclosure concerns:
https://github.com/mathew1046/CueBell/security/advisories/new
