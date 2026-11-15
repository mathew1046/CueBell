# Real-provider pipeline benchmark

Experiment date: 13 November 2026. See the [plain-language overview](PIPELINE_OPTIMIZATION.md) for the main results.

**Decision:** retain baseline defaults. Speech-aware setup plus Fast tier improved the observed setup median with equal completion counts. The combined monitoring candidate was faster on selected successful recordings but did not pass the full target-and-counter quality gate.

## Test design and coverage

- **22 formal runs / 174 case attempts:** 150 monitoring, 24 spoken setup. Compatibility probes and the discarded three-case pilot are separate.
- **30 cases / 24 synthetic clips:** 28 monitoring cases and two setup cases. Hindi, Malayalam, Tamil, Telugu, Marathi and Indian English each include a positive, near miss, spoken stop and rapid two-announcement sequence. Hindi/Malayalam add correction and cancellation cases; setup uses those two languages only.
- Real Gnani Prisma and `gpt-6-luna`; the same saved audio is replayed through the native WebSocket protocol, after pairing, intent extraction and confirmation. Target IDs are not added to ASR hints.
- Mono PCM16 at 16 kHz, 1,024 bytes every 32 ms, including silence. Absolute sender deadlines avoid cumulative timer drift without backlog bursts. All events remain visible through the observation window, including transient alerts later corrected.
- One Linux AMD Ryzen 7 4800H host, Python 3.12.14, OpenAI SDK 2.54.0. Client and server use the same monotonic clock. **No physical Android device**, microphone, notification, vibration, battery or denoising measurement is included.

The reference speech end is the final non-whitespace character's TTS alignment endpoint, including punctuation, not an independently verified human boundary. A Tamil endpoint overrun of 1 ms was bounded to the WAV endpoint without editing raw alignment. No native-speaker listening review was performed. Replaying the same recording is not another independent speech sample. Small-sample p95 uses linear interpolation and is descriptive, not a production tail guarantee.

### Scoring and provenance

Complete positives require the right target **and counter**, stricter than CueBell's allowed token-only production alert. A missing counter is inconclusive for this benchmark; a wrong counter is a failure. A completed negative decision requires the final transcript's interpretation to finish in the observation window. Silence after a provider timeout is not a successful negative.

The verified original scorer and manifest are used to rescore every run. An explicit secondary [label review](benchmarks/2026-11-13/adjudications.json) accepts Telugu `కౌంటర్. రెండుకు`, differing from its fixture alias only by an ASR-inserted period, uniformly across configurations. This is a test annotation, not a production parser or native-speaker review. Original client verdicts remain available.

Model-to-alert timing is joined by source/observation/extraction IDs. The last model call may belong to a later correction, so it cannot stand in for the call causing the first alert. Returned-response distributions exclude failed and unfinished calls; their counts and recorded error durations are separate. WER/CER compare against intended scripts using NFKC, case folding, punctuation and whitespace normalization, without number conversion. CER counts code points, not grapheme clusters.

## Full monitoring comparison

Each arm replayed the same 28 cases once. They are small sequential samples with nondeterministic provider/network behavior, not randomized population estimates.

| Outcome | Archived baseline | Fast + guarded orchestration |
|---|---:|---:|
| Original client pass / fail / inconclusive | 22 / 2 / 4 | 21 / 3 / 4 |
| Uniformly reviewed pass / fail / inconclusive | **23 / 1 / 4** | **22 / 2 / 4** |
| Complete single positives passing | 5/6 | 3/6 |
| Near misses passing | 6/6 | 6/6 |
| Spoken stops passing | 6/6 | 6/6 |
| Wrong-counter cases | 1 | 1 |
| Missing-counter cases | 1 | 3 |
| Provider-degraded cases | 3 | 1 |

The shared Tamil burst failure attached token 442 to the preceding announcement's counter three. Exact quotation did not prove the correct relationship. The candidate Hindi positive failed the verbatim-evidence check despite a correct transcript. Tamil/English positives and the English burst lacked counters. The English positive's apparent 222 ms alert is **not** a complete successful result.

Baseline encountered one OpenAI connection error and two timeouts; the candidate had one timeout. No wrong-target or unexpected-negative-case alerts were observed in either arm. That is not a venue false-alert rate. Correction suppression was exercised, but neither full arm demonstrated retraction of an already emitted alert; live retraction remains unproven by this sample.

| Timing | Baseline | Candidate | Population and limit |
|---|---:|---:|---|
| Passing single positives, median / p95 | 5.488 / 7.717 s | 3.222 / 3.804 s | Different cohorts: five versus three passes |
| Spoken stop, median | 3.656 s | 2.357 s | Same six inputs; Hindi became slower |
| Completed Luna observations, median / p95 | 4.429 / 8.222 s | 2.525 / 4.967 s | 38 versus 42 returned observations; not errors |
| Causal model end to passing-positive alert, median | 112.322 ms | 0.778 ms | Five versus three passes; local delivery, not whole pipeline |
| Gnani-reported transcription, median / p95 | 114 / 253 ms | 117 / 266 ms | 43 finals each; excludes endpoint wait and transit |

