# Optimization roadmap

CueBell's goal is a correct, timely alert during a real wait, not the lowest model latency or the cleanest-sounding audio in isolation. This roadmap separates completed experiments from remaining work.

## Completed evidence

- **Reproducible pipeline comparison:** real Gnani Prisma and GPT-6 Luna calls, archived source/configuration, fixed replay audio, provider traces and reviewed scoring. [Pipeline overview](PIPELINE_OPTIMIZATION.md) and [benchmark](LATENCY_BENCHMARK_2026-11-13.md).
- **Measured setup improvement:** speech-aware capture, a shorter quiet period and Fast tier reduced the observed speech-end-to-confirmation median from **10.747 s to 6.213 s (42.2%)**, with six complete successes in each arm. This is three replays each of two synthetic requests, not a multilingual reliability estimate.
- **Selected monitoring improvement:** the same two passing Hindi/Malayalam positives improved **5.663 s to 3.830 s (32.4%)** in a matched follow-up. Full 28-case reviewed results were **23 pass / 1 fail / 4 inconclusive** for baseline and **22 / 2 / 4** for the candidate. The candidate was **not promoted**.
- **Orchestration controls:** guarded deadline flushing, independent heartbeats, bounded ordered delivery and safe worker cancellation are implemented as opt-in capabilities. They preserve correction ordering rather than simply deleting waits.
- **Noise implementation and real-recording studies:** see the [implementation benchmark](NOISE_REDUCTION_BENCHMARK_2026-11-14.md), [real-noise evaluation](REAL_NOISE_DENOISING_2026-11-14.md), [station PA evaluation](STATION_PA_DENOISING_2026-11-14.md) and [recognition diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md). These contain both useful audio improvements and recognition/performance limits. They are separate from the synthetic latency experiment.

The original pipeline settings remain backend defaults: no explicit provider tier/reasoning or endpoint override, 3.5-second setup pause, 1.2-second grace and 2,000-token cap; new scheduling/writer/speech-aware controls are off. The benchmark's provider-default silence was 500 ms. Deployment overrides and noise-mode behavior must be checked separately rather than inferred from these defaults.

## Next priorities and acceptance evidence

| Priority | Work | Evidence needed before promotion |
|---|---|---|
| 1 | Fix token/counter association across utterances | Correct destination after nearby numbers, bursts and sentence splitting. The observed Tamil token-442/counter-three error must be in regression tests. |
| 2 | Improve multilingual verbatim evidence generation | Preserve the source validator while handling real grammatical forms. Test Hindi extraction rejection and Malayalam location forms without reconstructing unsupported evidence. |
| 3 | Expand held-out recognition evaluation | Independent speakers/sessions, native-reviewed references, clean/noisy/far-field speech, exact identifiers, corrections, stop commands and target-free listening. Report every non-pass. |
| 4 | Establish phone end-to-end latency | Capture through notification, vibration/audio onset and actual stop completion, with stage timing and clock alignment. Backend replay cannot establish these results. |
| 5 | Validate optional denoising under actual service conditions | Paired raw/enhanced recognition, startup and sustained frame timing, fallback accounting, energy and thermals on representative devices. Cleaner audio alone is not acceptance. |
| 6 | Bound continuous-backlog delay safely | Define which earlier/in-flight utterances can correct an alert. Test sustained unrelated speech, corrections, slow clients, timeouts and teardown. Current optimized scheduling still retains the global interpretation-idle guard. |
| 7 | Prove long-session reliability | Screen-locked runs crossing provider renewal, network handover, microphone interruptions and route changes. Measure coverage gaps, not just reconnect success. |
| 8 | Improve practical listening/alert diagnostics | Clipping/weak-input/route warnings and an actual-device alert test. Check spoken-alert feedback and accessible distinction between calls and corrections. |

### Recognition and acoustic cases

Start with a larger labelled set, reserving speakers or recording sessions for final evaluation. Include leading zeros, `43` versus `34`, `442` versus `441`, alphanumeric IDs, names, code-switching, multiple counters and later corrections. Keep expected identifiers out of ASR hints.

Test fan/traffic noise, distant loudspeakers, reverberation, clipping and overlapping nearby conversation separately. Denoising cannot by itself identify the official announcer, and echo cancellation for the phone's own playback is not general room dereverberation. Add long silence before the first important digit and long periods with no target announcement.

Report exact identifier/destination match, target recall, missed/wrong alerts, false alerts per listening hour, correction leakage and stop recall. WER/CER are supporting measures, not substitutes. Report denominators and provider failures rather than excluding hard cases from a speed claim.

### Resource and delivery checks

Retain native DSP, bounded queues, the 16-kHz mono PCM16 stream and paced 32 ms packets, including silence. The raw payload is **115.2 MB/hour before transport overhead**, calculated as `16,000 samples/s × 2 bytes × 3,600 s`. Dropping silent frames is a protocol change, not a free bandwidth optimization.

Record frame age, queue age/depth, endpoint delay, returned service tier, reasoning/cache/output tokens, provider failures and reference costs. On phones, separate initialization and steady state, and measure screen-off CPU, memory, battery/energy, temperature and deadline misses. A desktop RTF or model-file size does not establish phone latency or memory use.

## Settings not justified for promotion yet

Shorter Gnani silence, lower reasoning, compact prompts, cache-layout changes, a smaller output cap and shorter correction grace did not establish consistent quality/speed gains in the pipeline screening. Some altered segmentation or evidence validity; some failures were unrelated provider errors. Change one dimension at a time, preserve correction and grounding checks, then validate any combined profile on held-out inputs.

The 1.2-second grace overlaps model inference. Reducing it is not a guaranteed fixed saving. Likewise, a lower token ceiling does not guarantee fewer generated tokens, and warm-cache results do not establish cold-cache performance.

## Reproduce and review

Use the [offline replay audit](LATENCY_BENCHMARK_2026-11-13.md#reproduce-without-changing-evidence) before new paid runs. It verifies archived scorer/manifest hashes and compares all formal outcomes and by-kind latency distributions. Preserve raw artifacts; use fresh output paths, explicit budgets and private credentials for live experiments.

The [immutable original roadmap](https://github.com/mathew1046/CueBell/blob/af0173daa2db55b567154952e665cc6ff2734f19/docs/OPTIMIZATION_ROADMAP.md) records the earlier proposals. Some have since been implemented and measured; historical application deadlines and proposed experiments should not be presented as current product results. The [research review](LATENCY_NOISE_RESEARCH_2026-11-13.md) explains the technical trade-offs, and the [pipeline claim ledger](PIPELINE_OPTIMIZATION.md#claim-ledger) identifies numerical sources.
