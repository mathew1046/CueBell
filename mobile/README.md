# CueBell client development

The Expo app shares screens and task logic across Android and browsers. Android
adds a Kotlin foreground microphone service. The browser implementation uses web
audio APIs and **stops listening when the page is hidden**. See the
[web guide](../docs/WEB.md) for browser builds and limitations.

## Requirements and configuration

Use Node 24.3+ and npm; Android builds also need Java 17 and an Expo SDK 58-compatible
Android SDK/NDK. The SDK also supports Node 22.13+. The custom native module does
not run in Expo Go. Follow [AGENTS.md](AGENTS.md) before changing Expo APIs.

From `mobile/`, copy [`.env.example`](.env.example) to `.env` only if no configured
file exists. Set `EXPO_PUBLIC_API_URL` to the trusted HTTPS relay origin, without
a path, query or credentials. This value is bundled at build time. The EAS preview
and production profiles use `https://cuebell.mathewjoseph.xyz`.

There is no server URL field or pairing screen. After consent and a user action,
the app requests an expiring bearer automatically. Its relay must explicitly set
`ALLOW_APP_SESSIONS=true`. This permits paid-provider usage and is not production
authentication. See [backend setup and admission controls](../backend/README.md).
Never put provider keys, `DEMO_ACCESS_CODE` or long-lived credentials in an APK,
web export or `EXPO_PUBLIC_` variable.

## Check and build Android

From `mobile/`, after configuring the public origin:

```sh
npm ci
npm test
npm run typecheck
npm run lint
npm run check:service
npx expo prebuild --platform android --no-install
```

From the generated `mobile/android/` directory:

```sh
./gradlew :queue-listener:testDebugUnitTest
./gradlew :app:assembleRelease -PreactNativeArchitectures=arm64-v8a,x86_64 --max-workers=4
```

The APK is `android/app/build/outputs/apk/release/app-release.apk`, relative to
`mobile/`. Use `-PreactNativeArchitectures=arm64-v8a` for an ARM64-only build.
The app ID is `app.cuebell.mobile`, with scheme `cuebell`. Keep native source in
`modules/queue-listener` and configuration in `app.json` or config plugins; do not
hand-edit generated Android/iOS source.

### Noise-reduction runtime and signing

Ordinary builds use the checksum-pinned official sherpa-onnx AAR. The published
1.4.0 ARM64 preview instead uses the reviewed FFT runtime. To reproduce that
variant, first follow the [native build and provenance guide](modules/queue-listener/android/native/sherpa-fft/README.md),
then add `-PcuebellSherpaFftDir=/absolute/path/to/verified/dist` to the Gradle
release command and build ARM64. Gradle checks the artifact against the tracked
lock; a directory path alone does not authorize a replacement binary.

Local preview release builds use a development/debug signing certificate, not a
production/store key. The 1.4.0 preview certificate matches 1.3.1 for in-place
updates. Configure your own production signing through a config plugin or your
own EAS project before publishing. `eas.json` provides an internal APK profile;
account setup, remote uploads and builds are not automatic.

[Download the 1.4.0 preview and checksum](https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview).
It is version 1.4.0 / Android code 7, ARM64 only. See
[verification](../docs/VERIFICATION.md) for historical checks, not a guarantee for
new builds.

## Task and language behavior

A request identifies who or what to listen for and the spoken event that matters.
A valid submitted request automatically activates after consent and permission
checks; there is no second confirmation tap. Unclear requests must not activate.
Alerts show the interpreted event, location when heard and verbatim evidence.
This is speech monitoring, not live train tracking or general sound detection.
Deploy a matching `speech-event-v1` backend and submit a fresh request after updates.

The app bundles 21 UI languages, independent of Prisma's 10 speech languages.
Catalogs are machine-generated and need native-speaker review. Original transcripts,
identifiers and leading zeroes are not translated. Spoken Android alerts require
a matching installed offline voice; there is no different-language/network fallback.

For copy changes, from `mobile/`:

```sh
node scripts/extract-translations.mjs
python3 scripts/generate-translations.py
```

The second command contacts a translation service at development time and preserves
reviewed translations. Never submit user requests or private announcements to it.
The original three-pulse alarm can be regenerated with
`python3 scripts/generate-alarm.py`. Notification permission, channel settings,
volume and Do Not Disturb can silence sound or vibration.

Experimental noise reduction is off by default and can be changed only while
stopped. It runs locally for setup and monitoring, but replay studies found
recognition regressions. See [noise reduction](../docs/NOISE_REDUCTION.md).
Backend latency experiments also remain opt-in; see
[pipeline optimization](../docs/PIPELINE_OPTIMIZATION.md).

## Physical-device checklist

Use synthetic identifiers and consenting speakers. Record the phone, OS, app
version, backend version and exact results. Mock tests and emulator views do not
establish microphone, vibration, audibility or locked-screen reliability.

1. Accept processing and test typed and spoken requests. Check permission denial/recovery, clarification, leading zeroes and automatic activation without another tap.
2. Test a matching event, a wrong subject, negation, a future/delayed event, repetition, correction and cancellation. Check waveform activity and finalized live captions.
3. Lock the screen and background the app. Verify the microphone notification, a known alert and the notification stop control. Repeat with the phone's battery restrictions enabled.
4. Disable networking, microphone privacy and notification permission separately. Verify gap warnings, bounded reconnect and no stale-audio replay. Test sound/vibration combinations, channels and Do Not Disturb.
5. Check **Stop Listening** releases capture but retains the task/history. **Settings → Stop** must clear local events and notifications, including offline, and report failed remote cleanup. The saved suppression flag must prevent the old monitor returning after restart. If suppression and session removal both fail, retry Stop or clear app storage before closing.
6. Test voice stop while visible and locked, then explicit restart. Negated, quoted and PA/cancellation speech should not pause it. Nearby speakers can also pause it; use manual stop if recognition fails.
7. Check TalkBack, enlarged text, reduced motion, both themes, language persistence and right-to-left layout. Test installed offline spoken-alert voices on the phone.

## Lifecycle and privacy

The Android service owns capture, PCM framing, networking, reconnect and local
alerts. It starts from a visible Activity, is non-sticky, has no boot receiver and
releases capture, sockets and its timed wake lock on stop. Audio must negotiate
16 kHz mono; it is not relabelled. Frames are 1024-byte PCM16LE, with bounded
buffers and no replay after stalls.

Session metadata uses encrypted SecureStore (`cuebell.connection.v1`). The service
keeps notification language/catalog data in private preferences. Audio/transcripts
remain in bounded memory, not intentional recording files. See [privacy](../docs/PRIVACY.md),
[security](../SECURITY.md), [architecture](../docs/ARCHITECTURE.md) and the
[documentation index](../docs/README.md).
