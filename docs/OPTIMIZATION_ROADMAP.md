# Optimization roadmap

**Keep baseline defaults until correct alerts survive broader testing.** Setup improved in controlled replay, but the faster monitoring profile and denoising did not establish recognition preservation.

## What is complete

- [Pipeline experiment](LATENCY_BENCHMARK_2026-11-13.md): real providers, fixed replay audio, archived source/configuration and reviewed scoring.
- Setup median fell **10.747 → 6.213 s (42.2%)**, with six complete successes per arm. Each arm repeated two synthetic Hindi/Malayalam requests three times, not six independent speakers.
- Matched monitoring improved **5.663 → 3.830 s (32.4%)** on the same two passing positives. Full 28-case reviewed outcomes worsened from **23 pass / 1 fail / 4 inconclusive** to **22 / 2 / 4**. The candidate was not promoted.
- Guarded scheduling, independent health messages, bounded ordered delivery and speech-aware setup exist as opt-in controls.
- [Noise studies](NOISE_REDUCTION.md) demonstrate useful runtime and estimated-quality gains alongside recognition regressions. They are separate from the synthetic latency experiment.

Defaults retain a 3.5-second setup pause, 1.2-second correction grace and 2,000-token cap, without explicit provider tier/reasoning or endpoint overrides. New scheduling/writer/speech-aware controls and noise reduction remain off. Benchmark Gnani silence was 500 ms. Check deployment overrides separately.

## Next priorities

| Priority | Work | Acceptance evidence |
|---|---|---|
| 1 | Fix identifier/destination association | Correct nearby numbers, bursts and split sentences; retain the Tamil token-442/counter-three error as a regression case |
| 2 | Improve multilingual verbatim evidence | Handle Hindi/Malayalam forms without disabling the source validator or inventing quotations |
| 3 | Expand held-out recognition tests | Independent speakers/sessions, native-reviewed references, exact identifiers, corrections, stops and target-free listening; report every non-pass |
| 4 | Measure phone end-to-end delay | Capture through notification, vibration/audio onset and actual stop completion, with stage IDs and clock alignment |
| 5 | Qualify optional denoising | Paired raw/enhanced recognition plus startup, sustained timing, fallback, energy and thermals on representative devices |
| 6 | Bound continuous-backlog delay safely | Define which prior/in-flight utterances can correct an alert; test sustained speech, slow clients and teardown. Current optimized scheduling still waits for interpretation to become idle |
| 7 | Prove long-session reliability | Screen-locked provider renewal, network handover, microphone interruptions and route changes; measure coverage gaps |
| 8 | Improve practical diagnostics | Weak-input/clipping/route warnings, actual-device alert tests and accessible correction cues |

## Evaluation rules

Reserve speakers or sessions for final evaluation. Include leading zeros, reversed digits, near identifiers, alphanumeric IDs, names and code-switching. Keep expected identifiers out of recognition hints.

Test traffic/fans, distant loudspeakers, reverberation, clipping, overlapping conversation and first digits after long silence separately. Denoising does not identify the official announcer; echo cancellation for phone playback is not general room cleanup.

Report exact identifier/destination matches, target recall, wrong/missed alerts, false alerts per listening hour, correction leakage and stop recall. Word/character error rates support these measures, not replace them. Separate provider failures from successful negative decisions.

Preserve 16-kHz mono PCM16 and paced 32 ms packets, including silence. Payload is **115.2 MB/hour before transport overhead** (`16,000 × 2 × 3,600` bytes). Dropping silence changes the protocol.

Measure frame/queue age, endpoint delay, provider tier, token use, failures and reference costs. Separate startup from steady-state CPU, memory, energy, temperature and deadline misses. Desktop throughput does not establish phone performance.

## Changes not justified yet

Shorter Gnani silence, lower reasoning, compact prompts, explicit cache layout, smaller output caps and shorter grace did not establish consistent quality/speed gains. Grace already overlaps interpretation; reducing it is not a fixed saving. Warm-cache experiments do not establish cold-cache behavior.

Use the [offline audit](LATENCY_BENCHMARK_2026-11-13.md#reproduce-without-changing-evidence) before separately budgeted live tests. See [research rationale](LATENCY_NOISE_RESEARCH_2026-11-13.md) and the [claim ledger](PIPELINE_OPTIMIZATION.md#claim-ledger).

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/OPTIMIZATION_ROADMAP.md). Raw evidence and historical labels are unchanged.
