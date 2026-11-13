# CueBell: low-latency noise suppression and pipeline optimization

Date: 2026-11-13

## Scope and work status

This review targets CueBell's Android microphone → Gnani Prisma speech recognition → OpenAI GPT-6 Luna interpretation → native alert pipeline. Gnani speech models are mandatory. The desired audio includes distant public-address announcements and the user's spoken stop command.

Completed work: installed and registered the requested arXiv MCP server, verified its connection, and completed three independent parallel research reviews using that server. This document records the resulting optimization recommendations. Application optimizations are proposals until implemented and measured; installation and research do not establish a phone latency, battery, or recognition-accuracy improvement.

## Executive recommendation

1. **Measure and remove orchestration delays first:** prompt flushing when interpretation becomes idle, deadline wakeups, independent heartbeats, and ordered socket writes outside state locks.
2. **A/B Luna and Gnani settings separately:** Fast service tier at unchanged reasoning, then explicit reasoning levels, then a 500/400/350/300-ms Gnani endpoint sweep.
3. **Run a native-16-kHz denoiser comparison:** raw and mild WebRTC baselines, GTCRN, FastEnhancer-T, and UL-UNAS. GTCRN has the simplest verified integration route; FastEnhancer-T has stronger same-machine desktop speed evidence. Neither is a proven phone/Gnani winner.
4. **Choose by the actual task:** distant announcement and exact-identifier recall, false alerts, corrections, stop commands, tail latency, and sustained phone resource use. Include a conservative delay-aligned raw/enhanced blend.

The fresh review changes the earlier model ranking into a controlled comparison, identifies CoFi-Lite as a newer research challenger, and excludes the withdrawn GigaEdge Spench paper from affirmative performance evidence.

## Installed research tooling

Repository: https://github.com/blazickjp/arxiv-mcp-server

- Package: `arxiv-mcp-server[pdf]==0.8.2`, installed persistently with `uv tool` and Python 3.12.
- Executable: /home/mathew/.local/bin/arxiv-mcp-server
- Global OpenCode configuration: /home/mathew/.config/opencode/opencode.jsonc
- Persistent paper storage: /home/mathew/.local/share/arxiv-mcp/papers
- MCP server name: `arxiv`.
- Verification: OpenCode reported `connected` for /home/mathew/Arrakis/CueBell; a native MCP `list_watches` call returned `status: success`.

Installation and registration commands:

```bash
uv tool install --python 3.12 'arxiv-mcp-server[pdf]==0.8.2'
opencode mcp add arxiv --global -- /home/mathew/.local/bin/arxiv-mcp-server --storage-path /home/mathew/.local/share/arxiv-mcp/papers
```

The server is registered under `mcp.servers.arxiv`. Its runtime connection was also attached to CueBell's explicit location so this research session could use it immediately.

## Research method

Three parallel reviews cover:

1. **Mobile denoisers:** current papers, streaming interfaces, model checkpoints, computational cost, and actual device measurements.
2. **Recognition preservation:** enhancement-induced errors, far-field speech, reverberation, long silences, recurrent state, and exact identifier recognition.
3. **End-to-end latency:** endpointing literature, Gnani's available API controls, Luna settings, and the current CueBell execution path.

Primary papers and author repositories take precedence over search snippets. Reported frame hops, algorithmic delay, neural-network inference time, and end-to-end latency are treated as different quantities. Desktop, Raspberry Pi, embedded DSP/NPU, and Android measurements are identified separately. Results from another recognizer are evidence for an experiment, not a measured improvement to Gnani.

The reviewers used the installed MCP's paper search, abstract retrieval, LaTeX section listing/reading, and download tools. Searches covered relevant work through 2026-11-13. Original LaTeX recovered numerical tables missing from a paper's HTML conversion. Official repositories were checked for streaming code, checkpoints, and licenses; latest arXiv status was checked when version/download behavior was inconsistent.

## Findings and optimization plan

### Pipeline latency: prioritize measured waits and backlog

The current opportunity ranking is based on code inspection and provider contracts, not a production latency trace. Luna reasoning/inference, Gnani endpointing, and interpretation backlog are likely larger opportunities than shaving a few samples from capture.

For an isolated finalized announcement, the current behavior is approximately:

```text
speech-end → alert
  = audio/transport + Gnani endpoint/recognition
  + max(1.2 s correction grace, interpretation queue + Luna + validation)
  + scheduler wait + delivery
```

The grace deadline starts at transcript receipt, so it overlaps interpretation. Continuous backlog adds a separate queue-idle barrier and can exceed this isolated-announcement approximation. Stage measurements are necessary to avoid double-counting overlapping work.

| Priority | Proposed change | Expected mechanism and limits |
| --- | --- | --- |
| 1 | Instrument the whole speech-end-to-native-alert path. | Establish where median and tail time actually goes before choosing a model or changing safety margins. |
| 2 | Flush immediately when ordered interpretation becomes idle; use deadline wakeups; schedule heartbeat independently. | Removes avoidable polling/idle-transition delay while retaining the current correction guard. The 200-ms loop contributes nominally 0–200 ms only when otherwise unblocked. |
| 3 | Move socket writes to a bounded, ordered outbound writer; enqueue inference before optional caption delivery. | Removes slow-client network waits from provider intake and state locks. Preserve ordering, generations, backpressure and coverage-gap handling. |
| 4 | Test Luna Fast mode at the same reasoning level, then independently test `low` and `none`. | Fast mode changes service priority/cost; reasoning changes may change accuracy. Record actual returned service tier and reasoning-token usage. |
| 5 | Sweep Gnani endpoint silence: 500, 400, 350, 300 ms. | Reduces configured silence by 100–200 ms, not necessarily end-to-end time. Shorter segments can split identifiers and increase interpretation requests/backlog. |
| 6 | Design a correction-aware barrier for continuous backlog. | The current global queue-idle requirement can indefinitely defer an eligible alert. This needs ordered semantics and explicit correction tests, not simply deleting a guard. |
| 7 | Evaluate native, conservative denoising using the model comparison below. | May improve noisy recognition or endpoint stability, but adds processing/delay and can remove desired speech. |
| 8 | Consider smaller correction grace and faster spoken-request completion after the above measurements. | Accuracy-sensitive. Reducing grace helps only when it dominates interpretation; spoken-request completion is a different latency path. |

#### Exact code locations and behavior

- /home/mathew/Arrakis/CueBell/backend/app/intelligence.py:194-216 — shared OpenAI client, 12-second request timeout, retries disabled, structured Responses parsing. No explicit reasoning effort or service tier is supplied. Luna documentation specifies medium reasoning by default.
- /home/mathew/Arrakis/CueBell/backend/app/gnani.py:13-27 — Prisma v3 connection settings; no explicit VAD controls. Gnani documents a 500-ms minimum-silence default.
- /home/mathew/Arrakis/CueBell/backend/app/main.py:377-381 — transcript delivery to the phone is awaited before interpretation is enqueued.
- /home/mathew/Arrakis/CueBell/backend/app/main.py:387-435 — interpretation is serial and uses recent observations. Naïve parallel execution can invalidate correction context.
- /home/mathew/Arrakis/CueBell/backend/app/main.py:404-435 — some state-related sends occur while holding `session.lock`.
- /home/mathew/Arrakis/CueBell/backend/app/main.py:470-479 — `if interpreting or not queue.empty(): continue` gates flushing and also bypasses heartbeat work. Sustained unrelated speech can keep an otherwise-due alert waiting.
- /home/mathew/Arrakis/CueBell/backend/app/engine.py:249-263 — pending deadlines use transcript-receive time plus grace; the engine also rejects stale observations.
- /home/mathew/Arrakis/CueBell/backend/app/main.py:444-460 — spoken task setup waits 3.5 seconds after transcript activity. This does not impose a 3.5-second wait on each monitoring alert.
- /home/mathew/Arrakis/CueBell/mobile/modules/queue-listener/android/src/main/java/expo/modules/queuelistener/ListenerService.kt:249-293 — audio-priority capture thread, 16-kHz mono PCM, 512-sample/1024-byte frames, immediate WebSocket submission.

The first queue fix should retain ordered interpretation and the guard, while waking promptly when work becomes idle. A later starvation fix must define which earlier or in-progress utterances can still correct an observation, and ensure those are resolved before release. Continue delivering late corrections in order. A global timeout alone is not a correctness proof.

#### Gnani settings and protocol constraints

