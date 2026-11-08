# Demo CueBell

**Goal:** show a real request → automatic activation → announcement → alert flow on an Android phone, without presenting a prototype as a reliable deployed system.

This is a rehearsal runbook, not a claim that the full phone-and-speaker scenario has already passed. No public tunnel has been started on your behalf.

## 1. Prepare before presenting

- An ARM64 Android phone with microphone, internet and notification permission. Use the actual phone for haptics/background tests; an emulator is not a substitute.
- A standalone APK built with your deployed service origin. The v1.3.0 ARM64 preview uses https://cuebell.mathewjoseph.xyz . Expo Go cannot run the native microphone service.
- A laptop or hosted machine running the separate backend, with working Gnani and OpenAI access and sufficient account quota. Usage may incur provider costs.
- A publicly trusted HTTPS backend URL that supports WebSocket connections.
- A second, consenting speaker, or your own consented human recording played from a second device. Start in a quiet room, within useful microphone range. Do not use unconsented hospital audio.
- A screen-recording/mirroring arrangement if presenting to an audience. Hide credentials and private notifications; obtain consent before recording the demonstration.

Download the development-signed ARM64 preview from GitHub Releases:
https://github.com/mathew1046/CueBell/releases/tag/v1.3.0-preview

Download `CueBell-1.3.0-arm64.apk` and open a terminal in its download directory.
Install over USB with Android debugging enabled. Specify your physical phone's serial from `adb devices`; do not accidentally target an emulator. This preview is not production/store-signed:

```sh
adb -s YOUR_PHONE_SERIAL install -r CueBell-1.3.0-arm64.apk
```

Otherwise transfer it to the phone and allow installation from that source. Only install APKs you trust. Build instructions:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md

## 2. Start the separate backend

From the repository root, install if needed:

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
```

For a fresh checkout only, copy `.env.example` to `.env`. **Do not overwrite an existing configured `.env`.** Set these values in that ignored file, not in the app or on a presentation slide:

```dotenv
GNANI_API_KEY=your-speech-api-key
GNANI_LANGUAGE_CODE=indic-auto
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-6-luna
ALLOW_APP_SESSIONS=true
ALLOW_INSECURE_LOCAL=false
```

`gpt-6-luna` was verified in the implementation account; your account must also have access to the exact configured model and structured outputs. `ALLOW_APP_SESSIONS=true` explicitly opts into anonymous demo admission. Anyone reaching the endpoint can obtain a rate/capacity-limited bearer and incur provider usage: keep the demo short, apply gateway/provider budget limits, and turn this mode off afterward. It is not production authentication. Do not embed the optional legacy operator `DEMO_ACCESS_CODE` or any provider key in the APK.

Run **one worker**, from the backend directory:

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 --ws-max-size 8192 --timeout-keep-alive 5 --no-access-log
```

Keep that terminal running. Restarting the backend clears in-memory sessions; submit the request again if the app reports expiration.

### Fast temporary HTTPS option: Cloudflare Quick Tunnel

Install `cloudflared` using the official instructions:
https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/

In a **second terminal on the same laptop**, run:

```sh
cloudflared tunnel --url http://127.0.0.1:8000
```

Copy the generated HTTPS origin, for example https://your-random-name.trycloudflare.com . Use the actual printed hostname, not this example. **Set it in the mobile build environment as `EXPO_PUBLIC_API_URL`, then build/install the APK. Nothing is entered on the phone.** A new random tunnel hostname requires a new build; a stable HTTPS hostname is better. This temporarily exposes anonymous demo admission to the internet; protect provider budgets and stop the tunnel when finished. Do not enable request/header/body capture in extra proxy or monitoring tools.

This setup trusts forwarding headers only from the local tunnel connector at `127.0.0.1`. Keep Uvicorn bound to loopback. **Do not use `--forwarded-allow-ips '*'`, disable TLS checks or expose port 8000 publicly.** A different proxy/container topology needs its own exact trusted proxy address.

Do not add browser-login/email challenges to this tunnel: the native HTTP/WebSocket client cannot complete them. Quick Tunnels are temporary development tools with no uptime guarantee; a stable TLS host is preferable for a judged presentation. Provider audio goes from the backend to Gnani; the public relay introduces an additional network intermediary whose terms also need review.

Official tunnel and WebSocket references:
https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
https://developers.cloudflare.com/network/websockets/

