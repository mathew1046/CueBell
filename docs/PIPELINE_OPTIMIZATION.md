# Pipeline optimization

CueBell listens for a useful announcement, checks its meaning, and alerts the user. Optimization is useful only if the right identifier and destination survive that process. A faster wrong-counter alert is not an improvement.

## Measured improvements

The 13 November 2026 experiment used real Gnani Prisma and GPT-6 Luna calls with fixed synthetic recordings. These are local backend replay results, not phone notification timings.

| Measurement | Before | Experimental configuration | Observed change and scope |
|---|---:|---:|---|
| Spoken setup: speech end to confirmation, median | 10.747 s | 6.213 s | 42.2% lower; 6/6 complete and successful in each arm |
| Matched monitoring: speech end to alert, median | 5.663 s | 3.830 s | 32.4% lower on the same two passing Hindi/Malayalam positives |
| Spoken stop: speech end to stop control, median | 3.656 s | 2.357 s | 35.5% lower across the same six inputs; all passed, but Hindi individually became slower |

Setup used three replays each of one Hindi and one Malayalam recording. Repetition does not create six independent speakers or requests. The monitoring comparison selects recordings that passed in both arms; it is not an accuracy-neutral population speedup.

For example, a Hindi announcement calling **token 442 to counter two** went from **5.568 s to 4.467 s** in the matched replay. Its Malayalam counterpart went from **5.758 s to 3.192 s**. These are specific measured examples, not expected response-time guarantees.

## What changed

- **Speech-aware setup:** track outstanding provider utterance IDs before completing capture. A second sentence must finish even if the previous final transcript has already arrived.
- **Shorter setup pause:** test a 1.5-second quiet period instead of 3.5 seconds, together with speech tracking and Fast service tier. Simply shortening the timer truncated all three Malayalam requests in the naive experiment.
- **Guarded scheduling:** wake when an alert deadline is due and interpretation is idle, rather than waiting for the next polling tick. Preserve ordered correction handling.
- **Independent health reporting and ordered delivery:** keep heartbeats independent of interpretation and use a bounded outbound writer. Stop workers before slow provider teardown so expired sessions cannot emit late alerts.
- **Provider controls and measurement:** expose optional tier, reasoning and endpoint settings, and retain replay audio, source snapshots and traces for comparison.

The full monitoring arms recorded completed Luna observation medians of **4.429 s → 2.525 s** (38 versus 42 returned observations). The causal model-completion-to-alert median was **112.322 ms → 0.778 ms**, but on different successful-positive cohorts (five versus three). These locate promising changes in cloud processing and local delivery; neither isolates the scheduler's causal effect. Gnani's reported transcription median was **114 ms → 117 ms**, so this experiment does not show faster Gnani recognition. Provider transcription time excludes endpoint wait and network transit.

## Why the faster profile is still opt-in

The full six-language monitoring comparison did not preserve complete target-and-counter quality:

| Reviewed outcome, same 28 cases | Baseline | Fast + guarded orchestration |
|---|---:|---:|
| Pass / fail / inconclusive | 23 / 1 / 4 | 22 / 2 / 4 |
| Complete single positives passing | 5/6 | 3/6 |
| Wrong-counter cases | 1 | 1 |
| Missing-counter cases | 1 | 3 |

Both arms associated token 442 with the preceding announcement's counter three in a Tamil burst. The candidate also rejected a Hindi extraction that was not a verbatim source span. The evidence validator stayed enabled. No wrong-target or unexpected-negative-case alerts were observed, but that does not establish a real-venue false-alert rate or erase the wrong-counter failures.

The candidate's returned-usage Luna cost estimate for this full arm was **$0.025499**, versus **$0.011275** for baseline. Calls and token counts differ; these are reference estimates, not bills or a fixed per-request cost comparison.

**Shipped settings were not promoted by this experiment.** The backend defaults still omit explicit tier/reasoning and Gnani endpoint overrides, retain the 3.5-second setup pause, 1.2-second correction grace and 2,000-token ceiling, and leave optimized scheduling, the outbound writer and speech-aware completion off. The benchmark's unchanged Gnani default was 500 ms silence. Grace overlaps interpretation; it is not another fixed 1.2 seconds added afterward. Local/deployed environment overrides must be checked separately.

## Scope and evidence

- **Coverage:** 22 formal runs, 174 attempts: 150 monitoring and 24 setup. The corpus contains 30 cases built from 24 clips across Hindi, Malayalam, Tamil, Telugu, Marathi and Indian English. Setup covers Hindi and Malayalam only.
- **Limits:** one Linux Ryzen 7 4800H host, cloud/network variability, small synthetic corpus, no native-speaker listening review, and no physical Android device in this round. It did not measure microphone acoustics, notification/vibration onset, battery use or noise suppression.
- **Noise work is separate:** see the [noise implementation benchmark](NOISE_REDUCTION_BENCHMARK_2026-11-14.md), [real-noise study](REAL_NOISE_DENOISING_2026-11-14.md), [station PA study](STATION_PA_DENOISING_2026-11-14.md) and [recognition diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md). Cleaner audio is not automatically more accurate recognition.

### Claim ledger

All values above were recalculated from the saved raw replay/provider records using the verified scorer. Percent reduction is `(before - after) / before × 100`; displayed values are rounded only after calculation.

| Claim | Numerical source within [archived campaign](benchmarks/2026-11-13/) |
|---|---|
| Setup 42.2%, six successes and complete recordings | `setup-v1-baseline.jsonl`, `setup-fast-v2-fast-orchestrated.jsonl`: `metrics.speech_end_to_confirmation_ms`, `source_speech_sent`, all six rows per arm |
| Matched 32.4% and language examples | `paired-v2-{baseline,fast-orchestrated}.jsonl`: `hi-positive` and `ml-positive`, `metrics.speech_end_to_alert_ms`; both reviewed passes |
| Stop 35.5% | `full-v1-baseline.jsonl`, `validation-v2-fast-orchestrated.jsonl`: six `*-voice-stop` cases, `metrics.speech_end_to_voice_stop_ms` |
| Full outcomes, causal local delay, model time, Gnani time and cost | [final campaign analysis](benchmarks/2026-11-13/final-campaign-analysis.json): runs `full-v1-baseline` and `validation-v2-fast-orchestrated`, `verdicts`, `by_kind`, `provider`; linked raw traces and hashes are retained per run |
| Coverage and failed settings | Same analysis, all 22 runs; [corpus](benchmarks/2026-11-13/corpus.json), [environment](benchmarks/2026-11-13/environment.json), [review policy](benchmarks/2026-11-13/adjudications.json) |
| Unchanged defaults | [backend configuration](../backend/app/config.py); experiment settings in [candidate configuration](benchmarks/2026-11-13/configs/fast-orchestrated.json) |

For immutable provenance, the [campaign at commit af0173d](https://github.com/mathew1046/CueBell/tree/af0173daa2db55b567154952e665cc6ff2734f19/docs/benchmarks/2026-11-13) retains raw files, hashes, baseline and candidate source snapshots. The original baseline is commit `6e98d54a166f2d6d617ee0e36a0f2cd499659882`.

See the [benchmark method, failed variants and reproduction commands](LATENCY_BENCHMARK_2026-11-13.md), [research rationale](LATENCY_NOISE_RESEARCH_2026-11-13.md) and [next priorities](OPTIMIZATION_ROADMAP.md).
