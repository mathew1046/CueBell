# Android app

Requires Node 24.3+ (or the SDK-supported Node 22.13+), Java 17, Android SDK / NDK compatible with Expo SDK 58. This custom Kotlin module **does not run in Expo Go**. There are no provider secrets or fixed backend URLs in the app bundle.

```sh
npm ci
npm run typecheck
npm run lint
npx expo prebuild --platform android --no-install
```

Then, from the generated `android` directory:

```sh
./gradlew :app:assembleRelease -PreactNativeArchitectures=arm64-v8a,x86_64 --max-workers=4
./gradlew :queue-listener:testDebugUnitTest
```

The standalone APK is generated at `android/app/build/outputs/apk/release/app-release.apk`. ARM64 is for modern phones; x86_64 is included for emulator checks. To support older 32-bit phones, include `armeabi-v7a` explicitly when building.

**Local preview signing:** Expo's generated local release configuration uses its development/debug signing key. The preview is installable for review, not a production/store-signed distribution. Set up your own production keystore through a config plugin or use your own EAS project and signing credentials before publishing. Do not edit generated Android source; keep native service code under `modules/queue-listener` and configuration in `app.json` / config plugins.

An alternative internal build profile is provided in `eas.json`; EAS account setup and remote uploading/building are not performed automatically.

## Device check before use

1. Pair with your own publicly trusted HTTPS backend. App connections intentionally reject HTTP and untrusted certificates.
2. Test typed and spoken Malayalam / English requests, clarification, correction, exact zeroes and a non-target token.
3. Confirm no microphone permission request occurs until tapping Speak or Confirm/Start. Deny a permission and verify recovery via Android settings.
4. Test a consenting speaker's announcement; confirm token and counter. Repeat, correct and cancel it; inspect the timeline and correction notification.
5. Lock the screen and background the app. Verify the microphone notification remains, a known call reaches the phone, and Stop microphone releases capture. Test your OEM's battery restrictions. Do not infer this works from an emulator check.
6. Disable networking, microphone privacy and notification permission separately. Check degraded status, no stale audio replay, bounded reconnect, and recovery. Inspect sound/vibration channel settings and Do Not Disturb.
7. Stop & clear removes local session events, requests and token-call notifications even offline. A saved local suppression flag prevents an uncleared remote monitor from reappearing after restart; confirmation of a new request re-enables it. Disconnect deletes the encrypted credential locally even if remote deletion fails. Unreachable remote sessions expire server-side; the app reports unsuccessful remote cleanup separately.

## Privacy / lifecycle

The Kotlin foreground service owns microphone capture, framing, networking, heartbeat, reconnection, notification alerts and bounded in-memory event history. It starts from a visible Activity only, is non-sticky, has no boot receiver, and releases capture, sockets and its timed wake lock when stopped. PCM frames are exactly 1024 bytes; native capture must actually negotiate 16 kHz or it fails rather than relabelling samples. Buffers are bounded and not replayed after stalls. No audio files are created.

Only connection metadata (backend origin, bearer credential, expiry and a local monitor-suppression flag) is encrypted in SecureStore. Pairing codes, transcripts and audio are not written to app storage. Android/OS diagnostics and the configured cloud providers have separate policies. The ongoing notification and alert channels can be controlled by the user in Android settings.

Current dependency audit: 12 moderate reports propagated from Expo/lint tooling's `glob` / `minimatch` dependency ranges; no high/critical reports at implementation time. Audit suggests incompatible SDK downgrades, which were not forced. Recheck and update within a compatible SDK before production.
