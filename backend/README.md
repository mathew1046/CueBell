# CueBell standalone backend

Python 3.12+ FastAPI relay for the separately installed native Android app. This
directory is independently installable; it does not serve or build the APK.
The Android preview uses a separately hosted deployment. Automated tests use dummy
credentials and mocked providers; separate historical text-model smoke checks and
Gnani streaming connection/PCM checks passed. Spoken-audio recognition remains
unverified; see the evidence record:
https://github.com/mathew1046/CueBell/blob/main/docs/VERIFICATION.md

## Install and test

Run from the `backend/` directory of your checkout:

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
| `TEXT_PROVIDER` | `openai_fallback`; set `gnani_evon` for the Modal gateway. No automatic failover between providers. |
| `OPENAI_API_KEY` | Required only with `TEXT_PROVIDER=openai_fallback`. |
| `OPENAI_MODEL` | Exact Responses API ID for the OpenAI provider. The example uses account-verified `gpt-6-luna` with structured output support. |
| `EVON_API_KEY` | Required with `TEXT_PROVIDER=gnani_evon`; the bearer secret configured on your Modal gateway. |
| `EVON_BASE_URL` | Required for Evon; your gateway's HTTPS base URL ending in `/v1`. |
| `EVON_MODEL` | `gnani/gnani-evon-v3.3-30B-A3B`; must match the gateway's model ID. |
| `EVON_TIMEOUT_SECONDS` | `12`; live interpretation deadline, greater than 0 and at most 15 seconds. |
| `EVON_SETUP_TIMEOUT_SECONDS` | `130`; intent/setup deadline, greater than 0 and at most 130 seconds. |
| `DEMO_ACCESS_CODE` | Operator-generated random pairing secret, at least 16 characters; required for code-based pairing. No usable default. |
| `ALLOW_APP_SESSIONS` | `false`; explicitly set `true` to accept anonymous no-login demo app sessions without a pairing code. |
| `ALLOW_INSECURE_LOCAL` | `false`; use `true` only for isolated local development, never public hosting. |
| `MAX_SESSIONS` | `8`; allowed range 1–100. |
| `SESSION_TTL_SECONDS` | `14400`; allowed range 60–86400. |
| `CORRECTION_GRACE_SECONDS` | `1.2`; allowed range 0.2–10. Longer grace adds alert latency. |
| `REQUEST_PAUSE_SECONDS` | `3.5`; allowed range 1–15. Quiet interval after finalized setup speech; interim speech keeps capture open. |
| `REQUEST_TIMEOUT_SECONDS` | `90`; allowed range 20–180. Maximum spoken setup duration. |

