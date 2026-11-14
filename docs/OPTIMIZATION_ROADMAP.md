# CueBell: Optimization Roadmap for the Gnani.ai Internship

Research date: 9 November 2026.

**Noise reduction is worthwhile, but the strongest upgrade would be a complete “noisy-venue robustness” improvement: cleaner audio, better speech detection, fewer wrong alerts, and measured response times.**

These recommendations follow inspection of CueBell’s capture and processing pipeline. CueBell already has background listening, corrections, duplicate suppression, captions, and voice stopping. The following work would add further technical depth. The recommendations are not implemented or measured results.

## 1. Add actual noise suppression — high priority

Currently, the waveform’s noise-floor calculation only changes the visualization. **It does not clean the audio sent to Gnani.**

Compare these options:

| Approach | Fit for CueBell | Effort |
|---|---|---|
| **Android `NoiseSuppressor`** | Fastest experiment; attaches to the existing microphone session. Availability and quality vary by phone. | Small |
| **WebRTC Audio Processing / SpeexDSP** | More controlled processing, with noise suppression and optional gain control. Suitable for a native audio pipeline. | Medium |
| **RNNoise** | Worth testing as a neural denoising candidate. Uses 48 kHz processing, requiring resampling and reframing around the current 16 kHz pipeline. | Larger |
| **DeepFilterNet** | A more involved speech-enhancement experiment; needs careful streaming, CPU, and latency integration. | Larger |

**Recommendation:** start with an Android suppression on/off comparison. Consider a controlled native DSP implementation if results vary substantially across devices.

The important complication: **a distant PA announcement can resemble background sound to a denoiser.** Evaluate whether it preserves names, numbers, prefixes, and short words—not just whether recordings sound cleaner.

RNNoise and DeepFilterNet would also introduce an additional speech-processing model beyond the current Gnani-based stack.

## 2. Tune Gnani’s speech detection and endpointing — high priority

The integration currently relies on the provider’s default voice-activity detection settings.

Gnani exposes controls for:

- Speech-detection threshold.
- Silence required before completing an utterance.
- Minimum speech/segment duration.
- Maximum uninterrupted speech duration.

These directly affect whether CueBell hears a quiet announcement, cuts off a short number, or waits too long before interpreting it.

Experiment with **separate settings for spoken setup and announcement monitoring**. A person describing a task needs different pause handling from a short PA announcement.

Treat settings as measured configurations; increasing the threshold can reject distant speech. Gnani’s VAD settings are connection-level, so changing them requires reconnecting.

## 3. Add microphone-quality diagnostics

A useful addition would be detecting:

- **Clipping:** the microphone signal is overloaded.
- **Very weak input:** speech may be too distant.
- **Sustained silence or a silenced microphone.**
- **Audio-route changes:** for example, unexpectedly switching microphones when a headset connects.

Give actionable guidance such as “Move closer to the announcement speaker.”

Also test gentle rumble filtering and gain adjustment. Gain needs limits: amplifying everything also amplifies noise, and digital processing cannot recover already-clipped audio.

This would make the app’s listening status much more informative than a moving waveform.

## 4. Improve speech completion handling — a concrete code opportunity

The backend currently reacts to finalized transcripts but ignores Gnani’s `speech_start` and `processing` events.

That matters during spoken setup: **someone can begin a second sentence while the app’s transcript-based quiet timer is still running**, before the next final transcript arrives.

Track the provider’s speech state so the app can distinguish:

- The user has stopped speaking.
- Speech is still ongoing.
- Speech has ended, but transcription is processing.

Relevant code:

/home/mathew/Arrakis/CueBell/backend/app/main.py:336–377

This is a source-level concern to reproduce and test, rather than a confirmed failure from a live run.

## 5. Make alert latency predictable — high priority

Another concrete opportunity: pending alerts wait until interpretation finishes **and the transcript queue becomes empty**. Under sustained speech, unrelated queued segments can keep delaying an alert.

The same branch also skips heartbeat sending:

/home/mathew/Arrakis/CueBell/backend/app/main.py:462–471

Recommended improvements:

- Send health heartbeats independently of interpretation.
- Measure transcript queue age and model-processing time.
- Evaluate bounded batching of queued transcripts.
- Preserve correction/cancellation ordering when changing scheduling.

The existing correction protection is valuable. The goal is to keep it while preventing unrelated speech from indefinitely holding up delivery.

The current 1.2-second correction grace overlaps model processing—it is not necessarily an additional 1.2 seconds. Measure each stage before adjusting it.

## 6. Optimize multilingual and identifier recognition

For the Malayalam demonstration, compare:

- Automatic language detection versus a Malayalam–English language hint.
- `verbatim`, `codemix`, and `transcribe` output formats.
- Small, general domain vocabulary hints where useful.

