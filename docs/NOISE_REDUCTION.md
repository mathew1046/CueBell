# Noise reduction

**Experimental, opt-in and off by default.** Local enhancement improved runtime availability and estimated background quality. It did not reliably preserve recognition, so raw audio remains the baseline.

## How it works

GTCRN is a pretrained speech-enhancement model that cleans audio locally. CueBell integrates it rather than training a new model. Gnani Prisma still transcribes the audio in the cloud; the configured OpenAI text fallback interprets requests and transcripts. OpenAI is not an alternative speech recognizer.

The native implementation replaces a slow discrete Fourier transform (DFT) with a fast Fourier transform (FFT), without changing the model. If processing falls behind or output is invalid, CueBell returns to raw audio with a warning rather than building an unbounded delay.

| Path | Contract and boundary |
|---|---|
| Android | Kotlin/JNI, sherpa-onnx 2.0.1, one inference thread; 16 kHz mono PCM16, 512-sample packets every 32 ms; 16 ms signal delay |
| Revised Android fallback | Cumulative processing debt limited to 64 ms against each 32 ms interval; invalid output/exceptions fail open immediately |
| Browser | Same checksum-verified model, ONNX Runtime Web worker and local FFT; warm-up before capture, bounded work, 32 ms packet deadline and raw fallback |

Disabled Android mode does not load the model. Midstream fallback preserves sample alignment. These controls are not microphone-to-alert latency guarantees. Browser implementation does not inherit native phone measurements.

## Results and limits

DNSMOS estimates speech (SIG), background (BAK) and overall (OVRL) quality. Higher is better, but it is not human listening, noise removed or alert accuracy. Word error rate (WER) is recognition errors divided by reference words; lower is better. Processing p99 is the time below which 99% of measured calls fall.

| Study | Positive evidence | Important failure or limit |
|---|---|---|
| Native FFT | Zero float/PCM16 differences over 941,568 host samples. Transform tables/scratch fell 4,210,688 → 14,336 bytes, **99.66% less**. Short phone replay enhanced 1,095/1,095 frames; sustained p99 3.869 ms | Scratch is not total memory. Both managed foreground-service trials failed the strict processing gate |
| 16 DNS5 recordings | Fully enhanced availability rose **11/16 → 16/16**, with all 5,008 frames active. The 11 previously successful outputs stayed byte-identical | Fourteen completion-deadline misses; fresh engines and ten-second file replay, not long-session testing |
| DNS5 quality | BAK 2.514 → 3.927, improving 16/16; OVRL 2.340 → 2.778, improving 15/16 | SIG 3.303 → 3.089, declining 15/16 |
| DNS5 recognition | One eligible pair improved, six tied | Four worsened. Across 11/16 reference-eligible pairs, WER rose **49/216 (22.69%) → 77/216 (35.65%)**, up **12.96 percentage points**. Five incomplete references were excluded only from WER |
| Five station recordings | All 5,883 frames enhanced, no fallback/deadline misses; all three quality estimates improved 5/5 | Slough platform/time interpretation regressed repeatedly. Two pairs lacked usable transcripts; no full reference supports station WER |
| Targeted diagnosis | Enhanced air-conditioning errors fell 12/13 → 1/13 with `codemix`, repeated | Dishwasher stayed 15/21. Requested double denoising repeatedly lost Slough speech. Selected cases, not held-out accuracy |

## Evidence and release decision

[Native contract and licenses](../mobile/modules/queue-listener/NOISE_REDUCTION.md), [FFT provenance](../mobile/modules/queue-listener/android/native/sherpa-fft/README.md) and [browser behavior](WEB.md#experimental-noise-reduction) describe implementation.

Read the [native gate](NOISE_REDUCTION_BENCHMARK_2026-11-14.md), [DNS5 study](REAL_NOISE_DENOISING_2026-11-14.md), [station study](STATION_PA_DENOISING_2026-11-14.md) and [diagnosis](GNANI_DENOISER_DIAGNOSIS_2026-11-15.md) for methods and raw evidence.

Before promotion, require held-out multilingual identifier/destination scoring, complete streaming interpretation and representative live-microphone/device tests. `codemix`, gain compensation and blending remain candidates, not validated fixes. No new provider or device execution accompanied this documentation edit.

[Full pre-refactor report](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/NOISE_REDUCTION.md). Raw evidence and historical labels are unchanged.