Generate a pairing code, for example, with
`.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
Give the user the public HTTPS backend URL and pairing code out of band. The
app receives a short-lived session Bearer token; provider keys stay on the host.

### Evon on Modal

Set these on the **CueBell backend**, using the URL and secret from your deployed
gateway. The URL below is the one recorded in the supplied deployment handoff;
replace it if your deployment has a different address.
The branch's `.env.example` includes these non-secret trial settings. The bearer
key itself was deliberately excluded from the archive; use the `EVON_API_KEY`
stored in Modal Secret `cuebell-evon-api`.

```dotenv
TEXT_PROVIDER=gnani_evon
EVON_BASE_URL=https://mathewjosephparakka--cuebell-evon-api.us-east.modal.run/v1
EVON_MODEL=gnani/gnani-evon-v3.3-30B-A3B
EVON_API_KEY=<your-modal-gateway-bearer-secret>
EVON_TIMEOUT_SECONDS=12
EVON_SETUP_TIMEOUT_SECONDS=130
```

Keep `GNANI_API_KEY` for speech and `ALLOW_APP_SESSIONS=true` for the no-login app.
OpenAI credentials are not needed in Evon mode. Restart the relay after changing
configuration. `/health` should report `text_provider: "gnani_evon"`,
`intent_configured: true` and `evon: "configured"`; this does not invoke the model.

The adapter calls `/v1/chat/completions` with bearer authentication, JSON schemas,
`store=false`, and `chat_template_kwargs.enable_thinking=false`. It uses the
existing prompts and local Pydantic/evidence validation for setup, general events
and legacy queue extraction. Incomplete/refused/invalid responses are rejected;
SDK retries and automatic provider switching are disabled.

Rebuild/install the Android client from this branch for its Evon disclosure and
WebSocket consent header. The published v1.3.0 APK has OpenAI-only consent. Setup
remains a synchronous HTTP request: the app waits up to 135 seconds, and spoken
setup keeps its microphone-off service handoff alive for 150 seconds. Allow at
least 135 seconds through the relay's HTTP proxy too.

The handoff measured roughly 20–28-second cold starts and 0.5–5-second warm
responses. Its Modal `IDLE_SECONDS=2` scales the GPU down between requests. For
live monitoring, increase that deployment idle window to keep the GPU warm over
expected announcement gaps; budget for the additional idle GPU time. The live
12-second request timeout and existing 15-second freshness cutoff still apply,
so a cold live request may lose coverage rather than emit a stale alert.

Local adapter tests use mocked inference. The handoff's model-quality probes
also recorded negation/voice-stop mistakes; live inference and deployment checks
remain separate from transport/schema compatibility.

### Opt-in no-login demo client

For a client with a preconfigured backend URL and no pairing screen, the operator
must explicitly set `ALLOW_APP_SESSIONS=true` on the backend. The client sends
`POST /v1/sessions` with the JSON object `{}` (`{"access_code":null}` is equivalent).
Without that setting, missing/null codes return HTTP 401; deployed code-based
access does not silently become anonymous. A supplied code is always checked:
wrong codes still fail, and code-based pairing still requires a configured
`DEMO_ACCESS_CODE` of at least 16 characters. Empty strings and malformed payloads
are rejected, not treated as anonymous requests.

Only session admission changes. The response and subsequent Bearer-authenticated
HTTP/WebSocket protocol, expiry (four hours by default), processing consent,
per-session controls, TLS requirements, and provider privacy behavior are unchanged.
No provider keys or pairing secret belong in the APK. No actual environment or
deployment is changed by enabling support in this source tree.

**Public anonymous access permits use of the operator's paid providers.** The
in-process limits below provide no identity or anti-abuse guarantee. Before public
production use, add a protective gateway with attestation and/or account
authentication, edge abuse controls, and provider spending/budget restrictions.
IP limits can be bypassed by distributed clients and can block legitimate users
sharing a NAT; an anonymous endpoint is not production account authentication.

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
Anonymous admission similarly uses only `request.client.host`, the ASGI server's
effective client IP; it never reads raw `X-Forwarded-For` itself. Correct trusted
proxy configuration is essential: without it, all clients may share the proxy IP;
over-trusting proxies permits address spoofing.
The application bounds actual HTTP bodies at 8192 bytes, including chunked
bodies, but proxy/server timeouts are still needed against slow uploads.

The Docker image runs as an unprivileged user and exposes port 8000. Supply
secrets at runtime (`--env-file` or a secret manager), not at image build time.
Use a private network to the TLS proxy, keep one worker, and configure trusted
proxy addresses as above. Do not disable TLS checks to work around proxy setup.

## Native protocol

### General speech-event monitoring (`speech-event-v1`)

New requests are no longer queue-token forms. The setup prompt builds a grounded
`monitor_event` task with a subject, required condition, readable summary and any
explicit identifiers. For example, “Notify me when train 14922 is here” requests
an arrival announcement; it does not require a separate token or match every
mention of that number. Names being called, boarding, spoken instructions and
other speech-established events use the same path. Queue calls remain supported.

The complete rewritten setup/event instructions live in `app/prompts.py`.
The event prompt receives the confirmed task and bounded recent evidence. Exact
source validation, identifier checks, correction grace, duplicate suppression,
voice-stop priority and validated task activation remain enforced outside the prompt.
The client automatically calls the one-use confirmation endpoint after a valid
submitted request; this is not a second user confirmation screen. Consent and
Android permission checks remain required.
Alerts carry `summary`, `location`, `evidence_text` and `task_summary`; `token` and
`counter` are null for general tasks. The old queue extractor remains only for
legacy confirmed queue rules. No external tracking, messaging integration or
non-speech sound recognition is implied. This is a supplementary aid, not an
emergency-alert guarantee.

Deploy this backend together with the updated Android client. A prompt or APK
change in the checkout does not update a separately hosted service. Deployment
restarts discard in-memory sessions; users must submit and confirm a fresh task.
Session creation advertises `monitoring_schema: "speech-event-v1"`.

### Endpoints

- `POST /v1/sessions`: `{"access_code":"…"}` → session `token`, expiry, disclosure.
  The only payload change is optional `access_code`: `{}` or `{"access_code":null}`
  creates the same session only when `ALLOW_APP_SESSIONS=true`.
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
  header and `x-processing-consent` containing `audio-gnani` plus `text-openai`
  or `text-evon-modal`, matching the selected provider. The updated Android app
  discloses both supported text providers and sends
  `audio-gnani;text-openai;text-evon-modal`. Browser `Origin` headers are rejected;
  tokens are not accepted in query strings.
- Wait for `status` with `state: READY`, then send real-time **1024-byte frames
  of signed PCM16 little-endian, 16 kHz, mono** (512 samples / 32 ms). No WAV
  headers, compressed audio, or bulk replay. `request` returns one final spoken
  request transcript; the client submits that text through intent/confirmation.
  `monitor` requires an active confirmed rule. Only one stream per session.
- JSON controls remain `{"type":"ping"}`, `{"type":"stop"}`, and
  `{"type":"gap"}`. A gap means audio coverage was lost and forces reconnect;
  the app must disclose that calls may have been missed. A connected socket
  alone does not mean microphone coverage is healthy.
- During monitoring, extraction can return a semantic `stop_request` with verbatim
  evidence and chronological source IDs including the newest segment. Validated
  requests take priority over announcement events, clear pending calls and pause
  the rule. The relay sends `monitor.pause` with `reason: voice`, then closes the
  stream. The native client must stop capture and suppress reconnect on that event;
  resume requires an explicit user action. Token/history are retained. Spoken setup
  remains a request/confirmation flow and does not execute listening controls.

Session admission (anonymous and code-based combined) is limited globally to
20 attempts/minute. Anonymous sessions additionally allow three successful
admissions per effective client IP per rolling ten minutes, even if a session is
deleted. At most 1024 IP buckets are retained; expired buckets are reclaimed and
new IPs are rejected with HTTP 429 when the table is full, rather than evicting
active limits. Both modes share the configured session capacity and expiry.
Code-based sessions do not consume the anonymous IP budget. Ordinary authenticated
HTTP requests remain limited to 30/minute/session. These single-process, in-memory
demo safeguards are not identity, account authentication, reliable abuse prevention,
or a substitute for edge rate limits and spending controls.

## Providers, grounding, and safety limits

- **Gnani only for speech**: wss://api.vachana.ai/stt/v3/stream,
  `model: prisma-v3.0`. Negotiation must contain
  `config.sample_rate: 16000` and `config.chunk_size: 512` before audio starts.
   Final transcripts use `text`, `segment_id`, `is_final: true`. Setup combines
  sentence finals after a quiet interval; interim results keep setup capture open.
  Monitoring interprets finals only. Upstream connections are ended at 14 minutes, before the
   documented 15-minute limit; the app must reconnect and show the coverage gap.
- Automatic speech-language detection is enabled by `indic-auto`, not the
  unsupported value `auto`. Optional provider `detected_language_code` metadata
  derives from transcript script and may be absent; it is not acoustic confidence.
  The text model interprets token languages/forms without a local number parser;
  actual speech recognition remains limited by the provider's supported languages.
  Upstream HTTP 401/403 closes the app stream with 4403 and configuration guidance,
  avoiding repeated attempts with rejected credentials; transient failures retry.
- **OpenAI is the explicitly authorized text fallback**, not a speech provider.
  Text requests and PA transcript windows are sent using the configured model's
  Responses API, structured output, `store=false`, a 12-second timeout and no
  automatic SDK retries. This flag is not a promise about provider retention;
   check current provider terms and obtain consent before any processing.
- **Gnani Evon on Modal** is selected with `TEXT_PROVIDER=gnani_evon`, using the
  Chat Completions contract above. Text goes to your Modal deployment; speech
  still goes to Gnani Prisma. Only the selected text provider is called.
- No venue token grammar, digit count, prefix whitelist, number dictionary or
  counter range is enforced. The text model interprets setup and announcement
  identifiers consistently; users review the proposed target before monitoring.
  A clear token read-out alone can trigger a call, without a counter or keyword.
  Visual, vibration and sound alerts are the default unless explicitly silenced.
- Extraction does not receive the user's rule, target, alert preferences, or
  match state. Recent observed PA tokens are supplied only as bounded, filtered
  correction context; they are not the user's target. Evidence/source IDs,
  chronology and exact source spans are checked before matching the confirmed
  model-normalized target. Language/number semantics and counter interpretation
  are model judgments, not independently verified by handwritten rules.
- Voice-stop intent uses the same structured extraction call, not a phrase list
  or an extra model request. The prompt covers multilingual/indirect requests and
  excludes negations, quotations, hypotheticals and PA/cancellation instructions.
  Deterministic checks validate only source provenance, not semantic correctness.
  Recognition still depends on Gnani's supported languages and network/model
  availability; no offline or instantaneous stop guarantee is made. There is no
  speaker authentication, so nearby speech can pause monitoring. Keep manual and
  Android notification stop controls available.
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

- 227 isolated backend tests and Ruff lint/format checks passed, including opt-in
  anonymous admission, strict payload validation, IP/global/capacity limits, and
  unchanged Bearer authentication, expiry, consent, and session controls.
- Live account model discovery confirmed `gpt-6-luna`; the ignored local environment
  selects it and `GNANI_LANGUAGE_CODE=indic-auto`.
- Live English/Malayalam text intent/call extraction, negative announcements,
  instruction-injection abstention, HTTP confirmation/lifecycle, number-word and
  leading-zero handling, and counter correction through the reducer passed.
  These staged text probes do not test speech, PA acoustics or deployment accuracy.
- After the user corrected authorization, live Gnani streaming connected at
  `wss://api.vachana.ai/stt/v3/stream` with `model=prisma-v3.0` and
  `language_code=indic-auto`. Negotiation confirmed 16 kHz and 512-sample frames.
  A synthetic 440 Hz tone followed by silence (48 paced 1,024-byte PCM frames,
  1.536 seconds) was sent without a reported provider error. No transcript was
  returned during the bounded check. This verifies connection and client-side streaming,
  not speech recognition or end-to-end alert accuracy. Earlier HTTP 401 failures
  are resolved; no endpoint/model change or authentication bypass was necessary.

7 November regression run: 253 backend tests and Ruff lint/format checks passed.
Voice-stop tests inject structured model decisions in multiple languages, verify
source evidence, pause/stream closure, retained token, explicit resume, pending
alert cancellation and unchanged spoken setup. They do not verify live model
intent accuracy, spoken-language recognition or physical-phone background stopping.

Official automatic-language contracts:
https://docs.gnani.ai/api/STT/stt-websocket.md
https://docs.gnani.ai/api/STT/models/prisma-v3.md
