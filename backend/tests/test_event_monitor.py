"""General monitoring contracts: no queue slots, current evidence, safe alert lifecycle."""

from unittest.mock import AsyncMock

import pytest

from app.engine import Engine
from app.intelligence import OpenAIFallback
from app.models import EventExtraction, EventObservation, MonitoringTask
from app.validation import intent_errors, validate_match
from tests.conftest import make_intent, make_segment

REQUEST = "Alert me when train 14922 arrives."
ANNOUNCEMENT = "Train 14922 has arrived at platform 3."


def task_intent(**changes):
    task = MonitoringTask(
        subject="train 14922",
        condition="has arrived at this station",
        summary="Notify me when train 14922 has arrived.",
        request_evidence=REQUEST,
        identifiers=[{"value": "14922", "evidence_text": "14922"}],
    )
    return make_intent(
        intent="monitor_event", token=None, target_evidence=None, task=task, **changes
    )


def observation(**changes):
    return EventObservation.model_validate(
        {
            "type": "MATCH",
            "condition_met": True,
            "summary": ANNOUNCEMENT,
            "subject_evidence": "Train 14922",
            "condition_evidence": "has arrived",
            "identifiers": [{"value": "14922", "evidence_text": "14922"}],
            "location": "platform 3",
            "replaces_event_id": None,
            "evidence_text": ANNOUNCEMENT,
            "source_segment_ids": ["s1"],
            "ambiguity_reason": None,
            **changes,
        }
    )


def monitor():
    engine = Engine(grace=0.2)
    engine.activate(task_intent())
    return engine


def ingest(engine, proposed=None, now=100, text=ANNOUNCEMENT, sid="s1"):
    return engine.ingest_match(proposed or observation(), [make_segment(id=sid, text=text)], now)


def test_train_setup_does_not_require_a_token_and_retains_full_condition():
    intent = task_intent()
    assert intent_errors(intent, REQUEST) == []
    rule = monitor().rule
    assert rule["token"] is None
    assert rule["task"]["condition"] == "has arrived at this station"
    assert rule["task"]["identifiers"][0]["value"] == "14922"


@pytest.mark.parametrize(
    "subject,condition,utterance",
    [
        ("Sara", "her name is called", "Tell me when Sara is called."),
        (
            "evacuation instruction",
            "people are told to evacuate",
            "Alert me if people are told to evacuate.",
        ),
        ("boarding", "boarding starts", "Alert me when boarding starts."),
    ],
)
def test_non_numeric_and_identifier_free_tasks(subject, condition, utterance):
    intent = task_intent().model_copy(
        update={
            "task": MonitoringTask(
                subject=subject,
                condition=condition,
                summary=utterance,
                request_evidence=utterance,
                identifiers=[],
            )
        }
    )
    assert intent_errors(intent, utterance) == []


def test_missing_condition_or_invented_request_requires_relevant_clarification():
    intent = task_intent().model_copy(update={"task": None})
    assert "when should I alert" in intent_errors(intent, REQUEST)[0]
    assert "token" not in " ".join(intent_errors(intent, REQUEST)).lower()
    assert intent_errors(task_intent(), "Watch another train.")


def test_arrival_alert_contains_actual_event_location_and_evidence_not_a_fake_token():
    engine = monitor()
    ingest(engine)
    assert not engine.flush(100.1)
    alert = engine.flush(100.3)[0]["alert"]
    assert alert["token"] is None and alert["counter"] is None
    assert alert["summary"] == ANNOUNCEMENT
    assert alert["location"] == "platform 3"
    assert alert["evidence_text"] == ANNOUNCEMENT
    assert alert["task_summary"] == engine.rule["task"]["summary"]


@pytest.mark.parametrize(
    "changes,text",
    [
        ({"condition_met": False}, ANNOUNCEMENT),
        (
            {
                "identifiers": [{"value": "14923", "evidence_text": "14923"}],
                "subject_evidence": "Train 14923",
                "evidence_text": ANNOUNCEMENT.replace("14922", "14923"),
            },
            ANNOUNCEMENT.replace("14922", "14923"),
        ),
        (
            {
                "identifiers": [{"value": "14922", "evidence_text": "14923"}],
                "subject_evidence": "Train 14923",
                "evidence_text": ANNOUNCEMENT.replace("14922", "14923"),
            },
            ANNOUNCEMENT.replace("14922", "14923"),
        ),
        ({"location": "platform 8"}, ANNOUNCEMENT),
        ({"subject_evidence": None}, ANNOUNCEMENT),
        ({"condition_evidence": None}, ANNOUNCEMENT),
        ({"evidence_text": "Train 14922 will arrive."}, ANNOUNCEMENT),
        ({"source_segment_ids": ["unknown"]}, ANNOUNCEMENT),
        ({"source_segment_ids": ["s1", "s1"]}, ANNOUNCEMENT),
        ({"ambiguity_reason": "Arrival may refer to another train."}, ANNOUNCEMENT),
    ],
)
def test_ungrounded_or_unmet_event_never_alerts(changes, text):
    engine = monitor()
    result = ingest(engine, observation(**changes), text=text)
    assert result[0]["observation"]["type"] == "UNCERTAIN"
    assert engine.flush(101) == []


