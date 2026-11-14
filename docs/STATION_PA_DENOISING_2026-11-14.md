# Denoising actual railway-station announcements

## Scope and source material

This follow-up uses **five complete station field recordings**, totaling
**188.171375 seconds**. They contain PA announcements together with the original
station ambience, passing trains, and nearby activity. They were selected from
recordists' descriptions before processing outcomes were available.

| Recording | Duration | Source-described content |
|---|---:|---|
| Indian railway station | 55.458 s | Train arrival/departure announcements |
| Slough, platform 4 | 23.214 s | 07:00 service to Reading |
| Slough, platform 3 | 53.004 s | Stand-clear announcement, then a passing train |
| Slough, distant platform 2 | 27.098 s | Non-stopping train announcement, recorded two platforms away |
| Southall | 29.397 s | Platform announcement over the station PA |

The source pages, public high-quality MP3 previews, authors, licenses, and SHA256
hashes are retained. These MP3s are lossy published previews of the uploaded field
recordings. Some station PA voices are automated; the recordists captured them
through loudspeakers in the actual surroundings.

Sources:

https://freesound.org/people/soundstew/sounds/99516/

https://freesound.org/people/AlienXXX/sounds/129351/

https://freesound.org/people/AlienXXX/sounds/129331/

https://freesound.org/people/AlienXXX/sounds/129353/

https://freesound.org/people/JWS24/sounds/790794/

Attribution and the individual licenses:

/home/mathew/Arrakis/CueBell/docs/benchmarks/station-pa-2026-11-14/ATTRIBUTION.md

## Method

1. Convert each entire published recording to mono, 16 kHz PCM16. Preserve its
   content and level; add no speech, noise, artificial mixing, or padding to the
   delivered input WAV.
2. Replay the recordings through the production GTCRN implementation on the
   connected I2404 Android phone, alongside a bit-identical bypass control.
3. Export a fully enhanced pair only if every frame used the denoiser, the source
   and output hashes match, and the original length and causal alignment survive.
4. Compare official non-personalized DNSMOS SIG/BAK/OVRL estimates and actual
   Gnani Prisma v3 before/after transcripts, using the released language and VAD
   settings. References and expected platform numbers are never supplied as ASR
   hints.
5. Probe the existing GPT-6 Luna observer and evidence validator with the same
   broad train/platform monitoring task for both conditions. Each complete final
   transcript is one segment; this measures downstream interpretation rather than
   streaming notification latency. Source names and expected facts are withheld.

Native runtime: pinned FFT JNI with one CPU inference thread, 512-sample frames,
32 ms pacing, retained 16 ms alignment delay, and the current 64 ms cumulative
processing-debt fallback policy. Invalid results still fail open immediately.
The same previously built v4 APK is used without rebuilding or changing the
production audio algorithm for these sources.

## Interpretation limits

- The uploader identifies platforms 4, 3, and 2 in the three Slough recordings,
  with a 07:00 Reading service in the first. Those are useful partial annotations.
  There is no independently verified complete transcript or clean speech
  counterpart, so a full WER, SNR improvement, or clean-reference score would be
  unsupported.
- DNSMOS is a learned estimate. A higher background score alone does not prove
  that announcements remain intelligible or that platform identifiers survive.
- Native file replay preserves the captured station acoustics. The measurements
  do not establish live microphone-to-notification latency or long-session battery
  performance.
- GPT-6 Luna's component results use the whole final transcript. They do not
  replace a full streaming app test or constitute independent transcription truth.

## Results

### On-device processing

All **5/5 recordings** were fully enhanced: **5,883/5,883 frames** used the
denoiser. There were no fallbacks, dropped frames, schedule rebases, calls taking
32 ms or longer, or frame-completion deadline misses. The two fresh-engine reset
checks produced identical PCM.

Median processing time was **3.213 ms per 32 ms frame**, p99 **11.154 ms**, and
maximum **24.323 ms**. Initialization took **63.8–69.8 ms** per recording. The
**16 ms alignment delay** remains in every delivered output. These results apply
to this file replay, with a fresh engine for each 23–55 second recording.

### Estimated audio quality

Equal weight per recording; the official non-personalized DNSMOS model:

| Estimate | Before | After | Recordings improved |
|---|---:|---:|---:|
| Speech quality, SIG | 1.250 | 2.261 | 5/5 |
| Background quality, BAK | 1.251 | 3.555 | 5/5 |
| Overall quality, OVRL | 1.151 | 1.898 | 5/5 |

