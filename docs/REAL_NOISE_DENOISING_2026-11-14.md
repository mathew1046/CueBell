# Recorded DNS5 noise: before/after evidence

14 November 2026. **The revised runtime fully enhanced all 16 recordings, but recognition preservation failed.** Background-quality estimates improved 16/16; among 11 reference-eligible Gnani pairs, one improved, six tied and four worsened. Raw audio remained the default, with no new public release at campaign close.

## Sources and method

Microsoft DNS Challenge 5 Track 2 Speakerphone supplied 12 near-speaker and four far-speaker noisy recordings, ten seconds each. Filename-hash selection preceded outcomes. Near selection initially used case-sensitive `Primary`; the separate far cohort used case-insensitive matching. This is not a representative public-address benchmark.

Inputs were converted to mono 16-kHz PCM16 without mixing, normalization, trimming or added noise/reverberation. Production Kotlin GTCRN and pinned FFT JNI ran on the I2404 phone through standalone `app_process` file replay, with a fresh engine per clip. Each output retained **160,000 samples and 16 ms causal alignment**, without end-of-stream flushing.

[Source project](https://github.com/microsoft/DNS-Challenge), [official archive](https://dnschallengepublic.blob.core.windows.net/dns5archive/V5_dev_testset.zip), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and [attribution/modifications](benchmarks/real-noise-2026-11-14/ATTRIBUTION.md).

## Runtime: better availability, unchanged successful waveforms

The original ≥32 ms single-call fallback fully enhanced **8/12 near + 3/4 far = 11/16 clips (68.75%)**. Rejected fallback outputs remain archived, not counted as successful denoising.

The revised policy tracks cumulative processing debt against the 32 ms interval, allowing transient overruns up to a **64 ms debt limit**. Invalid output/exceptions still fail open immediately, and a post-inference age check rejects stale output. It is not a hard end-to-end delay bound.

Final v4 replay enhanced **16/16 clips (100%), 5,008/5,008 frames**. Bypass WAVs matched inputs; all **11 previously successful outputs stayed byte-identical**.

| Cohort | Active frames | Processing median / p99 | Maximum call |
|---|---:|---:|---:|
| Near | 3,756/3,756 | 4.608 / 10.882 ms | 50.922 ms |
| Far | 1,252/1,252 | 4.682 / 13.280 ms | 51.201 ms |

P99 is the time below which 99% of measured calls finish. There were **14 completion-deadline misses**, maximum lateness **27.610 ms**, but no fallback, dropped frames or schedule rebases. Reset outputs matched. Fresh-engine ten-second replay does not pass the earlier strict gate or establish live-microphone, battery or long-session performance.

## Estimated audio quality

Official non-personalized DNSMOS estimates speech (SIG), background (BAK) and overall quality (OVRL), not human ratings, intelligibility, signal-to-noise ratio or recognition accuracy. One 9.01-second window leaves 0.99 seconds unscored per clip. No clean reference or subjective listening review exists.

| Equal clip weight, 16 pairs | Before | After | Improved |
|---|---:|---:|---:|
| BAK | 2.514 | 3.927 | 16/16 |
| SIG | 3.303 | 3.089 | 1/16 |
| OVRL | 2.340 | 2.778 | 15/16 |

Breathing was the only overall decline; far creaky noise the only speech improvement. PCM-limit sample counts were 239 before / 258 after, mostly far typing. These converted-PCM threshold counts do not prove historical clipping, and no normalization hid them. Initial quality results covered only 11 successful clips, not all 16.

## Actual Gnani recognition

Released Prisma, `indic-auto`, VAD and observation settings were held equal. Paired connections used paced 512-sample frames, randomized condition order and no reference hints. No Luna interpretation was measured.

Word error rate (WER) divides recognition errors by reference words. Corrected `unicode-marks-v2` scoring retains Indic combining marks; preliminary Python `\w` scores inflated word counts and remain separately archived.

| Final eligible cohort | Reference words | Before errors / WER | After errors / WER |
|---|---:|---:|---:|
| Nine near pairs | 183 | 36 / 19.67% | 58 / 31.69% |
| Two far pairs | 33 | 13 / 39.39% | 19 / 57.58% |
| All 11 pairs | 216 | **49 / 22.69%** | **77 / 35.65%** |

WER rose **12.96 percentage points**. Five incomplete references were excluded only from WER, not audio/quality reporting. Confirmations are not counted again.

Air-conditioning regression **15.38% → 92.31%** and far typing **20% → 60%** repeated. English-reference WER penalizes script changes as well as word errors, but dishwasher also worsened **28.57% → 71.43%** with English in both arms: substitutions rose four → 13, plus two insertions each. References were not independently re-transcribed. [Later diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md) separates script, alignment and level controls.

## Evidence and decision

[Campaign](benchmarks/real-noise-2026-11-14/) retains inputs, rejected fallback outputs, full pairs, hashes and provider records. Canonical summaries: [timing](benchmarks/real-noise-2026-11-14/v4-timing-summary.json), [quality](benchmarks/real-noise-2026-11-14/quality-final-summary.json), [ASR](benchmarks/real-noise-2026-11-14/asr-final-analysis.json). Original ZIP delivery paths were historical local artifacts, not promised checkout files.

Study usage was **26 Gnani connections / 600.776 seconds**, including confirmations; no new Luna/TTS. Historical checks included 487 backend tests, 25 DNSMOS tests and 33 JVM tests; not newly rerun here. Improved availability and background estimates do not justify default-on deployment.

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/REAL_NOISE_DENOISING_2026-11-14.md), including artifact identities and historical verification details.