@pytest.mark.parametrize(
    "text",
    [
        "Train 14922 is delayed.",
        "Train 14922 will arrive in ten minutes.",
        "Train 14922 has not arrived.",
        "Train 14922 has departed.",
    ],
)
def test_nonmatching_model_decisions_do_not_become_alerts(text):
    engine = monitor()
    ingest(
        engine,
        observation(
            type="OTHER",
            condition_met=False,
            evidence_text=text,
            subject_evidence=None,
            condition_evidence=None,
            location=None,
        ),
        text=text,
    )
    assert engine.flush(101) == []


def test_split_announcements_and_stale_replay_validation():
    task = task_intent().task
    event = observation(source_segment_ids=["s0", "s1"])
    segments = [
        make_segment(id="s0", text="Train 14922"),
        make_segment(text="has arrived at platform 3."),
    ]
    assert validate_match(event, segments, task).type == "MATCH"
    segments = [make_segment(id="s0", text=ANNOUNCEMENT), make_segment(text="Please stand back.")]
    assert validate_match(event, segments, task).type == "UNCERTAIN"


def test_duplicates_are_suppressed_but_later_events_are_allowed():
    engine = monitor()
    ingest(engine)
    assert len(engine.flush(100.3)) == 1
    ingest(engine, observation(source_segment_ids=["s2"]), now=110, sid="s2")
    assert engine.flush(111) == []
    ingest(engine, observation(source_segment_ids=["s3"]), now=146, sid="s3")
    assert len(engine.flush(147)) == 1


def test_explicit_correction_can_revoke_an_arrival_without_creating_a_new_match():
    engine = monitor()
    old = ingest(engine)[0]["observation"]
    alert = engine.flush(100.3)[0]["alert"]
    engine.control("acknowledge", alert["id"])
    text = "Correction: train 14922 has not arrived."
    events = ingest(
        engine,
        observation(
            type="CORRECT",
            condition_met=False,
            summary=text,
            evidence_text=text,
            subject_evidence="train 14922",
            condition_evidence="has not arrived",
            location=None,
            source_segment_ids=["s2"],
            replaces_event_id=old["id"],
        ),
        now=101,
        sid="s2",
        text=text,
    )
    assert events[0]["type"] == "alert.corrected"
    assert events[0]["alert"]["acknowledged"] is False
    assert engine.flush(102) == []


def test_ambiguous_correction_clears_pending_and_pause_prevents_alerts():
    engine = monitor()
    ingest(engine)
    text = "Correction: please wait."
    ingest(
        engine,
        observation(
            type="CORRECT",
            condition_met=False,
            replaces_event_id="unknown",
            evidence_text=text,
            identifiers=[],
            location=None,
        ),
        now=100.1,
        text=text,
    )
    assert engine.flush(101) == []
    engine.control("pause")
    assert ingest(engine) == []


def test_general_prompt_receives_the_confirmed_condition_and_only_safe_recent_context():
    async def run():
        provider = object.__new__(OpenAIFallback)
        provider._parse = AsyncMock()
        task = task_intent().task
        await provider.observe(
            [make_segment(text=ANNOUNCEMENT)],
            [{"id": "o1", "state": "matched", "alert_preferences": ["sound"]}],
            task,
        )
        system, data, schema = provider._parse.call_args.args
        assert schema is EventExtraction
        assert data["confirmed_task"] == task.model_dump()
        assert data["recent_observations"] == [{"id": "o1"}]
        assert "entire subject" in system.lower()
        assert "negation" in system.lower()
        assert "untrusted data" in system
        assert "A stop request takes priority" in system

    import asyncio

    asyncio.run(run())


def test_general_task_confirmation_api_requires_explicit_confirmation(client, auth, intelligence):
    intelligence.intent_result = task_intent()
    response = client.post(
        "/v1/intent", headers=auth, json={"text": REQUEST, "consent_to_text_processing": True}
    )
    assert response.json()["status"] == "confirm"
    assert client.get("/v1/state", headers=auth).json()["rule"] is None
    confirmed = client.post(
        "/v1/confirm", headers=auth, json={"proposal_id": response.json()["proposal_id"]}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["rule"]["task"]["subject"] == "train 14922"
    assert confirmed.json()["rule"]["token"] is None
