import json
from contextlib import asynccontextmanager

from websockets.asyncio.client import connect

from .config import Settings


@asynccontextmanager
async def prisma(settings: Settings):
    if not settings.gnani_api_key:
        raise RuntimeError("Speech recognition is not configured on the backend.")
    async with connect(
        "wss://api.vachana.ai/stt/v3/stream",
        additional_headers={
            "x-api-key-id": settings.gnani_api_key,
            "model": "prisma-v3.0",
            "language_code": settings.gnani_language_code,
            "x-sample-rate": "16000",
            "format": "verbatim",
            "x-idle-timeout-sec": "900",
        },
        open_timeout=12,
        close_timeout=5,
        max_size=65536,
        max_queue=8,
        write_limit=8192,
    ) as socket:
        yield socket


def parse_message(raw: str | bytes) -> dict:
    """Preserve provider metadata, including optional per-utterance language tags.

    Prisma v3 derives detected_language_code from final transcript script. Do not
    infer a missing tag from the configured language hint (empty/digits-only text
    may have none), or turn it into a claim of acoustic language-ID confidence.
    """
    message = json.loads(raw)
    if not isinstance(message, dict):
        raise ValueError("Invalid provider envelope.")
    return message
