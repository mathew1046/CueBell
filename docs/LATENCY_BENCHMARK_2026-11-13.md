# CueBell real-provider latency experiments

Date started: 2026-11-13

## Result and decision

Completed **22 formal runs / 174 case attempts**, using real Gnani Prisma and GPT-6 Luna: 150 monitoring attempts and 24 spoken-setup attempts. Compatibility probes and the discarded three-case pilot are additional, separately retained evidence.

- **Spoken setup:** the speech-aware 1.5-second pause plus Fast tier passed **6/6**, reducing median speech-end → confirmation from **10.747 s to 6.213 s (42.2%)**. Both configurations captured all six requests completely.
- **Matched monitoring replay:** the two positives that passed in both arms improved from **5.663 s to 3.830 s median (32.4%)**. This is two matched recordings, not an accuracy-neutral population estimate.
- **Full monitoring validation:** reviewed outcomes were **23 pass / 1 fail / 4 inconclusive** for baseline and **22 / 2 / 4** for the candidate. The faster profile did **not** satisfy the complete target-and-counter quality gate and remains **opt-in**.
- **Implemented:** measurable configuration switches, guarded deadline scheduling, independent heartbeats, a bounded ordered writer, safe worker cancellation, speech-aware setup completion, and reproducible replay/analysis tooling. Baseline settings remain the defaults.

## Scope

Run the local CueBell backend against actual Gnani Prisma speech recognition and OpenAI `gpt-6-luna`, using the same generated Indian-language recordings for baseline and optimized configurations. Measure recognition outcomes as well as speed. The test input enters the native WebSocket protocol as paced PCM; it does not measure a physical microphone, Android notification delivery, or battery consumption.

## Baseline and approval record

- Branch: `main`.
- Baseline commit: `6e98d54a166f2d6d617ee0e36a0f2cd499659882`.
- Durable baseline source: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/source/baseline/backend
- Original source hashes and effective baseline settings: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/baseline-source.json
- Existing backend suite before changes: **280 passed in 7.78 seconds**. One existing Starlette/httpx deprecation warning.
- Provider credentials were checked for presence and used locally; they are excluded from benchmark artifacts.
- Approved TTS plan: OpenMontage `elevenlabs_tts`, ElevenLabs `eleven_v3`, Indian voice Viraj (`bajNon13EdhNMndG3z05`), Hindi, Malayalam, Tamil, Telugu, Marathi and Indian English. Up to 2,000 submitted characters, including retries; reference estimate up to $0.60, subject to account billing.
- Approved live-test ceiling: 120 minutes of Gnani streaming and 600 Luna calls for this round. Existing ElevenLabs allowance before generation: 2,206 characters.
- A connected Android device was unavailable during preflight. Local audio replay and provider timings are reported separately from device performance.

## Measurement design

The archived baseline and immutable candidate snapshots run through the same benchmark-only server wrapper. It records monotonic timestamps, actual OpenAI token usage and returned service tier, Gnani speech/processing/transcript events, and provider connection durations. It does not change the public protocol or insert target identifiers into ASR hints.

The client performs real pairing, intent extraction, confirmation, and monitoring. It waits for `READY`, then sends 1,024-byte mono PCM16 frames at 16 kHz every 32 ms, including silence. Each test retains all events through the observation window so a transient false alert followed by a correction remains visible.

Primary measurements:

1. Setup request → confirmed monitoring task.
2. WebSocket connect → `READY`.
3. Reference last-speech sample → first and last final transcript, reported separately.
4. Reference last-speech sample → first alert received by the client.
5. Transcript → alert, Luna request duration, and provider-reported transcription duration.
6. Correct target and counter, false/missed alerts, corrections and spoken stop handling.
7. Audio sender lateness, connection failures, token usage, actual service tier, and cumulative test usage.

The speech boundary comes from the saved fixture metadata. TTS generation time is excluded. Percentiles from this small synthetic corpus are descriptive; repeated replay uses identical files and is not a new independent speech sample. Published model prices are used only for reference cost estimates, not invoice claims.