All 66 returned baseline responses reported `default`; all 70 candidate responses reported `fast`. Recorded cache-hit input shares were 90.12% and 89.06%, so these are warm shared-prefix experiments, not cold-cache tests. Full-arm Luna returned-usage estimates were $0.011275 and $0.025499. Different token counts, failures and call counts prevent a fixed per-request cost ratio; these are not invoices.

Both arms had script-reference WER **46/287 = 16.03%** and CER **60/1,607 = 3.73%**. Equal aggregate script errors do not establish equal task accuracy.

## Matched follow-up and spoken setup

A separate five-case replay produced baseline **4 pass / 0 fail / 1 inconclusive** and candidate **5 / 0 / 0**. On the two common passing positives, the median was **5.663 → 3.830 s**, a **32.4% reduction**. Hindi: **5.568 → 4.467 s**; Malayalam: **5.758 → 3.192 s**. The candidate returned the English counter here but not in full validation. This shows response variability, not a resolved defect.

| Setup arm, six attempts each | Pass / inconclusive | Complete audio | Confirmation median / p95 |
|---|---:|---:|---:|
| Original 3.5-second pause | 6 / 0 | 6/6 | 10.747 / 11.124 s |
| Naive 1.5-second pause | 3 / 3 | 3/6 | 7.560 / 8.076 s, Hindi passes only |
| Speech-aware 1.5-second pause, default tier | 4 / 2 | 6/6 | 8.378 / 9.340 s, four passes only |
| Speech-aware 1.5-second pause, Fast tier | **6 / 0** | **6/6** | **6.213 / 7.364 s** |

Each arm repeats one Hindi and one Malayalam recording three times. Naive shortening ignored a second `speech_start` and truncated Malayalam. Outstanding-utterance tracking fixed capture in this sample; two subsequent default-tier model timeouts still prevented confirmation. The Fast arm reduced the observed median **42.2%** with equal completion counts. Combined setup transcript delivery improved **4.411 → 2.254 s**; that includes aggregation pause and is not raw Gnani recognition time.

## Screening: keep the unsuccessful variants visible

Each of 14 arms replayed the same six cases: three positives, one near miss, one correction and one stop. Positive medians below include **only passing positives**. Different success counts make them unsuitable as an accuracy-neutral speed ranking. Screening used parallel isolated server instances; order/concurrency are retained in the matrix record.

| Setting | Pass / fail / inconclusive | Passing positives / 3 | Positive median |
|---|---:|---:|---:|
| Baseline | 5 / 0 / 1 | 3 | 6.016 s |
| Guarded scheduling + ordered writer | 5 / 0 / 1 | 3 | 6.710 s |
| Fast, original reasoning | 5 / 0 / 1 | 2 | 3.299 s |
| Reasoning `none` | 5 / 0 / 1 | 2 | 3.973 s |
| Reasoning `low` | 4 / 1 / 1 | 1 | 5.373 s |
| Compact inputs/source aliases | 5 / 1 / 0 | 2 | 6.800 s |
| Low verbosity | 2 / 0 / 4 | 1 | 6.973 s |
| Explicit cache/layout | 3 / 1 / 2 | 1 | 7.416 s |
| Gnani silence 400 ms | 4 / 0 / 2 | 1 | 4.572 s |
| Gnani silence 350 ms | 3 / 0 / 3 | 1 | 4.194 s |
| Gnani silence 300 ms | 2 / 0 / 4 | 1 | 3.761 s |
| Grace 600 ms | 4 / 0 / 2 | 2 | 5.970 s |
| Output cap 1,024 tokens | 5 / 0 / 1 | 3 | 6.641 s |
| Verbatim-location hint | 4 / 0 / 2 | 2 | 5.586 s |

Shorter silence split Malayalam token and counter across finals. Some endpoint arms also had unrelated OpenAI setup failures, which cannot be attributed to Gnani endpointing. Lower reasoning/compact input reproduced a nonverbatim-location rejection. Explicit caching changed prompt layout too and did not establish a benefit over warm baseline caching. The smaller output cap encountered structured-output validation failure during correction. Shorter grace did not remove a fixed 600 ms because grace already overlaps inference. Scheduling-only total latency was slower in this small sample despite lower local delivery delay; cloud variability prevents isolating its effect from aggregate medians.

The selected [candidate configuration](benchmarks/2026-11-13/configs/fast-orchestrated.json) combines Fast tier, guarded scheduling, independent heartbeats, a bounded ordered writer, speech-aware setup and a 1.5-second setup pause. Original reasoning/prompt layout, implicit caching, 2,000-token cap, 500 ms default Gnani silence and 1.2-second grace remain. All new optimization switches remain off in backend defaults. The scheduler still waits for queued/in-flight interpretation; it does not eliminate head-of-line blocking. See [configuration defaults](../backend/app/config.py).

