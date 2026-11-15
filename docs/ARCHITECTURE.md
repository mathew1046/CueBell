# Architecture

CueBell separates the user's task, the speech transcript and the alert decision. An announcement is input to interpret, not an instruction to change the application.

## End-to-end flow

```text
1. User describes a task
   Typed request ──────────────────────────┐
   Spoken request → microphone → Prisma ───┤
                                          ↓
2. Text interpreter → validated task → automatic activation
                                          ↓
3. Microphone → optional local GTCRN → authenticated relay → Prisma
                                          ↓
4. Completed transcript → structured observation → evidence checks
                                          ↓
5. Ordered reducer → match / correction / uncertainty → alert
```

Example: “Tell me when pharmacy token 442 is called.” The task remains active while incoming announcements are evaluated. Hearing token 441 should not create the same alert; hearing a correction should update the result rather than silently overwrite history.

## Clients

**Shared interface.** React Native, Expo Router and TypeScript implement Home, task setup, history, settings and help. A clear task activates automatically after processing consent and permission checks. The protocol still separates proposal and confirmation; the client completes that sequence without asking for a second confirmation tap.

**Android.** A local Kotlin Expo module owns `AudioRecord`, WebSocket transport and foreground-service notifications. Capture starts while the app is visible. The service can continue capture in the background, subject to Android privacy, battery and notification settings. Expo Go cannot run it.

**Web.** AudioWorklet captures and converts microphone input. The browser stops capture when the page becomes hidden and requires an explicit restart. Sound, vibration, notifications and installation depend on browser/OS support. See [web setup](WEB.md).

Both paths send 16 kHz mono signed 16-bit little-endian PCM in 1,024-byte frames. Optional [GTCRN denoising](NOISE_REDUCTION.md) happens locally before relay transmission; raw capture is the default.

## Backend and providers

The Python/FastAPI relay manages one monitor per expiring bearer session. State is bounded and held in memory, so use **one worker and one instance**. Restarting the process clears sessions; additional workers would need a shared state design first.

- **Speech:** Gnani Prisma `prisma-v3.0`, through `wss://api.vachana.ai/stt/v3/stream`, with `indic-auto` by default.
- **Text interpretation:** the configured OpenAI Responses API model with structured outputs. Its exact model ID is operator configuration.
- **Not integrated:** Gnani Evon and Timbre. The repository does not assume an undocumented hosted Evon endpoint.

The backend sends completed transcript segments for interpretation. This is not a promise of instant partial-word captioning. Total delay includes speech finalization, network transport, text interpretation and the correction grace period.

## Validation and alert decisions

The text model proposes a task or observation; deterministic code checks whether it can be used.

- Source segment IDs must be known, unique, current and chronological.
- Evidence and location must appear in the cited transcript.
- Literal identifiers must agree with their source and the active task.
- A match needs evidence for both the subject and the requested condition.
- Unsupported or ambiguous results become uncertainty, not a forced match.
- The reducer handles ordering, repeated announcements, corrections, cancellation and acknowledgment.

The user's target is not sent as a recognition hint to Prisma. It is used downstream when interpreting and validating the task match. These checks constrain model output; they cannot repair a wrong transcript or prove the original audio was understood correctly.

A source-grounded voice-stop decision pauses listening. It still depends on the network and recognition, and there is no speaker identification. The visible Stop control remains essential.

## API map

All session operations except admission require a bearer credential.

- `GET /health`: process and provider-configuration flags. No provider inference.
- `POST /v1/sessions`: admit a session under configured demo/operator controls.
- `POST /v1/intent`: interpret a consented typed request.
- `POST /v1/confirm`: activate the validated proposal.
- `GET /v1/state`: current task, history, alerts and stream status.
- `POST /v1/control`: pause, resume, acknowledge or stop.
- `DELETE /v1/session`: delete session state and close its stream.
- `WSS /v1/stream`: request or monitoring audio, with bounded framing.

Native streaming uses authorization and consent headers. Browsers must pass an exact allowed Origin and authenticate in a bounded first WebSocket message; tokens never belong in URLs. The detailed schemas live in [`models.py`](../backend/app/models.py) and routes in [`main.py`](../backend/app/main.py).

## Interruptions and privacy

Queues and retry attempts are bounded. Connection loss produces a visible coverage gap; stale audio is not replayed as a current announcement. An active task does not imply the microphone is connected.

Provider secrets stay server-side. The app/relay do not save raw audio or transcript history to a recording database. Session memory and provider processing are still data handling: see [privacy](PRIVACY.md) and [security](../SECURITY.md).

## Deployment

The public frontend and API share `https://cuebell.mathewjoseph.xyz`. The reverse proxy routes `/v1/` and `/health` to the relay and other paths to the production web export. HTTPS/WSS, exact trusted-proxy configuration and exact browser origins are required.

See [backend setup](../backend/README.md), [deployment operations](../ops/README.md) and [pipeline experiments](PIPELINE_OPTIMIZATION.md).
