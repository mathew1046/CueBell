# Architecture

CueBell separates the user's task, the transcript and the alert decision.
Announcements are evidence to interpret, never application instructions.

## End-to-end flow

```text
Typed request ─────────────────────────┐
Spoken request → microphone → Prisma ───┤
                                       ↓
Text interpreter → validated task → automatic activation
                                       ↓
Microphone → optional local GTCRN → authenticated relay → Prisma
                                       ↓
Final transcript → structured observation → evidence checks
                                       ↓
Ordered reducer → match / correction / uncertainty → alert
```

Example: “Tell me when pharmacy token 442 is called.” Token 441 should not alert;
a correction should update the result without silently overwriting history.

## Clients

React Native, Expo Router and TypeScript share Home, setup, history, settings and
help. Clear requests activate after consent/permissions. The protocol separates
proposal and confirmation, but the client completes both without a second tap.

- **Android:** Kotlin Expo module owns `AudioRecord`, WebSockets and foreground notifications. Capture starts visibly and can continue in background, subject to privacy/battery/notification settings. Expo Go cannot run it.
- **Web:** AudioWorklet captures/converts audio. Hidden pages stop and require restart. Installation, notifications, sound and vibration depend on browser/OS. See [web setup](WEB.md).

Both send 16 kHz mono signed PCM16LE in 1024-byte frames. Optional local
[GTCRN denoising](NOISE_REDUCTION.md) precedes transmission; raw is default.

## Backend and providers

FastAPI manages one monitor per expiring bearer session. Bounded state lives in
memory: **one worker/instance** only. Restart clears sessions; scaling needs shared state.

- Speech: Gnani Prisma `prisma-v3.0`, `wss://api.vachana.ai/stt/v3/stream`, default `indic-auto`.
- Text: configured OpenAI Responses API model with structured outputs; exact ID is operator configuration.
- Evon/Timbre are not integrated; no undocumented hosted Evon endpoint is assumed.

Only final segments are interpreted. Delay includes speech finalization, network,
text interpretation and correction grace, not instant partial-word recognition.

## Validation and alert decisions

Deterministic checks constrain model proposals:

- Known, unique, current, chronological source segment IDs.
- Verbatim evidence/location and matching literal identifiers.
- Evidence for both requested subject and condition; ambiguity becomes uncertainty.
- Ordered reduction of repeats, corrections, cancellation and acknowledgment.

The target is not a Prisma recognition hint; it is used downstream. Checks cannot
repair transcripts or prove audio comprehension. Source-grounded voice stop pauses,
but depends on network/recognition and has no speaker identification. **Home → Stop
Listening** pauses manually; **Settings → Clear task** resets. Older APKs may say Stop.

## API map

Admission returns a bearer; other session operations require it.

| Route | Purpose |
| --- | --- |
| `GET /health` | Liveness/configuration, no provider inference. |
| `POST /v1/sessions` | Admission. |
| `POST /v1/intent` | Consented typed-request interpretation. |
| `POST /v1/confirm` | Activate proposal. |
| `GET /v1/state` | Task/history/alerts/stream. |
| `POST /v1/control` | Pause/resume/acknowledge/stop. |
| `DELETE /v1/session` | Delete/revoke/disconnect. |
| `WSS /v1/stream` | Request or monitor audio. |

Native sockets use authorization/consent headers; browsers require exact Origin
and bounded first-message authentication, never URL tokens. See [protocol](../backend/README.md#client-protocol),
[schemas](../backend/app/models.py) and [routes](../backend/app/main.py).

## Interruptions, privacy and deployment

Bounded queues/retries discard stale audio and warn of coverage gaps. An active
task does not prove connected capture. Provider keys stay server-side; no normal
recording database exists. See [privacy](PRIVACY.md) and [security](../SECURITY.md).

`https://cuebell.mathewjoseph.xyz` serves both layers: proxy `/v1/` and `/health`
to relay before static routes. HTTPS/WSS, exact proxy trust/origins and matching
client/backend versions matter. See [backend setup](../backend/README.md),
[operations](../ops/README.md) and [pipeline experiments](PIPELINE_OPTIMIZATION.md).