The target-and-counter benchmark is stricter than the production rule that permits a clear token-only alert. A correct-token alert with an absent counter is recorded as **inconclusive for complete counter recognition**, not a wrong-target false positive. A wrong counter is a separate failure. Provider failures, incomplete latest interpretations, missing counters and observed wrong-target alerts retain distinct classifications.

The analyzer verifies the manifest and scorer hashes, uniformly rescores the frozen evidence, and retains original client verdicts alongside reviewed verdicts. Model-to-alert timing is joined to the alert's source/observation IDs; the last model call in a stream may have caused a later correction rather than the first alert. Failed and unfinished calls are counted separately from returned-response latency distributions.

## Speech fixture generation

OpenMontage generated **24 clips / 99.44 seconds** in **77.68 seconds**, using **1,250 submitted Unicode characters**. All 24 calls returned HTTP 200; no retries or regeneration were used. The tool's cumulative text-length estimate is **$0.3750**, not a billing invoice. The 24 provider `character-cost` headers sum to **276 accounting units**. After the initial 22 clips, ElevenLabs' subscription counter rose from 7,794 to 8,037, a **243-unit** increase matching those calls' headers. Submitted Unicode characters, provider accounting units and USD estimates are distinct. The ledger is /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/tts/accounting-summary.json.

The **30 cases** comprise 28 monitoring cases and two spoken-setup cases. Monitoring includes a positive announcement, a near-miss number, a spoken stop request, and a rapid two-announcement sequence in each of six languages, plus Hindi/Malayalam corrections and cancellations. Spoken setup is tested in Hindi and Malayalam. Positive examples call token 442 to counter 2; near misses call 443 to counter 3. Reused recordings are intentional paired inputs.

All WAVs are mono PCM16 at 16 kHz. Audio and alignment hashes, prompts, English glosses, tool results and cost reservations are retained. Tamil's aligned final timestamp exceeded its WAV duration by 1 ms; only the metadata boundary was bounded to the file endpoint, preserving the raw alignment. Native-speaker listening review has not been performed. The aligned punctuation endpoint is a reproducible reference boundary, not an independently verified human speech endpoint.

## Preliminary API compatibility probes

These probes test setup intent extraction on one identical request, not speech-to-alert latency. Every request returned a valid structured intent. Fast requests were actually served as `fast`.

| Probe | Measured request/parse time | Returned reasoning tokens |
|---|---:|---:|
| Baseline, implicit reasoning / default tier | 6,489 ms | 68 |
| Explicit `low`, default tier | 6,781 ms | 65 |
| Explicit `none`, default tier | 2,360 ms | 0 |
| Implicit reasoning, `fast` tier | 1,952 ms | 62 |
| Explicit `low`, `fast` tier | 2,026 ms | 71 |

Each setting has only one observation here. Reasoning level, routing, caching, output length and network variation prevent treating these probes as a controlled speed ranking. The audio experiments below provide the task-level comparison.

## Pilot findings and benchmark corrections

The three-case pilot is retained separately and excluded from the formal comparison. It exposed:

- **Scoring mismatch:** the Hindi alert correctly reported token 442 and `काउंटर दो`. A scorer comparing only with the English label `counter 2` incorrectly marked its location wrong. The corpus now supplies explicit fixture-specific native location aliases. These are test annotations, not production translation or number-parsing rules; literal results remain available for inspection.
- **Actual grounding failure:** the Malayalam transcript contained `കൗണ്ടർ രണ്ടിലേക്ക്`, but Luna returned `കൗണ്ടർ രണ്ട്`. CueBell correctly rejected that reconstructed location with `Location has no source evidence.` The positive announcement therefore produced no alert. A separately controlled prompt-hint experiment reinforces exact grammatical forms without weakening the evidence validator.
- **Correction scoring:** the Hindi correction arrived before a confirmed initial match. Suppressing the alert is a valid outcome even when there is no previous emitted alert to retract. Retraction observations and any transient false-alert exposure are still reported separately.
- **Replay drift:** imposing a fresh 32 ms minimum interval after every slightly late timer accumulated about 232 ms of drift over the first positive replay. The formal client uses absolute deadlines, bounded recovery from small scheduling jitter, and rebasing after real stalls. It still sends all PCM and silence without backlog bursts.

