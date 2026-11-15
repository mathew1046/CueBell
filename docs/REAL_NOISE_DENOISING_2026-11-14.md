# Recorded DNS5 noise: before/after evidence

Date: 14 November 2026. Follow-up to the [original native device gate](NOISE_REDUCTION_BENCHMARK_2026-11-14.md).

## Outcome

**The revised runtime fully enhanced all 16 recordings, and background-quality estimates improved on all 16. Recognition preservation did not pass.** Of 11 reference-eligible Gnani pairs, one improved, six tied and four worsened. Two regressions repeated in confirmation trials.

At this campaign's close, the public 1.3.1 release remained the baseline, with no new public release. The experimental branch remained off by default. Deferring latency optimization did not remove the recognition problem. This audio delivery was not a release qualification.

## Sources and method

- Microsoft DNS Challenge 5 development set, Track 2 Speakerphone: **16 existing noisy recordings**, 12 near-speaker and four far-speaker, each ten seconds.
- Filename-hash selection preceded outcomes. The first near selection used case-sensitive `Primary`; the separate far cohort corrected that limitation with case-insensitive matching. This is a small sample, not a representative public-address benchmark.
- Only input preparation: conversion to mono PCM16 at 16 kHz. No generated speech/noise, artificial mixing, normalization, trimming or added reverberation.
- Production Kotlin GTCRN reducer and pinned FFT JNI ran on the I2404 phone in standalone `app_process` file replay, not a live microphone/foreground-service test. Each clip used a fresh engine.
- Each output retained **160,000 samples** and the **16 ms causal alignment delay**. Only the partial final frame was internally zero-filled; no output padding or end-of-stream flush.

