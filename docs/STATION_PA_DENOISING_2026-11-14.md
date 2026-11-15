# Actual station PA recordings: denoising evidence

14 November 2026. **All five recordings enhanced successfully, and all three estimated-quality measures improved 5/5. Task-critical recognition was not reliably preserved.** Slough platform-four/time interpretation regressed repeatedly. Noise reduction remained experimental and off by default.

## Sources and method

Five complete field recordings total **188.171375 seconds**. Selection used recordists' descriptions before outcomes. Published high-quality MP3 previews contain real loudspeaker capture, station ambience, trains and nearby activity, including some automated PA voices.

| Recording | Duration | Source |
|---|---:|---|
| Indian station, arrival/departure | 55.458 s | [soundstew, 99516](https://freesound.org/people/soundstew/sounds/99516/) |
| Slough platform 4, described as 07:00 Reading | 23.214 s | [AlienXXX, 129351](https://freesound.org/people/AlienXXX/sounds/129351/) |
| Slough platform 3, stand-clear/train | 53.004 s | [AlienXXX, 129331](https://freesound.org/people/AlienXXX/sounds/129331/) |
| Distant Slough platform 2 | 27.098 s | [AlienXXX, 129353](https://freesound.org/people/AlienXXX/sounds/129353/) |
| Southall station PA | 29.397 s | [JWS24, 790794](https://freesound.org/people/JWS24/sounds/790794/) |

[Attribution, individual licenses and hashes](benchmarks/station-pa-2026-11-14/ATTRIBUTION.md) are retained. Durations above are rounded; the total uses sample precision.

Convert full previews to mono 16-kHz PCM16 without added speech/noise, normalization or delivered-input padding. Replay production GTCRN on I2404 with the unchanged v4 APK/FFT JNI, one thread, 32 ms packets, 16 ms signal delay and 64 ms cumulative-debt fallback. Bit-identical bypass and hashes verify inputs/exports.

Compare official non-personalized DNSMOS and actual Gnani Prisma v3 transcripts. Send each complete final transcript as one segment to the existing GPT-6 Luna observer/evidence validator with the same broad train/platform task. Withhold source names, descriptions and expected facts from both providers. This is component interpretation, not streaming alert latency.

## Runtime and estimated quality

**5/5 recordings, 5,883/5,883 frames** enhanced with no fallback, dropped frames, schedule rebases, calls ≥32 ms or completion-deadline misses. Two reset checks matched.

Processing median/p99/max was **3.213 / 11.154 / 24.323 ms** per 32 ms frame. P99 means 99% of measured calls finish below that value. Initialization was **63.8–69.8 ms**; **16 ms signal delay remains**. Each 23–55 second recording used a fresh engine: not live-microphone, long-session or battery validation.

| DNSMOS, equal recording weight | Before | After | Improved |
|---|---:|---:|---:|
| Speech, SIG | 1.250 | 2.261 | 5/5 |
| Background, BAK | 1.251 | 3.555 | 5/5 |
| Overall, OVRL | 1.151 | 1.898 | 5/5 |

These learned estimates include non-speech train noise; they are not human ratings or accuracy. Overall remains below 2/5. No clean counterpart or independent full transcript supports full word error rate (WER), signal-to-noise improvement or clean-reference scoring. Uploader descriptions are partial annotations only.

## Recognition and interpretation

Ten initial Gnani connections produced six nonempty transcripts: three complete pairs. No provider errors or unfinished utterance IDs were reported. Empty outcomes remain included.

| Recording | Paired result |
|---|---|
| Indian station | Raw retains Narmada Express and `eight two three four`; enhanced loses them. Enhanced gives a generic train-delay match. Raw Luna times out twice, so paired interpretation is inconclusive |
| Slough platform 4 | Raw yields validated platform-four/0700 interpretation, though Reading is already “Breeding.” Enhanced changes wording to “Four four for the eight seven hundred hours” and yields `UNCERTAIN`, without location/identifiers |
| Slough through train | Neither yields usable words; enhanced has one empty final. No interpretation |
| Distant Slough PA | Neither yields speech-start/transcripts within the observation window. No demonstrated recovery |
| Southall | Both retain platform four/Paddington and yield validated matches. Enhanced omits calling points and changes first service-time wording, while extracting 14:48 from repetition |

Seven Luna attempts completed five times and timed out twice, including one bounded retry. Broad matches do not establish transcription truth. Repeating Slough platform four and both empty pairs produced **six identical confirmation transcripts/statuses**, reproducing regression and missing speech; Luna was not repeated on identical text.

## Evidence and decision

[Campaign](benchmarks/station-pa-2026-11-14/) retains source/runtime identities and audio. See [timing](benchmarks/station-pa-2026-11-14/timing-summary.json), [quality](benchmarks/station-pa-2026-11-14/quality.json) and [provider summary](benchmarks/station-pa-2026-11-14/provider-summary.json). Historical ZIP paths are not promised checkout downloads; retained pairs are in `audio/before/` and `audio/after/`.

Usage: **16 Gnani connections / 792.246 seconds**, including confirmations; **seven Luna attempts**; no TTS. No provider/device rerun accompanied this edit. Preserve raw defaults; see [controlled diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md).

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/STATION_PA_DENOISING_2026-11-14.md), including source links, job identities and historical accounting.
