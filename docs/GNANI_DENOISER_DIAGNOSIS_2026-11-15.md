# Gnani denoiser diagnosis: why cleaner audio can recognize worse

Date: 15 November 2026. Historical base: `v1.4.0-preview`, commit `7e793b2d5d460267bd8f5a26ab296e7659858e3a`.

## Findings

**There is more than one interaction.** Selected-case controls demonstrate output-script sensitivity, causal-shift sensitivity and an audio-level contribution. `codemix` helped one enhanced recording substantially, but did not fix another. These experiments do not identify every internal Gnani/GTCRN cause.

**Requested double denoising was not a reliable fix.** It helped one English recording's output script, increased errors on another and repeatedly returned `no speech detected` on Slough platform four.

**CueBell does not explicitly request a Gnani denoiser on its streaming connection.** The documented `with_denoise` flag is batch-only, default false. The public streaming contract has no documented equivalent. Always-on internal streaming enhancement remains unverified; VAD and noisy-speech training do not prove an explicit enhancement stage.

## Design and evidence

| Evaluation | Scope |
| --- | --- |
| Initial batch | 32 files: eight recordings × four conditions |
| Batch confirmation | Four Slough evaluations, reversing on/off job order |
| Initial streaming controls | 12 connections on two ten-second near-field DNS5 clips |
| Streaming follow-up | Four repeat controls, then two Slough `codemix` connections |
| Total | **54 evaluations: 36 batch files and 18 streaming connections**, not 54 independent recordings |

The eight selected recordings were five complete station field recordings and three known DNS5 regressions: air conditioning, dishwasher and distant typing. These are **diagnostic selections, not a held-out accuracy benchmark**. Batch and streaming segmentation differ, so scores stay separate.

Previously hash-verified raw and fully enhanced Android GTCRN audio was reused, without speech/noise generation or remixing. Signal controls only delayed or uniformly attenuated the original waveform. Batch held `prisma-v3.0`, automatic language and `verbatim` constant. No expected transcript, name, identifier, platform or uploader fact was sent.

Streaming reused released transport: 16 kHz mono PCM16, 512-sample / 32 ms pacing, default VAD and identical termination/observation policy. All 18 connections completed with zero pacing rebases. Returned metadata confirmed requested `verbatim`/`codemix`. Input hashes and headers were audited, with format the only declared header variable.

Canonical [analysis](benchmarks/gnani-denoiser-diagnosis-2026-11-15/analysis.json); [full requests, statuses, segments, transcripts, controls, hashes and usage](benchmarks/gnani-denoiser-diagnosis-2026-11-15/).

## 1. Custom, requested vendor and requested double denoising

WER uses only the three DNS5 recordings with complete references: **49 reference words per condition**. All three completed in every arm. The five station recordings lack full independent transcripts and are excluded from WER; missing station speech is reported separately.

| Custom GTCRN | Batch `with_denoise` requested | DNS5 errors / words | WER | Completed / 8 | Nonempty / 8 |
| --- | --- | ---: | ---: | ---: | ---: |
| Off | False | 11 / 49 | 22.45% | 6 | 6 |
| Off | True | 10 / 49 | 20.41% | 6 | 5 |
| On | False | 32 / 49 | 65.31% | 7 | 7 |
| On | True, requested double | 22 / 49 | 44.90% | 5 | 5 |

Vendor-only saved **one word error**, not evidence of a general accuracy improvement. Requested double had **ten fewer errors than custom-only**, but **twice baseline errors**, alongside station omissions.

### Station outcomes

| Recording | Observed batch result |
| --- | --- |
| Slough platform four | Flag off: raw and custom retain a platform-four mention, but departure time is already wrong. Raw/flag on retains only `It's first great Western service to breeding.`, with sole speech segment **16.652–21.024 s**, losing platform/time. Double fails: `no speech detected in 23s of audio`. All four statuses, full transcripts and segments repeat identically |
| Southall | Raw/off speech spans **3.020–27.136 s**. Raw/on completes empty, with an empty **3.628–5.280 s** segment. Double returns only the first part, then an empty segment |
| Slough through-train | Raw fails with either flag. Custom-only returns a short imperfect stand-clear fragment; double fails again |
| Distant Slough PA | No usable speech in any of the four conditions |
| Indian station | Raw/off retains Narmada Express and 8234. Custom loses details. Double recovers the name but adds other errors. No complete independent reference supports numerical accuracy |

