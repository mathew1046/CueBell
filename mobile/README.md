# CueBell client development

Expo shares screens and task logic across Android and browsers. Android adds a
Kotlin foreground microphone service; browsers **stop when the page is hidden**.
See [web development](../docs/WEB.md).

## Requirements and configuration

Use Node 24.3+ and npm (SDK 58 also supports Node 22.13+). Android needs Java 17
and compatible Android SDK/NDK. The native module cannot run in Expo Go.
Read [AGENTS.md](AGENTS.md) before changing Expo APIs.

From `mobile/`, copy [`.env.example`](.env.example) only if `.env` is absent.
Set `EXPO_PUBLIC_API_URL` to your trusted HTTPS relay origin, without path, query
or credentials. It is bundled at build time; EAS preview/production use
`https://cuebell.mathewjoseph.xyz`.

There is no pairing/server-URL screen. After consent and a user action, the app
requests an expiring bearer. The [backend](../backend/README.md) must explicitly
enable `ALLOW_APP_SESSIONS=true`. This allows paid usage, not production identity.
Never bundle provider keys, `DEMO_ACCESS_CODE` or long-lived credentials.

## Check and build Android

From `mobile/`:

```sh
npm ci
npm test
npm run typecheck
npm run lint
npm run check:service
npx expo prebuild --platform android --no-install
```

From generated `mobile/android/`:

```sh
./gradlew :queue-listener:testDebugUnitTest
./gradlew :app:assembleRelease -PreactNativeArchitectures=arm64-v8a,x86_64 --max-workers=4
```

Output relative to `mobile/`: `android/app/build/outputs/apk/release/app-release.apk`.
Use `-PreactNativeArchitectures=arm64-v8a` for ARM64 only. App ID:
`app.cuebell.mobile`; scheme: `cuebell`. Edit `modules/queue-listener`, `app.json`
or config plugins, never generated Android/iOS source.

### Noise-reduction runtime and signing

Normal builds use the checksum-pinned official sherpa-onnx AAR. The 1.4.0 and 1.4.1 ARM64
previews use the reviewed FFT runtime. Follow its [build/provenance guide](modules/queue-listener/android/native/sherpa-fft/README.md),
then add `-PcuebellSherpaFftDir=/absolute/path/to/verified/dist` to the ARM64 release
command. Gradle checks the tracked artifact lock, not just the directory.

Local previews use development/debug signing, not a store key. The 1.4.1
build verifies the same signing certificate as 1.4.0 for in-place updates. Configure production signing through a
config plugin or your EAS project. `eas.json` supplies an internal APK profile;
remote builds/uploads need separate setup.

[1.4.1 preview and checksum](https://github.com/mathew1046/CueBell/releases/tag/v1.4.1-preview):
version 1.4.1/code 8, ARM64 only. [Historical verification](../docs/VERIFICATION.md)
is not a guarantee for new builds.

On Linux ARM64, Android's standard x86-64 build tools require emulation
(such as QEMU) and matching x86-64 system libraries. An x86-64 Linux build
host avoids this extra setup.

## Task, language and audio behavior

A clear submitted request activates automatically after consent/permissions; no
second confirmation tap. Unclear requests must not activate. Alerts include the
interpreted event, location when heard and verbatim evidence. This monitors speech,
not live transport or general sounds. Use a matching `speech-event-v1` backend;
submit fresh requests after updates.

The 21 UI languages differ from Prisma's 10 speech languages. Machine-generated
catalogs need native-speaker review. Transcripts, identifiers and leading zeroes
are not translated. Android spoken alerts require a matching installed offline
voice, with no network/different-language fallback.

From `mobile/`, update copy with:

```sh
node scripts/extract-translations.mjs
python3 scripts/generate-translations.py
```

The second command contacts a translation service and preserves reviewed strings.
Never send private requests/announcements. Regenerate the original three-pulse
alarm with `python3 scripts/generate-alarm.py`. Permissions, channels, volume and
Do Not Disturb can silence alerts.

[Experimental denoising](../docs/NOISE_REDUCTION.md) is local, off by default and
changeable only while stopped; studies found recognition regressions.
[Pipeline latency settings](../docs/PIPELINE_OPTIMIZATION.md) also remain opt-in.

## Physical-device checklist

Use consenting speakers/synthetic identifiers. Record phone, OS, app/backend
versions and outcomes. Mocks/emulators do not establish capture or audibility.

1. Test typed/spoken setup, denial/recovery, clarification, leading zeroes and automatic activation.
2. Test matching/wrong subjects, negation, delayed events, repetition, correction/cancellation, waveform and final captions.
3. Background/lock the phone: verify microphone notification, known alert and notification stop. Repeat with battery restrictions.
4. Separately disable network, microphone privacy and notifications. Check gaps, bounded reconnect, no stale replay, sound/vibration, channels and Do Not Disturb.
5. **Home → Stop Listening** pauses capture, retaining task/history. **Settings → Clear task** clears local events/notifications even offline and reports failed remote cleanup. Older APKs may label this **Stop**. Suppression must prevent restoration; if suppression and session removal both fail, retry Clear task or clear app storage before closing.
6. Test voice stop visible/locked, then explicit restart. Negated, quoted and PA/cancellation speech should not pause. Nearby speakers can pause; retain manual controls.
7. Review TalkBack, large text, reduced motion, themes, language persistence, RTL and installed offline voices.

## Lifecycle and privacy

Android owns capture, framing, sockets/reconnect and alerts. It starts visibly,
is non-sticky, has no boot receiver and releases capture/sockets/timed wake lock
on stop. Audio negotiates 16 kHz mono, never relabelled; 1024-byte PCM16LE frames
use bounded buffers without stale replay.

Encrypted SecureStore uses `cuebell.connection.v1`; private preferences hold service
notification language/catalog data. Audio/transcripts stay in bounded memory, not
intentional recording files. See [privacy](../docs/PRIVACY.md),
[security](../SECURITY.md) and [architecture](../docs/ARCHITECTURE.md).
