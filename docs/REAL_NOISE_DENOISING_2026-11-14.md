# CueBell: sourced real-noise denoising observations

## Decision

**Background noise is reduced, but recognition preservation has not passed.**
Shipping is conditional on the denoiser working properly; relaxing the earlier
latency target does not resolve the observed recognition regressions. The public
1.3.1 release remains the baseline. The experiment is complete; the feature stays
off by default on the uncommitted `feat/on-device-denoising` branch. No new public
release was made. This decision is based on recognition quality, not the deferred
latency optimization target.

**Delivered:** 16 verified before/after pairs, 32 WAVs in a ZIP. All 16 recordings
remained fully enhanced in the final phone replay. Background-quality estimates
improved for all 16, but four of 11 eligible recognition pairs worsened, six tied,
and one improved. Two of the regressions reproduced in a confirmation run.

Audio bundle:
/home/mathew/Arrakis/CueBell/artifacts/CueBell-real-noise-before-after-2026-11-14.zip

Unpacked audio:
/home/mathew/Arrakis/CueBell/artifacts/CueBell-real-noise-before-after-2026-11-14/

## Source and processing

- Microsoft DNS Challenge 5 development set, Track 2 Speakerphone: **16 existing
  noisy recordings**, 12 near-speaker and four far-speaker clips, each 10 seconds.
- No generated speech, generated noise, artificial mixing, level normalization,
  trimming, or added reverberation. The source WAVs and supplied transcripts are
  retained. Conversion to mono PCM16 at 16 kHz is the only input preparation.
- Deterministic filename-hash selection precedes enhancement results. The first
  near selection used a case-sensitive `Primary` suffix; the separate far cohort
  corrects that selection limitation with case-insensitive matching. These are
  small samples, not a representative estimate of all public-address conditions.
- GTCRN runs on the connected I2404 Android phone, using the production Kotlin
  reducer and the pinned FFT native runtime. This is file replay in a standalone
  Android process, not a microphone/foreground-service deployment validation.
- The 16 ms causal alignment delay is retained. Each output remains 160,000
  samples. Only the partial final processing frame is internally zero-filled;
  there is no output padding or end-of-stream flush.

Source project: https://github.com/microsoft/DNS-Challenge

Official archive: https://dnschallengepublic.blob.core.windows.net/dns5archive/V5_dev_testset.zip

License: https://creativecommons.org/licenses/by/4.0/

Attribution and modification details:
/home/mathew/Arrakis/CueBell/docs/benchmarks/real-noise-2026-11-14/ATTRIBUTION.md

## Initial runtime availability

The original policy permanently disabled enhancement after any processing call
of 32 ms or longer. On real recordings, eight of 12 near clips and three of four
far clips remained fully enhanced. The other five outputs are retained as raw
evidence, **not presented as fully denoised audio**.

The replacement policy accounts for cumulative processing debt, with a 64 ms
limit and the same 32 ms frame interval. Brief valid overruns can recover; invalid
results and exceptions still fail open immediately. This changes availability,
not the normal enhanced waveform. A post-inference frame-age check also prevents
an excessively old frame being sent after a synchronous native stall.

### Final bounded-debt replay

The updated v4 harness fully enhanced **12/12 near and 4/4 far clips**. All 5,008
replay frames remained active, all bypass WAVs matched their inputs, and all
11 previously successful before/after pairs were byte-identical to the initial
outputs. The new policy changed availability without changing those waveforms.

| Cohort | Active replay frames | Processing p50 / p99 | Maximum call | Calls ≥32 ms | Peak processing debt |
| --- | ---: | ---: | ---: | ---: | ---: |
| Near | 3,756 / 3,756 | 4.608 / 10.882 ms | 50.922 ms | 3 | 18.913 ms |
| Far | 1,252 / 1,252 | 4.682 / 13.280 ms | 51.201 ms | 3 | 22.028 ms |

There were 14 completion-deadline misses across both cohorts, with a maximum
27.610 ms lateness, but no fallback, dropped frames, or schedule rebases. The
separate 16 ms signal delay remains. Both reset checks stayed active and produced
identical outputs. Each clip starts a fresh engine; these results do not establish
long-session, battery, live-microphone, or foreground-service performance. The
earlier strict latency gate is not claimed to pass.

APK SHA256: `b9318ebbb40a85633063175e7f478e492754faacd18889d2f74dbcd9926e7ac9`.
The runtime/model locks and compiled-source hashes are retained in the evidence.

## Initial acoustic-quality observations

Only the 11 fully enhanced initial pairs were scored. The runtime exclusions
are explicit; these aggregates must not be described as the full 16-clip result.

