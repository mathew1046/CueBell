# CueBell

**Hear the announcement. See your turn.**

CueBell is an Android assistive app that turns a matching queue announcement into a prominent visual alert, vibration and an alarm sound by default. Users can explicitly request silent alerts. It is designed primarily for people who are deaf or hard of hearing.

Tell it what to watch for, check the details, and confirm. A native Android microphone service then listens for announcements while a separate, self-hosted backend interprets them.

> “Listen for pharmacy token 442 and vibrate.”
>
> Review **442 · Visual + vibration + sound** → start → hear “Token 442 to counter two” → see **442 · Go to counter 2**.

**Prototype, not an official queue system. Calls can be missed. Always check the venue display or staff.**

## Why this matters

Imagine waiting for medicine in a crowded pharmacy. Your turn is announced over a loudspeaker, but you cannot reliably hear it. You may need to watch the display continuously or depend on someone else to notice the call.

CueBell aims to make that moment more accessible: the person specifies their own token and receives a personal, visible cue when a matching announcement is detected.

| Real-life need | Intended benefit |
| --- | --- |
| A deaf or hard-of-hearing patient cannot access an audio-only call. | Present the token and destination visually, with an optional vibration cue. |
| A patient wants to manage their own turn rather than rely on a companion. | Let them set, review, pause and stop their own monitor. |
| Announcements switch languages or number forms. | Detect speech language automatically and let the text model interpret equivalent identifiers. |
| Staff correct a counter after calling a token. | Preserve the announcement history and visibly mark a resolved correction. |
| Connectivity or microphone capture is interrupted. | Show a coverage gap instead of pretending the app is still listening. |

These are **intended benefits, not measured outcomes**. We have not demonstrated fewer missed turns, reduced waiting time or real-world recognition accuracy. Banks, government offices and transport terminals are possible future settings, not currently supported deployments.

## What it does today

- **Speak or type a request.** A model proposes the monitoring intent; it does not start listening until you review and confirm the exact token and alert preferences.
- **Listen through a native Android service.** Kotlin owns microphone capture, PCM framing, networking and notifications, rather than relying on background JavaScript timers.
- **Check before alerting.** Structured model output passes schema and source-evidence checks before matching the confirmed target; no custom token grammar is imposed.
- **Handle changing announcements.** Calls, repeats, corrections, cancellations and uncertain interpretations are separate events. Unclear input is not coerced toward the user's token.
- **Keep the session understandable.** Recent transcripts, listening status, coverage gaps, acknowledgment, pause and stop controls remain visible.
- **Stop by voice.** While monitoring, express that you want CueBell to stop listening, directly or indirectly. The text model interprets intent across languages, without a fixed command list; a source-grounded decision pauses the monitor and stops the native microphone, even with the app in the background. The token and history remain available, as with Home's Stop Listening.
- **Keep provider keys off the phone.** The APK connects to your separately hosted backend using an expiring session credential.
- **Open directly into the workflow.** No server URL, pairing code or developer settings screen. The release operator sets the service address before building; the app obtains its session automatically when you submit a request.

### Token interpretation

One confirmed monitor per session, without assumed venue formats, digit counts, prefixes or counter ranges. The text model interprets spoken/written identifiers consistently across setup and announcements, without handwritten number parsers. Review its interpretation before confirming.

Spoken setup waits for 3.5 seconds of transcript quiet after finalized speech instead of stopping on the first provider sentence; unfinished interim speech keeps capture open, up to 90 seconds overall. Recognition is limited by the speech provider's languages; model interpretation is not a guarantee of accuracy in every language or venue.

## How it works

```text
Spoken request ── Gnani Prisma ──┐
Typed request ──────────────────┴─> Text intent extraction
                                      │
                              Review and confirmation
                                      │
                         Active monitoring rule

Android microphone foreground service
    │  16 kHz mono PCM16LE · 1,024-byte frames
    ▼
Authenticated HTTPS/WSS backend relay
    ▼
Gnani Prisma v3.0 · automatic language detection
    ▼
Completed transcript → structured event extraction
    ▼
Deterministic validation → ordered correction-aware reducer
    ▼
Exact token match → visual alert + optional vibration / sound
```

The user's target is **not** supplied as a speech-recognition hint or to announcement extraction. Announcements cannot create monitors or change alert preferences.

