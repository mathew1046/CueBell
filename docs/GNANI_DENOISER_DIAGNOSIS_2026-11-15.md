# Why clearer audio sometimes produced worse Gnani recognition

Date: 15 November 2026. Base: `v1.4.0-preview`, commit
`7e793b2d5d460267bd8f5a26ab296e7659858e3a`.

## Findings

**There is more than one cause.** Controlled tests demonstrate output-script sensitivity,
causal-shift sensitivity, and an audio-level contribution on particular recordings.
They also show a remaining recognition regression that `codemix` does not fix.
The results do not establish exactly which internal Gnani or GTCRN features cause every error.

**Requested double denoising was not a reliable fix.** It improved the script of one
English recording but increased another recording's errors and repeatedly produced
`no speech detected` on the Slough station announcement.

**CueBell does not explicitly request a Gnani denoiser on its streaming connection.**
Gnani documents an optional batch-only `with_denoise` flag, default `false`.
The current public streaming contract has no equivalent documented switch.
Whether the streaming server has any always-on internal enhancement remains unverified.
Training on noisy speech and VAD are not proof of an explicit enhancement stage.

## Study design and evidence

- 32 initial batch file evaluations: eight recordings × four conditions.
  Five were complete authentic station field recordings; three were previously observed
  DNS5 regressions: air conditioning, dishwasher noise, and distant typing.
- Four repeat batch evaluations of Slough, with reversed on/off job order.
- Twelve streaming controls on the two ten-second near-field DNS5 recordings.
- Four repeat streaming controls, then two Slough `codemix` streaming evaluations.
- Total: **54 recognition evaluations**, comprising 36 batch files and 18 streaming connections.
  These are evaluations of eight selected recordings, not 54 independent recordings.
- Reused the previously hash-verified raw and fully enhanced Android GTCRN recordings.
  No speech/noise was generated or remixed. Additional signal controls only delayed
  or uniformly attenuated the original recorded waveform.
- Same `prisma-v3.0`, automatic language selection, and `verbatim` within the batch comparison;
  no expected transcripts, names, identifiers, platform numbers, or uploader facts were sent.
- Streaming reused CueBell's released transport: 16 kHz mono PCM16, 512-sample frames,
  32 ms pacing, default VAD settings, and the same termination/observation policy.
  All 18 connections completed with zero pacing rebases. Returned connection metadata
  confirmed the requested `verbatim` or `codemix` format.
- Selections were diagnostic cases with known problems, **not a held-out accuracy benchmark**.
  Batch and streaming have different segmentation; their scores are reported separately.

Canonical machine-readable audit:
/home/mathew/Arrakis/CueBell-denoiser-diagnosis-20261115/docs/benchmarks/gnani-denoiser-diagnosis-2026-11-15/analysis.json

Full request, status, transcript, segment, hash, timing, and control evidence:
/home/mathew/Arrakis/CueBell-denoiser-diagnosis-20261115/docs/benchmarks/gnani-denoiser-diagnosis-2026-11-15/

## 1. Requested Gnani denoising versus custom and double denoising

The WER column uses only the three DNS5 recordings with complete reference transcripts:
49 reference words per condition. Lower is better. The five station recordings lack
independent full transcripts and are **not** included in WER.

| Custom GTCRN | Gnani batch `with_denoise` | DNS5 errors / words | DNS5 WER | Completed / 8 | Nonempty transcripts / 8 |
|---|---|---:|---:|---:|---:|
| Off | False | 11 / 49 | 22.45% | 6 | 6 |
| Off | True | 10 / 49 | 20.41% | 6 | 5 |
| On | False | 32 / 49 | 65.31% | 7 | 7 |
| On | True — requested double | 22 / 49 | 44.90% | 5 | 5 |

Gnani-only saved **one reference word** in this small subset. That is insufficient
evidence of a general accuracy improvement, especially alongside station omissions.
Double denoising had ten fewer errors than custom-only, but twice the baseline errors.
All three reference-bearing recordings completed in every condition; missing station
speech is reported separately rather than disguised as a successful negative.

### Real station outcomes

- **Slough platform four:** with the batch flag off, both raw and custom audio retained
  a platform-four mention, although the departure time was already wrong in this batch run.
  Raw audio with Gnani denoising requested retained only
  `It's first great Western service to breeding.` Its sole reported speech segment was
  16.652–21.024 seconds, losing the platform/time information.
  With both denoisers requested, the job failed with `no speech detected in 23s of audio`.
  All four statuses, full transcripts, and segment records repeated identically.
- **Southall:** raw/flag-off returned speech spanning 3.020–27.136 seconds;
  raw/flag-on completed with an empty transcript and a 3.628–5.280-second empty segment.
  Double denoising returned only the first part of the announcement, followed by an empty segment.
- **Slough through-train:** raw failed with either flag value; custom-only returned a
  short, imperfect stand-clear fragment; double failed again.
