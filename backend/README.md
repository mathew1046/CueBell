# CueBell backend

A Python 3.12+ FastAPI relay for Android and browser clients. Gnani Prisma handles
speech recognition. OpenAI is the explicitly authorized text fallback for task
and announcement interpretation. No verified hosted Evon API is configured.
The relay does not build the APK or serve the web export.

See [architecture](../docs/ARCHITECTURE.md), [verification](../docs/VERIFICATION.md)
and the [documentation index](../docs/README.md).

## Install and test

From `backend/`:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
.venv/bin/python -m ruff format --check app tests
```

Tests use dummy credentials and mocked providers. They do not require microphone
access or establish recognition accuracy. `requirements.lock` is a tested Linux,
Python 3.12 dependency snapshot, including development tools, not a hash-verified
lock. For unpinned development use `.venv/bin/python -m pip install -e '.[dev]'`.
The Dockerfile installs runtime requirements constrained by the snapshot.

## Configure

Copy [`.env.example`](.env.example) to `backend/.env` only if no configured file
exists, or inject variables through your host's secret manager. Settings load
`.env` from the working directory. Keep provider keys and pairing codes server-side.

| Variable | Purpose / default |
| --- | --- |
| `GNANI_API_KEY` | Required for speech recognition. |
| `GNANI_LANGUAGE_CODE` | `indic-auto` detects among Prisma's 10 supported languages. A list of 1-4 codes, such as `ml-IN,en-IN`, prioritizes languages rather than restricting them. Do not use `auto`. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Required for text interpretation. Use an exact Responses API model ID enabled for your account. The example uses `gpt-6-luna`; there is no automatic model substitution. |
| `DEMO_ACCESS_CODE` | Random pairing secret of at least 16 characters, required for code-based admission. No usable default. |
| `ALLOW_APP_SESSIONS` | `false`. Set `true` explicitly for the current no-login app. Public anonymous access permits paid-provider use. |
| `WEB_ORIGINS` | `[]`. JSON array of exact browser HTTPS origins, without paths or wildcards. Native clients need no entry. Loopback HTTP origins are accepted for development. |
| `ALLOW_INSECURE_LOCAL` | `false`. Local development only, never public hosting. |
| `MAX_SESSIONS` | `8`, range 1-100. |
| `SESSION_TTL_SECONDS` | `14400`, range 60-86400. |
| `CORRECTION_GRACE_SECONDS` | `1.2`, range 0.2-10; longer grace delays alerts. |
| `REQUEST_PAUSE_SECONDS` | `3.5`, range 1-15; silence after finalized setup speech. Interim speech keeps capture open. |
| `REQUEST_TIMEOUT_SECONDS` | `90`, range 20-180. |

Optional scheduling, output, caching and VAD controls are listed in `.env.example`.
Keep baseline defaults unless you have validated the trade-offs. The faster
experimental profile improved setup latency but failed the full monitoring
quality gate. See [pipeline optimization](../docs/PIPELINE_OPTIMIZATION.md).

For local browser startup, use the [web guide](../docs/WEB.md#run-both-services-locally).
`GET /health` checks liveness and configuration presence only. It does not verify
credentials, billing, model availability or a working alert.

### Session admission

`POST /v1/sessions` accepts `{"access_code":"your-code"}`. With
`ALLOW_APP_SESSIONS=true`, `{}` or `{"access_code":null}` also works. Otherwise
missing/null codes return 401. Supplied codes are always checked; empty strings
and malformed payloads are not anonymous requests. The current app has no pairing
screen, so its backend must explicitly enable anonymous admission.

Sessions receive an expiring bearer token, four hours by default. Admission is
limited to 20 attempts/minute globally. Anonymous admission also allows three
successful sessions per effective client IP per rolling ten minutes, even after
deletion. The bounded table holds 1024 IP buckets and rejects new IPs when full.
Both modes share capacity and expiry; code admission does not consume the anonymous
IP budget. Authenticated HTTP requests allow 30/minute/session. Session deletion
remains available after that limit is exhausted.

These in-memory demo limits are not identity or reliable abuse prevention. Add
account authentication or attestation, edge limits and provider spending controls
before production use. Shared NATs can block legitimate users; distributed clients
can bypass IP limits.

## Host behind TLS

Run **one worker and one instance**. Sessions, history, pending alerts and rate
limits live in process memory. Restarts lose them; multiple workers or replicas
break stream consistency. There is no database, offline catch-up or push service.

From `backend/`, behind a TLS proxy on the same host:

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 --ws-max-size 8192 --timeout-keep-alive 5 --no-access-log
```

Example Caddy configuration, after configuring DNS for your own domain:

```text
queue.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

- Keep port 8000 private. Trust only exact proxy addresses, not `*`. Containerized proxies usually do not connect from `127.0.0.1`; configure their actual private address/network.
- Support WebSocket upgrades and long-lived streams. Set proxy read/idle timeouts, upload timeouts and edge rate limits explicitly.
- Replace client-supplied forwarding headers. TLS enforcement uses ASGI's effective scheme; anonymous limits use its effective client IP, not raw forwarding headers. Incorrect trust settings allow spoofing or group all clients under one IP.
- Keep the upstream WebSocket limit at 8192 bytes. HTTP bodies are also bounded at 8192 bytes, including chunked bodies; this does not prevent slow uploads without server/proxy timeouts.
- The Docker image runs unprivileged on port 8000. Inject secrets at runtime, use a private proxy network and retain one worker. Do not disable TLS enforcement to fix a proxy error.
- Disable sensitive request, header and body logging in proxies, monitoring agents and error collectors.

Deploy matching client/backend versions. A local prompt or APK change does not
update the hosted relay. After a restart, submit a fresh task.

## Client protocol

Session creation advertises `monitoring_schema: "speech-event-v1"`. A request
specifies a subject and a spoken event, such as train arrival, boarding or a name
being called. It is not live transport tracking or non-speech sound detection.
Prompts are in [`app/prompts.py`](app/prompts.py).

| Endpoint | Behavior |
| --- | --- |
| `POST /v1/sessions` | Admit a client; return token, expiry and processing disclosure. |
| `POST /v1/intent` | `{"text":"...","consent_to_text_processing":true}` returns clarification or a one-use `proposal_id`. It does not activate listening. |
| `POST /v1/confirm` | `{"proposal_id":"..."}` activates a valid grounded task. The client submits this automatically, without a second confirmation screen. |
| `GET /v1/state` | Current task, bounded history/alerts and connection status. |
| `POST /v1/control` | For example, `{"action":"pause","alert_id":null}`. Actions are `pause`, `resume`, `stop` and `acknowledge`; acknowledgment needs the alert ID. Pause/stop closes capture; stop clears observations, history, alerts and proposal. |
| `DELETE /v1/session` | Revoke the session and close its stream. |
| WebSocket `/v1/stream?mode=request` or `/v1/stream?mode=monitor` | Spoken setup or monitoring of a confirmed task; one stream per session. |

Authenticated HTTP uses `Authorization: Bearer <session-token>`. Native WebSockets
use that header plus `x-processing-consent: audio-gnani;text-openai`. Browsers must
use an allowed Origin and authenticate in a bounded first message:

```json
{"type":"authenticate","token":"<session-token>","consent":"audio-gnani;text-openai"}
```

Never put bearer tokens in URLs. Wait for `status` with `state: READY`, then send
real-time 1024-byte signed PCM16LE frames at 16 kHz mono: 512 samples, or 32 ms.
Do not send WAV headers, compressed audio or bulk replay. Setup returns a final
request transcript for the intent/confirmation flow; monitoring requires an active task.

Controls are `{"type":"ping"}`, `{"type":"stop"}` and `{"type":"gap"}`.
A gap forces reconnect and must warn that announcements may have been missed.
A connected socket does not prove healthy microphone coverage. Validated voice
stop takes priority over alerts: `monitor.pause` with `reason: voice` closes the
stream, retains the task/history and requires explicit user restart.

## Provider and safety limits

- Gnani uses `wss://api.vachana.ai/stt/v3/stream`, `prisma-v3.0`, negotiated at 16000 Hz / 512 samples. Monitoring interprets final transcripts only. Streams end at 14 minutes, before the provider's 15-minute limit, requiring reconnect and a visible gap. Rejected provider credentials close the client with 4403 rather than repeated retries.
- OpenAI receives text, not audio, through the Responses API with structured output, `store=false`, a 12-second timeout and no automatic SDK retries. Provider retention remains subject to provider terms.
- Exact source spans, source IDs, chronology and identifiers are validated outside the prompt. These checks do not prove semantic accuracy or that an announcement is true. Voice stop is not speaker authentication; nearby speech can pause listening.
- Corrections need a resolvable recent observation within 30 seconds. Unresolved corrections clear pending alerts. An issued alert can be marked corrected, not undone. Context is bounded to six segments / 15 seconds; stale work and coverage gaps invalidate pending context.
- Legacy queue extraction remains for confirmed queue rules. It does not receive the user's target or preferences. Repeated token/counter alerts are suppressed for 45 seconds; a changed counter is distinct. Suppression can hide a genuine repeated call.
- The relay does not intentionally record audio or transcripts to disk. Bounded session memory is cleared by stop, expiry, deletion or restart. See [privacy](../docs/PRIVACY.md) and [security](../SECURITY.md).

CueBell is a supplementary aid, not a medical/safety alarm or official announcement
source. Noise, incorrect interpretation, network gaps and device restrictions can
prevent alerts. Android owns local foreground capture and alert delivery; browsers
must remain visible. Neither receives backend push alerts after disconnecting.