Sources: [project](https://github.com/microsoft/DNS-Challenge), [official archive](https://dnschallengepublic.blob.core.windows.net/dns5archive/V5_dev_testset.zip), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [attribution and modifications](benchmarks/real-noise-2026-11-14/ATTRIBUTION.md).

## Runtime improvement: availability, not a new waveform

The original single-call ≥32 ms policy fully enhanced **8/12 near and 3/4 far clips**. Five fallback outputs remain in the evidence but are not labeled fully denoised.

The revised policy permits recoverable transient overruns, tracking cumulative debt with a **64 ms limit** against the same **32 ms frame interval**. Exceptions and invalid results still fail open immediately. A post-inference frame-age check rejects excessively old output after a synchronous native stall. This is not a hard end-to-end latency bound.

Final v4 replay fully enhanced **12/12 near and 4/4 far clips**, with **5,008/5,008 active frames**. Fully enhanced availability rose from **11/16 (68.75%) to 16/16 (100%)**. Bypass WAVs matched their inputs, and all **11 previously successful outputs were byte-identical**. The policy changed availability without changing those enhanced waveforms.

| Cohort | Active frames | Processing p50 / p99 | Max call | Calls ≥32 ms | Peak debt |
| --- | ---: | ---: | ---: | ---: | ---: |
| Near | 3,756 / 3,756 | 4.608 / 10.882 ms | 50.922 ms | 3 | 18.913 ms |
| Far | 1,252 / 1,252 | 4.682 / 13.280 ms | 51.201 ms | 3 | 22.028 ms |

There were **14 completion-deadline misses**, maximum lateness **27.610 ms**, but no fallback, dropped frames or schedule rebases. Both reset checks stayed active with identical outputs. The separate 16 ms signal delay remains. These fresh-engine ten-second replays do not pass the earlier strict latency gate or establish battery, long-session or live-microphone performance.

APK SHA-256: `b9318ebbb40a85633063175e7f478e492754faacd18889d2f74dbcd9926e7ac9`. Model/runtime locks and compiled-source hashes remain in the evidence.

## Estimated audio quality

Official non-personalized DNSMOS: SIG estimates speech quality, BAK background quality and OVRL overall quality. Higher is better. These are **model estimates**, not human ratings, intelligibility, SNR or recognition accuracy. No paired clean reference exists. The scorer uses one 9.01-second window per ten-second clip, leaving 0.99 seconds unscored; it does not align or normalize audio. No subjective listening evaluation is claimed.

### Initial successful outputs only

| Cohort | Pairs | BAK before → after | SIG before → after | OVRL before → after |
| --- | ---: | ---: | ---: | ---: |
| Near | 8 | 2.441 → 3.941 | 3.369 → 3.096 | 2.352 → 2.812 |
| Far | 3 | 2.906 → 3.838 | 3.280 → 3.111 | 2.502 → 2.723 |

Background improved on all 11; overall improved on ten; speech quality fell on all 11. Runtime exclusions mean these are not the full 16-clip results.

### Final complete output set

| Cohort | Pairs | BAK before → after | SIG before → after | OVRL before → after |
| --- | ---: | ---: | ---: | ---: |
| Near | 12 | 2.444 → 3.940 | 3.382 → 3.112 | 2.355 → 2.828 |
| Far | 4 | 2.727 → 3.889 | 3.065 → 3.022 | 2.295 → 2.627 |
| All, equal clip weight | 16 | 2.514 → 3.927 | 3.303 → 3.089 | 2.340 → 2.778 |

Background improved on **16/16**, overall on **15/16**, and speech on **1/16**. The other 15 speech estimates fell. Near breathing was the only overall decline, **3.060 → 3.017** (approximately -0.042 using unrounded scores); far creaky noise was the only speech improvement.

PCM-limit sample counts were **239 before / 258 after**. Far typing accounted for 238 before and all 258 after; near mouse clicks had one before and none after. These are converted-PCM threshold counts, not proof of historical clipping. No gain normalization hid these changes.

## Actual Gnani recognition

Released Prisma, `indic-auto`, VAD and observation settings were held equal. Reference text was not sent as a hint. Audio used 512-sample paced frames; paired connections ran concurrently with randomized condition order. No Luna calls were needed.

Initial eligibility required fully enhanced output and a complete source reference: five near pairs and two far pairs. References with unknown-speech markers were excluded from numerical WER.

| Initial cohort | Reference words | Before errors / WER | After errors / WER |
| --- | ---: | ---: | ---: |
| Near, five pairs | 94 | 13 / 13.83% | 21 / 22.34% |
| Far, two pairs | 33 | 13 / 39.39% | 19 / 57.58% |

Initial outcomes: one improved, four tied, two worsened. Both regressions repeated: near air conditioning **15.38% → 92.31%**, far typing **20.00% → 60.00%**, identical rates in the first and confirmation trials.

### Final coverage: 11 eligible pairs out of 16

After v4 recovered all audio, the four remaining reference-eligible near recordings were tested. Five incomplete references remained excluded: near water, breathing and cutlery; far baby and creaky noise. Their audio/quality results remain included.

| Final cohort | Reference words | Before errors / WER | After errors / WER |
| --- | ---: | ---: | ---: |
| Near, nine pairs | 183 | 36 / 19.67% | 58 / 31.69% |
| Far, two pairs | 33 | 13 / 39.39% | 19 / 57.58% |
| All 11 pairs | 216 | 49 / 22.69% | 77 / 35.65% |

Aggregate WER increased **12.96 percentage points**, calculated from the counts. Confirmations are not counted again. Final directions: **one improved, six tied, four worsened**.

| Recording | Before WER | After WER | Result |
| --- | ---: | ---: | --- |
| Near baby | 31.82% | 22.73% | Improved |
| Near typing | 5.26% | 5.26% | Tied |
| Near air conditioning | 15.38% | 92.31% | Worse; English/Tamil-script change; repeated |
| Near dog | 45.00% | 70.00% | Worse; English/Tamil-script change |
| Near mouse clicks | 11.11% | 11.11% | Tied |
| Near clatter | 19.23% | 19.23% | Tied |
| Near creaky noise | 4.55% | 4.55% | Tied |
| Near dishwasher | 28.57% | 71.43% | Worse; English in both arms |
| Near door | 13.64% | 13.64% | Tied |
| Far breathing | 55.56% | 55.56% | Tied |
| Far typing | 20.00% | 60.00% | Worse; language/script and word changes; repeated |

Strict English-reference WER penalizes script changes as well as lexical errors. The air-conditioning reference begins “Naturally, curly hair runs in my family.” Enhanced recognition rendered most of it in Tamil script. Far typing already had mixed-language output before enhancement. These are recognizer interactions, not proof that listeners lose the same fraction of information. No transliteration/numeric rewriting was applied to improve scores. The [later diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md) tests script, delay and level controls.

Dishwasher is a separate concern: both arms were labeled English, but substitutions rose from **four to 13**, with **two insertions** in each. Source transcripts contain awkward wording and were not independently re-transcribed; paired conditions use the same references. No end-to-end Luna alert accuracy was measured here.

### Scoring correction

The first tokenizer used Python `\w`, splitting Indic combining marks and inflating preliminary word counts. The corrected `unicode-marks-v2` scorer retains letters, combining marks, numbers and internal apostrophes after NFKC/lowercase normalization. Five accounting tests passed, including Indic word integrity. All rates here use corrected scoring. Original responses and preliminary scores remain unchanged; corrected initial scores are separate.

## Evidence and delivery

Root: [`benchmarks/real-noise-2026-11-14/`](benchmarks/real-noise-2026-11-14/).

| Evidence | Contents |
| --- | --- |
| `recordings/`, `recordings-far/` | Source/converted audio, transcripts, selection, hashes and device manifests |
| `device-real-noise-v3b/`, `device-real-noise-far-v3/` | Initial device frames, timings, bypass and rejected fallback output |
| `audio-near-initial/`, `audio-far-initial/` | Initial fully enhanced pairs, exclusions and provenance |
| `quality-near-initial.json`, `quality-far-initial.json` | Initial DNSMOS and signal statistics |
| `asr-initial-rescored.json` | Corrected initial WER |
| `asr-near-initial/`, `asr-far-initial/`, `asr-near-confirmation/`, `asr-far-confirmation/` | Immutable transcripts, events, language, timing, hashes and usage |
| `audio-near-v4/`, `audio-far-v4/` | All 16 final pairs with strict exports, hashes and provenance |
| `device-real-near-v4/`, `device-real-far-v4/`, `device-build-v4.json`, `v4-audio-verification.json`, [timing summary](benchmarks/real-noise-2026-11-14/v4-timing-summary.json) | Final runtime, inputs, active coverage and initial-output equivalence |
| `quality-near-v4.json`, `quality-far-v4.json`, [quality summary](benchmarks/real-noise-2026-11-14/quality-final-summary.json) | Full 16-clip quality results |
| `asr-near-completion/`, [final ASR analysis](benchmarks/real-noise-2026-11-14/asr-final-analysis.json) | Additional trials and canonical 11-pair scores with evidence hashes |

The original delivery contained **16 before/after pairs, 32 WAVs**, in `artifacts/CueBell-real-noise-before-after-2026-11-14.zip` and the corresponding unpacked directory. Those are historical local delivery paths, not files promised in this checkout. Use the benchmark evidence paths above for retained material.

## Historical verification and provider usage

- Backend: **487 passed**, one optional numerical-test module skipped. Isolated DNSMOS suite: **25 passed**, with two fixture scores matching the official implementation.
- Native: **33 JVM tests**, including **17 streaming-policy checks**, passed. Prior mobile suite: **49 passed**. Mobile lint/typecheck after policy changes, backend Ruff and whitespace checks passed.
- Delivered WAVs were mono PCM16, 16 kHz, 160,000 samples, with verified source/output hashes and attribution. These are campaign records, not newly rerun tests.
- Study usage: **26 Gnani connections / 600.776 seconds**, including confirmations; no new Luna or generated TTS.
- Cumulative authorized usage then: **82.093/120 Gnani minutes**, **419/600 Luna attempts**, unchanged **1,250 TTS characters**. No provider key was included.

**Decision:** demonstrated noise suppression and improved short-replay availability, but not recognition-preserving deployment. Keep the raw default and experimental opt-in status.
