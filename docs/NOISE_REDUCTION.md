# Noise reduction: methods and evidence

CueBell tests whether local noise reduction helps people follow spoken queue and station announcements. Cleaner background audio is useful, but preserving the number, platform, destination and correction matters more than a noise-quality score.

**Status: experimental, opt-in and off by default.** The evidence demonstrates local enhancement and useful runtime improvements. It does not establish better production recognition, live announcement accuracy or a default-on release recommendation.

## The approach in plain language

1. **Clean the audio locally.** GTCRN is a pretrained speech-enhancement model. CueBell runs it on the device before sending audio to Gnani, so it can suppress background noise without uploading audio to another enhancement service.
2. **Make that work fit real time.** The model needs to convert tiny audio chunks into frequency information. Replacing the slower DFT calculation with an FFT does that calculation more efficiently without retraining the model.
3. **Avoid a growing delay.** If the device cannot keep up, switch back to raw audio and show a warning instead of accumulating old sound.
4. **Check the words, not just the sound.** A less noisy clip can still lose an important digit. CueBell therefore evaluates recognition separately from estimated audio quality.

For example, reducing a fan sound is useful only if a call such as “token 442, counter two” remains understandable. This is an illustrative requirement, not a measured result for that phrase.

**Reading the scores:** WER is word error rate, where lower is better. DNSMOS estimates speech quality (SIG), background quality (BAK) and overall quality (OVRL), where higher is better. Those estimates are not human ratings or alert accuracy. Processing p99 is the time below which 99% of the measured processing calls fall, not a guaranteed maximum.

## What is implemented

| Layer | Technique | Important boundary |
| --- | --- | --- |
| Android | Pinned GTCRN speech-enhancement model through Kotlin/JNI and sherpa-onnx 2.0.1, with one inference thread | 16 kHz mono PCM16; 512-sample packets every 32 ms; 256-sample / 16 ms causal signal delay |
| Native optimization | Replace the original quadratic DFT frontend with a preallocated double-precision radix-2 FFT, keeping the model, window, hop and normalization unchanged | This is a transform optimization, not a new trained denoising model. The patched native build is explicitly identified and hash-locked |
| Android overload control | Track cumulative processing debt against the 32 ms frame interval, with a 64 ms fallback limit; invalid output and recoverable exceptions fail open immediately | This improves availability under brief stalls. It is not a hard microphone-to-alert latency guarantee |
| Browser | Same checksum-verified GTCRN model, single-threaded ONNX Runtime Web WASM in a dedicated worker; local FFT/STFT processing | Retains the 16 ms signal delay. Warm-up precedes capture. Bounded in-flight work and a 32 ms packet deadline fall back to raw audio with a warning |
| Gnani diagnostic control | Compare raw/custom-enhanced audio with batch `with_denoise` requested false or true; separately test streaming `verbatim` and `codemix` | The streaming connection does not explicitly request a vendor denoiser. Accepted batch flags do not independently prove that server enhancement ran |

Audio is enhanced locally before the existing Gnani recognition and GPT-6 Luna interpretation pipeline. Local denoising does not make recognition offline. The disabled Android path does not load or run the model. Fallback after enhancement begins preserves the existing sample alignment rather than replaying or skipping audio.

