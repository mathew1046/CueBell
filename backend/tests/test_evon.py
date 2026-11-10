"""Exercise the real OpenAI SDK's Evon wire format without a hosted model."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import Settings
from app.intelligence import GnaniEvon
from app.main import create_app
from app.models import EventExtraction, Extraction, Intent
from tests.conftest import ACCESS_CODE, make_segment, pair
from tests.test_event_monitor import REQUEST, task_intent


@pytest.fixture
def evon_settings(settings):
    return settings.model_copy(
        update={
            "text_provider": "gnani_evon",
            "evon_api_key": "dummy-evon-key",
            "evon_base_url": "https://evon.example/v1/",
            "evon_model": "gnani/gnani-evon-v3.3-30B-A3B",
        }
    )


@pytest.fixture
async def evon_http(monkeypatch):
    requests = []
    response = {"status": 200, "choices": None}
    outputs = {
        "Intent": task_intent(),
        "Extraction": Extraction(events=[]),
        "EventExtraction": EventExtraction(events=[]),
    }

    def handle(request):
        requests.append(request)
        payload = json.loads(request.content)
        output = outputs[payload["response_format"]["json_schema"]["name"]]
        choices = response["choices"]
        if choices is None:
            choices = [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": output.model_dump_json()},
                }
            ]
        return httpx.Response(
            response["status"],
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": payload["model"],
                "choices": choices,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        monkeypatch.setattr(
            "app.intelligence.AsyncOpenAI", lambda **kwargs: AsyncOpenAI(http_client=http, **kwargs)
        )
        yield requests, response, http


@pytest.mark.parametrize("missing", ["evon_api_key", "evon_base_url", "evon_model"])
def test_evon_requires_its_own_configuration_even_when_openai_is_configured(evon_settings, missing):
    evon_settings.openai_api_key = "dummy-openai-key"
    evon_settings.openai_model = "dummy-openai-model"
    setattr(evon_settings, missing, "")
    assert not evon_settings.model_ready
    with pytest.raises(RuntimeError, match="EVON_API_KEY, EVON_BASE_URL and EVON_MODEL"):
        GnaniEvon(evon_settings)
    with TestClient(create_app(evon_settings)) as client:
        assert client.get("/health").json()["intent_configured"] is False
        result = client.post(
            "/v1/intent",
            headers=pair(client),
            json={"text": REQUEST, "consent_to_text_processing": True},
        )
        assert result.status_code == 503
        assert "EVON_API_KEY" in result.json()["detail"]


def test_unknown_provider_cannot_silently_select_openai():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, text_provider="evon_typo")


async def test_evon_sdk_roundtrips_all_schemas_and_separates_setup_timeout(
    evon_settings, evon_http
):
    requests, _, _ = evon_http
    evon_settings.evon_timeout_seconds = 8
    evon_settings.evon_setup_timeout_seconds = 125
    evon = GnaniEvon(evon_settings)
    text = "ട്രെയിൻ 14922 എത്തുമ്പോൾ അറിയിക്കുക"
    segment = make_segment(text="ട്രെയിൻ 14922 എത്തിയിരിക്കുന്നു")
    task = task_intent().task
    assert evon_settings.model_ready  # No OpenAI credentials required.
    assert evon.client.max_retries == 0
    try:
        assert await evon.intent(text) == task_intent()
        assert await evon.extract([segment], []) == Extraction(events=[])
        assert await evon.observe([segment], [], task) == EventExtraction(events=[])
    finally:
        await evon.client.close()

    assert len(requests) == 3
    for request, schema, timeout in zip(
        requests, (Intent, Extraction, EventExtraction), (125, 8, 8), strict=True
    ):
        assert request.method == "POST"
        assert str(request.url) == "https://evon.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer dummy-evon-key"
        assert request.extensions["timeout"]["read"] == timeout
        payload = json.loads(request.content)
        assert payload["model"] == evon_settings.evon_model
        assert payload["store"] is False
        assert payload["temperature"] == 0
        assert payload["max_tokens"] <= 4096
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        assert payload["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": True,
            },
        }
        assert [item["role"] for item in payload["messages"]] == ["system", "user"]
        data = json.loads(payload["messages"][1]["content"])
        if schema is Intent:
            assert data == {"request": text}
        else:
            assert data["segments"][0]["text"] == segment.text
            assert ("confirmed_task" in data) is (schema is EventExtraction)


@pytest.mark.parametrize(
    ("finish_reason", "content", "refusal"),
    [
        ("length", '{"events":[]}', None),
        ("content_filter", '{"events":[]}', None),
        ("stop", '{"events":[]}', "refused"),
        ("stop", None, None),
        ("stop", "not-json", None),
        ("stop", '{"events":[],"unexpected":true}', None),
        ("stop", '{"events":"wrong-type"}', None),
    ],
)
async def test_evon_rejects_incomplete_refused_or_invalid_output(
    evon_settings, evon_http, finish_reason, content, refusal
):
    requests, response, _ = evon_http
    response["choices"] = [
        {
            "index": 0,
            "finish_reason": finish_reason,
            "message": {"role": "assistant", "content": content, "refusal": refusal},
        }
    ]
    evon = GnaniEvon(evon_settings)
    try:
        with pytest.raises((RuntimeError, ValidationError)):
            await evon.extract([make_segment()], [])
        assert len(requests) == 1
    finally:
        await evon.client.close()


async def test_evon_rejects_empty_choices(evon_settings, evon_http):
    _, response, _ = evon_http
    response["choices"] = []
    evon = GnaniEvon(evon_settings)
    try:
        with pytest.raises(RuntimeError, match="no structured extraction"):
            await evon.intent(REQUEST)
    finally:
        await evon.client.close()


def test_relay_selects_evon_discloses_it_and_closes_client(evon_settings, evon_http):
    requests, _, http = evon_http
    with TestClient(create_app(evon_settings)) as client:
        health = client.get("/health").json()
        assert health["intent_configured"] is True
        assert health["text_provider"] == "gnani_evon"
        assert health["evon"] == "configured"
        session = client.post("/v1/sessions", json={"access_code": ACCESS_CODE}).json()
        assert "Gnani Evon hosted on Modal" in session["disclosure"]
        assert "dummy-evon-key" not in json.dumps(health) + json.dumps(session)
        assert not requests  # Health/session admission must not wake the GPU.
        auth = {"Authorization": "Bearer " + session["token"]}
        result = client.post(
            "/v1/intent", headers=auth, json={"text": REQUEST, "consent_to_text_processing": True}
        )
        assert result.status_code == 200
        proposal = result.json()
        assert proposal["status"] == "confirm"
        confirmed = client.post(
            "/v1/confirm", headers=auth, json={"proposal_id": proposal["proposal_id"]}
        )
        assert confirmed.status_code == 200
        assert len(requests) == 1
    assert http.is_closed


def test_evon_failure_is_sanitized_without_retry_or_provider_switch(evon_settings, evon_http):
    requests, response, _ = evon_http
    response["status"] = 503
    evon_settings.openai_api_key = "dummy-openai-key"
    evon_settings.openai_model = "dummy-openai-model"
    with TestClient(create_app(evon_settings)) as client:
        result = client.post(
            "/v1/intent",
            headers=pair(client),
            json={"text": REQUEST, "consent_to_text_processing": True},
        )
        assert result.status_code == 502
        assert (
            result.json()["detail"]
            == "Intent service unavailable. Check backend model configuration."
        )
        assert len(requests) == 1
        assert requests[0].url.host == "evon.example"
