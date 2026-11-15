# Pipeline optimization

**Outcome: setup became faster in a small controlled replay, but the faster monitoring profile failed the quality gate. It remains opt-in.** A faster alert is useful only when it preserves the right identifier and destination.

## Measured improvements

The 13 November 2026 experiment used real Gnani Prisma and GPT-6 Luna calls with fixed synthetic recordings. These are backend timings, not phone notification timings. Median means the middle measured value.

| Speech end to result, median | Baseline | Candidate | Scope |
|---|---:|---:|---|
| Setup confirmation | 10.747 s | 6.213 s | **42.2% lower**, six complete successes per arm |
| Monitoring alert | 5.663 s | 3.830 s | **32.4% lower**, the same two passing Hindi/Malayalam positives |
| Spoken stop | 3.656 s | 2.357 s | **35.5% lower**, same six inputs; Hindi individually slowed |

Setup repeated one Hindi and one Malayalam request three times each. Those are not six independent speakers. Monitoring selected recordings that passed both arms, not an accuracy-neutral population speedup. For token 442 at counter two, Hindi improved 5.568 → 4.467 s and Malayalam 5.758 → 3.192 s.

## What changed

- Track unfinished speech before ending setup capture. A naive shorter pause truncated all three Malayalam attempts.
- Combine that tracking with a 1.5-second setup pause and Fast service tier.
- Wake the alert scheduler at deadlines, while preserving ordered corrections and waiting for interpretation to become idle.
- Keep health messages independent, bound outgoing writes and stop workers before slow provider teardown.

Completed Luna observations improved 4.429 → 2.525 s median, across 38 versus 42 returned observations. Causal model-completion-to-alert delay improved 112.322 → 0.778 ms, but across five versus three passing positives. Neither comparison isolates the scheduler's effect. Gnani-reported transcription was 114 → 117 ms, excluding endpoint wait and network transit: recognition itself was not faster.

## Why defaults did not change

| Same 28 monitoring cases | Baseline | Candidate |
|---|---:|---:|
| Reviewed pass / fail / inconclusive | 23 / 1 / 4 | 22 / 2 / 4 |
| Complete single positives passing | 5/6 | 3/6 |
| Wrong-counter cases | 1 | 1 |
| Missing-counter cases | 1 | 3 |

Both arms attached Tamil token 442 to the previous counter three. The candidate also failed a Hindi verbatim-evidence check; the validator stayed enabled. No wrong-target or unexpected-negative alerts were observed, but this is not a venue false-alert rate. Returned-usage Luna estimates were $0.011275 versus $0.025499, not invoices or equal-request cost comparisons.

Backend defaults retain the 3.5-second setup pause, 1.2-second correction grace and 2,000-token cap, with no explicit tier/reasoning or endpoint override. New scheduling, writer and speech-aware controls are off. Benchmark Gnani default silence was 500 ms. Grace overlaps interpretation, rather than adding another fixed wait. Check deployment overrides separately.

## Scope and evidence

Coverage: **22 runs, 174 attempts**, including 150 monitoring and 24 setup attempts; 30 cases from 24 clips across six languages. One Linux host, synthetic speech, no native-speaker review and no physical-phone measurement limit generalization.

### Claim ledger

[Final analysis](benchmarks/2026-11-13/final-campaign-analysis.json) records verdicts, by-kind timings and provider counts. [Raw campaign](benchmarks/2026-11-13/) retains setup/paired JSONL, source snapshots, hashes, corpus and adjudications. Reduction is `(before - after) / before × 100` using unrounded records.

See [method and reproduction](LATENCY_BENCHMARK_2026-11-13.md), [research](LATENCY_NOISE_RESEARCH_2026-11-13.md), [noise evidence](NOISE_REDUCTION.md) and [priorities](OPTIMIZATION_ROADMAP.md).

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/PIPELINE_OPTIMIZATION.md). Raw evidence and historical labels are unchanged.
