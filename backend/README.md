# QueueSaathi standalone backend

Python 3.12+ FastAPI relay for the separately installed native Android app. This
directory is independently installable; it does not serve or build the APK.
No backend has been deployed. Automated tests use dummy credentials and mocked
providers; separate live Luna smoke checks passed. Gnani streaming handshakes
were rejected with HTTP 401 before audio transmission; see verification below.

## Install and test

Run from `/home/mathew/Arrakis/QueueSaathi/backend` (or your standalone backend checkout):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/pytest -q
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
```

`requirements.lock` is `pip freeze --exclude-editable` from the tested Linux,
Python 3.12 environment, including test/lint tools. It contains no local/editable
paths and is not a hash-verified supply-chain lock. For unpinned development,
install `.[dev]` instead. The Dockerfile installs runtime ranges from
`pyproject.toml`, constrained by `requirements.lock`, without installing the full
development snapshot.

## Configuration

Copy `.env.example` to `.env` in the backend working directory, or inject the
following environment variables with your host's secret manager. Never put
provider keys or the operator pairing code in source control or the APK.

| Variable | Default / requirement |
| --- | --- |
| `GNANI_API_KEY` | Required for speech; sent only to Gnani Prisma. |
| `GNANI_LANGUAGE_CODE` | `indic-auto`; automatic detection among Prisma's 10 supported languages. Optional 1–4 language codes such as `ml-IN,en-IN` prioritize languages, not restrict recognition. |
| `OPENAI_API_KEY` | Required for text intent and announcement interpretation. |
| `OPENAI_MODEL` | Exact Responses API ID enabled in your account. The example uses account-verified `gpt-6-luna` with structured output support; no nickname or automatic substitution. |
| `DEMO_ACCESS_CODE` | Operator-generated random pairing secret, at least 16 characters. No usable default. |
| `ALLOW_INSECURE_LOCAL` | `false`; use `true` only for isolated local development, never public hosting. |
| `MAX_SESSIONS` | `8`; allowed range 1–100. |
| `SESSION_TTL_SECONDS` | `14400`; allowed range 60–86400. |
| `CORRECTION_GRACE_SECONDS` | `1.2`; allowed range 0.2–10. Longer grace adds alert latency. |

Generate a pairing code, for example, with
`.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
Give the user the public HTTPS backend URL and pairing code out of band. The
app receives a short-lived session Bearer token; provider keys stay on the host.

`GET /health` is a configuration/liveness check only. Its flags indicate keys
are present, **not** that credentials, billing, model availability, transcription
quality, or an end-to-end alert have been verified.

## Hosting with TLS and a trusted reverse proxy

Use **one worker and one instance**. Sessions, history, proposals, deduplication,
pending alerts, and rate limits live only in that process's memory. Restarts lose
all sessions; multiple workers/replicas will break pairing and stream consistency.
There is no database, cross-worker coordination, push notification service, or
offline catch-up.

Example host process behind a TLS proxy on the same machine:

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 --ws-max-size 8192 --timeout-keep-alive 5 --no-access-log
```

Example Caddy configuration (replace the illustrative domain and configure DNS):

```text
queue.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

The illustrative app base URL is https://queue.example.org and the stream URL
is wss://queue.example.org/v1/stream. The proxy must support WebSocket upgrades,
strip/replace client-supplied forwarding headers, and allow long-lived streaming
connections. Configure its idle/read timeouts and request rate limits explicitly;
health checks must use HTTPS or the trusted proxy too.

**Do not expose port 8000 publicly or trust arbitrary forwarded headers.** Only
allow exact trusted proxy addresses in `--forwarded-allow-ips`; never use `*`
unless network isolation actually prevents every untrusted direct connection.
With a containerized proxy, its source address is not normally `127.0.0.1`:
configure the exact proxy address/network and private networking accordingly.
The app checks ASGI's effective `https`/`wss` scheme, not an untrusted raw
`X-Forwarded-Proto` header. Keep the upstream WebSocket limit at 8192 bytes.
The application bounds actual HTTP bodies at 8192 bytes, including chunked
bodies, but proxy/server timeouts are still needed against slow uploads.

The Docker image runs as an unprivileged user and exposes port 8000. Supply
secrets at runtime (`--env-file` or a secret manager), not at image build time.
Use a private network to the TLS proxy, keep one worker, and configure trusted
proxy addresses as above. Do not disable TLS checks to work around proxy setup.

## Native protocol (unchanged)

- `POST /v1/sessions`: `{"access_code":"…"}` → session `token`, expiry, disclosure.
- Authenticated HTTP uses `Authorization: Bearer <session token>`.
- `POST /v1/intent`: `{"text":"…","consent_to_text_processing":true}` →
  `clarify` or `confirm` with a one-use `proposal_id`. This does not activate a monitor.
- `POST /v1/confirm`: `{"proposal_id":"…"}` → confirmed active rule. Missing
  slots or unsupported evidence cannot be confirmed.
- `GET /v1/state`: current rule, bounded history/alerts, connection status.
- `POST /v1/control`: `{"action":"pause|resume|stop|acknowledge","alert_id":null}`;
  acknowledge requires the relevant alert ID. Pause/stop closes the microphone
  stream. Stop clears retained session observations/history/alerts/proposal.
- `DELETE /v1/session`: invalidates pairing and closes its stream, including
  when the ordinary authenticated-request rate limit has been exhausted.
