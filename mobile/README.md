# Android app

Requires Node 24.3+ (or the SDK-supported Node 22.13+), Java 17, Android SDK / NDK compatible with Expo SDK 58. This custom Kotlin module **does not run in Expo Go**. The service origin is fixed at build time; provider secrets are never in the bundle. There is no URL field, pairing flow or developer settings screen in the app.

## Operator configuration (before building, not on the phone)

Copy `.env.example` to `.env` only if there is no existing configured file. Set `EXPO_PUBLIC_API_URL` to your actual deployed trusted HTTPS origin (no path/query/credentials). For the controlled no-login demo, the separately hosted backend must explicitly enable `ALLOW_APP_SESSIONS=true`. The app requests a short-lived bearer automatically on the first user action after consent and stores it encrypted. Existing expiry and session isolation remain in effect.

Only the service address is public. **Never embed `DEMO_ACCESS_CODE`, Gnani/OpenAI keys, or any long-lived credential in an APK or `EXPO_PUBLIC_` variable.** Anonymous demo admission is off by default and permits paid-provider usage; do not treat rate limits or an APK as production authentication. See the backend hosting/security guide before public distribution.

The preview and production EAS profiles now set the public origin to:
https://cuebell.mathewjoseph.xyz

For local builds, set the same `EXPO_PUBLIC_API_URL` in `.env` or the shell. No provider secrets belong in this file. The EAS post-install hook rejects missing/placeholder routing configuration.

The v1.4.0 ARM64 preview APK and checksum are published at:
https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview

Version 1.4.0 / Android version code 7 adds experimental on-device noise reduction
under Settings → Listening, off by default. Stop listening before changing it.
The published ARM64 preview selects the tested FFT runtime. The station-PA study
found recognition regressions, so this release is for hands-on comparison.
Experimental backend latency settings also remain opt-in. Submit a fresh request
after updating. Provider-key changes remain server-only.

For the same native runtime, add the following property to the local Gradle
release build, using the verified distribution described in the native guide:

```sh
-PcuebellSherpaFftDir=/home/mathew/.cache/cuebell/sherpa-fft-v1-storage/dist
```

Native runtime source, pinned hashes and rebuild instructions:
/home/mathew/Arrakis/CueBell/mobile/modules/queue-listener/android/native/sherpa-fft/README.md

The signing certificate matches the 1.3.1 preview for in-place updates. Versioned APK and device checks are recorded at:
https://github.com/mathew1046/CueBell/blob/main/docs/VERIFICATION.md

```sh
npm ci
npm run typecheck
npm run lint
npm test
npm run check:service
npx expo prebuild --platform android --no-install
```

Then, from the generated `android` directory:

```sh
./gradlew :app:assembleRelease -PreactNativeArchitectures=arm64-v8a,x86_64 --max-workers=4
./gradlew :queue-listener:testDebugUnitTest
```

The standalone APK is generated at `android/app/build/outputs/apk/release/app-release.apk`. The command above includes emulators; for the phone-only release use `-PreactNativeArchitectures=arm64-v8a`. The downloadable v1.3.1 APK is ARM64 only. Its application ID is `app.cuebell.mobile`, scheme `cuebell` and encrypted session key `cuebell.connection.v1`. It does not read another app's private storage. To support older 32-bit phones, include `armeabi-v7a` explicitly when building.

**Local preview signing:** Expo's generated local release configuration uses its development/debug signing key. The preview is installable for review, not a production/store-signed distribution. Set up your own production keystore through a config plugin or use your own EAS project and signing credentials before publishing. Do not edit generated Android source; keep native service code under `modules/queue-listener` and configuration in `app.json` / config plugins.

An alternative internal build profile is provided in `eas.json`; EAS account setup and remote uploading/building are not performed automatically.

## Device check before use

### General listening tasks (v1.3.0)

CueBell now asks who/what to listen for and which spoken event should trigger an
alert, rather than requiring a queue token. A valid submitted request automatically
activates the task and starts monitoring after consent/permission checks; there is
no second confirmation tap. The home card shows the active task. An alert displays
the interpreted event, explicit location when heard, and
verbatim source speech. Existing queue-call sessions remain readable. Static UI
copy is translated offline; task summaries and clarifications use the request's
language, and original evidence is never sent to the UI translation generator.

Deploy the backend's `speech-event-v1` changes before testing this client against
the configured hosted origin. Rebuilding/installing an APK alone cannot replace
the remote system prompt. Submit a fresh request after deployment. Test train
14922 arrival, a name being called, and flight boarding; verify that a delay,
future arrival, wrong train, negation and unrelated conversation do not alert.
Test corrections and voice stop, including locked-screen notifications. These
are speech-transcript monitors, not live train tracking or general sound detectors.

### App language and alarm (v1.3.0)

The home language button now opens a scrollable dropdown rather than an announcement-language help page. English and 20 Indian languages have bundled, offline UI catalogs. Selecting a language immediately updates screens, help, accessibility labels, service status and native notifications, and saves the selection for the next launch. Announcement recognition remains automatic; original transcripts, token prefixes and leading zeros are not translated. Urdu and Sindhi interpolated identifiers are direction-isolated. Spoken alerts require a matching installed offline Android voice; unavailable voices do not fall back to a different language or a network voice.

