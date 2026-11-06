import pytest

from app.engine import Engine
from tests.conftest import make_event, make_intent, make_segment


@pytest.fixture
def engine():
    engine = Engine(grace=1.2)
    engine.activate(make_intent())
    return engine


def call(engine, now=100.0, **changes):
    event = make_event(**changes)
    window = [make_segment(id=sid, text=event.evidence_text) for sid in event.source_segment_ids]
    return engine.ingest(event, window, now)


def test_only_confirmed_exact_target_alerts_after_grace(engine):
    assert engine.rule["alert_preferences"] == ["vibration", "visual"]
    outputs = call(engine)
    assert [output["type"] for output in outputs] == ["observation"]
    assert engine.flush(101.19) == []
    alerts = engine.flush(101.2)
    assert len(alerts) == 1
    assert alerts[0]["alert"]["token"] == "P042"
    assert engine.flush(102) == []


def test_new_confirmation_purges_previous_monitor_history_without_resetting_sequence(engine):
    call(engine)
    engine.flush(102)
    assert engine.alerts and len(engine.history) > 1
    previous_sequence = engine.sequence
    created = engine.activate(make_intent(token="P043"))
    assert created["sequence"] == previous_sequence + 1
    assert list(engine.history) == [created]
    assert not engine.alerts and not engine.observations and not engine.pending and not engine.seen
    assert engine.flush(200) == []


@pytest.mark.parametrize("raw", ["പത്ത്", "ten", "दस", "பத்து", "١٠", "one zero"])
def test_model_interpreted_readout_alerts_with_vibration_and_sound(raw):
    engine = Engine(grace=1.2)
    engine.activate(
        make_intent(
            token="10",
            target_evidence="പത്ത്",
            context="queue",
            alert_preferences=["visual", "vibration", "sound"],
        )
    )
    # Model outputs are supplied here; this tests delivery, not live language accuracy.
    call(engine, token_raw=raw, token_normalized="10", evidence_text=raw, counter=None)
    alerts = engine.flush(102)
    assert len(alerts) == 1
    assert alerts[0]["alert"]["token"] == "10"
    assert set(alerts[0]["alert"]["alert_preferences"]) == {"visual", "vibration", "sound"}


@pytest.mark.parametrize("token", ["042", "P420", "A042", "P0042"])
def test_no_fuzzy_prefix_or_zero_matching(engine, token):
    call(engine, token_raw=token, token_normalized=token, evidence_text=f"{token} to counter 2")
    assert engine.flush(102) == []


def test_exact_token_and_counter_are_distinct_and_repeat_alerts_are_suppressed():
    engine = Engine()
    engine.activate(make_intent(token="42", target_evidence="42"))
    call(
        engine,
        token_raw="forty-three",
        token_normalized="43",
        counter="3",
        evidence_text="Token forty-three, go to counter three.",
    )
    assert engine.flush(102) == []
    matching_call = {
        "token_raw": "forty-two",
        "token_normalized": "42",
        "counter": "3",
        "evidence_text": "Token forty-two, go to counter three.",
    }
    call(engine, now=103, source_segment_ids=["s2"], **matching_call)
    alert = engine.flush(105)[0]["alert"]
    assert (alert["token"], alert["counter"]) == ("42", "3")
    assert alert["alert_preferences"] == ["vibration", "visual"]
    call(engine, now=106, source_segment_ids=["s3"], **matching_call)
    assert engine.flush(108) == []


@pytest.mark.parametrize("kind", ["REPEAT", "OTHER", "UNCERTAIN", "CANCEL", "CORRECT"])
def test_non_calls_and_unresolved_corrections_do_not_alert(engine, kind):
    call(engine, type=kind)
    assert engine.flush(102) == []


def test_dedup_same_source_and_repeated_provider_transcript(engine):
    call(engine)
    assert call(engine) == []
    call(engine, now=100.5, source_segment_ids=["s2"])
    assert len(engine.pending) == 1
    assert len(engine.flush(102)) == 1
    call(engine, now=110, source_segment_ids=["s3"])
    assert engine.flush(112) == []
    call(engine, now=146, source_segment_ids=["s4"])
    assert len(engine.flush(148)) == 1


