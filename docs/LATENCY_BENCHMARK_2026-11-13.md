# Real-provider pipeline benchmark

13 November 2026. **Retain baseline defaults.** Setup improved with equal completion counts; faster selected monitoring failed the full quality gate.

## Test design and coverage

**22 formal runs, 174 attempts:** 150 monitoring and 24 setup. The corpus has 30 cases from 24 synthetic clips across Hindi, Malayalam, Tamil, Telugu, Marathi and Indian English. Setup covers Hindi/Malayalam only. Repetition is not independent speech coverage.

Real Gnani Prisma/GPT-6 Luna used 16-kHz PCM16, 1,024 bytes/32 ms including silence, without identifier hints. One Linux Ryzen 7 4800H host used a monotonic clock. No phone, microphone, notification, battery or denoising measurements.

Speech end uses TTS alignment without native-speaker review. Median is the middle value; interpolated small-sample p95 is not a production guarantee.

## Full monitoring comparison

Complete positives require the correct target and counter. Missing counters are inconclusive; wrong counters fail. Timed-out interpretation is not a successful negative.

| Same 28 cases per arm | Baseline | Fast + guarded orchestration |
|---|---:|---:|
| Original pass / fail / inconclusive | 22 / 2 / 4 | 21 / 3 / 4 |
| Uniformly reviewed outcomes | **23 / 1 / 4** | **22 / 2 / 4** |
| Complete single positives passing | 5/6 | 3/6 |
| Wrong / missing counter cases | 1 / 1 | 1 / 3 |
| Provider-degraded cases | 3 | 1 |

[Review policy](benchmarks/2026-11-13/adjudications.json) uniformly accepts an ASR-inserted Telugu period; original verdicts remain. Both arms attached Tamil token 442 to the prior counter three. The candidate rejected nonverbatim Hindi evidence. Its apparent 222 ms English alert lacked a counter and was not a complete success.

Near misses and spoken stops passed 6/6 per arm. No wrong-target or unexpected-negative alerts occurred, but no venue false-alert rate or retraction of an already emitted alert was established.

| Median timing | Baseline | Candidate | Denominator |
|---|---:|---:|---|
| Passing positives | 5.488 s | 3.222 s | Different cohorts, 5 versus 3 |
| Spoken stop | 3.656 s | 2.357 s | Same six inputs; Hindi slowed |
| Completed Luna observations | 4.429 s | 2.525 s | 38 versus 42 returned observations |
| Causal model end to alert | 112.322 ms | 0.778 ms | Five versus three passing positives |
| Gnani-reported transcription | 114 ms | 117 ms | 43 finals each; excludes endpoint wait/transit |

Causal delivery joins source/observation/extraction IDs, not the last model call. Failed/unfinished responses are separate. Returned-usage cost estimates were $0.011275 versus $0.025499, with warm cache and unequal calls/tokens, not invoices. Script-reference word errors were 46/287 and character errors 60/1,607 in both arms, without equal task accuracy.

## Matched follow-up and spoken setup

Five-case follow-up outcomes were baseline 4/0/1 and candidate 5/0/0. The same two passing Hindi/Malayalam positives improved **5.663 → 3.830 s (32.4%)**. English counter recovery varied between runs.

| Setup arm, six attempts | Pass / inconclusive | Complete audio | Confirmation median |
|---|---:|---:|---:|
| Original 3.5 s pause | 6 / 0 | 6/6 | 10.747 s |
| Naive 1.5 s pause | 3 / 3 | 3/6 | 7.560 s, passes only |
| Speech-aware, default tier | 4 / 2 | 6/6 | 8.378 s, passes only |
| Speech-aware, Fast tier | 6 / 0 | 6/6 | 6.213 s |

Each repeats two recordings three times. Tracking unfinished utterances fixed Malayalam truncation; default-tier timeouts remained. Fast setup improved **42.2%**, not general multilingual reliability.

## Failed variants and evidence

Fourteen six-case screening arms tested scheduling, tier/reasoning, prompts/cache, endpointing/grace and output limits. No quality-preserving monitoring improvement emerged. Shorter silence split identifiers/counters; compact/lower-reasoning variants failed evidence checks; output limits hit validation failures. Grace overlaps inference. Full screening tables and accounting remain in the full report.

[Final analysis](benchmarks/2026-11-13/final-campaign-analysis.json), [raw campaign and source snapshots](benchmarks/2026-11-13/), [candidate settings](benchmarks/2026-11-13/configs/fast-orchestrated.json) and [backend defaults](../backend/app/config.py) retain provenance. New controls remain off. No paid replay accompanied this edit.

## Reproduce without changing evidence

From the repository root, this offline audit uses temporary dependencies and resolves historical paths without editing evidence or calling providers:

```bash
uv run --no-project --with httpx --with websockets python - <<'PY'
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

For a separately authorized **paid** replay, approve a budget and configure private keys/access-code files first. Relocate the manifest temporarily; preserve originals:

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

Use fresh output/prefix; setup adds `--mode request --repeat 3`. Provider results vary. Paid replay was not rerun.

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/LATENCY_BENCHMARK_2026-11-13.md).
