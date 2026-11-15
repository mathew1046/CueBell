# Verification record

Evidence is scoped to its checkout, environment and inputs. Historical checks are
not fresh results or accuracy/reliability guarantees. Repeatable commands live in
[backend](../backend/README.md#install-and-test), [Android](../mobile/README.md)
and [browser](WEB.md#verify-changes) guides.

## What each check establishes

| Check | Establishes | Does not establish |
| --- | --- | --- |
| Unit tests | Logic with controlled inputs/mocked decisions. | Live recognition/model accuracy. |
| Browser suite | Synthetic microphone, UI/mock relay; some real local GTCRN. | Acoustics, all browsers, physical vibration/screen-reader speech. |
| Health/provider connection | Configuration or authentication/negotiation, depending on probe. | Complete alert or recognition quality. |
| Real-provider replay | Behavior on stated recordings/labels. | Venue accuracy or phone microphone reliability. |
| APK/signature | Packaging and artifact properties. | Lifecycle, audibility or usability. |

**Local browser status:** two repeatable audio checks failed on this review host.
No full local browser pass is claimed. Inspect timing, fallback and environment
before release; unit-test success does not replace these checks. **GitHub CI is
separate evidence and can pass independently.** The server deployment gate does
not run the entire browser/audio suite.

## Recorded documentation review | 15 November 2026

The earlier review used source `af0173d` and saved benchmark artifacts:

- Backend: 508 tests passed, one optional module skipped; Ruff lint/format passed.
- Client: 81 unit tests passed; TypeScript/lint passed.
- Saved JSON/JSONL recalculations covered setup delay, enhancement availability,
  background-quality and word-error figures, without new paid-provider calls or
  phone benchmarks.
- Local links/anchors were checked. These are recorded results, not execution of
  this documentation edit.

## Published 1.4.0 preview | 14 November 2026

[Release/checksum](https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview):
`app.cuebell.mobile`, version 1.4.0/code 7, ARM64 only, non-debuggable. Development
certificate matches 1.3.1 for in-place updates, not production signing. Signature,
16 KB ZIP alignment, origin, foreground service, cleartext rejection and unchanged
alarm bytes were checked. Targeted packaging scans found no configured private
values, environment files or keystores; this was not an independent audit.

| Artifact | Recorded SHA-256 |
| --- | --- |
| APK, 25,167,101 bytes | `99c6700e865951a20f250bea49fb8e3b5a072814c336d8b3e7563bb2f6c192e9` |
| FFT JNI | `59964bf7d9cf9520231d6cce3f6728b05f3c0ecac765bd9182bd9fc9d0539c65` |
| GTCRN model | `e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534` |

Recorded checks: backend 487, mobile 49, Android JUnit 33 and separate DNSMOS
numerical tests 25 passed; one optional backend module skipped. Backend lint/format,
mobile types/lint/service-origin and pinned ARM64 FFT release build passed.

Phone replay completed 16 selected DNS5 clips and five station-PA recordings;
5,883 station frames enhanced without fallback, with 16 ms alignment delay.
This was not live capture or endurance testing. Estimated background quality
improved, but Gnani/GPT-6 Luna recognition regressed: denoising remains off by default.
See [station PA](https://github.com/mathew1046/CueBell/blob/v1.4.0-preview/docs/STATION_PA_DENOISING_2026-11-14.md)
and [recorded-noise evidence](https://github.com/mathew1046/CueBell/blob/v1.4.0-preview/docs/REAL_NOISE_DENOISING_2026-11-14.md).

## Older records and remaining gaps

[Complete pre-refactor verification tables](https://github.com/mathew1046/CueBell/blob/8c9406f6528474848b11eb67308a1638fe9a78da/docs/VERIFICATION.md)
retain earlier release counts, APK hashes, CI links, provider probes and limitations.
The [pipeline report](PIPELINE_OPTIMIZATION.md) preserves the failed monitoring
quality gate; faster setup did not justify promoting its profile.

Still unestablished: general venue accuracy/false or missed-alert rates, current
APK sustained capture/locked-screen delivery, live voice stop, TalkBack usability,
physical audibility/vibration, OEM battery behavior and endurance. No evidence
establishes fewer missed turns, shorter waits or successful venue deployments.
Use consenting speakers/staged recordings and the [device checklist](../mobile/README.md#physical-device-checklist)
before supervised use. Emulator views and accepted sockets are not reliability proof.
