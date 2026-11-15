# CueBell backend

Python 3.12+ FastAPI relay: Prisma transcribes; authorized OpenAI interprets text.
No verified hosted Evon API. No APK/web hosting.

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

Mocked tests need no providers. `requirements.lock`: tested Linux/Python 3.12 snapshot,
not hash-verified. Unpinned: `.venv/bin/python -m pip install -e '.[dev]'`.
Docker constrains runtime dependencies with it.

## Configure

Copy [`.env.example`](.env.example) if `backend/.env` is absent, or inject
secrets. Settings read working-directory `.env`. Keys stay server-side.

| Variable | Meaning/default |
| --- | --- |
| `GNANI_API_KEY` | Required speech key. |
| `GNANI_LANGUAGE_CODE` | `indic-auto`: 10 languages. Lists of 1-4 codes, e.g. `ml-IN,en-IN`, prioritize rather than restrict. Never `auto`. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Required text key and exact enabled Responses model ID; example `gpt-6-luna`. No substitution. |
| `DEMO_ACCESS_CODE` | Random pairing secret, at least 16 characters; no default. |
| `ALLOW_APP_SESSIONS` | `false`; current no-login client requires `true`, permitting paid-provider usage. |
| `WEB_ORIGINS` | `[]`; exact HTTPS origins, no paths/wildcards. Loopback HTTP allowed for development. Native needs none. |
| `ALLOW_INSECURE_LOCAL` | `false`; never enable publicly. |
| `MAX_SESSIONS` | `8`, range 1-100. |
| `SESSION_TTL_SECONDS` | `14400`, range 60-86400. |
| `CORRECTION_GRACE_SECONDS` | `1.2`, range 0.2-10. |
| `REQUEST_PAUSE_SECONDS` | `3.5`, range 1-15; finalized-setup silence. Interim speech extends capture. |
| `REQUEST_TIMEOUT_SECONDS` | `90`, range 20-180. |

Choose baseline defaults; faster [pipeline experiments](../docs/PIPELINE_OPTIMIZATION.md)
failed quality gates. [Local startup](../docs/WEB.md#run-both-services-locally)
uses potentially paid providers. Other controls: `.env.example`.

### Session admission

`POST /v1/sessions`: `{"access_code":"your-code"}`. Only with
`ALLOW_APP_SESSIONS=true` are `{}` and `{"access_code":null}` accepted; otherwise
401. Supplied codes are checked; empty/malformed codes are not anonymous.

Limits: 20 admission attempts/minute globally; anonymous success limited to
three/effective IP/rolling ten minutes, surviving deletion. The 1024-IP table
rejects new IPs when full. Code admission shares capacity/expiry but bypasses that
IP budget. Authenticated HTTP: 30/minute/session; deletion remains available.
In-memory demo limits are not identity: add authentication/attestation,
edge limits/spending controls. NATs block users; distributed clients bypass limits.

## Host behind TLS

Use **one worker/instance**: sessions, history, alerts and limits are process-local.
Restarts clear them. No database, push or offline catch-up exists. From `backend/`:

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 --ws-max-size 8192 --timeout-keep-alive 5 --no-access-log
```

Example Caddy configuration after setting DNS:

```text
queue.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

Keep 8000 private. Trust exact proxies, never `*`; use container proxies' actual
addresses/networks. Replace forwarding headers: effective ASGI scheme/IP govern
TLS/admission. Preserve upgrades; configure idle/read/upload timeouts, edge limits
and log suppression. HTTP bodies (including chunked) and WebSockets: 8192 bytes.
Docker runs unprivileged; inject secrets, retain TLS. Match client versions;
restart requires fresh tasks. `/health` checks liveness/configuration only,
not credentials, billing or alerts.

## Client protocol

Admission advertises `monitoring_schema: "speech-event-v1"`. Tasks describe a subject
and spoken event, not transport tracking or non-speech detection.

| Endpoint | Contract |
| --- | --- |
| `POST /v1/sessions` | Token, expiry, processing disclosure. |
| `POST /v1/intent` | `{"text":"...","consent_to_text_processing":true}`: clarification or one-use `proposal_id`; no activation. |
| `POST /v1/confirm` | `{"proposal_id":"..."}` activates; client submits automatically. |
| `GET /v1/state` | Task, bounded history/alerts, connection. |
| `POST /v1/control` | `{"action":"pause","alert_id":null}`; `pause`, `resume`, `stop`, `acknowledge`. Acknowledgment requires alert ID. Pause retains task/history; stop clears observations/history/alerts/proposal. |
| `DELETE /v1/session` | Revoke and disconnect. |
| WebSocket `/v1/stream?mode=request` or `/v1/stream?mode=monitor` | Setup or confirmed-task monitoring; one stream/session. |

HTTP uses `Authorization: Bearer <session-token>`. Native WebSockets add
`x-processing-consent: audio-gnani;text-openai`. Allowed-origin browsers authenticate
in a bounded first message, never a URL:

```json
{"type":"authenticate","token":"<session-token>","consent":"audio-gnani;text-openai"}
```

Wait for `status` / `state: READY`. Send real-time 1024-byte PCM16LE frames:
16 kHz mono, 512 samples/32 ms; no WAV/compression/bulk replay. Setup returns the
final transcript for intent/confirmation. Controls: `{"type":"ping"}`,
`{"type":"stop"}`, `{"type":"gap"}`. Gaps force reconnect and visible warnings.
Validated voice stop emits `monitor.pause`, `reason: voice`, retaining task/history
until explicit restart. A connected socket does not prove microphone coverage.

## Provider and safety limits

- Prisma: `wss://api.vachana.ai/stt/v3/stream`, `prisma-v3.0`, 16000 Hz/512 samples. Final transcripts only. Reconnect at 14 minutes before its 15-minute limit; show gaps. Rejected credentials close with 4403.
- OpenAI: text-only Responses, structured output, `store=false`, 12-second timeout, no SDK retries. Provider retention terms apply.
- Source spans/IDs, chronology and identifiers are checked, not semantic truth. Corrections require a recent resolvable observation within 30 seconds; unresolved corrections clear pending alerts. Issued alerts can be marked corrected, not undone. Context: six segments/15 seconds; stale work/gaps invalidate it.
- Legacy queue extraction excludes targets/preferences. Token/counter duplicates are suppressed for 45 seconds; changed counters differ. Genuine repeated calls may be hidden.

Supplementary aid, not safety alarm. Nearby speech can pause it. Bounded memory
clears on stop/expiry/deletion/restart; no intentional recordings. No push after
disconnection. See [privacy](../docs/PRIVACY.md), [security](../SECURITY.md),
[architecture](../docs/ARCHITECTURE.md), [verification](../docs/VERIFICATION.md).