- **Distant Slough PA:** no usable speech in any of the four conditions.
- **Indian station:** raw/flag-off retained Narmada Express and 8234. Custom-only lost
  details from that announcement. Double recovered the name but introduced other errors.
  There is no complete independent reference for a numerical accuracy claim here.

These outcomes implicate the **speech-detection/segmentation path as well as decoding**.
They do not isolate a particular internal VAD implementation or prove which phonemes were removed.

### Did the provider actually execute its denoiser?

The API accepted and echoed the requested flag; results changed repeatedly with that flag.
However, the documented enhancement service can be bypassed during maintenance while a job
still completes. None of the returned terminal metadata exposed an explicit
`denoise_applied` or bypass indicator. An early Slough observation caught `diarize`,
not `denoise`. Therefore this report calls these **requested on/off conditions**, not
independently verified server enhancement execution. Different transcripts alone do not
resolve that distinction.

The four job IDs, suitable for a provider-side trace check, are:

- Initial off: `01a1db5a-84eb-78d4-9212-26251592cb4b`
- Initial on: `01a1db5a-8d2b-795a-9daf-ee14eef708af`
- Repeat on: `01a1db66-30f6-7564-9376-ff3f185fcf47`
- Repeat off: `01a1db66-8877-71d0-af19-e937b5a3ef1b`

Provider confirmation is still needed for: whether each requested-on job enhanced or
bypassed; the enhancement implementation/version; and whether `/stt/v3/stream` has
always-on preprocessing independent of the batch flag. No support ticket was submitted.

## 2. Why the custom-denoiser result got worse: streaming controls

| Streaming condition | Air conditioning, 13 words | Dishwasher, 21 words |
|---|---:|---:|
| Raw, `verbatim` | 2 errors — 15.38% | 6 errors — 28.57% |
| Raw shifted by 16 ms, `verbatim` | 8 — 61.54% | 7 — 33.33% |
| Shifted raw attenuated to enhanced global RMS, `verbatim` | 8 — 61.54% | 13 — 61.90% |
| GTCRN, `verbatim` | 12 — 92.31% | 15 — 71.43% |
| Raw, `codemix` | 2 — 15.38% | 6 — 28.57% |
| GTCRN, `codemix` | 1 — 7.69% | 15 — 71.43% |

### A. Output style explains much of one apparent regression

On the air-conditioning recording, custom audio in `verbatim` produced predominantly
Tamil-script spellings of English speech. The **identical audio** with `codemix` produced
English words in Latin script and reduced errors from 12 to one. That one-error result
repeated, although the particular remaining error changed from a substitution to an insertion.

This is stronger evidence than merely speculating that denoising destroyed speech.
Strict English-reference WER was penalizing script changes in addition to lexical mistakes.
Gnani documents `detected_language_code` as derived from final transcript script; its change
does not, by itself, diagnose an independent acoustic language classifier.
The output mode can affect decoding as well as presentation; this is not a post-hoc
transliteration of the hypothesis to improve the score.

### B. Small causal alignment changes matter

Adding the same 256-sample/16-ms delay to raw audio, with **no denoising**, increased
air-conditioning WER from 15.38% to 61.54% and changed part of the output to Telugu script.
The result repeated exactly. Its reported speech start changed from 1556 to 1588 ms,
and returned utterance duration from 9300 to 9268 ms.

This establishes sensitivity to the causal-shift control, not that all of GTCRN's loss is
caused by its delay. To match the production files, the control preserves total length:
it prepends 16 ms of zeros and drops the final 16 ms. Leading alignment, the final boundary,
VAD framing, and decoder context are therefore not separately isolated by this experiment.
No artificial cloud waiting delay was added.

### C. Global level contributes on another recording

GTCRN's whole-recording RMS was 3.32 dB lower on air conditioning and 9.67 dB lower
on the dishwasher recording. These are **global level differences, not noise-reduction
SNR measurements**; removed background noise also contributes to the difference.

On the dishwasher file, delay-only gave seven errors. Applying a uniform 0.328649 gain
to that delayed raw waveform, without denoising, gave 13 errors, versus 15 for GTCRN.
The 13-error control repeated exactly. Its reported speech start moved from 1396 to 1748 ms.
Thus a level change is sufficient to reproduce a substantial regression on this case.
It does not prove that restoring enhanced-audio gain would fix it, or quantify an additive
percentage of GTCRN's total error causally attributable to volume.

### D. A genuine recognition problem remains

The dishwasher custom-audio result stayed at 15 errors in both `verbatim` and `codemix`,
including the repeat. Both outputs were English. This regression cannot be dismissed
as only an English-versus-Indic-script scoring artifact.

GTCRN also changes the waveform beyond a scalar attenuation: after delay alignment and
a best-fit scalar, residual energy was 10.97% of enhanced energy for air conditioning and
29.98% for dishwasher. Those statistics include useful noise removal and do not identify
speech distortion or individual lost phonemes. Spectral modification/ASR-domain mismatch
remains a plausible contributor, rather than a fully isolated internal root cause.

