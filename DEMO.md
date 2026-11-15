# Demo CueBell

**Goal:** show one personal listening task, a non-match and a matching announcement. Use a consenting speaker or staged recording, not private venue audio.

## Prepare

- Open [the web app](https://cuebell.mathewjoseph.xyz) or install the [Android preview](https://github.com/mathew1046/CueBell/releases/tag/v1.4.0-preview).
- Check internet access, microphone permission and provider quota. A second device or consenting speaker supplies the announcements.
- Keep the browser page visible and screen unlocked. On Android, start while visible and check notification permissions.
- Rehearse before recording. The prototype can miss or misinterpret speech; use the actual result, not a fabricated transcript.

For your own deployment, follow [backend setup](backend/README.md) and [web](docs/WEB.md) or [Android setup](mobile/README.md). Provider keys never go in the client.

## A 60-second script

**0–10 seconds: show the problem**

“If you cannot hear a pharmacy loudspeaker, a token call can be easy to miss. CueBell aims to make that call visible and personal.”

**10–25 seconds: create the task**

Enter: **“Tell me when pharmacy token 442 is called. Vibrate.”**

Accept the processing disclosure, submit and grant microphone permission. Check the active task and wait for Listening. A valid task activates without a second confirmation tap.

**25–45 seconds: demonstrate the difference**

Say the following separately, pausing for recognition:

1. “Pharmacy token four four one, please go to counter one.” Expect no target alert.
2. “Pharmacy token four four two, please go to counter two.” Inspect the actual alert, destination and source text.

If interpretation takes longer, let it finish. Do not edit out waiting time in a way that implies faster live performance.

**45–60 seconds: show the engineering and limit**

“Gnani Prisma transcribes the speech. CueBell checks the interpretation before alerting. We also tested pipeline latency and local noise reduction. It is supplemental assistance, not a replacement for the venue display or staff.”

Stop listening and confirm microphone capture ends. A 60-second video may use clearly labelled cuts; it is not a guaranteed 60-second workflow.

## Optional follow-up checks

- **Correction:** “Correction: token 442 should go to counter three, not counter two.” Check the visible update, not just the transcript.
- **Repeat:** repeat a call and check that it does not create another immediate alert.
- **Spoken setup:** try it after the typed flow. Recognition waits for completed speech; allow short pauses and inspect the task.
- **Noise reduction:** compare the same staged audio and phone position with the setting off and on. Do not present a single rehearsal as a benchmark.
- **Connection loss:** disconnect the network and inspect the gap warning. Missing audio is not replayed as a current announcement.
- **Android background:** test on the actual phone. A native service is not a guarantee that every OEM, lock screen or notification configuration works.

## If something fails

- No transcript: check Listening, microphone permission, page visibility, connectivity and speaker distance.
- Transcript but no alert: inspect target digits, source evidence and uncertainty. Do not change the target to match a mistaken transcript.
- No sound/vibration: check device support, permissions, volume, notification channels and Do Not Disturb.
- Session or service error: submit again after the operator checks backend health, admission limits, credentials and quota. `/health` checks configuration, not successful recognition.

Show a failure honestly. Automated tests or a prerecorded rehearsal can be a clearly labelled fallback, never a claimed live result. See [verification](docs/VERIFICATION.md) and [privacy](docs/PRIVACY.md).
