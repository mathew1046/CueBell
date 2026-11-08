# CueBell

**Hear the announcement. See your turn.**

## Short solution pitch

**The problem:** People who are deaf or hard of hearing can miss important spoken announcements. In a busy pharmacy, missing a token call may mean waiting longer or needing someone else to help.

**Our solution:** CueBell is an Android app that acts as helping ears. It turns announcements that matter to the user into clear on-screen alerts, with vibration and sound options.

**How it works:** The user types or says what to listen for, such as “Tell me when pharmacy token 442 is called.” CueBell listens through the phone's microphone and uses speech recognition and AI to understand the announcement. When it detects a match, it shows the call and any counter details. The user can stop listening from the app or by voice.

**Why it matters:** CueBell aims to help people wait more independently, without constantly watching a display or relying on another person. It gives each user a personal alert for the information they asked for.

**Current stage:** An Android prototype that needs an internet connection. The next step is testing with users in busy, real-world settings.

## Project overview

**Status:** active prototype · Android only · development-signed preview

**Download the Android preview:**
https://github.com/mathew1046/CueBell/releases/tag/v1.3.0-preview

**Report a bug or suggest an improvement:**
https://github.com/mathew1046/CueBell/issues

Tell it who or what to listen for and when to alert you. A valid request starts monitoring automatically after consent and permission checks. A native Android microphone service listens while a separate, self-hosted backend interprets the speech.

> “Listen for pharmacy token 442 and vibrate.”
>
> Submit the request → monitoring starts → hear “Token 442 to counter two” → see an alert with the matching speech and counter details.

**Prototype, not an official queue system. Calls can be missed. Always check the venue display or staff.**

## Why CueBell?

Imagine waiting for medicine in a crowded pharmacy. Your turn is announced over a loudspeaker, but you cannot reliably hear it. You may need to watch the display continuously or depend on someone else to notice the call.

CueBell aims to make that moment more accessible: the person specifies their own token and receives a personal, visible cue when a matching announcement is detected.

These are **intended benefits, not measured outcomes**. Fewer missed turns, real-world speech accuracy and reliable locked-screen delivery have not been established. The workflow also accepts tasks such as a train arrival, a name being called or flight boarding; these are speech-based monitors, not established venue deployments or live tracking.

## What it does today

- **Speak or type a request.** Describe the subject and trigger condition. Valid requests activate automatically after consent and Android permission checks; unclear requests ask for clarification. No second confirmation tap is needed.
- **Listen through a native Android service.** Kotlin owns microphone capture, PCM framing, networking and notifications, rather than relying on background JavaScript timers.
- **Check before alerting.** Structured model output must match the task and pass schema and source-evidence checks. Alerts include the event summary, location when heard and verbatim source speech; queue tokens are not required for general tasks.
- **Handle changing announcements.** Calls, repeats, corrections, cancellations and uncertain interpretations are separate events. Unclear input is not coerced toward the user's token.
- **Keep the session understandable.** Recent transcripts, listening status, coverage gaps, acknowledgment, pause and stop controls remain visible.
- **Choose the app language.** English and 20 Indian languages have bundled UI translations, including native notifications. Sound-enabled alerts use a bundled three-pulse alarm; silent preferences remain respected.
- **Stop by voice.** While monitoring, express that you want CueBell to stop listening, directly or indirectly. The text model interprets intent across languages, without a fixed command list; a source-grounded decision pauses the monitor and stops the native microphone, even with the app in the background. The token and history remain available, as with Home's Stop Listening.
- **Keep provider keys off the phone.** The APK connects to your separately hosted backend using an expiring session credential.
- **Open directly into the workflow.** No server URL, pairing code or developer settings screen. The release operator sets the service address before building; the app obtains its session automatically when you submit a request.

### Task and identifier interpretation

One active monitor per session, without assumed venue formats, digit counts, prefixes or counter ranges. The text model interprets spoken/written identifiers consistently across setup and announcements, without handwritten number parsers. The home card shows the active task; stop and edit it if the interpretation is wrong.

Spoken setup waits for 3.5 seconds of transcript quiet after finalized speech instead of stopping on the first provider sentence; unfinished interim speech keeps capture open, up to 90 seconds overall. Recognition is limited by the speech provider's languages; model interpretation is not a guarantee of accuracy in every language or venue.

## How it works

```text
Spoken request ── Gnani Prisma ──┐
Typed request ──────────────────┴─> Text intent extraction
                                      │
                          Consent + valid task activation
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
Grounded task match → visual alert + optional vibration / sound
```

The user's target is **not** supplied as a speech-recognition hint. The text model evaluates the active subject and condition against the transcript; source evidence must pass validation. Announcements cannot create monitors or change alert preferences.

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

