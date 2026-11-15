# Real-world use and impact

## The problem

A pharmacy calls a token over a loudspeaker. A person who cannot reliably hear it may need to watch a display continuously or ask a companion to listen. The same accessibility barrier can arise when a name, platform change or boarding call is announced only through speech.

CueBell aims to provide a personal alternative: **tell it what matters, then receive a visible cue when matching speech is detected.** It works through a phone microphone rather than requiring integration with the venue's queue software.

## Example journeys

**Pharmacy collection**

- Request: “Tell me when pharmacy token 442 is called. Vibrate.”
- Announcement: “Token 442, collect your medicine at counter two.”
- Intended result: a visible call with counter information and the requested vibration.
- Important check: token 441 should not trigger the same alert.

**A name being called**

- Request: “Tell me when Anjali is called.”
- Intended result: an alert grounded in the matching announcement, without requiring a queue token.
- Limit: CueBell does not identify who is speaking or distinguish a loudspeaker from nearby conversation.

**An announcement changing**

- Initial call: token 442 to counter two.
- Correction: token 442 should go to counter three.
- Intended result: show the correction, rather than silently leaving outdated directions.

These are use examples, not records of deployments at named hospitals or transport operators.

## What supports the intended benefit

- Typed setup avoids requiring speech from every user.
- Visual alerts remain available when sound or vibration is unavailable.
- Captions and source speech make the interpretation inspectable.
- Short controls, larger text, themes and multilingual labels reduce interface barriers.
- Explicit listening status and coverage gaps avoid implying that silence means nothing happened.
- Android capture can continue through a native foreground service; browser listening requires a visible page.

These are implemented design choices. Their usability for elderly, low-literacy or deaf and hard-of-hearing users still needs representative-user testing.

## What has and has not been measured

The repository contains software tests, real-provider replays, device audio-processing benchmarks and recorded-noise experiments. [Pipeline](PIPELINE_OPTIMIZATION.md) and [noise](NOISE_REDUCTION.md) reports describe the results and limitations.

It does **not** establish fewer missed turns, shorter waiting times, reliable live-venue accuracy or improved independence in daily use. Those are the outcomes the project should measure next, not numbers to infer from a unit-test pass rate.

## A practical next field trial

1. Recruit consenting representative users and obtain venue permission. Start with staged, non-sensitive announcements.
2. Compare the existing way of noticing calls with CueBell assistance. Do not remove the official display, staff support or companion fallback.
3. Measure correctly noticed target calls, missed calls, false alerts, time from announcement end to alert, and time to acknowledge.
4. Test non-target speech, repeats, corrections, network loss, phone placement, different voices and language combinations.
5. Ask whether setup, status and alerts are understandable. Record device/OS settings and accessibility needs.
6. Report counts and failure examples. Keep speakers, sessions and venues separate when selecting improvements and evaluating them.

Any recording or research logging needs separate consent, a defined retention period and access controls. Do not collect patient information or publish bystander audio.

## Role of Gnani AI

Gnani Prisma v3.0 turns the user's microphone audio into text for setup and monitoring. That makes Indian-language speech a functional part of the application rather than a decorative integration. CueBell then validates text-model output before producing an alert.

The current text interpreter uses an explicitly configured OpenAI fallback. Evon and Timbre are not integrated. Local GTCRN is a separate third-party enhancement model; it does not replace Prisma recognition.
