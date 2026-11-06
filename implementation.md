# CueBell: implementation architecture

**Status:** Research-based implementation plan, 6 November 2026. Revised for intent-driven monitoring. No implementation or live API test is implied.

## 1. Goal and scope

Build a mobile-friendly assistive application that listens to public-address announcements, identifies queue token and counter information, and provides a prominent visual and, where supported, haptic alert for the user's token. Primary audience: people who are deaf or hard of hearing. Start with Malayalam and English announcements and a single venue's configured token and counter formats. Code-switching is a test case, not a proven capability.

This is a supplemental aid, not a safety-critical system or a substitute for the official display or staff. Never imply it cannot miss a call. A user can consult the recent transcript and monitoring status.

**User constraint: all AI models must be Gnani models.** Use Gnani Prisma for speech recognition. Use Gnani Evon only if its access and deployment are confirmed. No external speech, language, classification, enhancement, or embedding models. Handwritten rules and ordinary signal processing are allowed. Do not send audio or text to another model provider.

**Prior art:** The basic concept is not new. A 2018 paper describes a smartphone that detects bank announcements, recognizes a queue number and vibrates for a match. Differentiate through measured Malayalam/English queue performance, correction-aware handling, accessibility and honest reliability, rather than claiming the core concept was invented here. [Ruan et al.](https://onlinelibrary.wiley.com/doi/10.1155/2018/8786308)

## 2. Recommended MVP

- Foreground web app on a supported phone, one microphone and one active monitor. The user speaks or types a request specifying what to watch and their preferred alert. A visible confirmation step allows correction before monitoring starts.
- Browser captures microphone audio; backend relays it to Gnani Prisma streaming STT. Backend keeps the API key private.
- A deterministic, configurable parser extracts token, counter and event meaning from completed transcripts. The user's token is compared **after extraction**, never fed into STT as a hint.
- An event reducer handles calls, corrections, repeats, uncertain interpretations and deduplication. UI shows recent announcements, alerts, listening health and clear uncertainty.
- A microphone-based setup works only within useful acoustic range of the announcement. No background listening, screen-locked alert, source separation, automatic venue detection, queue prediction, or multi-venue support is assumed in the MVP. Verify actual mobile browser behavior on the demo device.

**Why not require an LLM initially?** Gnani's Evon model exists, but the official hosted API is described as closed beta. Until access, exact endpoint, terms, latency and hardware requirements are established, don't invent an API or silently use another provider. The deterministic path is functional without an LLM. If Gnani grants access or a suitable Evon model is self-hosted, add it behind the same extraction interface and compare against the rules baseline. [Gnani Evon waitlist](https://www.gnani.ai/evon-waitlist)

## 3. Data flow

```text
User request (speech via Gnani Prisma, or typed input)
  -> intent extraction (Gnani Evon if available, otherwise deterministic rules)
  -> user confirms token, context and alert -> active monitoring rule

Announcement microphone (explicit permission, visible indicator)
  -> AudioWorklet: downmix + resample + PCM16 framing
  -> authenticated browser/backend WebSocket over TLS
  -> backend streaming adapter (Gnani key remains server-side)
  -> Gnani Prisma v3.0 STT WebSocket
  -> final transcript segment + timing/IDs
  -> bounded context buffer -> deterministic event extractor
  -> schema and evidence checks -> ordered event reducer
  -> compare observed announcement with active monitoring rule
  -> alert / correction / uncertainty UI
```

Optionally place **Gnani Evon** in the extraction step only after access is confirmed. It proposes structured events; validation and alert decisions remain deterministic. Keep original transcript, source segment IDs and processing timestamps for the active session. Evidence grounded in a transcript does **not** verify what the audio actually said.

## Intent-driven monitor lifecycle

The agent orchestrates distinct objects rather than treating one event as the listener itself. A **request** is the user’s spoken or typed instruction. Intent extraction proposes a structured **monitoring rule**. A `monitor.created` event records its creation, while the rule persists for the active session. A transcribed announcement becomes an **observation event**. Validated observations are compared to active rules; a matching observation creates an **alert event**. This separation supports multiple monitors later without claiming the MVP already implements them.

Example request: “Listen for pharmacy token P042 and vibrate.” Gnani Prisma transcribes the request. Gnani Evon may extract the intent if access is verified; otherwise a deterministic parser supports a limited explicit grammar. The app presents “Pharmacy token P042 · Vibrate” for correction and confirmation. It must not begin a monitor based on ambiguous or missing token, destination context, or alert preference. The user can type or tap instead of speaking. Visual feedback accompanies vibration or sound. A sound option can serve people with residual hearing or companions; it must not be the sole feedback channel.

Illustrative internal rule, not a provider response:

```json
{
  "rule_id": "m1",
  "intent": "monitor_announcement",
  "context": "hospital_pharmacy",
  "target": {"kind": "token", "value": "P042"},
  "alert_preferences": ["visual", "vibration"],
  "status": "active",
  "created_at": "2026-11-06T07:00:00Z"
}
```

The timestamp is illustrative. States include `DRAFT`, `AWAITING_CONFIRMATION`, `ACTIVE`, `PAUSED`, `DEGRADED`, `STOPPED` and `EXPIRED`. Monitor lifecycle is distinct from microphone/connection health: an active rule can be degraded if the system is not actually listening. On disconnect, warn that calls may have been missed. Support explicit user actions to edit, pause, resume and stop; editing a target requires confirmation and must not silently apply historic matches.

The LLM may propose intent and fields, but deterministic code validates schema, checks the configured token grammar, and decides whether an observed announcement matches. Preserve the user's exact token and leading zeros. A successful string match does not prove ASR heard the audio correctly. Handle unclear input by asking for confirmation or typed correction. Announcements do not create new monitors or change preferences; treat them as untrusted content, not instructions. Keep the user request and announcement contexts separate. If concurrent speech sources cannot be distinguished reliably, use a visible push-to-talk setup phase followed by a separate listening phase.

## 4. Components and boundaries

### 4.1 Frontend

A React + TypeScript single-page web app is a practical choice, not a requirement. Screens: token setup, listening session, announcement timeline and accessible alert. Ask for microphone access only after the user taps Start. Use `getUserMedia`, secure HTTPS or localhost, and `AudioWorklet` for capture. Handle denied permission, unsupported browser, OS interruption and track-ended events. Offer Stop and make the fact that audio is sent to Gnani explicit before capture.

Obtain the actual `AudioContext.sampleRate`; do not relabel samples as 16 kHz. Downmix channels, resample with a tested implementation when necessary, clamp floating-point samples to [-1, 1], convert to signed 16-bit little-endian PCM, and frame per the actual Gnani specification. Test chunk boundaries and audio duration against a known waveform. Use bounded buffers and backpressure, not unlimited browser memory.

Show a large, high-contrast token/counter alert, text status, an announcement log, and an explicit dismiss/acknowledge button. Use accessible labels, keyboard navigation, screen-reader announcements and a non-colour-only status. `navigator.vibrate` is optional and may be unavailable, disabled, ignored or restricted; show a visual fallback. Do not promise vibration on iOS, in the background, or on a locked phone without device testing.

### 4.2 Backend relay

A small FastAPI/Python WebSocket server is a reasonable MVP because it can relay binary audio, manage per-session state and run deterministic parsing. Node/TypeScript is also viable; choose one rather than two backends. One user session maps to one provider stream; isolate sessions and never expose API keys to the client or log them. The backend is not an audio transcription model.

Enforce TLS, origin checks, authentication or short-lived demo sessions, maximum concurrent sessions, connection and message size limits, and rate limits. Validate input format and session configuration. Use bounded audio queues; if the connection is too slow, show a coverage gap instead of buffering indefinitely. Disconnect and delete in-memory audio when the user stops. Do not store recordings or raw transcripts by default; add explicit consent, retention limits and access control before any persistent logging.

### 4.3 Gnani STT adapter

The documented streaming endpoint is `wss://api.vachana.ai/stt/v3/stream`. Explicitly request `model=prisma-v3.0`; the documentation states omission selects v2.5. Use the current official authentication and connection parameters as documented, keeping credentials server-side. The published protocol expects raw mono signed 16-bit little-endian PCM in exactly 1,024-byte frames. At 16 kHz that is 512 samples or 32 ms per frame; at 8 kHz it is 64 ms. Pace frames in real time; do not send WAV or WebM container chunks. The backend supplies the documented x-api-key-id, language_code, model and x-sample-rate headers because browser WebSocket APIs do not support arbitrary headers. Verify the exact sample-rate setting, final schema and actual behavior against the current docs and a real session before coding the production adapter. [Streaming reference](https://docs.gnani.ai/api/STT/stt-websocket)

Documented results are VAD-completed segments; do not assume live partial-word hypotheses or a model confidence field. A segment marked final can still be corrected by a later spoken announcement. A session is documented to expire after 15 minutes; account for idle timeout, reconnect before expiry, and surface gaps. Test reconnect behavior and deduplicate events, rather than assuming provider IDs remain stable across connections. [Limits](https://docs.gnani.ai/api/STT/limits)

For controlled recorded-clip tests, REST `POST https://api.vachana.ai/stt/v3` uses multipart `audio_file`, `model=prisma-v3.0`, `language_code` and documented API-key authentication. The documented maximum clip length is 30 seconds. Supported file formats include WAV, MP3, OGG, FLAC, AAC and M4A, but WebM is not listed. Transcode a WebM recording into a real supported format; renaming its extension does not convert the audio. Confirm current language codes and request fields against the docs; do not reuse snippets containing secrets. [REST reference](https://docs.gnani.ai/api/STT/speech-to-text)

Prisma v3 does not document translation, word timestamps or live diarization; do not promise those features. Gnani advertises Malayalam and English support. That is not evidence of accurate Malayalam-English code-switching, alphanumeric token recognition, or noisy Kerala PA performance. Test these explicitly. [Prisma v3](https://www.gnani.ai/resources/prisma-v3)

### 4.4 Event extractor

Implement `Extractor.extract(segment_window, venue_config) -> list[ProposedEvent]`. Retain a small, time-bounded window so a token phrase split across VAD segments can be interpreted. Maintain source text verbatim; normalize for comparison separately. Recognize configured trigger words, token syntax, number words, counter phrases and common correction/negation cues in the language variants actually tested. Keep token identifiers as **strings**, including prefixes and leading zeros. Do not turn `A007` into `A7` unless the venue explicitly defines equivalence.

Proposed internal event (illustrative application schema, not a Gnani response):

```json
{
  "type": "CALL",
  "token_raw": "A zero zero seven",
  "token_normalized": "A007",
  "counter": "2",
  "replaces_event_id": null,
  "evidence_text": "Token A zero zero seven to counter two",
  "source_segment_ids": ["s17"],
  "ambiguity_reason": null,
  "observed_at_ms": 12450
}
```

Types: `CALL`, `CORRECT`, `REPEAT`, `CANCEL`, `OTHER`, `UNCERTAIN`. Keep `token_normalized`, `counter` and replacement target nullable; do not invent missing slots. Validate field types, configured token grammar, allowed counter identifiers, evidence spans and correction references. If a number could be a counter, room, age or date rather than a ticket, abstain. Support multiple tokens as separate events; do not infer ranges. A number not recognized by the parser should appear as uncertain, not be coerced to the nearest active token.

**Evon optional path:** An adapter receives only the minimum recent transcript plus venue grammar, requests these same fields, and can return unknown. Validate the result exactly as for rules; a JSON-valid answer can still be factually wrong. Evidence must be a substring of source segments, but that only checks transcript alignment. No user token, guessed next token or personal information goes into its prompt. Compare false alerts, missed calls and latency with the parser alone before deciding whether it improves the product. If Evon is unavailable, keep rules as the only path, clearly document limitations, and never substitute another model.

### 4.5 State and alert reducer

Each session has a unique ID and monotonic event sequence. Process segments in order; deduplicate retransmissions and avoid stale async extraction overwriting a newer event. States: `STARTING`, `LISTENING`, `DEGRADED`, `DISCONNECTED`, `STOPPED`; represent coverage gaps explicitly. Queue event states: proposed, pending, confirmed-for-display, superseded, cancelled and uncertain. Alert state: unacknowledged, acknowledged, corrected. Never call the largest number heard the current queue position: queues skip, repeat and run concurrently.

Use a short, configurable correction grace period, e.g. 0.8–1.5 seconds as an initial **experiment**, measuring latency and corrections. There is no safe universal delay. If a later correction invalidates an alert, show a prominent correction and mark the old alert superseded; do not erase history silently. If an ambiguous correction cannot be resolved, show the raw text and uncertainty. Compare the normalized user's token only after the event has passed validation. Show counter as unknown when absent. Deduplicate repeat announcements without suppressing genuinely new calls after a queue reset.

### Example: hospital pharmacy

A patient waiting for a prescription says “Listen for pharmacy token P042 and vibrate,” or types it, confirms the extracted details, and starts listening. The pharmacy announces, “Pharmacy token P042, please collect your medicine at counter two.” Gnani Prisma transcribes the announcement. The parser identifies **P042** as the token and **counter two** as the destination. After an exact match, the app displays a prominent alert: “Pharmacy token P042 called. Go to counter 2.” It can also vibrate on a supported device.

If the announcement is unclear, the app displays the transcript and marks the token or counter as uncertain rather than guessing. If listening is interrupted, it warns the patient that an announcement may have been missed. The patient can still check the pharmacy display or ask staff.

## 5. Network and lifecycle

1. Start: require user gesture and consent; connect backend then provider; mark listening only after audio is flowing and stream is ready.
2. While listening: track heartbeat, audio age and last transcript; distinguish silence from an unhealthy connection. Report short dropped frames or backpressure gaps, if detectable.
3. On provider close, token expiry, network loss or microphone interruption: immediately mark degraded/disconnected, stop claims of live monitoring, and attempt bounded exponential-backoff reconnect while user remains on the page. Do not generate current-looking alerts from stale replayed audio. The UI states the gap duration.
4. Stop: release microphone tracks, close both sockets, cancel timers, and purge session buffers. Refresh, browser sleep and OS backgrounding can interrupt capture; prototype is explicitly foreground-only until tested.
5. Retry and ordering: use server-generated session/segment identifiers where the provider does not provide reliable cross-reconnect IDs; assign timestamps on receipt. Avoid automatic replay of potentially old audio unless its timing and duplicate policy are explicit.

## 6. Interfaces and storage

Browser to backend messages can be versioned JSON control frames plus binary PCM frames. Illustrative control events: `start` with sample rate and a non-sensitive venue configuration ID; `stop`; server emits `status`, `transcript`, `event`, `alert`, `error`. Define maximum frame bytes and reject malformed frames. Keep selected token on the client if matching can run there; if matching on the server, disclose its use and keep it in memory for the session. A local venue config can specify grammar, language, token length, prefix rules, counter names and normalization policy. No user account or database is needed for a single-session MVP.

For optional evaluation persistence, collect separate, explicit permission, avoid public bystander recordings without appropriate consent, pseudonymize identifiers, restrict access and set a deletion date. Do not claim compliance with a particular privacy law without legal review. Read and explain Gnani's current retention, use and processing terms before real deployments. Don't log raw audio, tokens, transcripts or API keys by default. A venue-provided official queue feed, if available, is a stronger source than microphone inference and should be assessed separately, subject to authorization.

## 7. Security and deployment

- Serve frontend and WebSocket backend over HTTPS/WSS. Key only in a server environment variable or secret manager, never in browser code, repository or screenshots. Supply `.env.example` with placeholder names only.
- Apply least privilege, session limits, request-size bounds, allowed origins, input validation, safe error messages, dependency updates and rate limits. A URL or origin alone is not user authentication.
- Start locally with one backend and static frontend. For a demo, deploy to a provider supporting persistent WebSockets and publicly trusted TLS, and confirm idle and connection limits. Estimate speech, LLM, compute, egress and storage costs from current actual account pricing; this plan assumes no free quota.
- Never record a real site or publish its audio without permission. Prefer staged recordings from consenting speakers for the first demo. Give the user a visible Stop button and delete buffered audio on stop.

## 8. Validation and research plan

**Phase A: API feasibility.** Verify account access, pricing/quotas, supported language codes, API authentication, sample formats, session limits and provider retention terms. Run a known-duration synthetic waveform through capture (not an AI-generated model) and test a few consented spoken clips. Confirm transcripts are final segments and measure basic latency.

**Phase B: deterministic baseline.** Build parser and reducer first. Unit test number normalization, grammar, evidence validation, multi-call lists, negation, correction spanning segments, repeats, reconnection, stale/duplicate results and queue reset. Use a versioned labeled dataset and separate development vs held-out data. Record annotation guidelines and disagreements.

**Phase C: real-world robustness.** Collect consented real recordings across voices, sessions, acoustics, device placements, PA distortion, noise, silence, nearby conversation, code-switching and formats. Hold out speakers and recording sessions; preferably hold out venues and announcer templates. Include long negative recordings, not just neatly cropped announcements. A single venue and a handful of staged clips establish a prototype, not deployment reliability.

**Phase D: optional Evon comparison.** If Gnani Evon is available and allowed, use the exact same held-out set for rules vs rules + Evon. Track improvements and regressions, cost, latency, abstention, hallucinations and failure categories. Freeze model and prompt versions. A richer LLM is not automatically more accurate; text-based correction can contradict the audio. [ClozeGER](https://aclanthology.org/2024.findings-acl.37/)

**Primary metrics:** correct token-and-counter exact match; target-alert recall; missed calls; false alerts per non-target announcement **and per listening hour**; correction success; duplicates; abstention rate; interruption coverage; end-of-announcement-to-alert p50/p95 latency. Report numerators/denominators, data slices and confidence intervals when sample size supports them. WER alone hides a single wrong digit. Test silence and non-announcements for hallucination. [ASR hallucination study](https://arxiv.org/abs/2402.08021)

Relevant evidence: a 2018 bank-announcement study reports 4.11% character error and 34.09% sentence error on a held-out bank, not end-to-end alert accuracy. [Paper](https://onlinelibrary.wiley.com/doi/10.1155/2018/8786308) The Indian RailVaani study reports significant number/platform extraction challenges on real railway announcements; its figures are not estimates for this product or Gnani. [RailVaani](https://aclanthology.org/2026.emnlp-demos.51/)

## 9. Implementation sequence and acceptance gates

1. **Provider spike:** authenticated Gnani Prisma v3 streaming from a controlled audio file; confirm PCM, session closure, resulting schema, costs. Gate: known audio duration and transcript events verified, no key in client.
2. **Capture and relay:** foreground browser to backend to Gnani; implement Stop, permission and disconnect status. Gate: repeatable capture and honest coverage gap on simulated network loss.
3. **Rules and reducer:** implement schema, number grammar, tests and timestamped state. Gate: correction, negation and duplicate-handling tests pass; uncertain cases abstain.
4. **Accessible interface:** token setup, transcript timeline, status, visual alert, optional haptics. Gate: keyboard/screen-reader checks and actual target-phone test; don't claim background reliability.
5. **Evaluation:** run clean, noise and long-negative held-out recordings; publish actual results and failure examples. Gate: report metrics with counts and no unsupported reliability claims.
6. **Optional Gnani Evon:** only once real access or self-hosting is verified; implement adapter and compare against frozen baseline. Gate: no non-Gnani model and documented measured benefit or honest decision not to use it.

## 10. Open decisions and known unknowns

- Gnani API access, actual pricing, credentials, rate limits, retention terms and whether the challenge permits self-hosted Evon: unverified.
- Gnani Evon hosted availability and API contract: closed beta in the source consulted; exact inference endpoint and access are unverified. The official model card identifies gnani/gnani-evon-v3.3-30B-A3B and describes self-hosting with substantial GPU hardware. Check its license, hardware requirements and current compatibility before committing: https://huggingface.co/gnani/gnani-evon-v3.3-30B-A3B . A self-hosted server may expose a compatible chat API, but that is not evidence of a Gnani-hosted endpoint.
- Malayalam number spellings, accent/code-switch accuracy, correction detection, token grammars and PA-source attribution: unvalidated. VAD is not a PA speaker detector.
- Actual GNANI provider request/response examples and reconnect semantics must be verified at implementation time, not guessed from this plan.
- Browser microphone access, haptics, operating-system background limits, latency and memory must be tested on the target device.
- No data collection, deployment, employer contact or submission is authorized merely by this plan.

## Sources

1. Gnani streaming STT documentation: https://docs.gnani.ai/api/STT/stt-websocket
2. Gnani REST STT documentation: https://docs.gnani.ai/api/STT/speech-to-text
3. Gnani STT limits: https://docs.gnani.ai/api/STT/limits
4. Gnani Prisma v3 announcement: https://www.gnani.ai/resources/prisma-v3
5. Gnani Evon hosted API waitlist: https://www.gnani.ai/evon-waitlist
6. Ruan et al., mobile audio announcement recognition, 2018: https://onlinelibrary.wiley.com/doi/10.1155/2018/8786308
7. RailVaani, Indian railway announcements: https://aclanthology.org/2026.emnlp-demos.51/
8. ClozeGER, LLM speech correction and grounding: https://aclanthology.org/2024.findings-acl.37/
9. Careless Whisper, ASR hallucination: https://arxiv.org/abs/2402.08021
10. MDN microphone capture: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
11. MDN AudioWorklet: https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet
12. MDN Vibration API: https://developer.mozilla.org/en-US/docs/Web/API/Vibration_API
