# Real-world use and impact

## The problem

Audio-only announcements can force people who cannot reliably hear them to watch a display continuously or depend on a companion. CueBell aims to offer a personal visual cue using a phone microphone, without integration with venue software.

## Example uses

| Request or event | Intended response |
| --- | --- |
| “Tell me when pharmacy token 442 is called. Vibrate.” | Show the matching call and recognized counter, with vibration. Token 441 should not alert. |
| “Tell me when Anjali is called.” | Show the matching name call. |
| Token 442 changes from counter two to three. | Mark or update the earlier directions when the correction is recognized. |

These are examples, not documented venue deployments. CueBell cannot identify a PA speaker or distinguish announcements from nearby conversation. It is supplemental; official displays and staff remain the fallback.

## What is built

Typed setup, visual alerts, captions, source text, scalable text, themes and multilingual labels provide alternatives to audio-only interaction. Listening status and coverage-gap warnings make interruptions visible. Android supports foreground-service capture; the browser requires a visible page.

Gnani Prisma v3.0 recognizes microphone audio. Requests and transcripts go to the configured OpenAI text fallback for interpretation, followed by evidence checks. Evon and Timbre are not integrated. Optional local GTCRN enhancement does not replace recognition. See [privacy](PRIVACY.md).

## What the evidence shows

Software tests, provider replays and device audio-processing experiments guide development. The [pipeline](PIPELINE_OPTIMIZATION.md) and [noise-reduction](NOISE_REDUCTION.md) reports explain their measured results and limits.

They do not establish fewer missed turns, shorter waits, reliable live-venue accuracy or greater independence. Usability for deaf and hard-of-hearing, elderly and low-literacy users still needs representative-user testing.

## Next: a consented field trial

1. Recruit representative users and obtain venue permission. Start with staged, non-sensitive speech.
2. Compare existing call-noticing methods with CueBell assistance, retaining official displays, staff or companion support.
3. Count noticed targets, missed calls and false alerts. Measure announcement-end-to-alert and acknowledgment delay.
4. Include non-target speech, repeats, corrections, connection loss, phone placement, voices and languages.
5. Ask whether setup, status and alerts are understandable; record device settings and accessibility needs.
6. Publish denominators and failure examples. Separate speakers, sessions and venues used for improvements from those used for evaluation.

Recording or research logs require separate consent, retention limits and access controls. Do not collect patient details or publish bystander audio.