Use Prisma v3 with the existing language selection and verbatim output. A first controlled endpoint experiment can set:

```text
x-vad-threshold: 0.7
x-min-silence-ms: 350
x-min-speech-ms: 100
x-min-segment-ms: 120
```

Only the silence value changes from the documented defaults in this example. Compare it with 500/400/300 ms; VAD-setting changes require a new connection. Keep all other settings fixed during the first sweep.

- Prisma v3 explicitly does not offer token-by-token realtime transcription. Streaming Luna's JSON cannot remove the wait for Gnani's finalized utterance.
- Continue sending exactly 512 samples / 1024 bytes at the existing 16-kHz, 32-ms cadence, including silence. A smaller DSP hop does not change the provider's packet contract.
- The native 8192-byte buffer/queue thresholds represent capacity; they do not prove every frame waits 256 ms. Measure actual age and backlog before shrinking buffers.
- Consume `speech_start` and `processing` events for activity tracking and timing. The reported transcript `latency` is not end-to-end alert latency.
- `commit` can close an utterance, but fixed-interval forced commits can split a number or correction. Local VAD plus commit is a later experiment, not the first optimization.
- A maximum-utterance cap may bound continuous-speech waits, but changes segmentation. It needs separate tests and does not create incremental partial tokens.
- The documented batch `with_denoise` option and Agent Builder interruption filtering do not establish a live Prisma WebSocket denoising control.
- Do not bias recognition with the monitored target identifier: that can make an incorrect announcement resemble the desired match.

#### Luna settings

Keep the same model and structured evidence validation. Test these dimensions separately:

1. Explicit `medium` versus `low`, then `none` reasoning. Evaluate uncertainty, corrections, cancellations, multilingual identifiers, and stop commands.
2. `service_tier="fast"` at identical reasoning; `"priority"` is also documented. Record the response's actual tier and cost, including any downgrade. Vendor “up to” multipliers are not measured CueBell gains.
3. Shorter actual outputs and compact, locally expanded source aliases, while retaining grounding. Merely reducing the 2000-token cap does not make the same output faster and can cause truncation.
4. Stable instructions/schema/task prefixes for prompt caching, with changing transcripts/history later. Verify actual cached-token usage; caching is not a latency guarantee.

Keep event extraction and stop interpretation in the existing combined call. Partial structured output is not sufficient evidence for an alert before schema and source/correction validation complete.

#### Endpointing papers: useful lessons, not drop-in Gnani extensions

| Paper | Verified result | Applicability |
| --- | --- | --- |
| Dissecting User-Perceived Latency, 2021 | On-device model B→D halves RTF 0.42→0.21 while median user-perceived latency changes 1.47→1.50 s. Neural/joint endpoint variants improve a separate configuration from 1.37→0.87 s. | Optimize speech-end-to-usable-result, not just FLOPs or inference throughput. Those architecture results are not transferable savings for Gnani. |
| Two-pass Endpoint Detection, 2024 | Early-endpoint errors improve 16.34% relatively; median stays 300 ms, P90 rises 570→600 ms, P99 1110→1320 ms. | Accuracy and tail latency can move in opposite directions. Its arbitrator needs encoder embeddings and partial hypotheses unavailable here. |
| Improving endpoint detection, 2025 preprint | At a 200-ms configuration, trailing-silence versus end-of-word endpointing gives WER 23.7→21.4 but endpoint recall 83.0→65.6. | Very short silence-only endpointing is not automatically better. Encoder-trained VAD and end-of-word tokens require provider-side support. |

Sources:

- https://arxiv.org/abs/2104.02207
- https://arxiv.org/abs/2401.08916
- https://arxiv.org/abs/2505.17070
- https://docs.gnani.ai/api/STT/stt-websocket.md
- https://docs.gnani.ai/api/STT/models/prisma-v3.md
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://developers.openai.com/api/docs/guides/fast-mode
- https://developers.openai.com/api/docs/guides/prompt-caching

### Mobile denoiser comparison

RTF is processing time divided by audio duration. A low RTF is useful throughput evidence, but does not include every buffering, scheduling, or delivery delay. Authors' parameter and MAC counts use different scopes; especially distinguish MACs **per frame** from MACs **per second of audio**.