Check the actual public origin in a browser at `/health`, or:

```sh
curl --fail https://your-random-name.trycloudflare.com/health
```

Expect `status: "ok"`, `speech_configured: true` and `intent_configured: true`. These flags only check that configuration is present. They **do not** prove provider authorization, quota or successful recognition. A direct local HTTP request is deliberately rejected with insecure-local mode disabled; test through the HTTPS origin.

For a permanent deployment, follow:
https://github.com/mathew1046/CueBell/blob/main/backend/README.md

## 3. Build once, then rehearse the user workflow

Before handing over the phone, the operator builds using the real service origin and the instructions at:
https://github.com/mathew1046/CueBell/blob/main/mobile/README.md

1. Open CueBell. The request workflow appears immediately, with **no server fields, pairing or technical settings**.
2. Tap the pencil to enter a request and check **Allow audio & text processing**. Audio goes to Gnani; requests and announcement text go to OpenAI. **About & privacy** contains the full explanation.
3. For the first run, type **“Listen for pharmacy token 442 and vibrate.”** Tap **Start Listening**. Session setup and activation happen automatically; there is no second confirmation tap.
4. Grant microphone and notification permissions, then wait until the app reports **Listening**. An active rule alone is not listening coverage.
5. Check the active task on Home. If its subject, condition or preferences are wrong, stop listening and use the pencil to edit the request. No venue token format is assumed.
6. Check the ongoing microphone notification. Keep the app visible for the first rehearsal. Ensure microphone privacy is off, the notification channel is enabled, vibration is enabled, and Do Not Disturb is not suppressing delivery.

Speak one complete announcement at a time, then pause for the final transcript and interpretation. This is completed-utterance recognition, not instantaneous partial-word captioning. Alert latency also includes model processing and the configurable correction grace period (default 1.2 seconds); there is no measured end-to-end latency guarantee.

## 4. A three-minute presentation script

### 0:00–0:30 — The problem

> “If you cannot hear a pharmacy loudspeaker, knowing when your token is called can mean watching a display continuously or relying on a companion. CueBell aims to make that call visible and personal. It is a supplemental aid, not the official queue.”

### 0:30–1:15 — User-controlled intent

Show the typed request and the automatically activated task. Say:

> “The user describes what to listen for. Once processing and microphone access are allowed, a clear request starts monitoring automatically. The active task stays visible, and the user can stop it. Announcements cannot change that task.”

Typing first isolates the monitoring demonstration from speech-setup errors. After rehearsal, optionally use spoken setup instead: short pauses are allowed. Setup combines finalized speech and waits for 3.5 seconds of transcript quiet before interpreting it, then automatically activates a valid task. Do not speak setup instructions over the announcement-listening phase. Expand **Live captions** to inspect transcripts; the history is collapsed to keep the main screen quiet.

### 1:15–2:15 — A non-match, then a match

Have the consenting speaker say these separately:

| Announcement | Expected check |
| --- | --- |
| “Pharmacy token four four one, please go to counter one.” | Transcript/event may appear, but **no target alert** for `442`. |
| “Pharmacy token four four two, please go to counter two.” | A prominent alert for token `442`, counter 2 and the matching source speech, plus vibration if the phone permits it. |

Show the actual transcript and alert; do not describe a vibration as proven if nobody can verify it. Use **I’ve seen this** to acknowledge. If the transcript is wrong or no alert arrives, show that fact and check the official display rather than claiming success.

### 2:15–3:00 — Corrections and honest limits

If rehearsed successfully, say this **within 30 seconds of the matching observation**:

> “Correction: pharmacy token four four two should go to counter three, not counter two.”

Check that the destination becomes counter 3. If an old alert was already issued, inspect its visible correction and the replacement call. If the correction arrives during the grace period, the original alert may be withheld instead. Ambiguous corrections should remain uncertain, not silently become a guessed destination.

Close with:

> “The intended impact is more independent access to audio-only queue information. We have tested the software and provider connections, but we have not yet measured real pharmacy accuracy or shown that missed turns are reduced.”

## 5. Extra checks — rehearse, do not improvise