def test_different_counter_is_distinct(engine):
    call(engine)
    call(engine, counter="3", evidence_text="P042 to counter 3", source_segment_ids=["s2"])
    assert len(engine.flush(102)) == 2


@pytest.mark.parametrize("kind", ["CORRECT", "CANCEL"])
def test_explicit_correction_cancels_pending_old_target(engine, kind):
    call(engine)
    old = engine.observations[-1]
    token = "P043" if kind == "CORRECT" else "P042"
    call(
        engine,
        now=100.5,
        type=kind,
        token_raw=token,
        token_normalized=token,
        evidence_text=f"Correction {token} to counter 2",
        replaces_event_id=old["id"],
        source_segment_ids=["s2"],
    )
    assert old["state"] == ("superseded" if kind == "CORRECT" else "cancelled")
    assert engine.flush(102) == []


def test_corrected_target_can_alert_and_revoke_old_alert(engine):
    call(engine)
    old = engine.observations[-1]
    engine.flush(102)
    outputs = call(
        engine,
        now=103,
        type="CORRECT",
        replaces_event_id=old["id"],
        counter="3",
        evidence_text="Correction P042 to counter 3",
        source_segment_ids=["s2"],
    )
    assert outputs[0]["type"] == "alert.corrected"
    assert engine.alerts[0]["state"] == "corrected"
    assert len(engine.flush(105)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "UNCERTAIN", "ambiguity_reason": "Unclear correction"},
        {"type": "CORRECT", "replaces_event_id": "unknown"},
        {"type": "CANCEL", "replaces_event_id": "unknown"},
    ],
)
def test_uncertain_correction_withholds_prior_pending_alert(engine, changes):
    call(engine)
    call(engine, now=100.5, source_segment_ids=["s2"], **changes)
    assert engine.observations[-1]["type"] == "UNCERTAIN"
    assert engine.flush(102) == []


def test_correction_cannot_reference_stale_observation(engine):
    call(engine)
    old = engine.observations[-1]
    engine.pending.clear()
    call(engine, now=131, type="CORRECT", replaces_event_id=old["id"], source_segment_ids=["s2"])
    assert engine.observations[-1]["type"] == "UNCERTAIN"
    assert engine.flush(133) == []


def test_gap_is_a_hard_pending_and_correction_boundary(engine):
    call(engine)
    old = engine.observations[-1]
    generation = engine.generation
    engine.gap()
    assert engine.generation > generation
    assert engine.recent_observations(101) == []
    assert engine.flush(102) == []
    call(engine, now=103, type="CORRECT", replaces_event_id=old["id"], source_segment_ids=["s2"])
    assert engine.observations[-1]["type"] == "UNCERTAIN"


def test_recent_correction_context_has_no_target_or_alert_state(engine):
    call(engine)
    engine.flush(102)
    recent = engine.recent_observations(103)
    assert len(recent) == 1
    assert set(recent[0]) == {
        "id",
        "type",
        "token_normalized",
        "counter",
        "evidence_text",
        "source_segment_ids",
    }
    assert engine.recent_observations(131) == []
    assert engine.recent_observations(99) == []


def test_pause_resume_stop_and_new_monitor_invalidate_pending(engine):
    call(engine)
    engine.control("pause")
    assert engine.flush(102) == []
    call(engine, now=103, source_segment_ids=["s2"])
    assert not engine.pending
    engine.control("resume")
    call(engine, now=104, source_segment_ids=["s3"])
    assert engine.pending
    engine.control("stop")
    assert engine.flush(106) == []
    engine.activate(make_intent())
    assert not engine.observations
    assert not engine.alerts
    call(engine, now=107)
    assert len(engine.flush(109)) == 1


def test_acknowledgment_and_bounded_history(engine):
    call(engine)
    engine.flush(102)
    alert = engine.alerts[-1]
    result = engine.control("acknowledge", alert["id"])
    assert result["alert"]["state"] == "acknowledged"
    with pytest.raises(ValueError, match="Alert is no longer available"):
        engine.control("acknowledge", "missing")
    for _ in range(200):
        engine.control("pause")
    assert len(engine.history) == 100
    assert engine.history[-1]["sequence"] > engine.history[0]["sequence"]


def test_controls_require_monitor():
    with pytest.raises(ValueError, match="No confirmed monitor"):
        Engine().control("pause")


