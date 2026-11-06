# Android app

Requires Node 24.3+ (or the SDK-supported Node 22.13+), Java 17, Android SDK / NDK compatible with Expo SDK 58. This custom Kotlin module **does not run in Expo Go**. The service origin is fixed at build time; provider secrets are never in the bundle. There is no URL field, pairing flow or developer settings screen in the app.

## Operator configuration (before building, not on the phone)

Copy `.env.example` to `.env` only if there is no existing configured file. Set `EXPO_PUBLIC_API_URL` to your actual deployed trusted HTTPS origin (no path/query/credentials). For the controlled no-login demo, the separately hosted backend must explicitly enable `ALLOW_APP_SESSIONS=true`. The app requests a short-lived bearer automatically on the first user action after consent and stores it encrypted. Existing expiry and session isolation remain in effect.

Only the service address is public. **Never embed `DEMO_ACCESS_CODE`, Gnani/OpenAI keys, or any long-lived credential in an APK or `EXPO_PUBLIC_` variable.** Anonymous demo admission is off by default and permits paid-provider usage; do not treat rate limits or an APK as production authentication. See the backend hosting/security guide before public distribution.

The preview and production EAS profiles now set the public origin to:
https://queuesaathi.mathewjoseph.xyz

For local builds, set the same `EXPO_PUBLIC_API_URL` in `.env` or the shell. No provider secrets belong in this file. The EAS post-install hook rejects missing/placeholder routing configuration.

The v1.1.0 ARM64 preview APK and checksum are published at:
https://github.com/mathew1046/CueBell/releases/tag/v1.1.0-preview

Local copy:
/home/mathew/Arrakis/CueBell/artifacts/CueBell-1.1.0-arm64.apk

This preview has the unchanged deployed service origin baked in; it is not an unconfigured UI-only build. Release notes record CueBell's actual packaging and physical-phone verification. The backend previously reported both providers configured, and a temporary hosted typed-intent test returned the expected token and preferences before cleanup. No phone microphone capture was started. Provider-key changes remain server-only and do not require an APK rebuild. Source checks include 16 mobile workflow/session/branding tests, including consent withdrawal during admission, recovery from backend-invalidated bearers and preservation of the hosted origin. Prior light/dark + 1.3× font-size emulator review does not establish low-literacy usability, TalkBack or real-phone reliability.

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

The standalone APK is generated at `android/app/build/outputs/apk/release/app-release.apk`. The command above includes emulators; for the phone-only release use `-PreactNativeArchitectures=arm64-v8a`. The downloadable v1.1.0 APK is ARM64 only. Its application ID is `app.cuebell.mobile`, scheme `cuebell` and encrypted session key `cuebell.connection.v1`. It does not read another app's private storage or remove the previous app. To support older 32-bit phones, include `armeabi-v7a` explicitly when building.

**Local preview signing:** Expo's generated local release configuration uses its development/debug signing key. The preview is installable for review, not a production/store-signed distribution. Set up your own production keystore through a config plugin or use your own EAS project and signing credentials before publishing. Do not edit generated Android source; keep native service code under `modules/queue-listener` and configuration in `app.json` / config plugins.

An alternative internal build profile is provided in `eas.json`; EAS account setup and remote uploading/building are not performed automatically.

## Device check before use

1. Open the app and verify it immediately shows the request workflow, without any server/pairing setup. Agree to processing and submit a request; the APK uses its build-time service automatically. HTTP and untrusted certificates remain rejected.
2. Test typed and spoken Malayalam / English requests, clarification, correction, exact zeroes and a non-target token.
3. Confirm no microphone permission request occurs until tapping Speak or Confirm/Start. Deny a permission and verify recovery via Android settings.
4. Test a consenting speaker's announcement; confirm token and counter. Repeat, correct and cancel it; inspect the timeline and correction notification.
5. Lock the screen and background the app. Verify the microphone notification remains, a known call reaches the phone, and Stop microphone releases capture. Test your OEM's battery restrictions. Do not infer this works from an emulator check.
6. Disable networking, microphone privacy and notification permission separately. Check degraded status, no stale audio replay, bounded reconnect, and recovery. Inspect sound/vibration channel settings and Do Not Disturb.
7. Stop & clear removes local session events, requests and token-call notifications even offline. A saved local suppression flag prevents an uncleared remote monitor from reappearing after restart; confirmation of a new request re-enables it. Expired credentials are replaced on a new request, never by silently replaying an old monitor. Unreachable remote sessions expire server-side; unsuccessful remote cleanup is reported separately.

## Privacy / lifecycle

The Kotlin foreground service owns microphone capture, framing, networking, heartbeat, reconnection, notification alerts and bounded in-memory event history. It starts from a visible Activity only, is non-sticky, has no boot receiver, and releases capture, sockets and its timed wake lock when stopped. PCM frames are exactly 1024 bytes; native capture must actually negotiate 16 kHz or it fails rather than relabelling samples. Buffers are bounded and not replayed after stalls. No audio files are created.

Only session metadata (build-time origin, bearer credential, expiry and a local monitor-suppression flag) is encrypted in SecureStore. Transcripts and audio are not written to app storage. No admission request is sent until a user acts after consenting. Android/OS diagnostics and the configured cloud providers have separate policies. The ongoing notification and alert channels can be controlled by the user in Android settings.

Current dependency audit: 12 moderate reports propagated from Expo/lint tooling's `glob` / `minimatch` dependency ranges; no high/critical reports at implementation time. Audit suggests incompatible SDK downgrades, which were not forced. Recheck and update within a compatible SDK before production.
