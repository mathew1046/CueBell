import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Extraction, Intent, ProposedEvent, Segment

ACCESS_CODE = "test-pairing-code-123456789"


def make_intent(**changes):
    return Intent.model_validate(
        {
            "intent": "monitor_announcement",
            "context": "hospital_pharmacy",
            "token": "P042",
            "alert_preferences": ["vibration"],
            "clarification": None,
            "target_evidence": "P042",
            **changes,
        }
    )


def make_event(**changes):
    return ProposedEvent.model_validate(
        {
            "type": "CALL",
            "token_raw": "P042",
            "token_normalized": "P042",
            "counter": "2",
            "replaces_event_id": None,
            "evidence_text": "P042 to counter 2",
            "source_segment_ids": ["s1"],
            "ambiguity_reason": None,
            **changes,
        }
    )


def make_segment(**changes):
    return Segment.model_validate(
        {
            "id": "s1",
            "text": "P042 to counter 2",
            "received_at": 100.0,
            **changes,
        }
    )


class FakeIntelligence:
    def __init__(self):
        self.intent_result = make_intent()
        self.extract_calls = []
        self.intent_calls = []

    async def intent(self, text):
        self.intent_calls.append(text)
        return self.intent_result

    async def extract(self, window, recent):
        self.extract_calls.append((window, recent))
        return Extraction(
            events=[
                make_event(
                    source_segment_ids=[window[-1].id],
                    evidence_text=window[-1].text,
                )
            ]
        )


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        demo_access_code=ACCESS_CODE,
        gnani_api_key="",
        text_provider="openai_fallback",
        openai_api_key="",
        openai_model="",
        evon_api_key="",
        evon_base_url="",
        allow_insecure_local=True,
        max_sessions=8,
        session_ttl_seconds=14400,
        correction_grace_seconds=0.2,
    )


@pytest.fixture
def intelligence():
    return FakeIntelligence()


@pytest.fixture
def client(settings, intelligence):
    with TestClient(create_app(settings, intelligence)) as client:
        yield client


def pair(client):
    response = client.post("/v1/sessions", json={"access_code": ACCESS_CODE})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


@pytest.fixture
def auth(client):
    return pair(client)


def activate(client, auth):
    proposal = client.post(
        "/v1/intent",
        headers=auth,
        json={
            "text": "Vibrate for P042",
            "consent_to_text_processing": True,
        },
    )
    assert proposal.status_code == 200
    result = client.post(
        "/v1/confirm",
        headers=auth,
        json={
            "proposal_id": proposal.json()["proposal_id"],
        },
    )
    assert result.status_code == 200
    return result.json()
