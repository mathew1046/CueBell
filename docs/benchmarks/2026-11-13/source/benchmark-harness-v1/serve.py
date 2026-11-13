"""Run a benchmark-only local relay with real-provider timing sidecars.

This wrapper can import an archived baseline or the working application. It
leaves the production wire protocol unchanged and never records credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path


class Trace:
    def __init__(self, path: Path, secrets: list[str]):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a", encoding="utf-8")
        self.secrets = [value for value in secrets if value]

    def emit(self, event: str, **values):
        line = json.dumps(
            {
                "event": event,
                "monotonic_s": time.monotonic(),
                "wall_time": datetime.now(UTC).isoformat(),
                **values,
            },
            ensure_ascii=False,
            default=str,
        )
        for secret in self.secrets:
            line = line.replace(secret, "[REDACTED]")
        self.file.write(line + "\n")
        self.file.flush()


class MeasuredIntelligence:
    """Lazy real client, preserving the baseline's first-call initialization."""

    def __init__(self, factory, settings, trace: Trace):
        self.factory, self.settings, self.trace = factory, settings, trace
        self.delegate = None
        self.context = ContextVar("benchmark_interpretation", default={})

    def instance(self):
        if self.delegate is None:
            self.delegate = self.factory(self.settings)
            parse = self.delegate.client.responses.parse

            async def measured_parse(*args, **kwargs):
                call_id = uuid.uuid4().hex
                started = time.monotonic()
                encoded = json.dumps(kwargs.get("input"), ensure_ascii=False, default=str)
                self.trace.emit(
                    "openai_request",
                    call_id=call_id,
                    interpretation_id=self.context.get().get("call_id"),
                    stage=self.context.get().get("stage"),
                    model=kwargs.get("model"),
                    reasoning=kwargs.get("reasoning"),
                    service_tier=kwargs.get("service_tier"),
                    max_output_tokens=kwargs.get("max_output_tokens"),
                    text_options=kwargs.get("text"),
                    prompt_cache_options=kwargs.get("prompt_cache_options")
                    or (kwargs.get("extra_body") or {}).get("prompt_cache_options"),
                    input_chars=len(encoded),
                    input_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
                )
                try:
                    response = await parse(*args, **kwargs)
                except Exception as exc:
                    self.trace.emit(
                        "openai_error",
                        call_id=call_id,
                        interpretation_id=self.context.get().get("call_id"),
                        stage=self.context.get().get("stage"),
                        elapsed_ms=(time.monotonic() - started) * 1000,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    raise
                usage = getattr(response, "usage", None)
                self.trace.emit(
                    "openai_response",
                    call_id=call_id,
                    interpretation_id=self.context.get().get("call_id"),
                    stage=self.context.get().get("stage"),
                    elapsed_ms=(time.monotonic() - started) * 1000,
                    model=response.model,
                    status=response.status,
                    service_tier=getattr(response, "service_tier", None),
                    usage=usage.model_dump() if usage is not None else None,
                    request_id=getattr(response, "_request_id", None),
                )
                return response

            self.delegate.client.responses.parse = measured_parse
        return self.delegate

    async def invoke(self, name, *args):
        call_id = uuid.uuid4().hex
        started = time.monotonic()
        sources = [] if name == "intent" else [segment.id for segment in args[0]]
        self.trace.emit("interpretation_start", call_id=call_id, stage=name, source_ids=sources)
        context_token = self.context.set({"call_id": call_id, "stage": name})
        try:
            try:
                result = await getattr(self.instance(), name)(*args)
            except Exception as exc:
                self.trace.emit(
                    "interpretation_error",
                    call_id=call_id,
                    stage=name,
                    elapsed_ms=(time.monotonic() - started) * 1000,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                raise
            self.trace.emit(
                "interpretation_end",
                call_id=call_id,
                stage=name,
                source_ids=sources,
                elapsed_ms=(time.monotonic() - started) * 1000,
                result=result.model_dump(),
            )
            return result
        finally:
            self.context.reset(context_token)

    async def intent(self, text):
        return await self.invoke("intent", text)

    async def observe(self, window, recent, task):
        return await self.invoke("observe", window, recent, task)

    async def extract(self, window, recent):
        return await self.invoke("extract", window, recent)

    async def close(self):
        if self.delegate is not None:
            await self.delegate.client.close()


class MeasuredPrisma:
    def __init__(self, provider, trace, stream_id):
        self.provider, self.trace, self.stream_id = provider, trace, stream_id
        self.frames = 0
        self.send_total_ms = 0.0
        self.send_max_ms = 0.0

    def __getattr__(self, name):
        return getattr(self.provider, name)

    async def send(self, data):
        started = time.monotonic()
        await self.provider.send(data)
        elapsed = (time.monotonic() - started) * 1000
        if isinstance(data, bytes):
            self.frames += 1
            self.send_total_ms += elapsed
            self.send_max_ms = max(self.send_max_ms, elapsed)
            if self.frames == 1:
                self.trace.emit("gnani_first_audio", stream_id=self.stream_id)
        else:
            self.trace.emit("gnani_control", stream_id=self.stream_id, payload=data)

    async def __aiter__(self):
        async for raw in self.provider:
            try:
                message = json.loads(raw)
            except (TypeError, ValueError):
                message = {"type": "unparseable"}
            self.trace.emit("gnani_message", stream_id=self.stream_id, payload=message)
            yield raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Backend import directory")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--access-code-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8089)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source))

    import uvicorn

    from app import main as relay
    from app.config import Settings
    from app.intelligence import OpenAIFallback

    overrides = json.loads(args.config.read_text())
    unknown = set(overrides) - set(Settings.model_fields)
    if unknown:
        raise SystemExit(f"Unknown settings for this source: {sorted(unknown)}")
    overrides.update(
        allow_insecure_local=True,
        demo_access_code=args.access_code_file.read_text().strip(),
        openai_model="gpt-6-luna",
    )
    settings = Settings(_env_file=args.env_file, **overrides)
    if not settings.model_ready or not settings.gnani_api_key:
        raise SystemExit("Real Gnani and OpenAI credentials are required")
    trace = Trace(
        args.trace,
        [settings.gnani_api_key, settings.openai_api_key, settings.demo_access_code],
    )
    trace.emit(
        "server_start",
        source=str(source),
        pid=os.getpid(),
        port=args.port,
        wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        settings={
            key: value
            for key, value in settings.model_dump().items()
            if key not in {"gnani_api_key", "openai_api_key", "demo_access_code"}
        },
        source_hashes={
            str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((source / "app").glob("*.py"))
        },
        clocks={key: vars(time.get_clock_info(key)) for key in ("monotonic", "perf_counter")},
    )
    original_prisma = relay.prisma

    @asynccontextmanager
    async def measured_prisma(config):
        stream_id = uuid.uuid4().hex
        started = time.monotonic()
        trace.emit("gnani_connect_start", stream_id=stream_id)
        proxy = None
        try:
            async with original_prisma(config) as provider:
                proxy = MeasuredPrisma(provider, trace, stream_id)
                trace.emit(
                    "gnani_connected",
                    stream_id=stream_id,
                    elapsed_ms=(time.monotonic() - started) * 1000,
                )
                yield proxy
        finally:
            trace.emit(
                "gnani_stream_end",
                stream_id=stream_id,
                elapsed_ms=(time.monotonic() - started) * 1000,
                frames=proxy.frames if proxy else 0,
                audio_seconds=proxy.frames * 0.032 if proxy else 0,
                send_total_ms=proxy.send_total_ms if proxy else 0,
                send_max_ms=proxy.send_max_ms if proxy else 0,
            )

    relay.prisma = measured_prisma
    intelligence = MeasuredIntelligence(OpenAIFallback, settings, trace)
    app = relay.create_app(settings, intelligence=intelligence)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with original_lifespan(application):
                yield
        finally:
            await intelligence.close()
            trace.emit("server_stop")
            trace.file.close()

    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