## Try the Android preview

APK download:
https://github.com/mathew1046/CueBell/releases/download/v1.3.0-preview/CueBell-1.3.0-arm64.apk

Checksum:
https://github.com/mathew1046/CueBell/releases/download/v1.3.0-preview/CueBell-1.3.0-SHA256SUMS

- Android 7+ on an ARM64 phone; iOS is not implemented.
- Version **1.3.0**, Android version code **5**, package `app.cuebell.mobile`.
- Development-signed preview, **not a production/store distribution**. Its signing certificate matches the 1.2.0 preview for in-place updates.
- The preview is preconfigured; there is no backend URL or provider-key setup on the phone. Sessions for an older deployment are not reused: submit your request again after updating.
- **Expo Go cannot run the custom native microphone service.** Use the APK or a native development build.

What's changed:
https://github.com/mathew1046/CueBell/blob/main/CHANGELOG.md

## Run a controlled demo

**Start with the complete demo guide:**
https://github.com/mathew1046/CueBell/blob/main/DEMO.md

The shortest reliable presentation path is:

1. Run the separate backend with your provider credentials. For a controlled no-login demo, explicitly enable `ALLOW_APP_SESSIONS=true`; see the security warning below.
2. Give it a publicly trusted HTTPS URL with WebSocket support. Set that origin as `EXPO_PUBLIC_API_URL` in the mobile build environment and build the APK. A stable host avoids rebuilding when a temporary tunnel changes.
3. Install that APK on an Android phone and open it. **There is no connection setup in the app, and provider keys are never bundled.**
4. Use the pencil to enter a request, allow processing, type “Listen for pharmacy token 442 and vibrate,” then tap **Start Listening**. Grant permissions and check the active task and listening status; there is no second confirmation tap.
5. Have a consenting speaker announce a non-target token, then **“Pharmacy token four four two, please go to counter two.”** Inspect the transcript and resulting alert.

The guide includes exact commands, a three-minute script, correction and interruption checks, troubleshooting, and an honest fallback if the live pipeline fails.

## Verification

The 1.3.0 preview passed **280 backend tests, 43 mobile tests and 14 native unit tests**, plus TypeScript, lint, all 20 Expo Doctor checks and APK packaging/signature checks. The verification record separates mocked tests, historical smoke checks and unverified real-world behavior:
https://github.com/mathew1046/CueBell/blob/main/docs/VERIFICATION.md

GitHub Actions runs backend tests/lint and mobile tests/typecheck/lint without provider credentials. It does not build the APK, call paid providers or establish physical-phone reliability.

## Development and hosting

Backend installation, configuration, tests, TLS and single-worker hosting:
https://github.com/mathew1046/CueBell/blob/main/backend/README.md

Android setup, APK build, native tests and device checklist:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md

From the repository root, frontend checks are:

```sh
cd mobile
npm ci
npm test
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

- Contributor setup and review checklist: https://github.com/mathew1046/CueBell/blob/main/CONTRIBUTING.md
- Release history: https://github.com/mathew1046/CueBell/blob/main/CHANGELOG.md
- Privacy and data flow: https://github.com/mathew1046/CueBell/blob/main/docs/PRIVACY.md
- Security reporting: https://github.com/mathew1046/CueBell/blob/main/SECURITY.md
- Community guidelines: https://github.com/mathew1046/CueBell/blob/main/CODE_OF_CONDUCT.md
- Original research architecture: https://github.com/mathew1046/CueBell/blob/main/implementation.md
- Current product scope and subsequent decisions: https://github.com/mathew1046/CueBell/blob/main/PRODUCT.md
- Interface principles and review record: https://github.com/mathew1046/CueBell/blob/main/DESIGN.md

The later Android/background, general-task, automatic-activation and OpenAI-fallback decisions override the original plan's foreground-web / queue-only / manual-confirmation / Gnani-only scope. The basic queue-alert concept has prior art; this prototype does not claim to have invented it. Its intended contribution is an accessible multilingual workflow with personal listening tasks, correction-aware handling and honest coverage status—not a proven performance advantage.

## Contributing and support

Bug reports, accessibility feedback and small, focused improvements are welcome. Use the issue templates and include your app/Android version and reproducible steps using synthetic tokens. Do not post credentials, private patient information or unconsented venue recordings.

For security vulnerabilities, use private reporting instead of a public issue:
https://github.com/mathew1046/CueBell/security/advisories/new

## License

No project license has been selected yet. Public source availability alone does not grant an open-source license; clarify reuse or redistribution with the maintainer before proceeding.