For negative cases, the analysis checks transcript receipt and the server-side completion of the latest interpretation. Silence at the client alone does not prove a model completed its decision. Multi-utterance first-transcript timing can precede the final cue and is not pooled with single-announcement recognition latency.

## Experiment configurations

The configuration files isolate orchestration, reasoning effort (`low`/`none`), Fast service tier, compact inputs, low verbosity, explicit prompt caching, 400/350/300 ms Gnani silence thresholds, 600 ms correction grace, a 1,024-token output ceiling, and exact-location quotation guidance. Spoken setup separately compares the existing 3.5-second pause with 1.5 seconds. A final combined configuration is selected only after inspecting recognition and correction outcomes.

The screening set is small and intended to choose follow-up experiments. Full six-language replay, a separate matched five-case comparison, and three setup replays per language provide follow-up evidence. Each run records its input manifest hash, client hash, server source hashes, actual provider settings and returned service tier. Parallel screening uses separate local server instances; concurrency and ordering are retained in the matrix manifest.

## Evidence files and reproduction

Benchmark server: /home/mathew/Arrakis/CueBell/backend/benchmarks/serve.py

Provider-trace analyzer: /home/mathew/Arrakis/CueBell/backend/benchmarks/analyze_traces.py

Real-time replay client: /home/mathew/Arrakis/CueBell/backend/benchmarks/run_pipeline.py

Isolated experiment runner: /home/mathew/Arrakis/CueBell/backend/benchmarks/run_matrix.py

Configurations and raw evidence: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13

Saved first candidate source: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/source/candidate-v1/backend

Saved final candidate source: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/source/candidate-v2/backend

Original replay/server/runner source: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/source/benchmark-harness-v1

Host/software metadata: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/environment.json

The host is an AMD Ryzen 7 4800H running Linux, with Python 3.12.14, OpenAI SDK 2.54.0, FastAPI 0.162.0 and websockets 16.1.1. OpenAI uses `api.openai.com`; no base-URL override was present. All replay/server timestamps share the host's monotonic clock.

To repeat a monitoring comparison with the existing recordings, use a fresh output prefix and a private access-code file containing a random test code of at least 16 characters. This invokes real paid providers. The original private file was outside the evidence directory; recreate it if temporary storage has been cleared. Provider keys are read from the local backend environment.

```bash
/home/mathew/Arrakis/CueBell/backend/.venv/bin/python /home/mathew/Arrakis/CueBell/backend/benchmarks/run_matrix.py \
  --variants baseline fast-orchestrated \
  --source /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/source/candidate-v2/backend \
  --baseline-source /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/source/baseline/backend \
  --env-file /home/mathew/Arrakis/CueBell/backend/.env \
  --access-code-file /tmp/opencode/cuebell-benchmark-20261113/access-code \
  --configs /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/configs \
  --manifest /home/mathew/Arrakis/CueBell/backend/benchmarks/corpus.json \
  --output /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13 \
  --prefix reproduction-a --concurrency 1 --port 8090 --tail-silence 24
```

For spoken setup, add `--mode request`; the client then selects the two request fixtures. Add `--repeat 3` for three replays of each selected fixture. Each variant writes `.run.json`, raw client/server `.jsonl`, process logs and a client summary. Analyze completed `.run.json` files with /home/mathew/Arrakis/CueBell/backend/benchmarks/analyze_campaign.py and the explicit `--adjudications` file when reproducing the secondary reviewed score.

The durable baseline was reconstructed from the recorded Git commit and verified against all ten original application-source hashes. Benchmark output, source snapshots and fixture hashes provide the reproducibility record; live API responses are nondeterministic. All formal runs used replay-client SHA256 `350ea8efad5dd6160705f815562a20c7c13f4cbcc270eb160fb0b42b03c07d58`; that exact source is retained in the harness snapshot even if the working file is subsequently formatted. The analyzer uses the verified snapshot when the working scorer hash differs.

Offline analysis, with no provider calls:

```bash
/home/mathew/Arrakis/CueBell/backend/.venv/bin/python /home/mathew/Arrakis/CueBell/backend/benchmarks/analyze_campaign.py \
  /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/full-v1-baseline.run.json \
  /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/validation-v2-fast-orchestrated.run.json \
  --adjudications /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/adjudications.json \
  --output /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/reanalysis.json
```

