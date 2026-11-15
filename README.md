# CueBell

**Hear the announcement. See your turn.**

CueBell turns spoken announcements into personal visual alerts, with optional vibration and sound. It is built for people who are deaf or hard of hearing, starting with a familiar problem: missing your token call in a busy pharmacy.

[Try the web app](https://cuebell.mathewjoseph.xyz) · [Android preview](https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview) · [60-second demo guide](DEMO.md) · [Documentation](docs/README.md)

## A simple example

1. Type or say: **“Tell me when pharmacy token 442 is called. Vibrate.”**
2. Accept the processing disclosure and allow microphone access. A valid request starts listening automatically.
3. The announcement says: **“Token four four two, please go to counter two.”**
4. CueBell shows the matching call and counter, with the requested alert.

A non-matching token should not alert. Repeated calls are suppressed, and later corrections update the result. Live captions and listening status help the user check what was heard.

**Why it matters:** audio-only information should not require constant attention to a display or dependence on a companion. CueBell aims to make that information personal and visible. This is a working prototype, not a measured reduction in missed turns or a completed accessibility field trial.

## What is built

- **Android and web:** shared task setup, captions, history, accessible controls and alerts.
- **Natural-language tasks:** queue calls, a name being called or a stated transport announcement. No connection settings or API keys on the user's screen.
- **Gnani Prisma v3.0:** streaming speech recognition with automatic language selection (`indic-auto`).
- **Validated alerts:** structured text interpretation followed by source-evidence checks, correction handling and duplicate suppression.
- **Experimental noise reduction:** optional on-device GTCRN, with native Android and browser implementations. Off by default.
- **Multilingual interface:** English and 20 Indian languages. UI translations are not a guarantee of speech-recognition quality.

## How it works

```text
Spoken or typed request → active listening task
                                  ↓
Microphone → optional local denoising → Gnani Prisma
                                  ↓
Transcript → text interpretation → validation → personal alert
```

The backend keeps provider keys private. Audio goes to **Gnani**; requests and transcripts go to the configured **OpenAI text-model fallback**. Evon is not integrated, and CueBell does not claim a Gnani-only model stack. The target is not used as a speech-recognition hint.

The interface uses React Native, Expo and TypeScript. Android capture uses a Kotlin foreground service; web capture uses AudioWorklet. A Python/FastAPI relay manages sessions and the speech pipeline. See [architecture](docs/ARCHITECTURE.md).

## Engineering results

The project evaluates both **speed** and **whether the right alert survives**. A faster wrong token is not an improvement.

- **42.2% lower spoken-setup delay in a controlled comparison:** median speech-end-to-confirmation fell from **10.75 s to 6.21 s**, with six successful replays in each arm. This tested profile remains opt-in because broader monitoring quality regressed. [Pipeline results](docs/PIPELINE_OPTIMIZATION.md).
- **99.66% less transform scratch memory:** replacing GTCRN's quadratic DFT with a radix-2 FFT preserved the tested output while reducing transform tables/scratch from **4,210,688 to 14,336 bytes**. This is not total app memory. [Noise-reduction methods](docs/NOISE_REDUCTION.md).
- **More complete denoising under recorded-noise replay:** revised overload handling increased fully enhanced clips from **11/16 to 16/16**. Estimated background quality improved on all 16 clips, but recognition did not consistently improve, so denoising stays off by default. [Noise results](docs/NOISE_REDUCTION.md).

See [verification](docs/VERIFICATION.md) for reproducible checks and the distinction between automated tests, provider replays and real-device evidence.

Results are controlled experiments, not claims of reliable performance in every venue. Raw benchmark artifacts remain available alongside the reports.

## Try it

**Web:** open https://cuebell.mathewjoseph.xyz, enter a task and allow processing and microphone access. Keep the page visible and the screen unlocked while listening. Browser background listening is not supported.

**Android:** install the [v1.4.0 ARM64 preview](https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview) on Android 7 or later. It is development-signed, not a store release. Expo Go cannot run the native capture service. Device settings can interrupt background capture or suppress sound and vibration.

Use consenting speakers or staged audio for a demo. See [DEMO.md](DEMO.md) for a short script and expected outcomes.

## Develop

- [Backend setup](backend/README.md): Python 3.12+, provider configuration and one-worker hosting.
- [Android setup](mobile/README.md): Node.js 24+, native builds and device checks.
- [Web setup](docs/WEB.md): production export, exact origin allowlist and HTTPS/WSS.
- [Contributing](CONTRIBUTING.md): checks and review expectations.

Provider credentials belong only on the backend. Public demo admission can consume paid quota; it is not production authentication.

## Limits and responsible use

CueBell is a **supplemental aid**, not an official queue system, medical alarm or guaranteed notification service. Recognition errors, noise, nearby speech and network interruptions can cause missed or false alerts. Always check the venue display or staff. There is no offline recognition, queue-position prediction or PA-speaker identification.

Audio and transcript history are not saved to recording files or a database by the app/relay. Provider processing and retention terms still apply. See [privacy](docs/PRIVACY.md), [security](SECURITY.md) and the [impact and evaluation plan](docs/IMPACT.md).

## Team

**Mathew Joseph:** backend, speech/AI integration, Android background service, multilingual support, testing, deployment and releases.

**Devadathan M R:** mobile interface and navigation, live captions, waveform feedback, spoken alerts, accessibility controls and branding.

## License

No project-wide license has been selected. Public source availability does not grant reuse or redistribution rights. Bundled third-party components retain their own licenses and notices.