| Candidate | Published/current cost and framing | Device evidence and practical status |
| --- | --- | --- |
| **GTCRN** | Original paper: 23.7K trainable parameters, 39.6M MAC/s. Current repository: 48.2K including fixed ERB weights, 33.0M MAC/s after optimization. 16 kHz, 32-ms window, 16-ms hop, causal neural processing. | MIT; public checkpoints and streaming ONNX; an online sherpa-onnx integration exists. Repository RTF 0.07 is Intel i5-12400, not Android. Strong integration baseline; no reviewed sustained phone measurement. |
| **FastEnhancer-T** | 22K parameters; 55M MAC/s in the paper versus 60M in the current repository. 16 kHz, 32-ms window, 16-ms hop; documented waveform alignment delay 16 ms, before other costs. | MIT; public checkpoints and spec-to-spec/wave-to-wave ONNX. Single-thread RTF 0.012 on Xeon 6248R / 0.013 on Apple M1 versus GTCRN 0.060 / 0.042 in that comparison. Those timings exclude STFT/iSTFT. A serious speed challenger, requiring complete phone measurements. |
| **UL-UNAS v2** | 171.33K parameters, 34.91M MAC/s. 16 kHz, 32-ms Hann window, 16-ms hop; no future neural frames. | MIT; public checkpoints and streaming neural ONNX. Matched-training DNS3 PESQ 2.30 versus GTCRN 2.10, ESTOI 78.24 versus 75.71. No verified Android runtime. The example uses whole-file STFT/iSTFT around frame-wise inference, so a waveform-stream wrapper still needs work. |
| **faster-enhancer.c v1** | Specialized 48-kHz FastEnhancer-Medium, not 16-kHz Tiny. 511,754 parameters, 565,108-byte weights, 432,384-byte state; mixed int8/fp16/fp32. Window 21.33 ms, hop 6.67 ms, alignment delay 14.67 ms. 46.3M MAC/frame is approximately 6.95G MAC/s. | MIT C/SIMD runtime with weights. Galaxy S23+ Snapdragon 8 Gen 2 racing test: 0.640 ms/frame, median RTF 0.096. Thirty-minute paced operation: median RTF 0.7215, P99 1.0139, 1.77% deadline misses. Valuable Android implementation evidence, not validation of a 16-kHz Tiny deployment. |
| **μNet v1** | 46K parameters, 28M MAC/s, 90KB static weights excluding workspace. 16 kHz, 32-ms analysis, asymmetric synthesis with reported 16/8/4-ms algorithmic latency. | NXP RT685 / Cadence HiFi4 demonstration at approximately 70 MHz, not an Android measurement. Public listening demo; deployable checkpoint/runtime/license not verified. Suppression/latency settings have material quality tradeoffs. |
| **CoFi-Lite v1** | 83.12K parameters, 12.87M MAC/s. 16 kHz, 32-ms sqrt-Hann window, 16-ms hop, causal. Desktop ONNX RTF 0.033 versus GTCRN 0.050 on i5-14600KF, excluding STFT/iSTFT. | Public code/checkpoint released October 19. Explicit repository license and a released streaming enhancement export were not verified. Included ONNX evaluators are not necessarily the enhancer. Promising next research candidate rather than the first integration. |

#### Interpretation of the comparison

- **GTCRN versus FastEnhancer-T is a real experiment.** FastEnhancer-T uses more arithmetic yet runs faster in its controlled desktop comparison. Operator structure, memory movement, fusion, and framework overhead matter more than parameter count alone.
- **UL-UNAS is the quality challenger.** Its reverberant/matched-training results merit testing, but weights are larger and similar MAC/s does not establish similar phone latency or energy.
- **FastEnhancer-B is optional if the measured budget permits.** It has approximately 91–92K parameters and 262M MAC/s. The paper reports Whisper-large-v3-turbo WER 3.2% for B, versus 3.6% for T and GTCRN. These are not Gnani results; no raw-audio baseline in that comparison establishes an absolute recognition gain.
- **Far-field training is a major confound.** FastEnhancer's current DNS recipe omits reverberation, while the compared GTCRN checkpoint also learned dereverberation. Architecture-only conclusions do not establish the best distant-PA frontend.
- **The Android C runtime is useful but has a different workload.** Its fast headline measurement is a racing benchmark. In paced operation, late wakeups and governor/scheduling behavior matter; temperature remained approximately 38.2°C. The 1.77% deadline-miss result does not mean the neural kernel alone exceeded every corresponding budget.
- **CoFi-Lite deserves follow-up.** It preserves the first 100 ms of early reverberation in training; reported reverberant DNS2020 overall score is 2.48 versus GTCRN 2.43. Verify licensing and a persistent-state waveform-stream implementation before treating its public checkpoint as an app-ready package.
- **μNet is a useful research direction, not a verified Android component.** Its 90KB figure excludes runtime workspace. The 4-ms version has appreciably poorer listening quality than 8/16 ms; a small reported delay is not an accuracy-neutral setting.