These estimates improved across all five recordings. Scores cover the full
recordings, including non-speech train noise; they do not by themselves establish
recognition accuracy. The absolute overall estimates remain below 2/5 after
processing, so an improvement should not be described as pristine speech.

### Recognition and downstream interpretation

The first pass used ten actual Gnani connections, one before and one after for
each recording. Six produced nonempty transcripts, covering three complete
pairs. There were no provider error messages or unfinished utterance IDs.

| Recording | Observed recognition result | GPT-6 Luna component result |
|---|---|---|
| Indian railway station | Both recognize parts of the bilingual announcement. The raw transcript includes the Narmada Express and `eight two three four`; those details are absent after denoising. No complete verified reference is available. | The enhanced transcript yields a generic train-delay match without identifiers. The raw transcript timed out twice at the unchanged 12-second model timeout, so the paired Luna result is inconclusive. |
| Slough, platform 4 | Raw includes `Platform four for the O Seven Hundred Hours`; enhanced becomes `Four four for the eight seven hundred hours`. The uploader identifies platform 4 and the 07:00 Reading service. Raw already misrecognizes Reading as Breeding. | Raw yields a validated match with platform four and 0700; enhanced yields `UNCERTAIN`, no location, and no identifiers. This is a task-relevant regression despite higher audio-quality estimates. |
| Slough, through train | Neither condition produces usable words. Raw only receives the connection-ready message; enhanced receives one empty final transcript. | Excluded because there is no transcript to interpret. |
| Slough, distant PA | Neither condition produces speech-start or transcript messages within the fixed observation window. | Excluded; denoising has not demonstrated recovery of this distant announcement. |
| Southall | Both retain platform four and London Paddington. The enhanced transcript omits calling-point text present in the raw transcript and changes the first rendering of the service time. | Both yield validated platform-four/Paddington matches. The enhanced result also extracts 14:48 from the repeated wording. |

Seven Luna requests were made: five completed responses and two timeouts for the
raw Indian transcript, including its single bounded retry. Both timed-out
attempts remain in the evidence. Whole-transcript interpretation is not a
measurement of real-time alert delivery, and a broad match does not certify every
word or service detail.

The Slough platform-4 pair and both no-transcript pairs were repeated with the
same audio and ASR settings. **All six confirmation transcripts and statuses were
identical to their first attempts.** This reproduced both the platform/time
regression and the missing transcripts. Confirmation evidence is stored
separately from the initial attempts. The Luna component was not repeated on
these identical transcripts.

## Current conclusion

The denoiser runs successfully on all five field recordings and improves the
learned audio-quality estimates. **It has not demonstrated reliable preservation
of announcement details in the Gnani → GPT-6 Luna workflow.** The lost platform
and service-time interpretation is more important to CueBell than the higher
background-quality score. The feature remains experimental, with noise reduction
off by default; these findings do not qualify a default-on release.

## Before/after audio and evidence

The ZIP contains five complete before/after pairs, attribution, source/runtime
hashes, audio-quality estimates, device timings, transcripts, and provider evidence:

/home/mathew/Arrakis/CueBell/artifacts/CueBell-station-pa-before-after-2026-11-14.zip

The clearest task-relevant comparison is the Slough platform-4 announcement:

/home/mathew/Arrakis/CueBell/artifacts/CueBell-station-pa-before-after-2026-11-14/before/02-slough-platform-four.wav

/home/mathew/Arrakis/CueBell/artifacts/CueBell-station-pa-before-after-2026-11-14/after/02-slough-platform-four.wav

Detailed experiment directory:

/home/mathew/Arrakis/CueBell/docs/benchmarks/station-pa-2026-11-14

### Provider usage and verification

- This study: **16 Gnani connections, 792.246 connection-seconds**, including six
  confirmation attempts; **7 Luna attempts**, five completed and two timed out;
  no TTS generation.
- Combined with prior authorized work: **95.2974 / 120 Gnani minutes** and
  **426 / 600 Luna attempts**. Remaining allowance: **24.7026 Gnani minutes** and
  **174 Luna attempts**.
- Every provider input hash matches the delivered corresponding WAV. Source,
  denoiser, and bypass checks cover all five recordings, with no excluded audio
  pairs. The source descriptions were withheld from both providers.
- The delivery includes all failed, empty, and inconclusive provider outcomes;
  none are counted as successful recognition. No full-reference WER or live alert
  latency is claimed.
