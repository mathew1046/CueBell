# QueueSaathi

<!-- impeccable:product-schema 1 -->

## Platform
android

## Stack
Delegated recommendation: React Native with Expo development builds, TypeScript, a local Kotlin Expo module with an Android microphone foreground service, and one Python FastAPI backend. Native service owns audio, WebSocket transport, notifications and haptics so background operation does not depend on JavaScript timers. Expo Go is not supported.

## Users
People who are deaf or hard of hearing waiting for public-address queue announcements, initially a single hospital pharmacy with Malayalam and English announcements.

## Product Purpose
Turn recognized queue announcements into prominent visual and optional haptic alerts for a confirmed token. Supplemental assistance only: users must still consult official displays or staff.

## Operating Context
Android first. User explicitly requested background listening, superseding the plan's foreground-only MVP. Start microphone capture while the app is visible; continue using an Android microphone foreground service and persistent notification. OS interruptions, network loss and acoustic limits remain possible. No claim of reliable background or screen-locked operation before actual device testing.

## Capabilities and Constraints
Latest user instructions override the older plan: Gnani Prisma v3.0 for speech; Gnani Evon for intent and observations when its contract is supplied, with an explicitly authorized OpenAI text-model fallback. The exact OpenAI API model ID is server configuration, not an assumed marketing name. Disclose transcript transfer before capture or text submission. User reports hosted Evon access but has not supplied its API contract; do not invent it. One confirmed monitor per session; preserve prefixes and leading zeros. Separate setup speech and announcement capture. Correct, repeat, cancel and uncertain observations remain visible. No database or recordings by default; bounded in-memory session history. API credentials stay server-side. No deployment, recording bystanders or data collection is authorized.

## Accessibility & Inclusion
High contrast, large token/counter text, labelled controls, screen-reader updates, large touch targets and visual alternatives to all sound/vibration. Typed setup must work without speech. No color-only health state.

## Evidence on Hand
implementation.md is a research architecture, not tested provider access or measured product reliability. No credentials, evaluation recordings, device test evidence, pricing or provider retention verification is present.

## Product Principles
- Confirm before monitoring; ambiguous setup cannot start a monitor.
- Match extracted observations, never bias speech recognition with the user's token.
- Abstain instead of guessing; retain correction history.
- Make listening failures and gaps visible.
- Minimize collection and never persist raw audio by default.

## Open Decisions
Gnani credentials, account quotas/terms and a real response trace remain unverified. Minimum supported device behavior must be tested. User declined prebuilt-screen selection: build a standard accessible Material shell driven by inferred intents and events, not fixed token setup screens.