For GTCRN, sherpa-onnx provides a concrete online C++/Kotlin integration path. Its model download is about 523KB; that is not the JNI/runtime APK footprint. Use the online denoiser API and preserve its state. Offline examples and desktop RTF results do not establish live Android performance.

RNNoise remains a mature native-C alternative, but its standard model works at 48 kHz and requires a measured resampling path here. Larger full-band systems such as DeepFilterNet should be evaluated only if the native-16-kHz candidates fail the recognition-quality target and the resource budget permits them.

#### Source/version correction: withdrawn SDK paper

GigaEdge Spench, arXiv 2611.13243v2, was withdrawn on 2026-11-11 with the comment “Text is under additional internal review.” Exclude its claims from deployment/performance recommendations. Earlier cached v1 material does not override the current status. The MCP abstract response still exposed the original abstract without the withdrawal label; checking the primary arXiv record resolved this discrepancy.

Sources and implementation references:

- GTCRN paper: https://ieeexplore.ieee.org/document/10448310
- GTCRN implementation: https://github.com/Xiaobin-Rong/gtcrn
- UL-UNAS paper: https://arxiv.org/abs/2503.00340v2
- UL-UNAS implementation: https://github.com/Xiaobin-Rong/ul-unas
- FastEnhancer paper: https://arxiv.org/abs/2509.21867v1
- FastEnhancer implementation: https://github.com/aask1357/fastenhancer
- FastEnhancer ONNX interfaces: https://aask1357.github.io/fastenhancer/onnx
- Android C runtime paper: https://arxiv.org/abs/2607.25350v1
- Android C runtime implementation: https://github.com/kdrkdrkdr/faster-enhancer.c
- μNet paper: https://arxiv.org/abs/2608.21155v1
- μNet listening demo: https://sshetu-iis.github.io/uNet/ulm/
- CoFi-Lite paper: https://arxiv.org/abs/2607.10142v1
- CoFi-Lite implementation: https://github.com/Acceleration123/CoFi-Lite
- Withdrawn GigaEdge paper: https://arxiv.org/abs/2611.13243v2
- sherpa-onnx online enhancement API: https://k2-fsa.github.io/sherpa/onnx/c-api/html/speech_enhancement.html
- sherpa-onnx model details: https://k2-fsa.github.io/sherpa/onnx/speech-enhancement/models.html
- RNNoise: https://github.com/xiph/rnnoise
- DeepFilterNet: https://github.com/Rikorose/DeepFilterNet

### On-device integration requirements

The target processing path is:

```text
AudioRecord → native streaming DSP → PCM16 packetizer
            → existing paced WebSocket → Gnani → Luna → validated alert
```

Implement processing in the native Android service/JNI layer, with one persistent model instance and state per capture stream. Start with one CPU inference thread and measure alternatives; more threads, GPU dispatch, or NPU delegation can add synchronization and transfer costs for a tiny recurrent graph.

- Initialize and warm up the model before the critical capture path where possible; preallocate recurrent states, FFT buffers, and tensors.
- Use a genuinely online interface. Preserve state across frames; flush/reset only at appropriate stream boundaries, not after each packet or automatically after every silence.
- Keep audio frames off the React Native bridge. Reuse buffers and avoid per-hop allocation, file I/O, logging, or blocking network calls on the DSP path.
- Retain 16-kHz mono output. A 48-kHz enhancer needs resampling and its own measured delay/CPU budget; upsampling 16-kHz input does not recover missing high-frequency information.
- Separate the DSP hop from Gnani packetization. A 16-ms hop divides the existing 32-ms packet evenly. A 10-ms hop needs a careful ring-buffer adapter; feeding it only whole 32-ms capture blocks can accidentally introduce another packet's worth of buffering before a complete output packet exists.
- Preserve steady real-time packet pacing and silence. Do not improve an offline benchmark by collecting long chunks, submitting bursts, or dropping quiet frames.
- Keep queues bounded and measure audio age. Define an explicit recovery/bypass policy that maintains timing and stream state; do not silently replay old audio or alternate delayed/undelayed paths mid-word.
- Test one suppression stage at a time. Check any Android/OEM effect already attached to the recording session before combining it with another denoiser.