- **Malayalam:** try a clear, complete Malayalam request and announcement with a consenting speaker. For example, request **“ഫാർമസി ടോക്കൺ നാല് നാല് രണ്ട് വിളിക്കുമ്പോൾ വൈബ്രേറ്റ് ചെയ്യണം.”** and announcement **“ഫാർമസി ടോക്കൺ നാല് നാല് രണ്ട്, കൗണ്ടർ രണ്ടിലേക്ക് വരുക.”** Verify the actual transcript and active task. These are rehearsal phrases, not validated PA-recognition examples; automatic language detection is not proof of reliable code-switching.
- **Leading zeroes:** a separate monitor for “Listen for pharmacy token P042 and vibrate.” Review `P042`, then say “Pharmacy token P zero four two to counter two.” Never substitute `P42` or drop the prefix to make a match.
- **Repeat:** repeat the same call. Check that the 45-second repeat suppression does not create another token-call alert. This is a heuristic, not a queue-reset detector.
- **Interruption:** while listening, turn the phone's network off. Check degraded/disconnected status and the coverage warning. Restore networking and wait for verified listening before the next announcement. Reconnect is bounded; you may need **Start listening**. The missing audio is not replayed.
- **Background / lock screen:** start while visible, then background or lock the phone and repeat a known call. Check the ongoing service and actual delivery on this phone. Lock-screen content is private, so unlock to inspect the token. Only claim this device behavior if you observe it working; it has not been established by emulator tests.
- **Stop:** tap **Stop**, or the notification's **Stop microphone**. Confirm capture stops. The notification action pauses listening; the in-app **Stop** also clears the active monitor and session events.

## 6. If the live demo fails

| Symptom | Check |
| --- | --- |
| Service temporarily unavailable | Operator: confirm the build-time origin is current, `/health` works, `ALLOW_APP_SESSIONS=true` is enabled for the controlled demo, and both backend/tunnel processes are running. Rebuild if the hostname changed. There is no phone URL setting. |
| HTTP 403 / secure-transport error | Check the trusted local proxy and forwarded HTTPS scheme. Do not bypass by trusting every proxy or allowing insecure public traffic. |
| Session expired | Submit the request again. The app obtains a fresh bearer and activates the new valid request; an old monitor is never silently replayed. |
| Service busy | Wait before retrying. Anonymous demo admission permits three sessions per IP per ten minutes, plus global and concurrent limits; do not keep reinstalling or clearing storage. |
| Provider authorization / quota error | Check server-side keys, speech-platform access, model entitlement and quota. `/health` configuration flags do not authenticate providers. |
| Intent needs clarification | Clearly identify what to listen for and the event that should alert. Edit and resubmit rather than guessing; a token is not required for general tasks. |
| No transcript | Verify actual listening, microphone permission/privacy, connectivity and audio range. Speak clearly and pause at the end. |
| Transcript appears but no alert | Compare every digit/prefix, check uncertainty and counter evidence, and allow interpretation to finish. Inspect the real result; do not repeatedly change the target to match a wrong transcript. |
| Visual alert but no vibration/sound | Check Android notification permission, the selected alert channel, hardware and Do Not Disturb. Visual feedback is the fallback. |

**Fallback plan:** present the actual typed-request flow if it works, then run the automated reducer tests from the backend directory:

```sh
.venv/bin/pytest -q tests/test_engine.py
```

Explain explicitly that these are isolated automated tests, **not** live microphone recognition. If you have a recording from your own successful, consented rehearsal, you can show it as a **prerecorded demonstration**. Do not imply a fake transcript, test fixture or prerecorded video is a successful live run. There is no announcement-text simulator in the current app.

## 7. End the session

Tap **Stop**. Stop `cloudflared` and the backend with Ctrl+C, and disable anonymous demo admission if no longer needed. Check the microphone notification has gone. Avoid publishing audio, participant information or a video containing provider credentials.

## What you can honestly claim today

- A built Android prototype, with a native microphone foreground service and separate backend.
- Automated test and release-packaging results are recorded in https://github.com/mathew1046/CueBell/blob/main/docs/VERIFICATION.md . Historical emulator and text-model checks are separate from this release's device behavior.
- Gnani streaming authorization/negotiation and a bounded synthetic PCM transmission check succeeded.
- Any real speech, vibration or background behavior you actually reproduce in the rehearsal, clearly scoped to that device and staged scenario.

You cannot yet claim real-venue reliability, a measured reduction in missed turns, universal background delivery, accurate Malayalam/English code-switching, offline recognition or production readiness.
