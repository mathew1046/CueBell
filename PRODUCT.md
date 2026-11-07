# CueBell

<!-- impeccable:product-schema 1 -->

## Platform
android

## Stack
Delegated recommendation: React Native with Expo development builds, TypeScript, a local Kotlin Expo module with an Android microphone foreground service, and one Python FastAPI backend. Native service owns audio, WebSocket transport, notifications and haptics so background operation does not depend on JavaScript timers. Expo Go is not supported.

## Users
People who are deaf or hard of hearing who want help noticing events established by nearby speech, including public announcements, their name being called, transport updates and queue calls. The initial hospital-pharmacy scenario is an example, not the product boundary.

## Product Purpose
Act as helping ears: understand a user-described subject and trigger condition, automatically start the valid submitted task after consent/permission checks, then turn matching speech into prominent visual alerts with the requested vibration/sound. No second confirmation tap is required. Do not require a token for a general task. Supplemental assistance only: users must still consult official sources or staff.

## Operating Context
Android first. User explicitly requested background listening, superseding the plan's foreground-only MVP. Start microphone capture while the app is visible; continue using an Android microphone foreground service and persistent notification. OS interruptions, network loss and acoustic limits remain possible. No claim of reliable background or screen-locked operation before actual device testing.

## Capabilities and Constraints
Latest user instructions override the older plan: Gnani Prisma v3.0 for speech; Gnani Evon for intent and observations when its contract is supplied, with an explicitly authorized OpenAI text-model fallback. The exact OpenAI API model ID is server configuration, not an assumed marketing name. Disclose transcript transfer before capture or text submission. User reports hosted Evon access but has not supplied its API contract; do not invent it. One confirmed monitor per session; preserve prefixes and leading zeros. Separate setup speech and announcement capture. Correct, repeat, cancel and uncertain observations remain visible. No database or recordings by default; bounded in-memory session history. API credentials stay server-side. No deployment, recording bystanders or data collection is authorized.

Speech language is automatic (`indic-auto`), with no language chooser required. The user selected `gpt-6-luna`; its exact ID was verified against their account and set in the ignored environment. Latest instructions remove custom token rules and handwritten number parsing: the text model interprets identifiers across languages/forms, with source-evidence checks. A valid submitted request automatically activates after consent and Android permission checks; no second confirmation tap is required. There is no assumed venue format, digit count, prefix whitelist or counter range. Speech recognition is still limited to the provider's supported languages, not a universal accuracy guarantee.

Spoken setup waits through short sentence pauses (3.5 seconds of transcript quiet after finalized speech, 90 seconds maximum), combining finals before interpretation. A clear queue token read-out alone can alert. Visual, vibration and an Android alarm-tone notification are the default unless explicitly silenced; Android channel settings, volume and interruption policy still apply. These source changes require backend rollout and a rebuilt app, not an update to historical preview binaries.

The app contains only the user workflow: speak/type → automatic task activation → monitor/alert. Stop remains available during creation and capture. The native foreground service stays alive between spoken setup and monitoring, with the microphone off during interpretation; only that existing service can continue a pending request in the background. Fresh microphone starts still require a visible app. Explanations live in Help and monitoring captions are expandable. Server URL, pairing code and developer connection settings are not user-facing. Operators supply `EXPO_PUBLIC_API_URL` before building. The app obtains and encrypts an expiring bearer on the first consented action. No provider or pairing secret is embedded. Controlled anonymous demo admission is an explicit backend opt-in (`ALLOW_APP_SESSIONS`), not production identity or proof of an authorized device; public deployment needs stronger admission and provider budget protection. The current operator-supplied hosted origin is https://cuebell.mathewjoseph.xyz, introduced in the v1.2.0 preview. Sessions for a different deployment are not reused.

CueBell v1.1.0 uses application ID `app.cuebell.mobile`, scheme/slug `cuebell`, npm package `cuebell-mobile`, Python distribution `cuebell` and encrypted session key `cuebell.connection.v1`. Renaming the Android package creates a separate install, not an in-place migration; the previous app and its private data are left untouched. The API paths, consent requirements, provider configuration and monitoring protocol do not change. Historical commits/releases remain historical rather than being rewritten.

## Accessibility & Inclusion
High contrast, large token/counter text, labelled controls, screen-reader updates, large touch targets and visual alternatives to all sound/vibration. Typed setup must work without speech. No color-only health state.

The user prioritizes elderly and low-literacy users: no greeting, repeated instructions or technical paragraphs in the main workflow. Use short labels and a 64dp Speak action. Full privacy/venue details and announcement history are expandable; processing recipients, consent, listening failures, latest uncertainty and the missed-call warning remain visible. A simpler screen is not evidence of validated low-literacy usability; test with representative people before claiming that outcome.

## Evidence on Hand

8 November general-monitoring source update: rewritten setup/event prompts and structured task/event schemas replace queue-only setup. Train 14922 arrival, a name being called and boarding need no fake token. Exact evidence validation and the shared correction/deduplication reducer remain mandatory. A configured-model synthetic text probe passed 14/14 setup/match/nonmatch/injection/voice-stop checks, including Hindi arrival text. Backend tests passed 280 cases; mobile tests passed 37. These are not spoken-audio or real-phone alert reliability measurements. Deploy the updated backend and rebuild the Android client together; source edits do not update the separately hosted service. Arbitrary acoustic-sound detection, external tracking, messaging and device control are unsupported.

Historical evidence (before that update):
implementation.md is the original research architecture, not measured product reliability. Credentials were supplied locally and are excluded from source control. Live Luna staged text probes and HTTP/reducer flows passed. After the user corrected authorization, Gnani connected with Prisma v3.0 / indic-auto and negotiated 16 kHz / 512-sample frames. The client sent 48 paced synthetic tone/silence PCM frames without a reported error. Earlier HTTP 401 failures are resolved; no spoken audio was tested. There are 227 passing backend tests, 16 mobile tests, six native unit tests, and historical Android emulator setup/theme captures. CueBell v1.1.0 installed on the physical phone and its Android launch request succeeded; the phone was asleep, so fresh visible-screen verification remains pending. No emulator installation or microphone action was performed. A prior temporary hosted typed-intent session passed and was deleted. No real-phone speech/haptic/background evaluation, pricing or provider retention verification is present.

## Product Principles
- Confirm before monitoring; ambiguous setup cannot start a monitor.
- Evaluate the complete confirmed subject and condition against grounded speech; never bias speech recognition with the user's target or alert preferences.
- Abstain instead of guessing; retain correction history.
- Make listening failures and gaps visible.
- Minimize collection and never persist raw audio by default.

## Open Decisions
Gnani connection authorization is verified; account quotas/terms and speech recognition results remain unverified. Minimum supported physical-device behavior must be tested. User declined prebuilt-screen selection: build a standard accessible Material shell driven by inferred intents and events, not fixed token setup screens.
