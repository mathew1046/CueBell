import asyncio
import hmac
import json
import secrets
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field

from anyio import move_on_after
from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from websockets.exceptions import InvalidStatus

from .config import Settings
from .engine import Engine
from .gnani import parse_message, prisma
from .guard import RequestGuard
from .intelligence import GnaniEvon, OpenAIFallback
from .models import (
    ConfirmRequest,
    ControlRequest,
    Intent,
    IntentRequest,
    MonitoringTask,
    PairRequest,
    Segment,
)
from .validation import grounded_stop_request, intent_errors

APP_SESSION_IP_LIMIT = 3
APP_SESSION_IP_WINDOW_SECONDS = 600
APP_SESSION_IP_BUCKETS = 1024


@dataclass
class Session:
    expires: float
    engine: Engine
    proposal: tuple[str, Intent] | None = None
    busy: bool = False
    extracting: bool = False
    socket: WebSocket | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    requests: deque = field(default_factory=lambda: deque(maxlen=30))


def create_app(settings: Settings | None = None, intelligence=None) -> FastAPI:
    settings = settings or Settings()
    sessions: dict[str, Session] = {}
    pair_attempts: deque = deque(maxlen=100)
    app_admissions: dict[str, deque] = {}
    fallback: OpenAIFallback | GnaniEvon | None = None
    uses_evon = settings.text_provider == "gnani_evon"
    text_recipient = "Gnani Evon hosted on Modal" if uses_evon else "OpenAI text fallback"

    async def close_stream(session: Session, code: int, reason: str):
        if session.socket:
            with suppress(RuntimeError, WebSocketDisconnect, OSError):
                await session.socket.close(code, reason)

    @asynccontextmanager
    async def lifespan(app):
        async def reap():
            while True:
                await asyncio.sleep(30)
                for token, session in list(sessions.items()):
                    if session.expires <= time.time():
                        sessions.pop(token, None)
                        await close_stream(session, 4401, "Session expired; submit a new request.")

        task = asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            sessions.clear()
            if fallback is not None:
                await fallback.client.close()

    app = FastAPI(title="CueBell relay", lifespan=lifespan)
    app.add_middleware(RequestGuard, allow_insecure_local=settings.allow_insecure_local)

    def ai():
        nonlocal fallback
        if intelligence:
            return intelligence
        if not settings.model_ready:
            if uses_evon:
                raise HTTPException(
                    503, "Set EVON_API_KEY, EVON_BASE_URL and EVON_MODEL on the backend."
                )
            raise HTTPException(503, "Set OPENAI_API_KEY and an exact OPENAI_MODEL on the backend.")
        if fallback is None:
            fallback = GnaniEvon(settings) if uses_evon else OpenAIFallback(settings)
        return fallback

    def lookup(authorization: str | None) -> Session:
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        session = sessions.get(token)
        if not session or session.expires <= time.time():
            raise HTTPException(401, "Session expired. Submit your request again.")
        return session

    async def authenticate(authorization: str | None = Header(default=None)) -> Session:
        session = lookup(authorization)
        now = time.monotonic()
        if sum(t > now - 60 for t in session.requests) >= 30:
            raise HTTPException(429, "Too many requests. Wait a minute.")
        session.requests.append(now)
        return session

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "speech_configured": bool(settings.gnani_api_key),
            "intent_configured": settings.model_ready or intelligence is not None,
            "text_provider": settings.text_provider,
            "evon": "configured" if uses_evon and settings.model_ready else "not_configured",
        }

    @app.post("/v1/sessions")
    async def pair(body: PairRequest, request: Request):
        now = time.monotonic()
        if sum(t > now - 60 for t in pair_attempts) >= 20:
            raise HTTPException(429, "Pairing rate limit. Wait a minute.")
        pair_attempts.append(now)
        client_ip = None
        if body.access_code is None:
            if not settings.allow_app_sessions:
                raise HTTPException(401, "A pairing code is required.")
            # Only the ASGI server's effective client address is trusted. Configure
            # exact trusted proxies there; never parse forwarding headers here.
            if request.client is None:
                raise HTTPException(400, "Client address unavailable.")
            client_ip = request.client.host
            for address, admissions in list(app_admissions.items()):
                while admissions and admissions[0] <= now - APP_SESSION_IP_WINDOW_SECONDS:
                    admissions.popleft()
                if not admissions:
                    app_admissions.pop(address)
            admissions = app_admissions.get(client_ip)
            if admissions is not None and len(admissions) >= APP_SESSION_IP_LIMIT:
                raise HTTPException(429, "App session IP limit. Wait ten minutes.")
            if admissions is None and len(app_admissions) >= APP_SESSION_IP_BUCKETS:
                raise HTTPException(429, "App session admission capacity reached. Try later.")
        else:
            if not settings.demo_access_code or len(settings.demo_access_code) < 16:
                raise HTTPException(503, "Set a DEMO_ACCESS_CODE of at least 16 characters.")
            if not hmac.compare_digest(
                body.access_code.encode(), settings.demo_access_code.encode()
            ):
                raise HTTPException(401, "Incorrect pairing code.")
        for token, session in list(sessions.items()):
            if session.expires < time.time() and not session.busy:
                sessions.pop(token, None)
        if len(sessions) >= settings.max_sessions:
            raise HTTPException(429, "Backend session capacity reached.")
        token = secrets.token_urlsafe(32)
        expires = time.time() + settings.session_ttl_seconds
        sessions[token] = Session(expires, Engine(settings.correction_grace_seconds))
        if client_ip is not None:
            app_admissions.setdefault(client_ip, deque(maxlen=APP_SESSION_IP_LIMIT)).append(now)
        return {
            "token": token,
            "expires_at": expires,
            "venue": "nearby_speech",
            "monitoring_schema": "speech-event-v1",
            "disclosure": f"Audio: Gnani Prisma. Requests and transcripts: {text_recipient}. "
            "No recordings or transcript persistence by this relay; provider terms apply.",
        }

    @app.get("/v1/state")
    async def state(session: Session = Depends(authenticate)):
        return {
            "rule": session.engine.rule,
            "history": list(session.engine.history),
            "alerts": list(session.engine.alerts),
            "stream_connected": session.busy,
            "expires_at": session.expires,
        }

    @app.post("/v1/intent")
    async def intent(body: IntentRequest, session: Session = Depends(authenticate)):
        if not body.consent_to_text_processing:
            raise HTTPException(400, "Consent to text processing is required.")
        if session.extracting or session.busy:
            raise HTTPException(409, "Stop or pause the microphone before editing your request.")
        session.extracting = True
        session.proposal = None
        generation = session.engine.generation
        try:
            proposal = await ai().intent(body.text)
            if generation != session.engine.generation:
                raise HTTPException(409, "Monitor changed. Submit the request again.")
            errors = intent_errors(proposal, body.text)
            session.proposal = None
            if errors:
                return {
                    "status": "clarify",
                    "messages": list(dict.fromkeys(errors)),
                    "intent": proposal.model_dump(),
                }
            proposal_id = uuid.uuid4().hex
            session.proposal = (proposal_id, proposal)
            return {
                "status": "confirm",
                "proposal_id": proposal_id,
                "intent": proposal.model_dump(),
            }
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                502, "Intent service unavailable. Check backend model configuration."
            )
        finally:
            session.extracting = False

    @app.post("/v1/confirm")
    async def confirm(body: ConfirmRequest, session: Session = Depends(authenticate)):
        async with session.lock:
            if session.busy or session.extracting:
                raise HTTPException(409, "Pause listening before changing the monitor.")
            if not session.proposal or session.proposal[0] != body.proposal_id:
                raise HTTPException(409, "Proposal expired. Submit the request again.")
            result = session.engine.activate(session.proposal[1])
            session.proposal = None
            return result

    @app.post("/v1/control")
    async def control(body: ControlRequest, session: Session = Depends(authenticate)):
        async with session.lock:
            try:
                event = session.engine.control(body.action, body.alert_id)
            except ValueError as error:
                raise HTTPException(409, str(error))
            if body.action in {"pause", "stop"}:
                await close_stream(session, 1000, "Monitor paused or stopped.")
            if body.action == "stop":
                session.engine.observations.clear()
                session.engine.history.clear()
                session.engine.alerts.clear()
                session.engine.seen.clear()
                session.proposal = None
            return event

    @app.delete("/v1/session")
    async def delete_session(authorization: str | None = Header(default=None)):
        session = lookup(authorization)
        session.engine.gap()
        sessions.pop(authorization.removeprefix("Bearer "), None)
        await close_stream(session, 1000, "Session deleted.")
        return {"deleted": True}

    @app.websocket("/v1/stream")
    async def stream(socket: WebSocket):
        try:
            if socket.url.scheme != "wss" and not settings.allow_insecure_local:
                raise HTTPException(400, "TLS required.")
            # This is an authenticated native-only protocol, not a browser-origin API.
            if socket.headers.get("origin"):
                raise HTTPException(403, "Browser origins are not accepted.")
            session = lookup(socket.headers.get("authorization"))
            mode = socket.query_params.get("mode", "monitor")
            if mode not in {"request", "monitor"} or session.busy or session.extracting:
                raise HTTPException(409, "Stream already open or mode invalid.")
            consent = set(socket.headers.get("x-processing-consent", "").split(";"))
            required = {"audio-gnani", "text-evon-modal" if uses_evon else "text-openai"}
            if not required <= consent:
                raise HTTPException(400, "Processing disclosure must be accepted.")
            if mode == "monitor" and (
                not session.engine.rule or session.engine.rule["status"] != "ACTIVE"
            ):
                raise HTTPException(409, "Confirm or resume a monitor first.")
            if not settings.gnani_api_key:
                raise HTTPException(503, "Configure GNANI_API_KEY on the backend.")
            model = ai() if mode == "monitor" else None
        except HTTPException:
            await socket.close(4403, "Check credentials, consent, and backend configuration.")
            return
        session.busy, session.socket = True, socket
        try:
            await socket.accept()
        except BaseException:
            session.engine.gap()
            session.busy, session.socket = False, None
            raise
        window: deque[Segment] = deque(maxlen=6)
        queue: asyncio.Queue[Segment] = asyncio.Queue(maxsize=8)
        send_lock = asyncio.Lock()
        ready = asyncio.Event()
        started = time.monotonic()
        last_audio = started
        frames = 0
        interpreting = False
        seen_provider_ids: set[str] = set()
        connection_id = uuid.uuid4().hex
        request_segments: list[Segment] = []
        request_activity = started
        request_partial = False

        async def send(payload):
            async with send_lock:
                await socket.send_json(payload)

        async def status(state, message):
            await send({"type": "status", "state": state, "message": message})

        async def receive_audio(provider):
            nonlocal last_audio, frames
            while True:
                packet = await socket.receive()
                if packet["type"] == "websocket.disconnect":
                    return
                data = packet.get("bytes")
                if data is not None:
                    if not ready.is_set() or len(data) != 1024:
                        raise ValueError("Expected 1024-byte PCM frames after stream readiness.")
                    now = time.monotonic()
                    frames += 1
                    if frames > (now - started) * 40 + 50:
                        raise ValueError("Audio must be paced in real time.")
                    last_audio = now
                    await asyncio.wait_for(provider.send(data), timeout=1)
                elif packet.get("text"):
                    if len(packet["text"]) > 1024:
                        raise ValueError("Control frame too large.")
                    control_frame = json.loads(packet["text"])
                    if not isinstance(control_frame, dict):
                        raise ValueError("Invalid control frame.")
                    if control_frame.get("type") == "stop":
                        return
                    if control_frame.get("type") == "gap":
                        session.engine.gap()
                        window.clear()
                        await status("DEGRADED", "Audio frames were dropped. A call may be missed.")
                        raise ValueError("Restart after audio coverage gap.")
                    if control_frame.get("type") == "ping":
                        await send({"type": "pong"})

        async def receive_transcripts(provider):
            nonlocal request_activity, request_partial
            async for raw in provider:
                message = parse_message(raw)
                kind = message.get("type")
                if kind == "connected":
                    config = message.get("config", {})
                    if config.get("sample_rate") != 16000 or config.get("chunk_size") != 512:
                        raise ValueError("Provider sample-rate negotiation failed.")
                    ready.set()
                    await status("READY", "Speech stream ready; starting microphone.")
                elif kind == "error":
                    raise ValueError("Provider reported an error.")
                elif kind == "transcript":
                    text = message.get("text", "")
                    if not isinstance(text, str) or not text.strip():
                        continue
                    if mode == "request":
                        request_activity = time.monotonic()
                        request_partial = message.get("is_final") is not True
                    if message.get("is_final") is not True:
                        continue
                    if len(text) > 4000:
                        raise ValueError("Provider segment too long.")
                    provider_id = str(message.get("segment_id", uuid.uuid4().hex))
                    if provider_id in seen_provider_ids:
                        continue
                    seen_provider_ids.add(provider_id)
                    if len(seen_provider_ids) > 2048:
                        raise ValueError("Stream segment limit reached.")
                    segment = Segment(
                        id=f"{connection_id}:{provider_id}", text=text, received_at=time.time()
                    )
                    if mode == "monitor":
                        await send(
                            {"type": "transcript", "mode": mode, "segment": segment.model_dump()}
                        )
                        queue.put_nowait(segment)
                    else:
                        request_segments.append(segment)
                        if len(" ".join(s.text for s in request_segments)) > 1500:
                            raise ValueError("Spoken request too long. Please shorten it or type.")

        async def process_segments():
            nonlocal interpreting
            while True:
                segment = await queue.get()
                interpreting = True
                window.append(segment)
                while window and segment.received_at - window[0].received_at > 15:
                    window.popleft()
                generation = session.engine.generation
                task = (session.engine.rule or {}).get("task")
                recent = session.engine.recent_observations(time.time())
                if task:
                    extraction = await model.observe(
                        list(window), recent, MonitoringTask.model_validate(task)
                    )
                else:
                    extraction = await model.extract(list(window), recent)
                async with session.lock:
                    interpreting = False
                    if generation != session.engine.generation:
                        continue
                    if time.time() - segment.received_at > 15:
                        await status(
                            "DEGRADED", "Interpretation arrived too late; check the display."
                        )
                        session.engine.gap()
                        raise TimeoutError("Interpretation exceeded the coverage window.")
                    if extraction.stop_request is not None:
                        if not grounded_stop_request(extraction.stop_request, list(window)):
                            raise ValueError("Stop request has no current source evidence.")
                        # Pause preserves the token/history like Home's Stop Listening. Changing
                        # generation clears pending calls before the native microphone is stopped.
                        event = session.engine.control("pause")
                        event["reason"] = "voice"
                        event["message"] = "Stopped listening at your request. Microphone is off."
                        await send(event)
                        return
                    # Never silently truncate: a later event may cancel an earlier call.
                    # Reject the whole batch before mutating observations or pending alerts.
                    if len(extraction.events) > 16:
                        raise ValueError("Extraction event limit exceeded.")
                    for proposal in extraction.events:
                        if segment.id not in proposal.source_segment_ids:
                            continue
                        # Grace, deduplication and alert age track the announcement,
                        # not when a potentially slow text model finished interpreting it.
                        ingest = session.engine.ingest_match if task else session.engine.ingest
                        for event in ingest(proposal, list(window), segment.received_at):
                            await send(event)

        async def health_loop():
            listening = False
            while True:
                await asyncio.sleep(0.2)
                now = time.monotonic()
                if time.time() >= session.expires:
                    raise TimeoutError("Session expired.")
                if (
                    mode == "request"
                    and request_segments
                    and not request_partial
                    and (now - request_activity >= settings.request_pause_seconds)
                ):
                    # Provider sentence finals are not the end of a user's request.
                    # Keep capturing through short pauses and submit one combined request.
                    segment = Segment(
                        id=f"{connection_id}:request",
                        text=" ".join(s.text for s in request_segments),
                        received_at=time.time(),
                    )
                    await send(
                        {"type": "transcript", "mode": mode, "segment": segment.model_dump()}
                    )
                    return
                if mode == "request" and now - started > settings.request_timeout_seconds:
                    raise TimeoutError("No completed spoken request. Please try again or type.")
                if now - started > 14 * 60:
                    raise TimeoutError("Renewing speech connection before provider expiry.")
                if now - last_audio > (8 if not listening else 4):
                    raise TimeoutError("Audio stopped arriving. Calls may have been missed.")
                if frames > 0 and not listening:
                    listening = True
                    await status("LISTENING", "Microphone audio is reaching Gnani.")
                if listening and mode == "monitor":
                    async with session.lock:
                        # Don't release a pending call while a correction is being interpreted.
                        if interpreting or not queue.empty():
                            continue
                        for event in session.engine.flush(time.time()):
                            await send(event)
                if int(now * 5) % 25 == 0:
                    await send(
                        {"type": "heartbeat", "audio_age_ms": int((now - last_audio) * 1000)}
                    )

        tasks = []
        close_code = 1000
        try:
            await status("STARTING", "Connecting to Gnani Prisma…")
            async with prisma(settings) as provider:
                tasks = [
                    asyncio.create_task(receive_audio(provider)),
                    asyncio.create_task(receive_transcripts(provider)),
                    asyncio.create_task(health_loop()),
                ]
                if mode == "monitor":
                    tasks.append(asyncio.create_task(process_segments()))
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
        except (
            WebSocketDisconnect,
            RuntimeError,
            ValueError,
            TimeoutError,
            asyncio.QueueFull,
            OSError,
        ):
            try:
                await status(
                    "DISCONNECTED",
                    "Listening interrupted. Calls may have been missed. "
                    "Check network and backend credentials; reconnect from the app.",
                )
            except Exception:
                pass
        except Exception as error:
            provider_auth_failed = isinstance(
                error, InvalidStatus
            ) and error.response.status_code in {401, 403}
            if provider_auth_failed:
                close_code = 4403
            try:
                await status(
                    "DEGRADED",
                    (
                        "Gnani authentication rejected. Ask the backend operator to check "
                        "the provider credentials and access configuration before reconnecting."
                        if provider_auth_failed
                        else "Speech or interpretation service unavailable. "
                        "Check backend configuration and the official display."
                    ),
                )
            except Exception:
                pass
        finally:
            for task in tasks:
                task.cancel()
            try:
                # ASGI servers may cancel the handler immediately after a peer closes.
                # Finish bounded child-task cleanup even under AnyIO cancellation scopes.
                with move_on_after(2, shield=True):
                    await asyncio.gather(*tasks, return_exceptions=True)
                    with suppress(RuntimeError, WebSocketDisconnect, OSError):
                        await socket.close(code=close_code)
            finally:
                session.engine.gap()
                window.clear()
                session.busy, session.socket = False, None

    return app


app = create_app()