Voice stopping depends on connectivity, speech recognition and model interpretation; it is not an instant or offline microphone kill switch. Speech-language coverage remains limited by the speech provider. There is no speaker identification, so a nearby person's request may also pause listening. Check that the microphone notification disappears; use the app or notification stop control if speech is missed. Voice-stop tests use mocked model decisions and do not establish live multilingual accuracy.

| Layer | Stack |
| --- | --- |
| Android interface | React Native, Expo SDK 58, TypeScript, Expo Router, React Native Paper / Material 3 |
| Native background runtime | Kotlin local Expo module, `AudioRecord`, OkHttp WebSocket, microphone foreground service, notification channels |
| Separate backend | Python 3.12+, FastAPI, bounded in-memory sessions; one worker / one instance |
| Speech | Gnani Prisma `prisma-v3.0`, `indic-auto`; audio goes only to Gnani |
| Text intent and events | OpenAI structured output, configured as `gpt-6-luna` in the tested account; explicitly authorized fallback for Evon |
| Persistence | No database or app/relay recording files; bounded session memory and encrypted Android connection metadata |

Gnani Evon is **not integrated**: its usable API contract has not been supplied. There is no invented endpoint or silent speech-provider substitution. Provider retention policies are separate from the app's no-recording policy.

## Try it / present a demo

**Start with the complete demo guide:**
https://github.com/mathew1046/CueBell/blob/main/DEMO.md

The shortest reliable presentation path is:

1. Run the separate backend with your provider credentials. For a controlled no-login demo, explicitly enable `ALLOW_APP_SESSIONS=true`; see the security warning below.
2. Give it a publicly trusted HTTPS URL with WebSocket support. Set that origin as `EXPO_PUBLIC_API_URL` in the mobile build environment and build the APK. A stable host avoids rebuilding when a temporary tunnel changes.
3. Install that APK on an Android phone and open it. **There is no connection setup in the app, and provider keys are never bundled.**
4. Allow processing, type “Listen for pharmacy token 442 and vibrate,” tap **Continue**, review the token, then tap **Start listening**.
5. Have a consenting speaker announce a non-target token, then **“Pharmacy token four four two, please go to counter two.”** Inspect the transcript and resulting alert.

The guide includes exact commands, a three-minute script, correction and interruption checks, troubleshooting, and an honest fallback if the live pipeline fails.

### Android preview download

The v1.1.0 preview routes to the operator-supplied backend:
https://queuesaathi.mathewjoseph.xyz

Release and APK download:
https://github.com/mathew1046/CueBell/releases/tag/v1.1.0-preview
https://github.com/mathew1046/CueBell/releases/download/v1.1.0-preview/CueBell-1.1.0-arm64.apk

Local copy:
/home/mathew/Arrakis/CueBell/artifacts/CueBell-1.1.0-arm64.apk

This is a **development-signed ARM64 preview**, not a production/store distribution. APKs are published as GitHub Release assets, not committed to source history. Historical preview binaries are superseded, not renamed and misrepresented as new builds. CueBell uses Android package `app.cuebell.mobile` and is a separate install; the previous app and its data are not removed.

**Server readiness:** the supplied server reports both providers configured. A staged hosted request, “Listen for pharmacy token 442 and vibrate,” returned an exact-token confirmation with visual/vibration preferences; its temporary session was deleted. The APK installs and opens on the connected physical phone. No microphone capture was started during installation, and hosted speech recognition/background alerts remain untested. Provider keys stay on the backend, never in the APK.

Build your own APK using:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md

**Expo Go does not support the custom native service.** This download targets ARM64 phones only; emulators and older 32-bit phones need a different build.

## Verification — what is and is not established