Catalogs are stored in `src/lib/i18n/catalogs.json`. They are machine-generated and need native-speaker review before production. Bodo and Kashmiri are not offered because the configured generation source did not support them; no English-only catalog is presented as a translated language. To update public copy, run `node scripts/extract-translations.mjs`, then explicitly run `python3 scripts/generate-translations.py`. The latter contacts a translation service at development time only and preserves reviewed translations. Never submit user requests, announcements or private data to that script.

Normal token calls already default to visual, vibration and sound. Sound-enabled calls now use a bundled original 2.4-second, three-pulse alarm alongside vibration; explicit silent/vibration-only and visual-only preferences remain respected. Versioned notification channels apply the new sound without overwriting an existing Android channel. Android volume, notification permissions, channel settings and Do Not Disturb can still silence it. Changing language redraws existing notifications silently; it does not replay an alarm. Regenerate the local audio with `python3 scripts/generate-alarm.py` if needed.

Check dropdown dismissal, scrolling to the last language, switching back to English, persistence after force-stop, enlarged text, and a right-to-left language. Test alarms on a physical phone with vibration+sound, sound-only, vibration-only and visual-only preferences, including the locked screen and DND. Emulator/source checks cannot establish real-device audibility.

1. Open the app and verify it immediately shows the request workflow, without any server/pairing setup. Agree to processing and submit a request; the APK uses its build-time service automatically. HTTP and untrusted certificates remain rejected.
2. Test typed and spoken Malayalam / English requests, clarification, correction, exact zeroes and a non-target token.
3. Confirm microphone permission is requested only after Speak or a submitted listening request. A valid spoken or typed request must start monitoring without another tap; unclear/unsupported requests must not start it. Deny a permission and verify recovery via Android settings.
4. Test a consenting speaker's announcement. The waveform should react to nearby speech and settle in quiet; expand **Live captions** for finalized segments. Check a matching and a nonmatching event, then repeat, correct and cancel it.
5. Lock the screen and background the app. Verify the microphone notification remains, a known call reaches the phone, and Stop microphone releases capture. Test your OEM's battery restrictions. Do not infer this works from an emulator check.
6. Disable networking, microphone privacy and notification permission separately. Check degraded status, no stale audio replay, bounded reconnect, and recovery. Inspect sound/vibration channel settings and Do Not Disturb.
7. **Stop Listening** turns off the microphone and keeps the task and recent captions available for review. **Settings → Stop** clears local session events, requests and notifications even offline. A saved local suppression flag prevents an uncleared remote monitor from reappearing after restart; activation of a new request re-enables it. Expired credentials are replaced on a new request, never by silently replaying an old monitor. Unreachable remote sessions expire server-side; unsuccessful remote cleanup is reported separately.
8. Check TalkBack focus and announcements, enlarged system text and reduced motion. The waveform represents local microphone activity and becomes static with reduced motion. **Settings → Spoken token alerts** uses an installed offline Android voice when the monitor allows sound.
9. While monitoring, express that you want listening to stop, including an indirect request in a speech-provider-supported language. Repeat with the screen locked. A recognized intent should remove the microphone notification without reopening capture, retain the token/history and require explicit restart. Negated, quoted and PA/call-cancellation speech should not pause it. Intent is model-interpreted, not matched to a fixed phrase list; connectivity, speech/model mistakes and nearby speakers can affect it. If missed, use the app or notification stop control.

8 November release verification: 43 mobile workflow tests, 14 native unit tests, TypeScript, lint and all 20 Expo Doctor checks passed. Tests cover general tasks, automatic activation, cancellation, foreground-service handoff, localization, session cleanup and spoken-alert queuing. Live voice-stop recognition and physical-phone locked-screen behavior remain unverified. If saving stop suppression fails, the app tries removing the saved session; if both fail, retry Stop or clear CueBell storage in Android settings before closing the app.

## Privacy / lifecycle

The Kotlin foreground service owns microphone capture, framing, networking, heartbeat, reconnection, notification alerts and bounded in-memory event history. It starts from a visible Activity only, is non-sticky, has no boot receiver, and releases capture, sockets and its timed wake lock when stopped. PCM frames are exactly 1024 bytes; native capture must actually negotiate 16 kHz or it fails rather than relabelling samples. Buffers are bounded and not replayed after stalls. No audio files are created.

Session metadata (build-time origin, bearer credential, expiry and a local monitor-suppression flag) and the app language choice are encrypted in SecureStore. The native service also stores the language choice and its public UI catalog in private preferences so background notifications retain their language. Transcripts and captured audio are not written to app storage. The bundled alarm is public, generated audio, not a recording. No admission request is sent until a user acts after consenting. Android/OS diagnostics and the configured cloud providers have separate policies. The ongoing notification and alert channels can be controlled by the user in Android settings.

Current dependency audit: 12 moderate reports propagated from Expo/lint tooling's `glob` / `minimatch` dependency ranges; no high/critical reports at implementation time. Audit suggests incompatible SDK downgrades, which were not forced. Recheck and update within a compatible SDK before production.