These outcomes implicate speech detection/segmentation as well as decoding. They do not identify an internal VAD implementation or prove which phonemes were removed.

### Requested flag is not verified server execution

The API accepted/echoed `with_denoise`, and outcomes changed repeatably. However, documented maintenance behavior permits enhancement bypass while a job completes. Terminal metadata supplied no `denoise_applied` or bypass marker. An early Slough observation caught `diarize`, not `denoise`. Therefore these are **requested on/off conditions**, not verified execution of a server enhancement stage.

Slough provider trace identifiers:

| Attempt | Job ID |
| --- | --- |
| Initial off | `01a1db5a-84eb-78d4-9212-26251592cb4b` |
| Initial on | `01a1db5a-8d2b-795a-9daf-ee14eef708af` |
| Repeat on | `01a1db66-30f6-7564-9376-ff3f185fcf47` |
| Repeat off | `01a1db66-8877-71d0-af19-e937b5a3ef1b` |

Provider confirmation is still needed on actual enhancement/bypass, implementation/version and always-on preprocessing in `/stt/v3/stream`. No support ticket was submitted.

## 2. Streaming controls: script, alignment and level

| Condition | Air conditioning, 13 words | Dishwasher, 21 words |
| --- | ---: | ---: |
| Raw, `verbatim` | 2 errors / 15.38% | 6 / 28.57% |
| Raw delayed 16 ms, `verbatim` | 8 / 61.54% | 7 / 33.33% |
| Delayed raw attenuated to enhanced global RMS, `verbatim` | 8 / 61.54% | 13 / 61.90% |
| GTCRN, `verbatim` | 12 / 92.31% | 15 / 71.43% |
| Raw, `codemix` | 2 / 15.38% | 6 / 28.57% |
| GTCRN, `codemix` | 1 / 7.69% | 15 / 71.43% |

### Output mode helped one recording

On air conditioning, identical enhanced audio in `verbatim` produced mostly Tamil-script English; `codemix` produced Latin-script English, reducing errors **12 → 1**. The one-error outcome repeated, with the remaining error changing from substitution to insertion.

Strict English-reference WER was penalizing script changes as well as lexical mistakes. Gnani documents `detected_language_code` as derived from final transcript script, so a changed label does not independently diagnose an acoustic language classifier. Output mode can affect decoding as well as presentation; this was not post-hoc transliteration to improve a score.

### Causal alignment matters, but is not an isolated root cause

Adding **256 samples / 16 ms** to raw air-conditioning audio, without denoising, increased WER **15.38% → 61.54%** and changed some output to Telugu script. This repeated exactly. Reported speech start changed **1556 → 1588 ms**, and utterance duration **9300 → 9268 ms**.

To match production output length, the control prepends 16 ms zeros and drops the final 16 ms. Leading alignment, final boundary, VAD framing and decoder context are not separately isolated. No artificial cloud waiting was added, and the result does not attribute all GTCRN loss to delay.

### Global level contributes on dishwasher

Enhanced whole-recording RMS was **3.32 dB lower** for air conditioning and **9.67 dB lower** for dishwasher. These are global-level changes, **not noise-reduction SNR measurements**; removed background contributes too.

Dishwasher delay-only gave seven errors. Uniform **0.328649 gain** on delayed raw audio, with no denoising, gave **13 errors**, versus **15 for GTCRN**. The 13-error control repeated exactly; reported speech start moved **1396 → 1748 ms**. Level change is sufficient to reproduce a substantial regression here, but this does not prove gain restoration would fix enhanced audio or assign an additive percentage of causation to volume.

### A recognition problem remains

Dishwasher GTCRN stayed at **15 errors** in both formats, including the repeat. Both were English. This cannot be dismissed as only a script-scoring artifact.

After delay alignment and best-fit scalar, residual waveform energy was **10.97% of enhanced energy** for air conditioning and **29.98%** for dishwasher. This includes useful noise removal, not an isolated speech-distortion measure. Spectral modification/ASR-domain mismatch remains plausible, not a proven internal mechanism or evidence of individual missing phonemes.

## 3. Station `codemix`: partial recovery, not a pass