Evaluate identifiers such as:

- `43` versus `34`.
- `442` versus `441`.
- `P042` versus `P024`.
- Names and train/flight identifiers.
- Mixed-language announcements.

**Keep the user’s target out of ASR hints.** Otherwise, recognition can become biased toward the answer CueBell is waiting for.

This is particularly relevant to Gnani: it demonstrates practical understanding of Indic speech and code-switching.

## 7. Handle reverberation and competing speech as separate problems

There are several different acoustic challenges:

| Problem | Useful direction |
|---|---|
| Fan, AC, traffic rumble | Noise suppression and filtering |
| Echoey station or hospital hall | Dereverberation experiments and microphone placement |
| Nearby people talking over the announcement | Source-separation research or a better audio source |
| CueBell hearing its own spoken alert | Playback-feedback testing; echo cancellation where supported |

Ordinary denoising does not establish which speaker is the official announcer. Likewise, acoustic echo cancellation for the phone’s own playback does not remove arbitrary room reverberation.

**PA-versus-nearby-conversation discrimination** could become a strong longer-term research contribution, but it needs representative recordings and careful evaluation.

## 8. Improve long-session reliability

The backend renews the Gnani connection before its 15-minute limit, currently through a disconnect/reconnect cycle.

Useful improvements:

- Measure the actual coverage gap during renewal.
- Explore controlled provider handover.
- Test Wi-Fi/mobile-data transitions.
- Test microphone interruptions and headset changes.
- Run screen-locked sessions long enough to cross a renewal boundary.

CueBell already has reconnect and gap reporting. The next step is demonstrating how well they behave on real phones.

## 9. Measure battery, bandwidth, and processing cost

At the current format, raw microphone audio is approximately **115 MB per hour before transport overhead**.

Track:

- Battery drain per listening hour.
- CPU and memory with each denoiser.
- Audio-processing time and dropped frames.
- Mobile-data usage.
- Gnani usage and text-model calls per hour.

Keep DSP native and buffers bounded. The continuous realtime protocol should not simply start dropping “silent” frames to save bandwidth; that needs an explicitly designed transport strategy.

These measurements would make the project much more convincing as something usable during a long hospital wait.

## 10. Strengthen alert delivery

Two useful accessibility refinements:

- **A “test my alert” action** to verify vibration, sound, and notification delivery on the actual phone.
- **Distinct vibration patterns for a call and a correction**, so users can distinguish them without reading.

Also test whether the existing optional spoken alerts get picked up again by the microphone.

## The most important addition: a reproducible audio benchmark

This is what would make the optimizations stand out in the application.

Start with **60–100 labelled examples**, including clean speech, fan noise, crowd speech, distant playback, and mixed-language announcements. Include different speakers, and reserve speakers or recording sessions for final evaluation.

Compare:

1. Current baseline.
2. Noise suppression enabled.
3. Noise suppression plus tuned endpointing.

Measure:

| Metric | Why it matters |
|---|---|
| Correct event/identifier detection | A single wrong digit can invalidate an otherwise good transcript |
| Target-alert recall | How many relevant announcements are caught |
| False alerts per listening hour | Whether prolonged monitoring remains useful |
| Correction and cancellation handling | Whether later speech properly updates decisions |
| Median and p95 announcement-end-to-alert latency | Whether alerts arrive promptly |
| Battery and processing cost | Whether the improvement is practical |

Include long stretches with **no target announcement**. A short successful demo cannot establish the false-alert rate.

The existing demo and automated tests are useful; this benchmark would add the acoustic evidence currently missing from the written verification.

## Recommended priorities

For the immediate application:

1. **Capture a baseline benchmark.**
2. **Trial Android noise suppression.**
3. **Tune Gnani endpointing and handle speech-state events.**
4. **Separate heartbeats from interpretation and measure alert delays.**
5. **Show a real before/after result in the demo and README.**

That gives the project a strong engineering story: **identify failure modes, compare approaches, measure trade-offs, and improve an Indic speech application.**

As of the research date, the current challenge’s published deadline is **10 November 2026, 23:59 IST**, and interview shortlisting also uses verified engagement on nominated public posts—so leave time to publish the evidence.

## References

- Gnani streaming controls: https://docs.gnani.ai/api/STT/stt-websocket
- Prisma language/format options: https://docs.gnani.ai/api/STT/models/prisma-v3.md
- Android noise suppression: https://developer.android.com/reference/android/media/audiofx/NoiseSuppressor
- WebRTC audio processing: https://webrtc.googlesource.com/src/+/main/modules/audio_processing/g3doc/audio_processing_module.md
- RNNoise: https://gitlab.xiph.org/xiph/rnnoise
- DeepFilterNet: https://github.com/Rikorose/DeepFilterNet
- Challenge details: https://www.gnani.ai/internship