## Evidence and verification

[Immutable campaign at af0173d](https://github.com/mathew1046/CueBell/tree/af0173daa2db55b567154952e665cc6ff2734f19/docs/benchmarks/2026-11-13), also available [locally](benchmarks/2026-11-13/):

- [Final campaign analysis](benchmarks/2026-11-13/final-campaign-analysis.json), [selected validation analysis](benchmarks/2026-11-13/final-validation-analysis.json), [provider usage](benchmarks/2026-11-13/provider-summary.json).
- Each `.run.json` names its raw client `.jsonl`, provider `-server.jsonl`, settings and hashes. [Corpus](benchmarks/2026-11-13/corpus.json), WAVs, alignments and [environment](benchmarks/2026-11-13/environment.json) are retained.
- [Baseline provenance](benchmarks/2026-11-13/baseline-source.json): commit `6e98d54a166f2d6d617ee0e36a0f2cd499659882`; all ten application-source hashes verified. Archived [baseline](benchmarks/2026-11-13/source/baseline/backend), [candidate v2](benchmarks/2026-11-13/source/candidate-v2/backend) and [original harness](benchmarks/2026-11-13/source/benchmark-harness-v1) preserve code used in the experiment.
- Original scorer SHA256: `350ea8efad5dd6160705f815562a20c7c13f4cbcc270eb160fb0b42b03c07d58`. The analyzer verifies this and the manifest, falling back to the archived scorer if the working file differs.
- Deduplicated total: **419 OpenAI attempts, 403 responses, 15 errors, one unfinished call; 72.080 Gnani connection minutes**. Reference returned-usage Luna estimate $0.094774; failed/cancelled usage may be absent. Gnani billing is not estimated.
- TTS: **24 successful clips, 99.44 s, 1,250 submitted Unicode characters**, no retries. Text-length estimate $0.3750 is not an invoice. Provider headers total 276 accounting units, distinct from submitted characters. See [TTS ledger](benchmarks/2026-11-13/tts/accounting-summary.json).
- Historical checks: [410 passing backend tests](benchmarks/2026-11-13/backend-tests.xml), Ruff/format checks and 43 mobile tests. These are archived checks, not newly run tests or physical-phone results. The documentation audit reanalyzed all 22 runs and matched every reviewed outcome and by-kind latency distribution.

## Reproduce without changing evidence

Run from the repository root with backend dependencies installed. Old records contain absolute paths from the original host. This offline command resolves missing record paths by filename within their campaign directory, without modifying archived files or making provider calls:

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, 'backend/benchmarks')
import analyze_campaign as a
root = Path('docs/benchmarks/2026-11-13').resolve()
original = a.relative_to_run
def resolve(value, run):
    path = Path(value)
    return original(value, run) if path.exists() else run.parent / path.name
a.relative_to_run = resolve
reviews = json.loads((root / 'adjudications.json').read_text())['cases']
saved = {r['label']: r for r in json.loads(
    (root / 'final-campaign-analysis.json').read_text())['runs']}
runs = [a.analyze_run(p, reviews) for p in sorted(root.glob('*.run.json'))]
for run in runs:
    assert run['verdicts'] == saved[run['label']]['verdicts']
    assert run['by_kind'] == saved[run['label']]['by_kind']
print(len(runs), 'runs;', sum(r['case_count'] for r in runs), 'attempts; verified')
PY
```

For a new **paid** replay, first set an approved budget, configure provider keys privately and create a private access-code file outside the archive. Prepare a relocated manifest in temporary storage; this intentionally creates a new manifest hash. Do not edit the original:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('docs/benchmarks/2026-11-13').resolve()
data = json.loads((root / 'corpus.json').read_text())
for fixture in data['fixtures']:
    audio = root / 'audio' / Path(fixture['audio_path']).name
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == fixture['sha256']
    fixture['audio_path'] = str(audio)
Path('/tmp/cuebell-replay-corpus.json').write_text(json.dumps(data))
PY

# Requires the backend virtualenv and private files named below.
backend/.venv/bin/python backend/benchmarks/run_matrix.py \
  --variants baseline fast-orchestrated \
  --source docs/benchmarks/2026-11-13/source/candidate-v2/backend \
  --baseline-source docs/benchmarks/2026-11-13/source/baseline/backend \
  --env-file backend/.env --access-code-file /tmp/cuebell-private/access-code \
  --configs docs/benchmarks/2026-11-13/configs \
  --manifest /tmp/cuebell-replay-corpus.json \
  --output /tmp/cuebell-replay-results --prefix reproduction-a \
  --concurrency 1 --port 8090 --tail-silence 24
```

Use a fresh output/prefix. For setup, add `--mode request --repeat 3`. Live provider output is nondeterministic; a new run is not expected to reproduce identical timing or verdicts. The paid command was not rerun during this documentation audit.