## Completed baseline and setup experiment

The full archived-baseline run completed all 28 monitoring trials. Original client scoring gave **22 pass / 2 fail / 4 inconclusive**. A separately recorded, uniformly applied label review accepts Telugu `కౌంటర్. రెండుకు`: it differs from the predeclared counter-two label only by an ASR-inserted period. This changes the reviewed result to **23 pass / 1 fail / 4 inconclusive**, without changing raw evidence.

- Five of six single-announcement positives passed. Their speech-reference-end → alert latency was **5,488 ms median / 7,717 ms p95**. The remaining positive encountered an OpenAI connection error.
- The real failure was a Tamil burst: token 442 was incorrectly associated with the preceding announcement's counter three. Exact quotation alone does not establish the correct relationship between entities.
- English burst monitoring emitted the correct token with an absent counter. Two Malayalam correction/cancellation trials encountered 12-second OpenAI timeouts. These are not counted as successful negative decisions.
- All six near-miss and all six spoken-stop cases passed. Spoken-stop latency was **3,656 ms median / 5,761 ms p95**.
- There were no unexpected/wrong-target alerts in this run; the wrong-counter failure is counted separately.
- Of 69 OpenAI attempts, 66 returned responses; the errors were one connection failure and two timeouts. Completed observation calls took **4,429 ms median / 8,222 ms p95**. The median delay from the causally associated completed model response to a successful positive alert was **112 ms**.

Spoken setup at the original 3.5-second pause passed **6/6** trials, with **10,747 ms median / 11,124 ms p95** from reference speech end to confirmation. The combined request transcript arrived about **4,411 ms** after speech end; this includes the setup aggregation pause and is not raw Gnani transcription latency.

Changing only the setup pause to 1.5 seconds passed the three Hindi trials but truncated all three Malayalam recordings. The provider had already sent a second `speech_start`, which the original completion logic ignored. All three truncated trials remain **inconclusive**, even though Luna extracted token 442 from the incomplete request. A speech-aware completion experiment tracks outstanding utterance IDs before allowing the shorter quiet period to complete capture.

Raw and reviewed analyses: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/initial-baseline-analysis.json and /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/baseline-reviewed-analysis.json

Explicit secondary label review: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/adjudications.json

## Fourteen-setting screening result

Each arm replayed the same six cases: three positives, one near miss, one correction and one voice-stop request. The table retains all non-passes. Positive latency is **conditional on a passing target-and-counter result**; rows with different successful-case counts are not accuracy-neutral speed comparisons.

| Setting | Pass / fail / inconclusive, of 6 | Passing positives, of 3 | Conditional positive median |
|---|---:|---:|---:|
| Archived baseline | 5 / 0 / 1 | 3 | 6.016 s |
| Guarded scheduling + ordered writer | 5 / 0 / 1 | 3 | 6.710 s |
| Fast tier, original reasoning | 5 / 0 / 1 | 2 | 3.299 s |
| Reasoning `none` | 5 / 0 / 1 | 2 | 3.973 s |
| Reasoning `low` | 4 / 1 / 1 | 1 | 5.373 s |
| Compact inputs/source aliases | 5 / 1 / 0 | 2 | 6.800 s |
| Low verbosity | 2 / 0 / 4 | 1 | 6.973 s |
| Explicit prompt cache | 3 / 1 / 2 | 1 | 7.416 s |
| Gnani silence 400 ms | 4 / 0 / 2 | 1 | 4.572 s |
| Gnani silence 350 ms | 3 / 0 / 3 | 1 | 4.194 s |
| Gnani silence 300 ms | 2 / 0 / 4 | 1 | 3.761 s |
| Correction grace 600 ms | 4 / 0 / 2 | 2 | 5.970 s |
| Output ceiling 1,024 tokens | 5 / 0 / 1 | 3 | 6.641 s |
| Verbatim-location prompt hint | 4 / 0 / 2 | 2 | 5.586 s |

Observed reasons matter more than the conditional speed ranking:

