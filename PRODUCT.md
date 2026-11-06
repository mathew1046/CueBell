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

Speech language is automatic (`indic-auto`), with no language chooser required. The user selected `gpt-6-luna`; its exact ID was verified against their account and set in the ignored environment. Automatic speech recognition does not expand the configured token grammar or the supported Malayalam/English number normalization.

## Accessibility & Inclusion
High contrast, large token/counter text, labelled controls, screen-reader updates, large touch targets and visual alternatives to all sound/vibration. Typed setup must work without speech. No color-only health state.

## Evidence on Hand
implementation.md is the original research architecture, not measured product reliability. Credentials were supplied locally and are excluded from source control. Live Luna staged text probes and HTTP/reducer flows passed. After the user corrected authorization, Gnani connected with Prisma v3.0 / indic-auto and negotiated 16 kHz / 512-sample frames. The client sent 48 paced synthetic tone/silence PCM frames without a reported error. Earlier HTTP 401 failures are resolved; no spoken audio was tested. There are 189 passing backend tests, six native unit tests, and Android emulator setup/theme captures. No real-phone speech/haptic/background evaluation, pricing or provider retention verification is present.

## Product Principles
- Confirm before monitoring; ambiguous setup cannot start a monitor.
- Match extracted observations, never bias speech recognition with the user's token.
- Abstain instead of guessing; retain correction history.
- Make listening failures and gaps visible.
- Minimize collection and never persist raw audio by default.

## Open Decisions
Gnani connection authorization is verified; account quotas/terms and speech recognition results remain unverified. Minimum supported physical-device behavior must be tested. User declined prebuilt-screen selection: build a standard accessible Material shell driven by inferred intents and events, not fixed token setup screens.
