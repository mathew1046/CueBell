# Recorded audio source

Microsoft DNS Challenge 5 development set, Track 2 Speakerphone, real recordings.

Source project: https://github.com/microsoft/DNS-Challenge

Official archive: https://dnschallengepublic.blob.core.windows.net/dns5archive/V5_dev_testset.zip

Official download script: https://github.com/microsoft/DNS-Challenge/blob/master/download-dns5-dev-testset.sh

Dataset license: Creative Commons Attribution 4.0 International.

License source: https://github.com/microsoft/DNS-Challenge/blob/master/LICENSE

License terms: https://creativecommons.org/licenses/by/4.0/

The source is provided without warranties. Microsoft and the original contributors
have not endorsed CueBell or these results.

The manifests retain each original archive member name, SHA256, ZIP CRC, source
transcript, and archive HTTP identity. Original downloaded WAVs are retained in
each corpus's `source` directory.

## Modifications

- **Before:** conversion to mono, 16 kHz, signed PCM16 for CueBell's audio path.
  No generated speech, generated noise, artificial mixing, gain normalization,
  reverberation, trimming, or file padding was applied.
- **After:** the same recording processed by CueBell's stateful GTCRN denoiser
  on the Android test device. The paired export records the exact model, APK,
  native library, and output hashes. Its causal 16 ms alignment delay is retained.
- A partial final 32 ms processing frame is internally zero-filled; the output
  WAV retains the original recording's sample count. No tail is flushed.

Selection is based on source filenames and categories, before enhancement
outcomes are known. The first cohort covers 12 near-speaker noise categories.
A separate four-recording far-speaker cohort checks more distant speech.
There is no eligible primary-speaker NoNoise control in these selected cohorts,
and no paired clean reference. The original near-cohort selection used an
uppercase Primary suffix; the far cohort uses case-insensitive suffix matching.

Source transcript markers such as `<UNKNOWN/>` and `<UNKOWN/>` are retained.
Recordings containing these markers are excluded from numerical word-error-rate
comparisons rather than treating the markers as spoken words.