- Raw: `Platform 4 for the 8700 hours first Great Western Service to breeding.`
- Custom: `Platform four for the eight seven hundred hours first grade western service to breeding ...`

Both contain the platform label, but both still miss uploader-described **07:00** and **Reading**. There is no full independent station transcript or station WER. This one ASR pair did not include a new Luna interpretation or live alert measurement, and does not validate a global format change.

## 4. Research context and source limits

The vendor article library was inspected through its public collection. Its initial displayed “0” was a client-rendering placeholder, not an empty library.

Gnani's rural-noise and acoustic-training articles caution that perception-optimized enhancement can alter features used by ASR, favoring compatible noise/codec training. Its code-switching article discusses joint multilingual modeling, which cautions against inferring separate language routing from script alone. These are earlier-2026 vendor descriptions, not proof of the deployed Prisma v3 frontend.

The independently checked *When De-noising Hurts* paper also reports ASR degradation, but studies MetricGAN-plus and other recognizers, **not GTCRN/Gnani**. Literature supports caution, not a substitute for the controlled results.

Sources retained from the original investigation, not newly live-verified by this documentation audit:

- [Gnani research collection](https://www.gnani.ai/resources/research)
- [Rural India ASR and background noise](https://www.gnani.ai/resources/research/the-rural-india-asr-problem-engineering-speech-recognition-for-background-noise)
- [Acoustic training on 14 million hours](https://www.gnani.ai/resources/research/how-we-train-acoustic-models-on-14-million-hours-of-telephonic-speech)
- [Code-switching at 8 kHz](https://www.gnani.ai/resources/research/code-switching-at-8khz)
- [When De-noising Hurts](https://arxiv.org/abs/2512.17562)
- Gnani batch: [introduction](https://docs.gnani.ai/api/STTBatch/Introduction.md), [create job](https://docs.gnani.ai/api/STTBatch/Create_Job.md), [get files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md)
- Gnani [streaming contract](https://docs.gnani.ai/api/STT/stt-websocket.md), [Prisma v3](https://docs.gnani.ai/api/STT/models/prisma-v3.md)

## Decision and next experiments

1. Do not recommend double denoising for station announcements: it repeatedly removed usable Slough speech.
2. Keep raw audio as the baseline. One fewer word error across three selected vendor-only references does not outweigh station failures or prove broad benefit.
3. Evaluate `codemix` on held-out multilingual announcements, scoring exact numbers, destinations, platforms, spoken stop and complete Luna interpretation.
4. Evaluate level-aware, delay-aligned mild enhancement or blending against raw. Gain compensation and blending were **not validated fixes** here.
5. Obtain provider traces before asserting actual server enhancement execution.

Production app/backend defaults were not edited by this research. It ran in an isolated worktree without changing concurrent web-app work or the installed 1.4.0 APK.

## Accounting and historical verification

- Batch submitted audio: **965.542 seconds**, including failures and confirmations.
- New streaming time: **441.661796 connection-seconds**; conservative attempt time **445.399432 seconds**.
- Prior use: **5717.845675 seconds**. Combined conservative use: **7128.787107/7200 seconds**, or **118.813118/120 minutes**, leaving **71.212893 seconds**. This combines batch audio and connection/attempt time for the spending guard, not an invoice or exact billed time.
- No new Luna or TTS: cumulative **426 Luna attempts**, **1,250 TTS characters**.
- HTTP 429 interrupted read-only collection; collection resumed without resubmission. A repeat job start also received 429. Recovery verified authoritative `CREATED` and `started_at: null`, then started that same job once, without duplicate upload/job.
- **11 focused control/scoring/recovery tests passed**; Ruff passed on all **seven new Python files**. Saved-input audit passed. Scan of **144 new text files** found **zero configured private-credential matches**. Production transport/configuration and existing recognition/scoring helper remained byte-identical to release. These are recorded campaign checks, not newly rerun tests.

[Verification record](benchmarks/gnani-denoiser-diagnosis-2026-11-15/verification.json). Helpers under [`backend/benchmarks/denoising/`](../backend/benchmarks/denoising/): `diagnose_batch.py`, `confirm_batch.py`, `diagnose_stream.py`, `followup_stream.py`, `analyze_diagnosis.py`. They retain explicit input identities, local references, provider evidence and bounded accounting.