| Cohort | Scored pairs | Background quality, before → after | Speech quality, before → after | Overall quality, before → after |
| --- | ---: | ---: | ---: | ---: |
| Near | 8 | 2.441 → 3.941 | 3.369 → 3.096 | 2.352 → 2.812 |
| Far | 3 | 2.906 → 3.838 | 3.280 → 3.111 | 2.502 → 2.723 |

The background-quality proxy improved in all 11 pairs. Overall quality improved
in 10; predicted speech quality fell in all 11. This is the reason recognition
was checked rather than equating lower noise with better CueBell performance.

### Final acoustic-quality observations: all 16 recordings

| Cohort | Scored pairs | Background quality, before → after | Speech quality, before → after | Overall quality, before → after |
| --- | ---: | ---: | ---: | ---: |
| Near | 12 | 2.444 → 3.940 | 3.382 → 3.112 | 2.355 → 2.828 |
| Far | 4 | 2.727 → 3.889 | 3.065 → 3.022 | 2.295 → 2.627 |
| All, equal clip weight | 16 | 2.514 → 3.927 | 3.303 → 3.089 | 2.340 → 2.778 |

Background quality improved in **16/16**, overall quality in **15/16**, and speech
quality in **1/16**. Speech-quality estimates fell in the other 15. Near breathing
was the sole overall-quality decline, from 3.060 to 3.017 (approximately −0.042).
Far creaky noise was the sole speech-quality improvement.

PCM-limit sample counts were 239 before and 258 after across all recordings.
Far typing accounted for 238 before and all 258 after; near mouse clicks had one
before and none after. These are threshold counts in converted PCM, not proof of
historical clipping in the original recording. No gain normalization was applied
to hide the level changes or saturation.

These are the official non-personalized DNSMOS SIG/BAK/OVRL **model estimates**,
not human ratings or an SNR measurement. No paired clean reference is available.
The pinned implementation scores one 9.01-second window in each 10-second clip;
the remaining 0.99 seconds are outside that metric's coverage. Audio is neither
aligned nor normalized for scoring. No subjective listening evaluation is claimed.

## Real Gnani recognition

Seven initial pairs had both fully enhanced output and an eligible source
transcript: five near and two far. Source transcripts containing unknown-speech
markers were excluded from numerical WER. The same released Prisma model,
`indic-auto` language setting, and VAD settings were used for both conditions.
Reference text was never supplied as a recognition hint. Audio was paced in
512-sample frames; two paired connections ran concurrently, with randomized
condition order and equal final observation windows. No Luna calls were needed
for this speech-recognition comparison.

| Initial cohort | Reference words | Before errors / WER | After errors / WER |
| --- | ---: | ---: | ---: |
| Near: five pairs | 94 | 13 / 13.83% | 21 / 22.34% |
| Far: two pairs | 33 | 13 / 39.39% | 19 / 57.58% |

Across the seven pairs, one improved, four tied, and two worsened. Repeating both
regressing pairs reproduced their before/after error rates:

| Recording | First before → after WER | Confirmation before → after WER |
| --- | ---: | ---: |
| Near, air conditioning | 15.38% → 92.31% | 15.38% → 92.31% |
| Far, typing | 20.00% → 60.00% | 20.00% → 60.00% |

### Final recognition coverage

After v4 recovered the remaining outputs, the four additional near recordings
with complete source references were also tested. This completes all **11
eligible pairs out of 16**. The five excluded references contain unknown-speech
markers: near water, breathing, and cutlery; far baby and creaky noise. Their
audio and acoustic-quality results remain included in the delivery.

| Final cohort | Reference words | Before errors / WER | After errors / WER |
| --- | ---: | ---: | ---: |
| Near: nine pairs | 183 | 36 / 19.67% | 58 / 31.69% |
| Far: two pairs | 33 | 13 / 39.39% | 19 / 57.58% |
| All 11 pairs | 216 | 49 / 22.69% | 77 / 35.65% |

The final paired outcomes are **one improved, six tied, four worsened**.
Confirmation trials are not counted again in these averages.

| Recording | Before WER | After WER | Observation |
| --- | ---: | ---: | --- |
| Near baby | 31.82% | 22.73% | Improved |
| Near typing | 5.26% | 5.26% | Tied |
| Near air conditioning | 15.38% | 92.31% | Worse; English → Tamil detection; repeated |
| Near dog | 45.00% | 70.00% | Worse; English → Tamil detection |
| Near mouse clicks | 11.11% | 11.11% | Tied |
| Near clatter | 19.23% | 19.23% | Tied |
| Near creaky noise | 4.55% | 4.55% | Tied |
| Near dishwasher | 28.57% | 71.43% | Worse despite English detection in both arms |
| Near door | 13.64% | 13.64% | Tied |
| Far breathing | 55.56% | 55.56% | Tied |
| Far typing | 20.00% | 60.00% | Worse; mixed-language/word changes; repeated |

