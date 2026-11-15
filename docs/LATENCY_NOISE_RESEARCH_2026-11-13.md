# Latency and noise research

Research date: 13 November 2026. This is the rationale behind the experiments, not a claim that every proposal shipped or improved recognition.

For measured pipeline results, start with [Pipeline optimization](PIPELINE_OPTIMIZATION.md) and the [real-provider benchmark](LATENCY_BENCHMARK_2026-11-13.md). Later [noise implementation](NOISE_REDUCTION_BENCHMARK_2026-11-14.md), [real-noise](REAL_NOISE_DENOISING_2026-11-14.md), [station PA](STATION_PA_DENOISING_2026-11-14.md) and [recognition diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md) reports supersede the original untested-noise proposals.

## What the research recommended

1. Measure the complete path before tuning individual stages.
2. Remove avoidable backend waits while preserving corrections, health reporting and event order.
3. Compare service tier, reasoning and Gnani endpointing separately before combining changes.
4. Test native noise suppression against raw audio using exact identifiers, not listening quality alone.
5. Measure on the actual Android service over sustained sessions. Desktop throughput is not a phone deadline or battery result.

Three parallel reviews covered mobile denoisers, recognition preservation and end-to-end latency. They used primary papers, author repositories, paper LaTeX where tables were missing, and provider documentation. The original research tooling used `arxiv-mcp-server[pdf]==0.8.2`; installing a research tool is not evidence of application performance. The [immutable original review](https://github.com/mathew1046/CueBell/blob/af0173daa2db55b567154952e665cc6ff2734f19/docs/LATENCY_NOISE_RESEARCH_2026-11-13.md) retains the detailed historical tables and tooling record. External repositories and provider documentation can change after that review.

## Measure the useful result, not just inference speed

For an isolated finalized announcement, a useful approximation is:

```text
speech end to alert
  = capture/transport + Gnani endpointing/recognition
  + max(correction grace, interpretation queue + Luna + validation)
  + scheduler wait + delivery
```

Grace starts at transcript receipt and overlaps interpretation. Continuous queued speech adds an idle barrier not captured by this simple expression. Faster inference alone need not make the alert earlier.

| Research direction | Experiment outcome or remaining constraint |
|---|---|
| Deadline wakeups, idle flushing, independent heartbeats, bounded ordered writes | Implemented as opt-in controls. Selected local delivery measurements improved; full monitoring quality still blocked promotion. |
| Fast service tier at unchanged reasoning | Promising setup and selected monitoring results; actual returned tier and token costs were recorded. Not proof of accuracy preservation. |
| Lower reasoning, compact inputs, shorter output cap, explicit cache layout | Screened; none established a consistent quality/speed benefit. A cap does not guarantee shorter output; caching was already warm. |
| Shorter Gnani silence | Screened at 400/350/300 ms against the 500 ms default. Segmentation could split token and counter. Lower configured silence is not equivalent to lower usable-result latency. |
| Speech-aware setup completion | Outstanding utterance IDs prevented the observed truncation when using a shorter pause. End-to-end provider timeouts remained a separate failure mode. |
| Continuous-backlog starvation | Still open. The optimized scheduler retains the queued/in-flight interpretation guard. Removing it without correction semantics is unsafe. |

### Provider and transport boundaries

- Prisma v3 provides finalized utterances, not token-by-token partial recognition. Streaming Luna JSON cannot bypass that dependency or the final schema/evidence checks.
- Keep 16-kHz mono PCM16, 512 samples / 1,024 bytes per 32 ms packet, including silence. A denoiser's smaller hop does not change the provider packet contract.
- Endpoint settings are connection-level. Forced periodic commits can split identifiers or corrections and need a separate experiment.
- Buffer capacity is not measured waiting time. Measure frame age and backlog before shrinking buffers.
- Do not put the monitored identifier into ASR hints. That would bias recognition toward the desired answer.
- The documented batch `with_denoise` option does not establish an equivalent live streaming switch. Provider-internal enhancement remains unverified.

Relevant sources: [Gnani streaming API](https://docs.gnani.ai/api/STT/stt-websocket.md), [Prisma v3](https://docs.gnani.ai/api/STT/models/prisma-v3.md), [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [Fast mode](https://developers.openai.com/api/docs/guides/fast-mode), [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).

Endpointing studies support measuring full user-visible delay and error trade-offs, not transferring their numerical gains to Gnani: [user-perceived latency](https://arxiv.org/abs/2104.02207), [two-pass endpoint detection](https://arxiv.org/abs/2401.08916), [endpoint detection preprint](https://arxiv.org/abs/2505.17070).

## Noise suppression: compare, do not assume a winner

CueBell must preserve a quiet, distant PA announcement and the user's stop command. A model that retains the closest or loudest speaker can remove the useful signal. Noise suppression, dereverberation, competing-speaker separation and echo cancellation for the phone's own playback solve different problems.

| Candidate | Why it merits testing | Evidence limit |
|---|---|---|
| GTCRN | Native 16-kHz model, public checkpoint and streaming ONNX; concrete sherpa-onnx integration route | Desktop throughput did not establish Android foreground-service performance or Gnani accuracy. Later experiments must be read separately. |
| FastEnhancer-T | Native 16-kHz model with streaming/export options; promising controlled desktop timing | Published timing excludes STFT/iSTFT; training/reverberation differences confound architecture comparisons. |
| UL-UNAS v2 | Quality challenger with public streaming neural inference | Whole-file waveform/STFT examples are not a complete persistent-state waveform-stream adapter; Android runtime was not verified in this review. |
| faster-enhancer.c v1 | Useful native Android implementation and paced-run evidence | Different 48-kHz Medium workload, not a 16-kHz Tiny deployment. Racing throughput and paced deadline reliability differ. |
| CoFi-Lite v1 | Promising far-field research challenger | License and deployable persistent-state streaming export were not verified in the original review. |
| μNet v1 | Low-delay embedded research direction | DSP measurements are not Android measurements; deployable checkpoint/runtime/license were unverified. |
| Android suppression / mild WebRTC | Practical raw-versus-processed baselines | Device support varies; neither API implies hardware acceleration or a fixed overhead. |
| RNNoise / DeepFilterNet | Additional candidates if simpler approaches fail | Resampling, framing, compute and model/runtime footprint require separate budgets. |

RTF is processing time divided by audio duration, not signal delay or end-to-end alert latency. Parameter count, MACs per frame, MACs per second, model download size, APK growth and runtime memory must not be used interchangeably. A low desktop RTF does not establish screen-off phone reliability.

Sources: [GTCRN](https://github.com/Xiaobin-Rong/gtcrn), [FastEnhancer v1](https://arxiv.org/abs/2509.21867v1) and [ONNX interfaces](https://aask1357.github.io/fastenhancer/onnx), [UL-UNAS v2](https://arxiv.org/abs/2503.00340v2), [Android C runtime v1](https://arxiv.org/abs/2607.25350v1), [CoFi-Lite v1](https://arxiv.org/abs/2607.10142v1), [μNet v1](https://arxiv.org/abs/2608.21155v1), [sherpa-onnx online API](https://k2-fsa.github.io/sherpa/onnx/c-api/html/speech_enhancement.html), [Android NoiseSuppressor](https://developer.android.com/reference/android/media/audiofx/NoiseSuppressor), [WebRTC](https://webrtc.googlesource.com/src/+/refs/heads/main/api/audio/audio_processing.h).

**Excluded affirmative evidence:** [GigaEdge Spench v2](https://arxiv.org/abs/2611.13243v2) was recorded as withdrawn on 11 November 2026. Cached earlier abstracts do not override that withdrawal.

## Recognition preservation and native integration

Studies of [enhancement distortion](https://arxiv.org/abs/2404.14860v1) and [observation addition](https://arxiv.org/abs/2602.20967v2) show why cleaner audio can worsen ASR and why raw/enhanced blends merit testing. Their recognizers are not Gnani. Confidence-guided multi-pass recognition is not a drop-in, single-stream frontend, and DNSMOS is not recognizer confidence.

Other studies motivate long-silence/onset tests ([DPDFNet v3](https://arxiv.org/abs/2512.16420v3)), persistent-state tests ([Fast-ULCNet](https://arxiv.org/abs/2601.14925v1)) and far-field training ([dereverberation](https://arxiv.org/abs/2505.01338v1)). They do not prove a generic reset policy or a CueBell accuracy improvement. DPDFNet's “OA loss” means over-attenuation loss, not observation addition.

Native integration should preserve one model/state per stream, preallocate buffers, keep frames off the React Native bridge, and separate DSP hops from packetization. Include initialization, waveform alignment delay, transform costs and fallback behavior. Bypass/fallback frames are not successful enhancement. A raw/enhanced blend must align delay, gain and phase; it restores noise as well as desired speech.

## Evaluation required before promotion

- Paired raw/enhanced inputs with independent references, held-out speakers/sessions and per-language results.
- Exact identifiers and counters, leading zeros, corrections/cancellations, stop commands, long target-free periods and first phonemes after silence.
- Distant PA, overlapping nearby talk, clipping, traffic/fans, reverberation and different microphone routes.
- Native capture, DSP/frame age, provider endpointing, interpretation queue, validation, outbound write, phone receipt and notification/vibration onset. Correlate IDs; use monotonic intervals and explicit cross-device clock alignment.
- Sustained screen-off phone sessions, including provider renewal, backpressure, interruptions, network changes, deadline misses, energy and thermals. Separate cold start from steady state.

Choose quality and resource gates before testing. Do not claim “no performance impact” or promote a preset because it sounds cleaner. See the [roadmap](OPTIMIZATION_ROADMAP.md) for remaining priorities and the [benchmark reproduction commands](LATENCY_BENCHMARK_2026-11-13.md#reproduce-without-changing-evidence) for offline verification and separately budgeted live replay.