| Check | Result |
| --- | --- |
| Backend tests | **253 passed**: validation, confirmation, correction/repeat aliases, acknowledgment, stale results, gaps, cleanup, language configuration, cancellations, authorization, opt-in automatic session admission and source-grounded voice-stop routing with mocked multilingual model decisions. Ruff checks passed. |
| Native unit tests | **12 passed**: PCM16 framing/waveform boundaries, permanent versus retryable WebSocket rejection and initialization-time spoken-alert queue order/deduplication/bounds. TypeScript and lint checks passed. |
| Mobile workflow tests | **28 passed**: automatic session admission/reuse, expiry/revocation, consent withdrawal, configuration guards, CueBell identity, unchanged backend and local microphone-stop/storage/remote-cleanup failure recovery. |
| App build and rendering | Earlier minimal-interface QA launched on an Android 16 emulator; light/dark and enlarged text inspected. The CueBell v1.1.0 build retains the same hosted origin. Packaging a route does not verify live speech or alert delivery. |
| Hosted preview installation | CueBell v1.1.0 installed on the physical phone only; Android's cold-launch request returned `Status: ok`. The phone was asleep, so a fresh visible-screen check was not completed and no unlock was attempted. Compiled branding/package/version, unchanged origin, ARM64 architecture, signature and absence of configured server credentials were checked. Prior hosted typed intent returned the expected token/preferences. No phone microphone capture was started. |
| Live text model | Staged English/Malayalam intent, call, negation, injection-abstention and correction checks passed using `gpt-6-luna`. HTTP lifecycle and leading-zero checks passed. |
| Live speech connection | Gnani authentication and streaming negotiation succeeded at 16 kHz / 512 samples. Sent 48 paced synthetic tone/silence frames without a reported provider error. **This was not spoken-audio recognition testing.** |
| Real PA recognition and user outcomes | **Not measured.** No speech-accuracy percentage, false-alert rate, missed-call rate or latency benchmark is claimed. |
| Physical-phone accessibility and endurance | **Not yet verified:** TalkBack, vibration/sound, background/locked-screen delivery and OEM battery behavior. |

Automated tests and emulator captures do not establish real-world reliability. A successful socket connection is not proof that a spoken token will be recognized correctly.

## Development and hosting

Backend installation, configuration, tests, TLS and single-worker hosting:
https://github.com/mathew1046/CueBell/blob/main/backend/README.md

Android setup, APK build, native tests and device checklist:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md

From the repository root, frontend checks are:

```sh
cd mobile
npm ci
npm run typecheck
npm run lint
```

Backend environment variables include `GNANI_API_KEY`, `GNANI_LANGUAGE_CODE=indic-auto`, `OPENAI_API_KEY`, an account-enabled `OPENAI_MODEL`, and a random `DEMO_ACCESS_CODE` of at least 16 characters. Keep them in the ignored backend environment or your host's secret manager.

`EXPO_PUBLIC_API_URL` is a public routing address, not a secret. Never put provider keys or `DEMO_ACCESS_CODE` in any `EXPO_PUBLIC_` variable. The no-login demo admission mode is **off by default**: enabling it permits unauthenticated people to obtain limited bearer sessions and consume paid provider usage. Its IP/global rate and capacity limits are not production authentication. Before a public launch, add appropriate gateway/device-attestation or account admission and provider budgets; an APK's address or embedded code is not a security boundary.

## Safety, privacy and limitations

- **Supplemental aid only.** Noise, incorrect recognition or interpretation, and network problems can cause missed or false alerts. It is not a medical alarm or a substitute for official staff/displays.
- **Android-first, Android 7+.** iOS is not implemented. Start capture while the app is visible. The native service is designed for background capture, but Android privacy controls, battery management or the OEM can stop/silence it. No boot restart or background start is implemented.
- **Notifications are conditional.** Vibration/sound depend on hardware, permission, channel settings and Do Not Disturb. Visual feedback accompanies alerts; lock-screen content is private by default.
- **No offline recognition or catch-up.** Lost audio is not replayed as a current call. Gaps are visible. Sessions expire after four hours by default; provider streams recycle before the documented 15-minute cap.
- **No queue-position prediction or PA-speaker identification.** Nearby conversation can be captured. Use staged recordings or consenting speakers; do not record a real venue without permission.
- **Processing is disclosed.** Audio goes to Gnani; requests/transcripts go to the configured OpenAI text fallback. No audio or transcripts are persisted by the app/relay, but provider terms still apply. Disable sensitive payload logging in hosting/monitoring tools.

## Project documents

- Original research architecture: https://github.com/mathew1046/CueBell/blob/main/implementation.md
- Current product scope and subsequent decisions: https://github.com/mathew1046/CueBell/blob/main/PRODUCT.md
- Interface principles and review record: https://github.com/mathew1046/CueBell/blob/main/DESIGN.md

The later Android/background and OpenAI-fallback decisions override the original plan's foreground-web / Gnani-only scope. The basic queue-alert concept has prior art; this prototype does not claim to have invented it. Its intended contribution is an accessible Malayalam/English workflow with explicit confirmation, correction-aware handling and honest coverage status—not a proven performance advantage.
