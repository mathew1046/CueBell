# CueBell product scope

<!-- impeccable:product-schema 1 -->

## Platform

Android 7+ ARM64 preview and installable web app. No iOS implementation.

## Users and purpose

Help people who are deaf or hard of hearing notice nearby spoken announcements. A user describes a token, name or event; matching speech produces a visual alert, with optional vibration and sound. These are listening tasks, not venue or transport integrations.

## Workflow

One task per session. Spoken or typed setup activates automatically after consent and permission checks. Captions, history, corrections and duplicate suppression help users inspect results. Keep the task, microphone status and stop control distinct.

## Stack and data

React Native, Expo, TypeScript and React Native Paper share the interface. Kotlin captures Android audio; AudioWorklet captures browser audio. A single-worker FastAPI relay sends audio to Gnani Prisma v3.0 and requests/transcripts to the configured OpenAI text fallback. Evon is not integrated. Provider keys stay server-side; public demo admission is not production authentication.

Sessions expire and history is bounded in memory. There is no recording database. See [privacy](docs/PRIVACY.md).

## Operating limits

Internet and useful microphone placement are required. Android starts capture while visible; its foreground service can continue afterward, subject to OS restrictions. Web capture stops when hidden and needs explicit restart.

Speech-language selection is automatic. English and 20 Indian UI languages are bundled, without a recognition-quality guarantee. Experimental local GTCRN noise reduction is off by default.

No fixed token length is required. There is no offline recognition, queue prediction, speaker identification or external transport tracking.

## Accessibility and principles

- Provide typed setup, labelled controls, readable contrast, scalable text, themes and visual alternatives to sound.
- Keep consent, uncertainty, listening failures and coverage gaps visible.
- Do not use the target as a recognition hint. Validate source evidence before alerting, while recognizing that a transcript can be wrong.
- Show corrections rather than silently retaining outdated directions.

CueBell is supplemental, not the official announcement source. Representative-user usability and real-world benefit remain unmeasured. See [engineering results](docs/README.md#understand-the-results) and the [field-evaluation plan](docs/IMPACT.md).
