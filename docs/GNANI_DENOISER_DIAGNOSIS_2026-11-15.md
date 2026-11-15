# Gnani denoiser diagnosis

15 November 2026. **Script, alignment and level each affected selected recognition results. No universal fix was established.** `codemix` helped one enhanced clip, not another. Requested double denoising repeatedly lost usable Slough speech. Keep raw audio as the baseline.

CueBell does not explicitly request vendor denoising on its streaming connection. Documented batch `with_denoise` defaults false and has no documented streaming equivalent. Always-on internal streaming enhancement remains unverified.

## Design

**54 evaluations, not 54 independent recordings:** 32 initial batch files (eight recordings × four conditions), four batch confirmations and 18 streaming connections. Inputs reused hash-verified raw/Android-GTCRN audio: five full station recordings and three known DNS5 regressions. These are selected diagnostic cases, not held-out accuracy evidence.

Batch held `prisma-v3.0`, automatic language and `verbatim` constant. Streaming retained released 16-kHz PCM16 transport, 512-sample/32 ms pacing, VAD and observation policy. All 18 connections completed without pacing rebases; metadata confirmed requested format. No expected words, identifiers or source facts were hints. Batch/streaming segmentation differs, so their scores stay separate.

## Requested batch denoising

Word error rate (WER) is recognition errors divided by reference words. Only three DNS5 clips have complete references: **49 words per condition**, all completed. Five station recordings are excluded from WER, not from failure reporting.

| Custom GTCRN | Vendor denoise requested | Errors / words | WER | Completed / 8 | Nonempty / 8 |
|---|---|---:|---:|---:|---:|
| Off | False | 11/49 | 22.45% | 6 | 6 |
| Off | True | 10/49 | 20.41% | 6 | 5 |
| On | False | 32/49 | 65.31% | 7 | 7 |
| On | True, double | 22/49 | 44.90% | 5 | 5 |

Vendor-only saved one word error; double still had twice baseline errors. Double helped air-conditioning script but worsened dishwasher, with these station failures:

- **Slough platform four:** flag-off raw/custom retain platform mentions but wrong time. Vendor-only loses platform/time. Double returns `no speech detected in 23s of audio`. All four statuses/transcripts/segments repeated identically with reversed job order.
- **Southall:** vendor-only completes empty; double retains only the first part.
- **Through train:** raw fails with either flag; custom-only recovers an imperfect fragment; double fails.
- **Distant PA:** no usable speech in any arm.
- **Indian station:** custom loses Narmada Express/8234; double recovers the name but adds errors. No independent full reference exists.

The API accepted/echoed `with_denoise`, but maintenance behavior permits bypass and terminal metadata had no `denoise_applied` marker. These are **requested conditions, not verified server execution**. Segmentation/detection is implicated without identifying internal implementation. Provider confirmation remains outstanding; no support ticket was submitted.

## Streaming controls

| Condition | Air conditioning, 13 words | Dishwasher, 21 words |
|---|---:|---:|
| Raw, `verbatim` | 2 errors / 15.38% | 6 / 28.57% |
| Raw delayed 16 ms | 8 / 61.54% | 7 / 33.33% |
| Delayed raw, attenuated to enhanced RMS | 8 / 61.54% | 13 / 61.90% |
| GTCRN, `verbatim` | 12 / 92.31% | 15 / 71.43% |
| Raw, `codemix` | 2 / 15.38% | 6 / 28.57% |
| GTCRN, `codemix` | 1 / 7.69% | 15 / 71.43% |

**Script:** identical enhanced air-conditioning audio changed from mostly Tamil-script English to Latin-script English with `codemix`; **12 → one error**, repeated. WER penalizes script and lexical changes. Output mode may affect decoding, not just presentation. Transcript-derived language labels do not independently diagnose acoustic routing.

**Alignment:** adding 256 samples/16 ms to raw air-conditioning reproduced eight errors. The fixed-length control prepends zeros and removes the final 16 ms, so onset, endpoint, VAD framing and decoder context are not isolated. It does not attribute all GTCRN loss to delay.

**Level:** enhanced global RMS fell 3.32 dB on air conditioning and 9.67 dB on dishwasher, not signal-to-noise improvements. Applying 0.328649 gain to delayed raw dishwasher increased seven → 13 errors, repeated, versus 15 enhanced errors. This supports a level contribution, not proof that gain restoration fixes enhancement.

Dishwasher remained 15/21 in both formats, including repeat, with English output. It is not only a script-scoring artifact. Residual waveform energy after alignment/scalar fitting includes useful noise removal, not isolated speech distortion.

Station `codemix` recovered platform wording but still missed uploader-described 07:00/Reading in both arms. No new Luna interpretation, full station WER or live alert was measured.

## Evidence, sources and next steps

[Canonical analysis](benchmarks/gnani-denoiser-diagnosis-2026-11-15/analysis.json), [requests/transcripts/controls](benchmarks/gnani-denoiser-diagnosis-2026-11-15/), [verification](benchmarks/gnani-denoiser-diagnosis-2026-11-15/verification.json) and [analysis/replay helpers](../backend/benchmarks/denoising/) retain identities and accounting. The full report links vendor research, batch contracts and *When De-noising Hurts*, which studies other models, not GTCRN/Gnani. Literature does not prove the deployed frontend.

Conservative budget accounting reached **7,128.787107/7,200 seconds (118.813118/120 minutes)**, combining batch audio and streaming attempt time, not an invoice. No new Luna/TTS; 429 recovery reused authoritative unstarted jobs rather than duplicating uploads. Historical checks: 11 focused tests passed; not rerun here.

Do not recommend double denoising. Evaluate `codemix`, delay-aligned mild enhancement/blending and level controls on held-out multilingual tasks with complete interpretation. These remain candidates, not validated fixes. Production defaults were unchanged.

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/GNANI_DENOISER_DIAGNOSIS_2026-11-15.md), including source links, job identities and historical accounting.
