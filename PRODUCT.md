# CueBell product scope

<!-- impeccable:product-schema 1 -->

## Platform

Android and installable web app. Android 7+ ARM64 preview; iOS is not implemented.

## Stack

React Native, Expo, TypeScript and React Native Paper share the interface. Kotlin owns Android microphone capture and foreground-service delivery. The browser uses AudioWorklet. A single-worker FastAPI relay connects audio to Gnani Prisma v3.0 and text to a configured OpenAI fallback.

## Users

People who are deaf or hard of hearing who want a personal cue for nearby spoken announcements. The initial example is a pharmacy token call; names and other speech-described events are supported tasks, not verified venue integrations.

## Product Purpose

Turn a user-described listening task into a visible, source-grounded alert, with optional vibration and sound. A valid request starts automatically after consent and permission checks. Keep the active task inspectable and Stop available.

## Operating Context

An internet connection and usable microphone position are required. Android starts capture while visible and uses a foreground service for continued capture. OS restrictions can interrupt it. Web listening stops when the page is hidden and requires explicit restart.

## Capabilities and Constraints

- One active monitor per session.
- Spoken or typed setup, captions, history, correction handling and duplicate suppression.
- No required venue token format, fixed digit length or handwritten number parser.
- Gnani automatic speech-language selection; English and 20 Indian UI languages.
- Optional experimental GTCRN noise reduction, off by default.
- No offline recognition, queue prediction, speaker identification or external transport tracking.
- Expiring bearer sessions and bounded in-memory history; no recording database.
- Provider keys stay server-side. Public demo admission is not production authentication.
- Evon is not integrated. The OpenAI text fallback and provider data transfers are disclosed.

## Accessibility & Inclusion

Typed setup, labelled controls, readable contrast, larger text, themes, visual alternatives to sound, and visible listening failures. Keep detailed explanations in Help without hiding processing recipients, consent, uncertainty or missed-call warnings. Representative-user usability remains to be evaluated.

## Product Principles

- Do not use the target as a recognition hint.
- Validate source evidence before alerting; a transcript-grounded result can still be acoustically wrong.
- Show corrections and uncertainty rather than guessing or erasing history.
- Distinguish an active task from an actively connected microphone.
- Treat CueBell as supplemental assistance, not the official announcement source.

## Evidence and Next Steps

See [measured results](docs/README.md#understand-the-results) and the [impact evaluation plan](docs/IMPACT.md). Controlled technical tests support development decisions; they do not yet establish real-world accessibility outcomes.
