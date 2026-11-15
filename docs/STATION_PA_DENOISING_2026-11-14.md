# Actual station PA recordings: denoising evidence

Date: 14 November 2026.

## Outcome

**All five field recordings were fully enhanced, and estimated speech, background and overall quality improved on all five. Task-critical recognition was not reliably preserved.** The Slough platform-four pair lost useful platform/time interpretation, and the regression repeated. Noise reduction remained experimental and off by default.

## Sources and scope

Five complete recordings, **188.171375 seconds total**, contain actual PA announcements, station ambience, passing trains and nearby activity. Selection used recordists' descriptions before outcomes were available. The sources are lossy published high-quality MP3 previews of uploaded field recordings. Some PA voices are automated, but were captured through loudspeakers in real surroundings.

| Recording | Duration | Source-described content | Source |
| --- | ---: | --- | --- |
| Indian railway station | 55.458 s | Arrival/departure announcements | [soundstew, 99516](https://freesound.org/people/soundstew/sounds/99516/) |
| Slough, platform 4 | 23.214 s | 07:00 service to Reading | [AlienXXX, 129351](https://freesound.org/people/AlienXXX/sounds/129351/) |
| Slough, platform 3 | 53.004 s | Stand-clear announcement and passing train | [AlienXXX, 129331](https://freesound.org/people/AlienXXX/sounds/129331/) |
| Slough, distant platform 2 | 27.098 s | Non-stopping train, two platforms away | [AlienXXX, 129353](https://freesound.org/people/AlienXXX/sounds/129353/) |
| Southall | 29.397 s | Station PA platform announcement | [JWS24, 790794](https://freesound.org/people/JWS24/sounds/790794/) |

[Attribution, individual licenses and source hashes](benchmarks/station-pa-2026-11-14/ATTRIBUTION.md) are retained. The total uses full sample precision; table durations are rounded.

## Method

1. Convert each complete preview to mono 16 kHz PCM16. Preserve content and level, with no added speech, noise, mixing or delivered-input padding.
2. Replay production GTCRN on the I2404 phone with a bit-identical bypass control. Export only fully active enhancement with verified hashes, original length and causal alignment.
3. Use the previously built v4 APK and pinned FFT JNI unchanged: one inference thread, 512-sample / 32 ms pacing, 16 ms alignment delay and 64 ms cumulative-debt fallback. Invalid output still fails open immediately.
4. Compare official non-personalized DNSMOS and actual Gnani Prisma v3 transcripts with released language/VAD settings. Reference text, expected platform numbers and source descriptions are not ASR hints.
5. Pass each complete final transcript as one segment to the existing GPT-6 Luna observer/evidence validator, using the same broad train/platform task. Source names and expected facts are withheld. This measures downstream interpretation, not streaming alert latency.

## Device and estimated-quality results

All **5/5 recordings** were fully enhanced: **5,883/5,883 frames** active, no fallback, dropped frames, schedule rebases, calls ≥32 ms or completion-deadline misses. Two fresh-engine reset checks produced identical PCM.

Processing median: **3.213 ms**, p99 **11.154 ms**, maximum **24.323 ms** per 32 ms frame. Initialization: **63.8–69.8 ms** per recording. The **16 ms signal delay remains**. Each 23–55 second recording used a fresh engine. These are file-replay measurements, not live microphone, long-session or battery results.

| DNSMOS estimate, equal weight per recording | Before | After | Improved |
| --- | ---: | ---: | ---: |
| Speech, SIG | 1.250 | 2.261 | 5/5 |
| Background, BAK | 1.251 | 3.555 | 5/5 |
| Overall, OVRL | 1.151 | 1.898 | 5/5 |

Scores cover full recordings, including non-speech train noise. They are learned estimates, not human ratings or recognition proof. Overall estimates remain below **2/5** after processing, so “pristine speech” would overstate the result. There is no clean counterpart or independently verified full transcript: **no full WER, SNR improvement or clean-reference score is supported**. Uploader platform/service descriptions are partial annotations only.

Evidence: [timing summary](benchmarks/station-pa-2026-11-14/timing-summary.json), [quality results](benchmarks/station-pa-2026-11-14/quality.json).

## Actual recognition and interpretation

Ten initial Gnani connections produced six nonempty transcripts, covering three complete pairs. No provider error messages or unfinished utterance IDs were reported. Empty and inconclusive outcomes remain included.

| Recording | Recognition observation | Luna component outcome |
| --- | --- | --- |
| Indian station | Both retain parts of the bilingual announcement. Raw includes Narmada Express and `eight two three four`; enhanced loses those details. No complete verified reference exists | Enhanced gives a generic train-delay match without identifiers. Raw times out twice at the unchanged 12-second timeout, making the paired interpretation inconclusive |
| Slough, platform 4 | Raw: `Platform four for the O Seven Hundred Hours`; enhanced: `Four four for the eight seven hundred hours`. Uploader identifies platform 4 and 07:00 Reading. Raw already renders Reading as Breeding | Raw yields a validated platform-four/0700 match. Enhanced yields `UNCERTAIN`, no location or identifiers. This is a task-relevant regression despite higher quality estimates |
| Slough, through train | Neither yields usable words. Raw receives only connection-ready; enhanced returns one empty final transcript | Excluded from interpretation because there is no usable transcript |
| Slough, distant PA | Neither yields speech-start or transcript messages within the fixed observation window | Excluded; no demonstrated recovery of the distant announcement |
| Southall | Both retain platform four and London Paddington. Enhanced omits calling-point text and changes the first rendering of the service time | Both yield validated platform-four/Paddington matches. Enhanced also extracts 14:48 from repeated wording |

Luna usage: **seven requests**, five completed and two timed out on the raw Indian transcript, including one bounded retry. Both failed attempts remain in evidence. A broad match does not verify every word/service detail or constitute independent transcription truth.

Slough platform four and both no-transcript pairs were repeated with identical audio/settings. **All six confirmation transcripts and statuses matched the first attempts**, reproducing the platform/time regression and missing speech. Confirmations are separate; Luna was not rerun on identical transcripts.

Evidence: [provider summary](benchmarks/station-pa-2026-11-14/provider-summary.json), [initial ASR](benchmarks/station-pa-2026-11-14/asr/), [ASR confirmations](benchmarks/station-pa-2026-11-14/asr-confirmation/), [Luna](benchmarks/station-pa-2026-11-14/luna/), [Luna retry](benchmarks/station-pa-2026-11-14/luna-retry/).

## Delivery, verification and usage

Root: [`benchmarks/station-pa-2026-11-14/`](benchmarks/station-pa-2026-11-14/). It retains source/runtime hashes, before/after evidence, quality scores, device timing, transcripts and provider outcomes. Every provider input hash matched its corresponding delivered WAV; all five pairs were included. Source descriptions were withheld from both providers.

Historical local delivery: `artifacts/CueBell-station-pa-before-after-2026-11-14.zip` and the matching unpacked directory. The clearest task comparison was `before/02-slough-platform-four.wav` versus `after/02-slough-platform-four.wav` within that directory. These artifact paths describe the original delivery, not files guaranteed in this checkout. Retained audio is under the benchmark's `audio/before/` and `audio/after/` directories.

- Study: **16 Gnani connections / 792.246 connection-seconds**, including six confirmations; **7 Luna attempts**, five complete and two timeouts; no TTS.
- Cumulative usage at study close: **95.2974/120 Gnani minutes**, **426/600 Luna attempts**. Remaining: **24.7026 Gnani minutes**, **174 Luna attempts**.
- Failed, empty and inconclusive outcomes are not successful recognition. No full-reference WER or live alert latency is claimed. This documentation audit did not rerun providers or device tests.

## Decision

Successful native replay and improved estimated audio quality do not qualify a default-on release. Preserving platform and service-time details matters more to CueBell than background score alone. Keep the raw baseline and experimental opt-in; see the [later controlled diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md) for script, alignment, level and vendor-denoiser controls.