Implementation: [native contract](../mobile/modules/queue-listener/NOISE_REDUCTION.md), [FFT provenance](../mobile/modules/queue-listener/android/native/sherpa-fft/README.md), [browser behavior](WEB.md#experimental-noise-reduction), [WASM worker](../mobile/public/audio/gtcrn-worker.mjs), [browser DSP](../mobile/public/audio/gtcrn-dsp.mjs), [browser deadline/fallback control](../mobile/modules/queue-listener/browser-noise-reducer.ts). These are integrations of third-party models and runtimes, not claims of model authorship. Model, runtime and dataset licenses remain with the source evidence.

## Results at a glance

| Study | Positive result | Tradeoff or limit |
| --- | --- | --- |
| Native FFT experiment | Zero float/PCM16 differences across 941,568 host comparison samples; transform tables/scratch reduced from 4,210,688 to 14,336 bytes, a **99.66% reduction**. Short phone replay enhanced all 1,095 frames, with sustained p99 processing **3.869 ms** | Scratch is not total memory. Both earlier managed foreground-service trials failed the strict processing gate. The short shell result is not live-microphone validation |
| 16 recorded DNS5 clips | Revised policy increased fully enhanced clip availability from **11/16 (68.75%) to 16/16 (100%)** in the final replay; all 5,008 frames active. The 11 previously successful outputs remained byte-identical | There were 14 completion-deadline misses. This was file replay with a fresh engine per ten-second clip, not a long-session test |
| DNS5 estimated quality | Background DNSMOS BAK **2.514 → 3.927**, improved on 16/16 clips; overall OVRL **2.340 → 2.778**, improved on 15/16 | Speech SIG **3.303 → 3.089**, declining on 15/16. These are learned estimates, not human ratings, SNR or recognition accuracy |
| DNS5 real Gnani recognition | One of 11 reference-eligible pairs improved and six tied | Four worsened. Aggregate WER rose from **49/216 (22.69%) to 77/216 (35.65%)**, a **12.96 percentage-point increase**. Five incomplete references were excluded from WER, not from audio delivery |
| Five authentic station recordings | All **5,883 frames** enhanced without fallback or completion-deadline misses. SIG, BAK and OVRL estimates improved on all five | Platform/time interpretation regressed on Slough platform four; two pairs had no usable transcripts. No complete station reference supports WER |
| Targeted diagnosis | On one air-conditioning clip, the same enhanced audio with `codemix` reduced errors from **12/13 (92.31%) to 1/13 (7.69%)**, with the one-error outcome repeated | Dishwasher stayed at 15/21 errors in both formats. Double denoising repeatedly lost the usable Slough speech result. This is selected-case diagnosis, not a held-out benchmark |

Percentages above were calculated from the saved counts, not rounded display scores. No percentage improvement in DNSMOS is presented as a percentage of noise removed.

## What the research established

- **Runtime engineering helped:** the FFT preserved tested outputs while reducing transform scratch; bounded debt recovered the five previously unavailable DNS5 outputs without changing already-successful waveforms.
- **Perception and recognition can diverge:** better background-quality estimates did not reliably preserve task-critical words or identifiers.
- **More than one interaction matters:** output script, causal alignment and global audio level affected selected Gnani results. Waveform modification or ASR-domain mismatch remains a plausible contributor, not a fully isolated cause.
- **A useful failure is retained:** empty transcripts, timeouts, fallback audio and repeat regressions remain in the evidence. None are counted as successful recognition.

## Evidence reports

1. [Native implementation and strict device gate](NOISE_REDUCTION_BENCHMARK_2026-11-14.md): original processing experiment, FFT equivalence and execution-context failures.
2. [Recorded DNS5 noise](REAL_NOISE_DENOISING_2026-11-14.md): 16 before/after pairs, revised availability policy, DNSMOS and 11-pair WER.
3. [Actual station PA recordings](STATION_PA_DENOISING_2026-11-14.md): five full field recordings, task-level outcomes and repeat checks.
4. [Gnani denoiser diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md): 54 selected-case evaluations separating batch controls from streaming controls.

Canonical artifacts are under [`docs/benchmarks`](benchmarks/). The reports link to their JSON analyses, attribution and archived provider evidence. Historical test counts describe the original campaigns; this documentation audit did not rerun paid providers or claim new device measurements. Browser implementation is documented separately and has no physical-device performance result in these native campaigns.

## Release decision

Keep raw audio as the baseline and noise reduction off by default. A future default change needs held-out multilingual announcements scored for exact numbers, destinations, platforms, corrections and stop behavior, followed by complete streaming interpretation and representative live-microphone/device testing. `codemix`, gain compensation and mild blending are follow-up candidates, not validated universal fixes. These studies do not establish telephony results, beneficiary counts or production accuracy.