- WebSocket `/v1/stream?mode=request|monitor` requires the same authorization
  header and `x-processing-consent: audio-gnani;text-openai`. Browser `Origin`
  headers are rejected; tokens are not accepted in query strings.
- Wait for `status` with `state: READY`, then send real-time **1024-byte frames
  of signed PCM16 little-endian, 16 kHz, mono** (512 samples / 32 ms). No WAV
  headers, compressed audio, or bulk replay. `request` returns one final spoken
  request transcript; the client submits that text through intent/confirmation.
  `monitor` requires an active confirmed rule. Only one stream per session.
- JSON controls remain `{"type":"ping"}`, `{"type":"stop"}`, and
  `{"type":"gap"}`. A gap means audio coverage was lost and forces reconnect;
  the app must disclose that calls may have been missed. A connected socket
  alone does not mean microphone coverage is healthy.

Pairing is limited globally to 20 attempts/minute; authenticated ordinary HTTP
requests to 30/minute/session. These are demo safeguards, not production account
authentication, per-IP abuse prevention, or a substitute for edge rate limits.

## Providers, grounding, and safety limits

- **Gnani only for speech**: wss://api.vachana.ai/stt/v3/stream,
  `model: prisma-v3.0`. Negotiation must contain
  `config.sample_rate: 16000` and `config.chunk_size: 512` before audio starts.
   Final transcripts use `text`, `segment_id`, `is_final: true`; interim results
  are ignored. Upstream connections are ended at 14 minutes, before the
   documented 15-minute limit; the app must reconnect and show the coverage gap.
- Automatic speech-language detection is enabled by `indic-auto`, not the
  unsupported value `auto`. Optional provider `detected_language_code` metadata
  derives from transcript script and may be absent; it is not acoustic confidence.
  Queue normalization still supports only the tested Malayalam/English forms.
  Upstream HTTP 401/403 closes the app stream with 4403 and configuration guidance,
  avoiding repeated attempts with rejected credentials; transient failures retry.
- **OpenAI is the explicitly authorized text fallback**, not a speech provider.
  Text requests and PA transcript windows are sent using the configured model's
  Responses API, structured output, `store=false`, a 12-second timeout and no
  automatic SDK retries. This flag is not a promise about provider retention;
   check current provider terms and obtain consent before any processing.
- **Evon is unavailable**: no verified hosted API contract/endpoint is configured.
  There is no guessed endpoint, Evon integration, or silent model substitution.
- The venue is hospital pharmacy, with exact string tokens `[AP]?[0-9]{3}` and
  counters 1–10. Prefixes and zeros are never padded or dropped. Supported
  Malayalam/English number forms are deliberately narrow; other native
  languages, malformed/ambiguous forms, and broader venues require clarification
   or remain uncertain, even if the speech provider recognizes them.
- Extraction does not receive the user's rule, target, alert preferences, or
  match state. Recent observed PA tokens are supplied only as bounded, filtered
  correction context; they are not the user's target. Evidence/source IDs,
  chronology, exact token spans and normalization, and counter evidence are
  checked deterministically before matching the locally confirmed target.
- Corrections/cancellations need a resolvable recent observation (30 seconds).
  Uncertain or unresolved corrections clear pending alerts instead of guessing.
  An already-issued alert can be marked corrected, not physically undone. Split
  phrase context is at most 6 segments/15 seconds; overdue interpretation closes
  coverage instead of reusing a stale queue. Disconnects, gaps, pause/resume,
  and replacement monitors invalidate pending/correction context.
- Repeated token/counter alerts are suppressed for 45 seconds; a changed counter
  is distinct. This heuristic can suppress a genuine repeated call. Uncertainty
  handling intentionally favors missed alerts over unsafe guesses. Explicit
  call-vs-negation semantics and counter/token association still depend on model
  accuracy; substring grounding cannot establish that a PA announcement is true.
- Audio/transcripts are not recorded to disk by this relay. Bounded recent
  transcripts, observations, and history remain in session memory until stop,
  expiry, deletion, or restart. Disable request/header/body capture in proxies,
  monitoring agents and error collectors; never log pairing codes or tokens.

This is an assistive monitor, not an official queue display or a medical/safety
alarm. Noise, missed audio, late or wrong recognition, network interruption,
OS background-microphone restrictions, notification permissions, and battery
management can prevent an alert. The separate native app owns foreground-service
capture and local vibration/sound/visual delivery; this backend does not send
push alerts to a disconnected APK. Users must still check the official display.

## Verification on 6 November 2026

- 189 isolated backend tests and Ruff lint/format checks passed.
- Live account model discovery confirmed `gpt-6-luna`; the ignored local environment
  selects it and `GNANI_LANGUAGE_CODE=indic-auto`.
- Live English/Malayalam text intent/call extraction, negative announcements,
  instruction-injection abstention, HTTP confirmation/lifecycle, number-word and
  leading-zero handling, and counter correction through the reducer passed.
  These staged text probes do not test speech, PA acoustics or deployment accuracy.
- Gnani streaming returned HTTP 401 on two bounded handshakes using configured
  credentials. No successful speech connection or audio transmission occurred.
  Check the key and account's streaming access with Gnani; do not replace speech
  with another provider or disable authentication/TLS to bypass the failure.

Official automatic-language contracts:
https://docs.gnani.ai/api/STT/stt-websocket.md
https://docs.gnani.ai/api/STT/models/prisma-v3.md