## 3. Does `codemix` fix the real station announcement?

Only partially in this one diagnostic pair:

- Raw: `Platform 4 for the 8700 hours first Great Western Service to breeding.`
- Custom: `Platform four for the eight seven hundred hours first grade western service to breeding ...`

Both now contained the platform label, but both still got the uploader-described **07:00**
departure and **Reading** destination wrong. The source is not a complete independently
annotated transcript, so there is no station WER. This is not a complete announcement pass
and does not establish that switching format fixes CueBell. It was an ASR component test,
without a new Luna interpretation or live alert measurement.

## 4. What Gnani's research supports

The supplied research library was inspected through its public article collection; the
initial page's “0” count was a client-rendering placeholder, not an empty library.

The rural-noise article's denoising-paradox discussion and the acoustic-training article's
preprocessing discussion both caution that perception-optimized enhancement can distort
features an ASR model uses. They favor compatible/matched noise and codec training.
The code-switching article discusses joint multilingual modeling, supporting caution about
inferring a separate language-routing failure from a transcript's script.

These are vendor research descriptions from earlier 2026, not proof of the exact deployed
Prisma v3 frontend. An independently checked paper, *When De-noising Hurts*, also reports
ASR degradation with enhancement, but studied MetricGAN-plus and other recognizers, not
this GTCRN/Gnani combination. Neither source replaces the controlled measurements above.

Sources:

https://www.gnani.ai/resources/research

https://www.gnani.ai/resources/research/the-rural-india-asr-problem-engineering-speech-recognition-for-background-noise

https://www.gnani.ai/resources/research/how-we-train-acoustic-models-on-14-million-hours-of-telephonic-speech

https://www.gnani.ai/resources/research/code-switching-at-8khz

https://arxiv.org/abs/2512.17562

https://docs.gnani.ai/api/STTBatch/Introduction.md

https://docs.gnani.ai/api/STTBatch/Create_Job.md

https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md

https://docs.gnani.ai/api/STT/stt-websocket.md

https://docs.gnani.ai/api/STT/models/prisma-v3.md

## 5. Decision and next useful changes

1. **Do not recommend double denoising for station announcements from these results.**
   It repeatedly removed the entire usable Slough speech result.
2. **Keep raw audio as the comparison baseline.** Gnani-only's one-word gain in three
   selected references does not outweigh the station failures or establish a broad benefit.
3. **Evaluate `codemix` on a held-out multilingual announcement corpus**, scoring exact
   numbers, destinations, platforms, spoken-stop behavior, and complete Luna interpretation.
   It is a promising format intervention, not a validated global default change.
4. **Evaluate level-aware, delay-aligned mild enhancement or blending** against raw audio.
   Gain compensation and blending were not validated as fixes in this study.
5. Obtain provider traces to settle the server-enhancement execution question; do not
   infer it from VAD presence, marketing noise robustness, or echoed configuration.

Production app/backend defaults were not edited. Research lives on an isolated worktree;
the user's concurrent web-app work and installed 1.4.0 APK were not changed.

## Accounting and reproducibility

- Batch audio submitted: 965.542 seconds, counting failures and confirmations.
- New streaming connection time: 441.661796 seconds; conservative attempt time: 445.399432 seconds.
- Prior use: 5717.845675 seconds. Combined conservative use: **7128.787107 / 7200 seconds**
  (118.813118 / 120 minutes), leaving 71.212893 seconds under the existing authorization.
- No new Luna calls or TTS; prior totals remain 426 Luna attempts and 1250 submitted TTS characters.
- Initial read-only collection encountered HTTP 429 and was resumed without resubmission.
  One repeat job's start was rejected with 429. Recovery checked authoritative
  `CREATED` / `started_at: null` before starting that same job once; no duplicate upload/job.
- Provider batch charges and connection seconds are conservatively combined for the
  existing spending guard; this is not a provider invoice or an exact billed-time statement.

Benchmark helpers are under:
/home/mathew/Arrakis/CueBell-denoiser-diagnosis-20261115/backend/benchmarks/denoising/

`diagnose_batch.py`, `confirm_batch.py`, `diagnose_stream.py`, `followup_stream.py`, and
`analyze_diagnosis.py` retain explicit input identities, local scoring references,
provider request/response evidence, and bounded submission accounting.
Production transport and scoring were reused. The analysis checks all input hashes and
that the streaming headers are identical apart from the declared format variable.

Final checks: 11 focused control/scoring/recovery tests passed; Ruff passed on all seven
new Python files. The saved-input audit passed. A scan of 144 new text files found zero
configured private-credential matches. Production transport, configuration, and the
existing recognition/scoring helper were byte-identical to the release. Source hashes and
verification details are in the campaign's `verification.json`.