- **Fast tier** reduced Hindi/Malayalam alert latency while retaining the original reasoning and prompt. English produced the right token but lacked its counter, a recurrent baseline-family problem after sentence splitting. This remains a non-pass.
- **Shorter Gnani silence thresholds** split the Malayalam token and counter into separate finals. The apparent endpoint saving did not establish a complete, faster target-and-counter result. Some rows also contain unrelated OpenAI setup failures; those cannot be attributed to the Gnani setting.
- **Lower reasoning and compact inputs** each reproduced the Malayalam nonverbatim-location rejection. Keeping the guard prevented an unsupported location from becoming an alert.
- **Explicit caching** did not demonstrate a benefit over the already warm baseline. One Hindi result demanded explicit pharmacy context absent from the announcement. The current explicit-cache experiment also changes prompt layout, so it is not a pure cache on/off experiment.
- **The smaller output ceiling** encountered a structured-output validation failure on correction processing. Lowering a ceiling does not guarantee fewer generated tokens or faster complete decisions.
- **Shorter grace** did not remove a fixed 600 ms from these results: inference and the existing grace already overlap.
- **Scheduling changes** target the post-interpretation wait and heartbeat/backpressure behavior. Cloud inference variation dominates their six-case total-latency comparison; the aggregate median alone cannot measure their local scheduling benefit.

### Follow-up candidate

The selected experimental profile combines Fast tier with guarded immediate/deadline flushing, independent heartbeats and an ordered bounded writer. It keeps the original reasoning, prompt layout, 2,000-token ceiling, implicit caching, 500 ms Gnani silence and 1.2-second grace. Spoken setup adds outstanding-utterance tracking and the 1.5-second quiet period.

Configuration: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/configs/fast-orchestrated.json

Selection rationale and pre-validation usage: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/validation-selection.json

The speech-aware setup trial captured all six requests completely. Four subsequently confirmed and two encountered OpenAI timeouts; that is **4 pass / 2 inconclusive**, not six successful end-to-end trials. A Fast-tier setup follow-up is evaluated separately.

## Full-corpus candidate validation

Both arms replayed the same 28 monitoring cases. Each case ran once per full-corpus arm; these are small, sequential samples, with nondeterministic provider output and network conditions.

| Outcome | Archived baseline | Fast + guarded orchestration |
|---|---:|---:|
| Original client pass / fail / inconclusive | 22 / 2 / 4 | 21 / 3 / 4 |
| Uniformly reviewed pass / fail / inconclusive | **23 / 1 / 4** | **22 / 2 / 4** |
| Complete single positives passing | 5 / 6 | 3 / 6 |
| Near misses passing | 6 / 6 | 6 / 6 |
| Spoken stops passing | 6 / 6 | 6 / 6 |
| Wrong-counter cases after label review | 1 | 1 |
| Missing-counter cases | 1 | 3 |
| Provider-degraded cases | 3 | 1 |
| Client exceptions | 0 | 0 |

The candidate's observed defects were:

1. **Hindi positive missed:** Gnani produced the correct announcement, but Luna's extracted evidence failed the exact-source-span check: `Evidence is not a verbatim span of the source.` The completed interpretation produced no alert. The validator was retained.
2. **Tamil burst wrong counter:** token 442 was associated with the preceding token's counter three. This also occurred in baseline; quoting real words does not prove the correct token/counter association.
3. **Missing counters:** Tamil positive, English positive and English burst emitted the right token without a counter. The English positive's **222 ms** apparent speech-end → alert time is not a valid complete target-and-counter result.
4. **Malayalam cancellation timeout:** the last interpretation hit the 12-second OpenAI timeout. Absence of an alert is not credited as a completed negative decision.

No wrong-target or unexpected-negative-case alert was observed in either full arm. This does not erase the wrong-counter failure or establish a venue false-alert rate. Correction/cancellation suppression was exercised, but neither full arm demonstrated an actual emitted-alert retraction; retraction behavior remains covered by offline regression tests rather than this live sample.

### Latency with explicit populations