The air-conditioning clip's reference begins “Naturally, curly hair runs in my
family.” Before enhancement, Gnani detected English. After enhancement, it
detected Tamil and rendered most of the English utterance in Tamil script. The
far typing clip already triggered mixed-language recognition before enhancement;
the enhanced version introduced additional language/script and word changes.
**Strict English-reference WER penalizes these script changes:** this is a
production recognizer interaction, not proof that a listener loses the same
fraction of spoken information. There is no transliteration or numeric rewriting
to make the scores appear better. End-to-end Luna interpretation/alert accuracy
has not been measured on these recordings.

The dishwasher regression is not explained by a detected-language switch: both
arms were labeled English, while substitutions increased from four to 13 and
insertions remained two. Thus the concern is broader than English-reference
scoring of an alternative script. Source transcripts themselves contain some
awkward wording and have not been independently re-transcribed by a listener;
the paired test holds those same references constant.

### Scoring correction

An initial tokenizer used Python `\w`, which splits Indic combining vowel marks
and inflated some preliminary word counts. The corrected `unicode-marks-v2`
scorer retains letters, combining marks, numbers, and internal apostrophes after
NFKC/lowercase normalization. Five accounting tests pass, including Indic-script
word integrity. All rates above use the corrected scorer. Original provider
responses and preliminary score files are preserved; corrected initial scores
are in a separate evidence file.

## Evidence

Root:
/home/mathew/Arrakis/CueBell/docs/benchmarks/real-noise-2026-11-14/

- `recordings/` and `recordings-far/`: original audio, converted input, source
  transcripts, member hashes, selection metadata, and device manifests.
- `device-real-noise-v3b/` and `device-real-noise-far-v3/`: initial device results,
  per-frame timing, bypass controls, and the outputs rejected after fallback.
- `audio-near-initial/` and `audio-far-initial/`: verified fully enhanced initial
  pairs, with explicit excluded IDs and provenance.
- `quality-near-initial.json` and `quality-far-initial.json`: complete initial
  DNSMOS results and signal statistics.
- `asr-initial-rescored.json`: corrected word-error accounting for initial pairs.
- `asr-near-initial/`, `asr-far-initial/`, `asr-near-confirmation/`, and
  `asr-far-confirmation/`: immutable provider events, transcripts, language
  decisions, timing, hashes, and connection usage.

- `audio-near-v4/` and `audio-far-v4/`: all 16 final pairs, strict export checks,
  hashes, and provenance; no fallback output is labeled fully enhanced.
- `device-real-near-v4/`, `device-real-far-v4/`, `device-build-v4.json`,
  `v4-audio-verification.json`, and `v4-timing-summary.json`: final physical-device
  results, compiled inputs, active-frame checks, and initial-output equivalence.
- `quality-near-v4.json`, `quality-far-v4.json`, and `quality-final-summary.json`:
  full 16-clip DNSMOS results and signal statistics.
- `asr-near-completion/` and `asr-final-analysis.json`: additional provider trials
  and the canonical 11-pair recognition analysis, with input/evidence hashes.

## Verification and provider usage

- Backend: **487 passed, one optional numerical-test module skipped** in the app
  environment. The DNSMOS numerical suite separately passed **25 tests** in its
  isolated environment; two fixture scores matched the official implementation.
- Native: **33 JVM tests passed**, including 17 streaming-policy checks.
- Mobile: prior **49 tests passed**; lint and typecheck passed after the policy
  changes. Backend Ruff and whitespace checks passed.
- Every delivered WAV is mono PCM16, 16 kHz, 160,000 samples; all source and output
  hashes were verified. Provenance and attribution accompany the audio.
- This real-noise study used **26 Gnani connections / 600.776 seconds**, including
  confirmations, with no new Luna calls and no generated TTS.
- Combined with the prior campaign: **82.093 / 120 authorized Gnani minutes** and
  **419 / 600 authorized Luna attempts**. The prior 1,250 TTS characters are
  unchanged. No provider key is included in the deliverables.

The audio bundle is a listening/evidence deliverable, not a new app release.
Noise suppression is demonstrated, but recognition-preserving deployment remains
unqualified. Latency optimization is deferred as requested.