Use raw audio, Android `NoiseSuppressor` where available, and mild WebRTC noise suppression as practical baselines. Android support and behavior depend on the device; the API does not promise hardware acceleration or a fixed CPU/latency cost. WebRTC supports 16-kHz processing in approximately 10-ms frames, but frame duration is not total algorithmic delay.

Acoustic echo cancellation addresses CueBell's own speaker playback and requires the playback reference/alignment. It is a separate problem from suppressing fans, traffic, nearby conversation, or room reverberation.

Sources:

- https://developer.android.com/reference/android/media/audiofx/NoiseSuppressor
- https://developer.android.com/media/platform/mediarecorder
- https://webrtc.googlesource.com/src/+/refs/heads/main/api/audio/audio_processing.h
- https://developer.android.com/ndk/guides/audio/audio-latency
- https://source.android.com/docs/core/audio/latency/measure

### Instrumentation and paired experiments

Correlate session, connection generation, provider utterance, segment, model request, observation, and alert IDs. Record:

| Stage | Measurements |
| --- | --- |
| Native audio | Capture sample position, read completion, DSP duration, frame age, WebSocket queue bytes, overruns and missed processing deadlines. |
| Relay and ASR | Audio ingress, `speech_start`, `processing`, final receipt, provider-reported recognition latency, and segment duration. |
| Interpretation | Queue entry/start/end, queue depth and oldest age, model duration, reasoning/output/cache tokens, actual service tier. |
| Decision and delivery | Pending deadline, correction resolution, time blocked by the queue-idle guard, lock wait, outbound queue/write completion. |
| Phone alert | Socket receipt, main-thread dispatch, notification issuance, vibration/audio onset, and stop completion. Spoken playback begins after notification issuance and should be measured separately. |

Use monotonic clocks for intervals within each process. Device, server, and provider timestamps cannot be directly subtracted without an explicit clock-alignment method. Use annotated replay audio and sample indices to locate true speech end; distinguish the useful announcement's end from the end of a later trailing correction.

Run paired trials on identical inputs: baseline; outbound/deadline changes; Fast tier; reasoning levels; endpoint thresholds; denoiser candidates; then grace changes. Report P50/P90/P95/P99 speech-end-to-notification, queue age, missed/late/false alerts, correction leakage, identifier accuracy, and cloud cost. Include slow-client backpressure, sustained announcements, split numbers, and model timeouts.

For phone evaluation, use representative low- and mid-range Android devices as well as a flagship. Measure 30–60-minute paced sessions with screen off and the normal foreground service; include CPU utilization, process memory, temperature, battery/energy, and deadline misses. Cold-start/model-load time and steady-state processing should be reported separately. A model file's size does not equal added APK size or runtime memory.

Define acceptable accuracy and resource budgets before choosing a winner. “No performance impact” is not an established result: extra DSP consumes resources, and lower reasoning/shorter endpointing can change recognition or interpretation. Prefer measured improvements with held-out regression checks rather than a theoretical minimum-delay preset.

### Recognition preservation: cleaner audio can produce worse transcripts

CueBell needs to preserve a potentially quiet, distant announcement beneath louder nearby speech. A model trained to retain the dominant or closest speaker can remove the desired signal. Neither perceptual speech quality nor a desktop speed benchmark establishes usefulness for this task.

