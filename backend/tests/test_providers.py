import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import gnani
from app.intelligence import OpenAIFallback
from app.models import Extraction
from tests.conftest import make_segment


@pytest.mark.parametrize("raw", ["[]", '"hello"', "null", "12", "not-json", b"\xff"])
def test_provider_parser_rejects_non_envelopes(raw):
    with pytest.raises((ValueError, UnicodeDecodeError)):
        gnani.parse_message(raw)


def test_provider_parser_preserves_final_and_malayalam():
    message = {"type": "transcript", "text": "പി പൂജ്യം നാല് രണ്ട്", "segment_id": 7, "is_final": True}
    assert gnani.parse_message(json.dumps(message).encode()) == message


async def test_gnani_connect_contract_is_mocked(settings, monkeypatch):
    calls = []
    sentinel = object()

    @asynccontextmanager
    async def connect(url, **kwargs):
        calls.append((url, kwargs))
        yield sentinel

    monkeypatch.setattr(gnani, "connect", connect)
    with pytest.raises(RuntimeError, match="not configured"):
        async with gnani.prisma(settings):
            pass
    settings.gnani_api_key = "dummy-test-key"
    async with gnani.prisma(settings) as provider:
        assert provider is sentinel
    assert calls[0][0] == "wss://api.vachana.ai/stt/v3/stream"
    assert calls[0][1]["additional_headers"] == {
        "x-api-key-id": "dummy-test-key",
        "model": "prisma-v3.0",
        "language_code": "ml-IN,en-IN",
        "x-sample-rate": "16000",
        "format": "verbatim",
        "x-idle-timeout-sec": "900",
    }
    assert calls[0][1]["max_size"] == 65536


def test_fallback_requires_exact_model_and_credentials(settings):
    with pytest.raises(RuntimeError, match="exact OPENAI_MODEL"):
        OpenAIFallback(settings)
    settings.openai_api_key = "dummy-test-key"
    assert not settings.model_ready


async def test_text_fallback_payload_and_target_independence(settings, monkeypatch):
    parse = AsyncMock(
        return_value=SimpleNamespace(
            status="completed",
            output_parsed=Extraction(events=[]),
        )
    )
    init = {}

    def fake_openai(**kwargs):
        init.update(kwargs)
        return SimpleNamespace(responses=SimpleNamespace(parse=parse))

    monkeypatch.setattr("app.intelligence.AsyncOpenAI", fake_openai)
    settings.openai_api_key, settings.openai_model = "dummy-test-key", "exact-test-model"
    fallback = OpenAIFallback(settings)
    recent = [
        {
            "id": "o1",
            "type": "CALL",
            "token_normalized": "A007",
            "counter": "3",
            "evidence_text": "A007 to counter 3",
            "source_segment_ids": ["s0"],
            "rule": {"token": "P042"},
            "alert_preferences": ["sound"],
            "state": "matches_target",
            "pending": True,
        }
    ]
    await fallback.extract([make_segment(text="A007 to counter 3")], recent)
    payload = parse.call_args.kwargs
    assert payload["model"] == "exact-test-model"
    assert payload["store"] is False
    assert init["max_retries"] == 0
    assert init["timeout"] == 12
    data = json.loads(payload["input"][1]["content"])
    assert set(data) == {"segments", "recent_observations"}
    assert set(data["recent_observations"][0]) == {
        "id",
        "type",
        "token_normalized",
        "counter",
        "evidence_text",
        "source_segment_ids",
    }
    assert "P042" not in payload["input"][1]["content"]
    assert "matches_target" not in payload["input"][1]["content"]
    assert "rule" in recent[0]  # No mutation of caller-owned state.


@pytest.mark.parametrize(
    ("status", "parsed"), [("incomplete", Extraction(events=[])), ("completed", None)]
)
async def test_incomplete_or_refused_response_is_not_accepted(
    settings, monkeypatch, status, parsed
):
    parse = AsyncMock(return_value=SimpleNamespace(status=status, output_parsed=parsed))
    monkeypatch.setattr(
        "app.intelligence.AsyncOpenAI",
        lambda **kwargs: SimpleNamespace(
            responses=SimpleNamespace(parse=parse),
        ),
    )
    settings.openai_api_key, settings.openai_model = "dummy-test-key", "exact-test-model"
    with pytest.raises(RuntimeError, match="did not complete"):
        await OpenAIFallback(settings).intent("Vibrate for P042")
