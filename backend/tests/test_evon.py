"""Exercise the real OpenAI SDK's Evon wire format without a hosted model."""

import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import Settings
from app.intelligence import GnaniEvon, SourcePlan, repair_source_evidence
from app.main import create_app
from app.models import EventExtraction, Extraction, Intent, MonitoringTask
from app.validation import intent_errors
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
    response["outputs"] = outputs

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
    requests, response, _ = evon_http
    evon_settings.evon_timeout_seconds = 8
    evon_settings.evon_setup_timeout_seconds = 125
    evon = GnaniEvon(evon_settings)
    text = "ട്രെയിൻ 14922 എത്തുമ്പോൾ അറിയിക്കുക"
    expected = task_intent()
    expected.task.request_evidence = text
    response["outputs"]["Intent"] = expected
    segment = make_segment(text="ട്രെയിൻ 14922 എത്തിയിരിക്കുന്നു")
    task = task_intent().task
    assert evon_settings.model_ready  # No OpenAI credentials required.
    assert evon.client.max_retries == 0
    try:
        assert await evon.intent(text) == expected
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


MALAYALAM_REQUEST = "ഫാർമസിയിൽ ടോക്കൺ അറുപത്തൊൻപത് വിളിക്കുമ്പോൾ എന്നെ അറിയിക്കൂ."


def ungrounded_token_intent():
    return Intent(
        intent="monitor_event",
        context=None,
        token=None,
        target_evidence=None,
        clarification=None,
        task=MonitoringTask(
            subject="pharmacy token 69",
            condition="is called at the pharmacy",
            summary="Notify me when pharmacy token 69 is called.",
            request_evidence="Call when token number 69 is called",
            identifiers=[{"value": "69", "evidence_text": "69"}],
        ),
        alert_preferences=["visual", "vibration", "sound"],
    )


def source_plan(value="69", ids=None, **changes):
    return SourcePlan.model_validate(
        {
            "intent": "monitor_event",
            "subject": "token",
            "condition": "is called",
            "summary": "Notify when the token is called.",
            "identifiers": [{"value": value, "source_word_ids": [2] if ids is None else ids}],
            "alert_preferences": ["sound"],
            "clarification": "The event has not happened yet.",
            **changes,
        }
    )


def test_relay_repairs_malayalam_source_quotes_without_changing_the_task(evon_settings, evon_http):
    requests, response, _ = evon_http
    original = ungrounded_token_intent()
    assert intent_errors(original, MALAYALAM_REQUEST)
    response["outputs"].update(Intent=original, SourcePlan=source_plan())
    with TestClient(create_app(evon_settings)) as client:
        result = client.post(
            "/v1/intent",
            headers=pair(client),
            json={"text": MALAYALAM_REQUEST, "consent_to_text_processing": True},
        )
        assert result.status_code == 200
        proposal = result.json()
        assert proposal["status"] == "confirm"
        repaired = Intent.model_validate(proposal["intent"])
        assert not intent_errors(repaired, MALAYALAM_REQUEST)
        assert repaired.task.request_evidence == MALAYALAM_REQUEST
        assert repaired.task.identifiers[0].evidence_text == "അറുപത്തൊൻപത്"
        expected = original.model_dump()
        expected["task"]["request_evidence"] = MALAYALAM_REQUEST
        expected["task"]["identifiers"][0]["evidence_text"] = "അറുപത്തൊൻപത്"
        assert repaired.model_dump() == expected
        assert original.task.identifiers[0].evidence_text == "69"
    assert len(requests) == 2
    second = json.loads(requests[1].content)
    assert second["response_format"]["json_schema"]["name"] == "SourcePlan"
    data = json.loads(second["messages"][1]["content"])
    assert set(data) == {"request", "source_words"}
    assert data["request"] == MALAYALAM_REQUEST
    assert data["source_words"][2] == {"id": 2, "text": "അറുപത്തൊൻപത്"}
    assert "69" not in second["messages"][1]["content"]  # No proposed identity to copy.
    assert requests[1].extensions["timeout"]["read"] == 130


@pytest.mark.parametrize(
    "source",
    [
        source_plan(value="68"),
        source_plan(ids=[-1]),
        source_plan(ids=[99]),
        source_plan(ids=[2, 2]),
        source_plan(ids=[3, 2]),
        source_plan(ids=[1, 3]),
        source_plan(intent="unclear"),
        source_plan(condition=" "),
        source_plan(identifiers=[]),
        source_plan(
            identifiers=[
                {"value": "69", "source_word_ids": [2]},
                {"value": "69", "source_word_ids": [1, 2]},
            ]
        ),
    ],
)
def test_evon_source_repair_rejects_disagreement_invalid_indices_and_ambiguity(source):
    original = ungrounded_token_intent()
    assert repair_source_evidence(original, MALAYALAM_REQUEST, source) is original
    assert intent_errors(original, MALAYALAM_REQUEST)


@pytest.mark.parametrize(("value", "quote"), [("69", "68"), ("B7", "B007"), ("P042", "P0420")])
def test_evon_source_repair_cannot_change_literal_identity_or_drop_leading_zeros(value, quote):
    original = ungrounded_token_intent()
    original.task.identifiers[0].value = value
    text = f"Call token {quote}."
    assert repair_source_evidence(original, text, source_plan(value=value)) is original


def test_relay_keeps_disagreed_evon_proposal_in_clarification(evon_settings, evon_http):
    requests, response, _ = evon_http
    original = ungrounded_token_intent()
    response["outputs"].update(Intent=original, SourcePlan=source_plan(value="68"))
    with TestClient(create_app(evon_settings)) as client:
        result = client.post(
            "/v1/intent",
            headers=pair(client),
            json={"text": MALAYALAM_REQUEST, "consent_to_text_processing": True},
        )
        assert result.status_code == 200
        assert result.json()["status"] == "clarify"
        assert "proposal_id" not in result.json()
        assert result.json()["intent"] == original.model_dump()
    assert len(requests) == 2


async def test_evon_repair_is_bounded_by_the_original_setup_deadline(evon_settings, monkeypatch):
    evon = GnaniEvon(evon_settings)
    evon.setup_timeout = 0.02
    cancelled = asyncio.Event()

    async def parse(system, data, schema):
        if schema is Intent:
            return ungrounded_token_intent()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    parse_mock = AsyncMock(side_effect=parse)
    monkeypatch.setattr(evon, "_parse", parse_mock)
    started = asyncio.get_running_loop().time()
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(evon.intent(MALAYALAM_REQUEST), timeout=0.5)
        assert asyncio.get_running_loop().time() - started < 0.3
        assert cancelled.is_set()
        assert parse_mock.await_count == 2
    finally:
        await evon.client.close()


async def test_evon_does_not_expand_long_requests_into_indexed_prompts(evon_settings, evon_http):
    requests, _, _ = evon_http
    evon = GnaniEvon(evon_settings)
    try:
        result = await evon.intent("word " * 129)
        assert intent_errors(result, "word " * 129)
        assert len(requests) == 1
    finally:
        await evon.client.close()