| Primary evidence | Published result | Consequence for CueBell |
| --- | --- | --- |
| Ochiai et al., processing distortions, 2024 | On 1,320 real CHiME-3 recordings, WER was 28.7% for raw audio, 31.7% after SNR-trained enhancement, and 22.5% after adding 40% raw audio to the enhanced signal. | Include bypass and a conservative raw/enhanced blend. These results used another recognizer; the mixing weight must be selected against Gnani. |
| Li et al., intelligibility-guided observation addition, 2026 | On CHiME-4 real recordings with Whisper and GR-KAN MP-SENet: raw WER 6.48%, enhanced 15.75%, DNSMOS-guided mixing 11.56%, confidence-guided mixing 5.86%. With Demucs, confidence-guided mixing still lost to raw: 6.60% versus 6.48%. | Stronger suppression and better audio-quality scores are insufficient selection criteria. The confidence-guided method needs two preliminary ASR assessments plus final recognition; it is not a one-pass Gnani frontend. |
| DPDFNet, version 3 | Authors observed initial-speech truncation after 3–4 seconds of silence. Continuous fine-tuning on 30–40-second segments improved a supplementary ablation from PESQ 2.92 to 3.04 and STOI 90.2 to 91.6, while DNSMOS overall fell from 2.89 to 2.83. | Test the first digits and phonemes after long quiet periods. Short-clip scores and a multilingual audio-quality evaluation do not establish identifier recognition. |
| Fast-ULCNet, 2026 | Repeated-clip tests from 10 to 90 seconds degraded uncorrected PESQ from 2.51 to 2.24 and SI-SDR from 15.99 to 13.58 dB. Its trained complementary-filter variant achieved 2.51 / 16.48 dB at 90 seconds. | Persistent state needs long-session validation. This architecture-specific result does not establish that periodically resetting any denoiser improves recognition. |
| “How much to Dereverberate?”, 2025 | Distant-trained DFN3 improved DNSMOS overall from 2.77 to 3.04 at the same reported 40-ms algorithmic latency. The study considers distances up to 10 m and retaining useful early reflections. | Far-field training and the dereverberation target matter. This English-only study reports no downstream WER and does not establish a ready-made Gnani improvement. |

Primary sources:

- https://arxiv.org/abs/2404.14860v1
- https://arxiv.org/abs/2602.20967v2
- https://arxiv.org/abs/2512.16420v3
- https://arxiv.org/abs/2601.14925v1
- https://arxiv.org/abs/2505.01338v1

#### Feasible mitigation around black-box Gnani

Evaluate a **single production audio stream** with an optional local blend:

```text
output = alpha * delay_aligned_raw + (1 - alpha) * enhanced
```

Choose the weight using separate, held-out Gnani tests; include raw-only and enhanced-only endpoints. Alignment must account for the enhancer's actual delay, gain, phase behavior, and clipping. Mixing restores noise and competing speech as well as useful speech, so it is an experiment rather than an unconditional improvement. Fixed mixing needs no extra production ASR request.

The confidence-guided paper uses recognizer probabilities unavailable in the documented Gnani interface and repeated recognition passes. DNSMOS is not a substitute for those probabilities. The DPDFNet paper's “OA loss” means **over-attenuation loss**, not observation addition; its long-silence mitigation was model fine-tuning, not a proven reset policy.

Keep the raw audio available locally to the processing chain and preserve speech onsets. The existing continuously streamed path should continue transmitting silence. A pre-roll buffer becomes relevant if a later local VAD/commit design needs onset protection; it should not become an extra delay imposed on every frame.

Do not use speaker enrollment or “own-voice cancellation” as the default: CueBell must hear both the PA and the user's stop command. A separate local stop detector would introduce a new multilingual/product behavior and is outside the initial denoiser experiment.

#### Required acoustic and recognition cases

Proposed test conditions, not published success thresholds:

- PA-to-nearby-conversation ratios of −10, −5, 0, and +5 dB; weak desired speech must be represented.
- Multiple distances, measured room reverberation, loudspeaker distortion, fan/traffic noise, and overlapping conversations.
- Onset recovery after 3–4, 15, and 60 seconds of background-only audio, plus sustained sessions.
- Exact identifiers, leading zeros, digit substitutions/deletions, multilingual number words, code-switching, corrections, and cancellations.
- Stop-command recall, first-phoneme loss, false stops caused by announcements, and time until capture actually stops.

Report identifier exact match and missed/false alerts alongside WER/CER. GPT-6 Luna cannot reliably reconstruct an identifier whose distinguishing sound was removed upstream. Select the frontend using paired comparisons on the same recordings and report results by language and acoustic condition.
