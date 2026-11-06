# QueueSaathi

Android assistive queue-announcement listener, with a **separate, self-hosted backend**.

Speak Malayalam or English (or type) → model extracts a monitoring request → review the exact token and alert preference → confirm → native Android microphone foreground service listens → validated matching announcements produce visual / optional vibration / sound notifications.

## Stack

- **App:** Expo SDK 58, React Native, TypeScript, Expo Router, React Native Paper / Material 3.
- **Background runtime:** local Kotlin Expo module, `AudioRecord` (16 kHz mono PCM16LE), OkHttp WebSocket, Android foreground microphone service and notification channels. No background JavaScript timers or Expo Go dependency.
- **Separate backend:** Python / FastAPI, authenticated session relay, Gnani Prisma v3.0 speech recognition. OpenAI structured text extraction is the explicitly requested Evon fallback; exact model is configured by the host. No invented Evon endpoint.
- **Automatic language:** Prisma uses `indic-auto`; no language selection is required in the app. The configured text model is `gpt-6-luna`, verified against the operator's OpenAI account. Speech recognition supports more languages than the deliberately narrow Malayalam/English queue-number validation.
- No database, accounts, persisted recordings, or transcript logging in this implementation. Only connection metadata and the expiring session credential are saved in Android encrypted storage. Active events stay in bounded memory.

## Run

1. Follow `backend/README.md` to configure the provider keys, exact `OPENAI_MODEL`, pairing code, HTTPS and persistent WebSockets. Hosting remains separate; no backend has been deployed for you.
2. Install the preview APK on an Android phone. In **Backend connection**, enter your HTTPS origin and pairing code. Do not enter provider API keys in the app.
3. Accept the processing disclosure. Speak a request or type, for example **“Listen for pharmacy token P042 and vibrate.”** Review every digit and confirm. Grant microphone and notification permissions.
4. Keep the phone in useful acoustic range. An ongoing notification shows microphone activity and offers **Stop microphone**. Pause, resume, stop, acknowledge and edit are available in the app. Changing a target always requires confirmation.

The initial configured venue is a hospital pharmacy, with exactly three token digits, an optional `A` or `P` prefix, and counters 1–10. Leading zeroes are preserved. Other token grammars require a coordinated backend configuration/schema change, not a guessed conversion. A model extracts natural-language intent/events; deterministic schema/evidence/grammar checks and the reducer decide alerts. Announcement text cannot create monitors or change preferences.

## Build and checks

App details and reproducible APK commands: `mobile/README.md`.

```sh
cd mobile
npm ci
npm run typecheck
npm run lint
```

Backend tests run with mocked provider boundaries; see its README. Native PCM tests verify signed little-endian samples, exact frame length and a known waveform across boundaries. These are not measurements of real PA recognition quality.

### Verification so far

- 189 backend tests cover validation, confirmation, correction/repeat aliases, acknowledgment, stale results, gaps, cleanup, automatic-language configuration, cross-counter cancellations, oversized extraction rejection and permanent provider-authorization failures. Ruff checks pass.
- Six native tests cover PCM16 framing/waveform boundaries and permanent versus retryable WebSocket rejection. TypeScript and lint checks pass.
- The standalone APK builds and launches on an Android 16 emulator. Light theme, dark theme at 1.3× text scale, and backend setup have rendered captures; microphone and notification permissions are not requested at launch.
- Live `gpt-6-luna` checks passed for English/Malayalam intent and call extraction, negation and instruction injection. Live HTTP confirmation/lifecycle checks passed for `442`, spoken cardinal words, and Malayalam spoken digits preserving `P042`; model-to-reducer checks issued counter 2 and corrected it to counter 3. A token-evidence prompt issue found during testing was tightened without relaxing validation. This small synthetic-text smoke set is not an accuracy benchmark.
- Gnani authorization now succeeds: live streaming negotiated 16 kHz / 512-sample frames using `prisma-v3.0` and `indic-auto`. Sent 48 paced PCM frames of a synthetic tone/silence without a reported provider error; no spoken audio or speech accuracy was tested. Earlier HTTP 401 failures are resolved. Provider 401/403 errors stop retrying and show safe configuration guidance.
- Recognition accuracy, TalkBack usability and physical-phone background/locked-screen delivery are **not yet verified**. Valid speech authorization and consented spoken samples are needed; unit tests and emulator renders do not establish those properties.

## Important limitations

- Supplemental aid only. Recognition or interpretation can be wrong; calls can be missed. Check the official display or staff. No queue-position prediction or PA-speaker identification.
- Android-first, Android 7+; iOS is not implemented. Start the microphone while the app is visible. The native service can continue when the screen locks, but Android, privacy controls, battery management or an OEM may stop/silence it. No boot restart or background start. A real target-phone test is required before relying on it.
- Notification vibration/sound are requests, subject to Android channel settings, hardware and Do Not Disturb. Visual alerts always accompany them. Lock-screen content is private by default.
- Reconnection drops old audio instead of replaying it. Coverage gaps are explicit. One monitor per session; sessions expire (four hours by default), and Gnani streams recycle before the documented 15-minute cap.
- Audio goes only to Gnani. Text goes to the configured OpenAI fallback. The relay's no-persistence policy does **not** claim either provider has zero retention. Review current provider terms before real use. Evon remains unimplemented until its real contract is supplied.
- Credentials stay in the ignored backend environment, never the repository or APK. Malayalam/code-switch speech performance, end-to-end latency, physical-phone haptics and background endurance remain unverified. No reliability percentage is claimed.

`implementation.md` is the original research plan. `PRODUCT.md` records subsequent Android/background and OpenAI-fallback decisions; those explicit user decisions override the original foreground-web / Gnani-only scope. `DESIGN.md` describes the minimal native interface.