def test_cancellation_must_name_the_observed_token(engine):
    call(engine)
    old = engine.observations[-1]
    call(
        engine,
        now=101,
        type="CANCEL",
        token_raw="A007",
        token_normalized="A007",
        replaces_event_id=old["id"],
        evidence_text="Cancel A007 to counter 2",
        source_segment_ids=["s2"],
    )
    assert engine.observations[-1]["type"] == "UNCERTAIN"
    assert old["state"] == "confirmed"
    assert engine.flush(103) == []


def test_other_is_not_a_correction_target(engine):
    call(engine, type="OTHER")
    old = engine.observations[-1]
    assert engine.recent_observations(101) == []
    call(engine, now=101, type="CORRECT", replaces_event_id=old["id"], source_segment_ids=["s2"])
    assert engine.observations[-1]["type"] == "UNCERTAIN"
    assert engine.flush(103) == []


def test_cancellation_cannot_revoke_same_token_at_a_different_counter(engine):
    call(engine)
    old = engine.observations[-1]
    engine.flush(102)
    outputs = call(
        engine,
        now=103,
        type="CANCEL",
        counter="3",
        evidence_text="Cancel P042 to counter 3",
        replaces_event_id=old["id"],
        source_segment_ids=["s2"],
    )
    assert old["state"] == "confirmed"
    assert engine.alerts[-1]["state"] == "unacknowledged"
    assert outputs[-1]["observation"]["type"] == "UNCERTAIN"
    assert all(output["type"] != "alert.corrected" for output in outputs)


def test_pause_resume_cannot_reuse_pre_pause_correction_context(engine):
    call(engine)
    old = engine.observations[-1]
    engine.control("pause")
    engine.control("resume")
    assert engine.recent_observations(101) == []
    call(engine, now=101, type="CORRECT", replaces_event_id=old["id"], source_segment_ids=["s2"])
    assert engine.flush(103) == []


def test_overdue_pending_call_never_releases_as_live_alert(engine):
    call(engine)
    assert engine.flush(116) == []
    assert not engine.pending


@pytest.mark.parametrize("duplicate_type", ["CALL", "REPEAT"])
@pytest.mark.parametrize("already_alerted", [False, True])
@pytest.mark.parametrize("correction_type", ["CORRECT", "CANCEL"])
def test_correction_of_duplicate_revokes_original_call(
    engine, duplicate_type, already_alerted, correction_type
):
    call(engine)
    if already_alerted:
        engine.flush(102)
    call(engine, now=103, type=duplicate_type, source_segment_ids=["s2"])
    duplicate = engine.observations[-1]
    token = "P043" if correction_type == "CORRECT" else "P042"
    outputs = call(
        engine,
        now=104,
        type=correction_type,
        token_raw=token,
        token_normalized=token,
        evidence_text=f"Correction {token} to counter 2",
        replaces_event_id=duplicate["id"],
        source_segment_ids=["s3"],
    )
    assert engine.flush(106) == []
    if already_alerted:
        assert engine.alerts[0]["state"] == "corrected"
        assert any(output["type"] == "alert.corrected" for output in outputs)
    state = "superseded" if correction_type == "CORRECT" else "cancelled"
    assert all(o["state"] == state for o in list(engine.observations)[:2])


def test_correction_does_not_revoke_same_token_at_other_counter(engine):
    call(engine)
    call(
        engine, now=100.1, counter="3", evidence_text="P042 to counter 3", source_segment_ids=["s2"]
    )
    other = engine.observations[-1]
    original = engine.observations[0]
    call(
        engine,
        now=101,
        type="CANCEL",
        replaces_event_id=original["id"],
        evidence_text="Cancel P042 to counter 2",
        source_segment_ids=["s3"],
    )
    assert other["state"] == "confirmed"
    assert [event["alert"]["counter"] for event in engine.flush(103)] == ["3"]