| Measurement | Baseline | Candidate | Population / interpretation |
|---|---:|---:|---|
| Passing single positives, median / p95 | 5.488 / 7.717 s | 3.222 / 3.804 s | **Different cohorts:** 5 versus 3 passes; not an accuracy-neutral speedup |
| Same two passing positives, median | 5.825 s | 3.192 s | Malayalam + Telugu only; excludes other failed/inconclusive positives |
| Same four passing bursts, median | 7.479 s | 3.376 s | Hindi, Malayalam, Telugu, Marathi; conditional on success |
| Six spoken stops, median | 3.656 s | 2.357 s | Same six inputs; Hindi individually became slower |
| Completed observation calls, median / p95 | 4.429 / 8.222 s | 2.525 / 4.967 s | 38 versus 42 returned observations; errors separately counted |
| All terminated OpenAI attempts, median / p95 | 3.674 / 8.907 s | 2.108 / 4.813 s | Includes recorded error durations, 69 versus 71 attempts |
| Causal model-end → passing-positive alert, median | 112.3 ms | 0.78 ms | Local relay/scheduler path, 5 versus 3 successful positives |
| Gnani-reported transcription duration, median / p95 | 114 / 253 ms | 117 / 266 ms | 43 finals each; excludes endpoint wait and network transit |

The strongest measured latency change is in Luna processing and the local post-model wait, not in Gnani's transcription duration. Ordinary input framing remains 32 ms, Gnani's configured silence remains 500 ms, and correction grace remains 1.2 seconds. Grace overlaps interpretation; it is not a second fixed delay added afterward.

All 70 returned candidate responses reported service tier `fast`; baseline's 66 returned responses reported `default`. Recorded cache-hit input shares were already **90.12% baseline / 89.06% candidate**. These were warm, shared-prefix experiments, not isolated cold-cache tests. Reference token costs for these two full arms were **$0.011275 / $0.025499**, respectively; token counts and failures differ, so this is not a fixed per-request cost ratio.

Both full arms had the same script-reference lexical errors: **WER 46/287 = 16.03%**, **CER 60/1,607 = 3.73%**. Normalization uses Unicode NFKC, case folding and punctuation removal, without number-word conversion; CER counts code points, not grapheme clusters. These scores compare against the intended TTS scripts, not independently transcribed audio, and are secondary to correct identifiers, counters and outcomes.

## Matched follow-up and spoken setup

The separate five-case matched replay gave **4 pass / 0 fail / 1 inconclusive** for baseline and **5 / 0 / 0** for the candidate. The common successful Hindi/Malayalam positives improved from **5.663 s to 3.830 s median (32.4%)**. Hindi was 5.568 → 4.467 s; Malayalam 5.758 → 3.192 s. The candidate also returned the English counter correctly in this replay; baseline did not. That contrast with full-corpus validation illustrates response variability rather than proof that the issue is fixed.

| Spoken-setup configuration | Pass / inconclusive, of 6 | Complete source audio | Confirmation median / p95 |
|---|---:|---:|---:|
| Baseline 3.5-second pause | 6 / 0 | 6 / 6 | 10.747 / 11.124 s |
| Naive 1.5-second pause | 3 / 3 | 3 / 6 | 7.560 / 8.076 s, **Hindi successes only** |
| Speech-aware 1.5-second pause, default tier | 4 / 2 | 6 / 6 | 8.378 / 9.340 s, four successes; two model timeouts |
| Speech-aware 1.5-second pause, Fast tier | **6 / 0** | **6 / 6** | **6.213 / 7.364 s** |

Each setup arm contains three replays of one Hindi and one Malayalam recording. The final Fast arm's overall median was **42.2% lower** than baseline with equal observed completion counts. Combined transcript delivery improved from **4.411 s to 2.254 s median**, and subsequent Luna processing also shortened. Six synthetic successes are a useful result, not a multilingual production reliability estimate.

## Implemented code and adoption decision

The implementation is on `main` in the working tree. The following changes are available for controlled use:

- /home/mathew/Arrakis/CueBell/backend/app/config.py: validated, optional Gnani/Luna controls and orchestration/setup switches; absent provider options preserve the original request shape.
- /home/mathew/Arrakis/CueBell/backend/app/gnani.py: forwards explicitly configured endpointing parameters while preserving the paced PCM contract and unbiased ASR input.
- /home/mathew/Arrakis/CueBell/backend/app/intelligence.py and /home/mathew/Arrakis/CueBell/backend/app/prompts.py: optional reasoning/tier/verbosity/cache/output controls, compact scoped source aliases restored before validation, and generic verbatim-location guidance.
- /home/mathew/Arrakis/CueBell/backend/app/engine.py: exposes the next pending deadline for scheduling.
- /home/mathew/Arrakis/CueBell/backend/app/main.py: guarded immediate/deadline flushing, independent heartbeat scheduling, bounded ordered outbound delivery, speech-aware setup completion, and cancellation of workers before slow provider teardown.
- /home/mathew/Arrakis/CueBell/backend/.env.example: documents every opt-in setting.
- /home/mathew/Arrakis/CueBell/backend/benchmarks: real-provider instrumentation, corpus, replay client, matrix runner and offline audited analysis.

The shutdown fix addresses a reproduced race: a 4-second audio watchdog, 4.5-second grace and 1-second provider shutdown previously allowed an optimized worker to emit a pending alert after coverage failed. Workers now stop and the generation is invalidated before awaiting provider exit. Late results after pause/stop are rejected, and ordered control/error delivery is retained.

Speech-aware setup uses outstanding utterance IDs rather than a single speaking flag. A new utterance may start before the previous final arrives. Matching finals, including empty finals, resolve their own IDs; the shortened quiet period cannot finish while another known utterance remains outstanding. Missing completion metadata is bounded by the existing setup timeout.

**Adoption decision:** retain baseline defaults and ship the new controls as opt-in experiments. Fast tier plus speech-aware setup is the strongest measured setup candidate. The full monitoring profile is not promoted because the complete target-and-counter gate did not hold. This small experiment cannot establish that Fast tier caused the additional errors; it establishes that accuracy preservation has not yet been demonstrated.

Keep the original reasoning, 500 ms Gnani silence, 1.2-second grace and 2,000-token ceiling for now. Shorter silence, reduced reasoning, compact inputs, explicit-cache layout changes, smaller output caps and the exact-location hint did not establish a sufficiently consistent quality/speed benefit here. The guarded scheduler still waits for in-flight/queued interpretation to preserve correction ordering; this work does not claim to eliminate all head-of-line blocking.

Next targeted work should address cross-utterance token/counter association and verbatim multilingual evidence generation, then rerun a larger held-out, native-reviewed set. Physical PA replay, microphone behavior, Android alert delivery and long-session power/thermal performance require a connected phone and remain separate measurements. Noise suppression was excluded from this implementation round.

## Final usage, checks and evidence

- **419 OpenAI attempts**, including **15 recorded errors** and **one unfinished/cancelled call**; **403 returned responses**. Counts include probes, pilot and all formal runs, with trace paths deduplicated.
- **72.080 Gnani connection minutes**, within the approved 120-minute ceiling; OpenAI attempts are within the 600-call ceiling.
- **1,250 submitted ElevenLabs characters**, within the 2,000-character ceiling; 24 successful generations, no retries.
- OpenAI returned-usage reference estimate: **$0.094774**. ElevenLabs text-length reference estimate: **$0.3750**. Gnani charges are not estimated here. These are not invoice totals; failed/cancelled calls can incur usage absent from recorded responses.
- Backend: **410 tests passed**; the existing Starlette/httpx warning remains. JUnit evidence: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/backend-tests.xml.
- Final Ruff lint, Ruff formatting and whitespace checks passed. Formatting preserved the Python AST of all four adjusted files; 42 focused benchmark tests passed afterward, and the original replay snapshots stayed byte-identical.
- Mobile: lint, TypeScript checking, **43 tests**, and service-origin checking passed. Existing Node module-type warnings remain. No physical Android benchmark is implied.
- All 22 formal runs passed manifest/original-scorer hash verification. The saved evidence was scanned for configured provider-key and pairing-secret bytes; none were found.

Final audited full/matched/setup comparison: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/final-validation-analysis.json

Uniformly rescored analysis of all 22 formal runs: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/final-campaign-analysis.json

Deduplicated provider usage: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13/provider-summary.json

Complete run records, WAVs, alignments, source snapshots, annotations, provider traces, process logs and configuration files: /home/mathew/Arrakis/CueBell/docs/benchmarks/2026-11-13

This report records the completed local benchmark round; subsequent publication and deployment are tracked in Git and deployment records.
