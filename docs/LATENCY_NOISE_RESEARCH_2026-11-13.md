# Latency and noise research

13 November 2026. **Research recommended measuring correct end-to-end results before promoting faster or cleaner processing.** Later experiments found useful runtime gains, but neither the faster monitoring profile nor denoising established recognition preservation.

Read the [pipeline results](PIPELINE_OPTIMIZATION.md), [noise overview](NOISE_REDUCTION.md) and [remaining priorities](OPTIMIZATION_ROADMAP.md) before the historical proposals below.

## Where delay comes from

For an isolated finalized announcement:

```text
speech end to alert = capture/transport + recognition endpointing
  + max(correction grace, interpretation queue + model + validation)
  + scheduler wait + delivery
```

Endpointing decides when speech has finished. Correction grace overlaps interpretation, rather than adding a fixed delay afterward. Continuous queued speech adds another wait not captured here.

| Direction | Finding or limit |
|---|---|
| Deadline scheduling, independent health messages, ordered bounded writes | Implemented as opt-in; promising local delivery timings did not establish full monitoring quality |
| Fast tier, unchanged reasoning | Promising setup and selected monitoring results; actual tier, tokens and cost were recorded |
| Lower reasoning, compact prompts, smaller output cap, cache layout | No consistent quality/speed benefit; baseline caching was already warm |
| Shorter Gnani silence, 400/350/300 ms versus 500 ms | Could split a token from its counter |
| Speech-aware setup completion | Prevented observed truncation, not later provider timeouts |
| Continuous-backlog starvation | Open: optimized scheduling still waits for queued/in-flight interpretation |

Prisma v3 returns finalized utterances, not token-by-token partial recognition. Streaming model JSON cannot bypass that dependency or evidence validation. Keep 16-kHz mono PCM16, 512 samples per 32 ms packet including silence. Buffer capacity is not measured waiting time. Never bias recognition with the expected identifier.

## Choosing a noise frontend

A nearby-speaker enhancer can suppress the distant announcement that matters. Noise suppression, competing-speaker separation, reverberation removal and echo cancellation solve different problems.

| Candidate | Reason to investigate | Boundary |
|---|---|---|
| GTCRN | Native 16-kHz checkpoint and streaming ONNX integration | Desktop speed is not phone reliability or recognition accuracy |
| FastEnhancer-T | 16-kHz streaming/export options | Published timing excludes frequency transforms; training differs |
| UL-UNAS v2 | Quality challenger | Persistent waveform-stream adapter and Android runtime unverified |
| faster-enhancer.c v1 | Native Android evidence | Different 48-kHz Medium workload |
| CoFi-Lite / μNet | Far-field / embedded research | Deployable export/checkpoint/runtime/licenses not fully verified |
| Android suppression / WebRTC / RNNoise / DeepFilterNet | Practical comparison candidates | Support, resampling, framing and resource budgets need testing |

Real-time factor is processing time divided by audio duration, not signal delay. Model size, operation count, download size and process memory are different measures. Preserve per-stream state, preallocate buffers, separate processing hops from provider packets, and count bypass/fallback separately from successful enhancement.

Enhancement can alter recognizer features. Delay-aligned raw/enhanced blending merits testing but restores noise too. DNSMOS quality estimates are not recognition confidence. DPDFNet's “OA loss” means over-attenuation, not observation addition.

## Sources and evaluation

The three original reviews used primary papers, author repositories and provider documentation. Sources below are retained research references, not newly live-verified claims about deployed services:

- [Gnani streaming](https://docs.gnani.ai/api/STT/stt-websocket.md), [Prisma v3](https://docs.gnani.ai/api/STT/models/prisma-v3.md), [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [Fast mode](https://developers.openai.com/api/docs/guides/fast-mode), [caching](https://developers.openai.com/api/docs/guides/prompt-caching).
- [Endpoint latency](https://arxiv.org/abs/2104.02207), [two-pass endpointing](https://arxiv.org/abs/2401.08916), [endpoint preprint](https://arxiv.org/abs/2505.17070).
- [GTCRN](https://github.com/Xiaobin-Rong/gtcrn), [FastEnhancer](https://arxiv.org/abs/2509.21867v1), [ONNX interfaces](https://aask1357.github.io/fastenhancer/onnx), [UL-UNAS](https://arxiv.org/abs/2503.00340v2), [Android C runtime](https://arxiv.org/abs/2607.25350v1), [CoFi-Lite](https://arxiv.org/abs/2607.10142v1), [μNet](https://arxiv.org/abs/2608.21155v1).
- [sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/c-api/html/speech_enhancement.html), [Android NoiseSuppressor](https://developer.android.com/reference/android/media/audiofx/NoiseSuppressor), [WebRTC](https://webrtc.googlesource.com/src/+/refs/heads/main/api/audio/audio_processing.h).
- [Enhancement distortion](https://arxiv.org/abs/2404.14860v1), [observation addition](https://arxiv.org/abs/2602.20967v2), [DPDFNet](https://arxiv.org/abs/2512.16420v3), [Fast-ULCNet](https://arxiv.org/abs/2601.14925v1), [dereverberation](https://arxiv.org/abs/2505.01338v1). Their gains do not transfer automatically to Gnani.

[GigaEdge Spench v2](https://arxiv.org/abs/2611.13243v2) was recorded as withdrawn on 11 November 2026 and excluded as affirmative evidence.

Before promotion, test held-out multilingual speakers, exact identifiers/destinations, corrections, stops, long silence, distant PA and overlapping speech. Measure capture through physical notification plus sustained screen-off performance, energy and thermal behavior. Choose quality/resource gates first. See [offline reproduction](LATENCY_BENCHMARK_2026-11-13.md#reproduce-without-changing-evidence).

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/LATENCY_NOISE_RESEARCH_2026-11-13.md), including original tooling and detailed research tables.