def test_two_corrections_in_one_source_keep_distinct_replacement_targets(engine):
    call(engine)
    first = engine.observations[-1]
    call(
        engine, now=100.1, counter="3", evidence_text="P042 to counter 3", source_segment_ids=["s2"]
    )
    second = engine.observations[-1]
    for old in [first, second]:
        call(
            engine,
            now=101,
            type="CORRECT",
            token_raw="P043",
            token_normalized="P043",
            evidence_text="Correction P043 to counter 4",
            counter="4",
            replaces_event_id=old["id"],
            source_segment_ids=["s3"],
        )
    assert first["state"] == second["state"] == "superseded"
    assert engine.flush(103) == []


def test_acknowledgment_cannot_undo_a_correction(engine):
    call(engine)
    old = engine.observations[-1]
    engine.flush(102)
    alert = engine.alerts[-1]
    call(engine, now=103, type="CANCEL", replaces_event_id=old["id"], source_segment_ids=["s2"])
    assert alert["state"] == "corrected"
    assert alert["acknowledged"] is False
    result = engine.control("acknowledge", alert["id"])
    assert result["type"] == "alert.acknowledged"
    assert result["alert"]["state"] == "corrected"
    assert result["alert"]["acknowledged"] is True
    assert alert["state"] == "corrected"
    assert alert["acknowledged"] is True


def test_correction_after_acknowledgment_requires_acknowledgment_again(engine):
    call(engine)
    old = engine.observations[-1]
    engine.flush(102)
    alert = engine.alerts[-1]
    assert alert["acknowledged"] is False
    engine.control("acknowledge", alert["id"])
    assert alert["state"] == "acknowledged"
    assert alert["acknowledged"] is True
    outputs = call(
        engine, now=103, type="CANCEL", replaces_event_id=old["id"], source_segment_ids=["s2"]
    )
    assert outputs[0]["type"] == "alert.corrected"
    assert outputs[0]["alert"]["acknowledged"] is False
    assert alert["state"] == "corrected"
    assert alert["acknowledged"] is False


@pytest.mark.parametrize("corrected", [False, True])
def test_repeated_acknowledgment_is_harmless(engine, corrected):
    call(engine)
    old = engine.observations[-1]
    engine.flush(102)
    alert = engine.alerts[-1]
    if corrected:
        call(engine, now=103, type="CANCEL", replaces_event_id=old["id"], source_segment_ids=["s2"])
    first = engine.control("acknowledge", alert["id"])
    second = engine.control("acknowledge", alert["id"])
    assert first["alert"] == second["alert"]
    assert alert["state"] == ("corrected" if corrected else "acknowledged")
    assert alert["acknowledged"] is True
    assert engine.flush(105) == []


@pytest.mark.parametrize("action", ["resume", "pause"])
def test_stopped_monitor_requires_fresh_confirmation(engine, action):
    engine.control("stop")
    with pytest.raises(ValueError, match="confirm"):
        engine.control(action)
    assert engine.rule["status"] == "STOPPED"
    engine.activate(make_intent())
    assert engine.rule["status"] == "ACTIVE"


@pytest.mark.parametrize("already_alerted", [False, True])
def test_duplicate_correction_survives_eviction_of_original_observation(engine, already_alerted):
    call(engine)
    original_id = engine.observations[-1]["id"]
    if already_alerted:
        engine.flush(102)
    for i in range(55):
        call(engine, now=103, type="OTHER", source_segment_ids=[f"unrelated-{i}"])
    assert all(o["id"] != original_id for o in engine.observations)
    call(engine, now=104, type="REPEAT", source_segment_ids=["s2"])
    duplicate_id = engine.observations[-1]["id"]
    assert len(engine._occurrences) <= engine.observations.maxlen
    call(
        engine,
        now=105,
        type="CANCEL",
        replaces_event_id=duplicate_id,
        source_segment_ids=["s3"],
    )
    assert engine.flush(107) == []
    assert not engine.alerts or engine.alerts[0]["state"] == "corrected"


def test_repeat_chain_does_not_merge_a_new_call_beyond_dedup_window(engine):
    call(engine)
    engine.flush(102)
    call(engine, now=140, type="REPEAT", source_segment_ids=["s2"])
    call(engine, now=146, source_segment_ids=["s3"])
    new = engine.observations[-1]
    engine.flush(148)
    call(
        engine,
        now=149,
        type="CANCEL",
        replaces_event_id=new["id"],
        source_segment_ids=["s4"],
    )
    assert [a["state"] for a in engine.alerts] == ["unacknowledged", "corrected"]
