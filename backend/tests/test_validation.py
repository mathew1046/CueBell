import pytest

from app.validation import intent_errors, validate_event
from tests.conftest import make_event, make_intent, make_segment


def test_intent_requires_actual_source_evidence():
    assert intent_errors(make_intent(), "Vibrate for P042") == []
    assert intent_errors(make_intent(token="042", target_evidence="042"), "Vibrate for P042")
    assert intent_errors(make_intent(), "Vibrate for P0420")


@pytest.mark.parametrize(
    "changes",
    [
        {"intent": "unsupported"},
        {"target_evidence": None},
        {"token": None},
        {"alert_preferences": []},
        {"clarification": "Which token?"},
    ],
)
def test_intent_missing_slots(changes):
    assert intent_errors(make_intent(**changes), "Vibrate for P042")


@pytest.mark.parametrize(
    ("text", "raw", "token", "venue"),
    [
        ("ടോക്കൺ പത്ത് ആകുമ്പോൾ വൈബ്രേറ്റ് ചെയ്യുക", "പത്ത്", "10", "queue"),
        ("Alert for token दस", "दस", "10", "queue"),
        ("Alert for token பத்து", "பத்து", "10", "queue"),
        ("Airport token AB/12345", "AB/12345", "AB/12345", "airport"),
        ("Ticket 7", "7", "7", "queue"),
        ("Ticket VIP", "VIP", "VIP", "bank"),
        ("Ticket A-0-0-7", "A-0-0-7", "A-0-0-7", "queue"),
        ("Ticket blue whale", "blue whale", "BLUE WHALE", "queue"),
    ],
)
def test_intent_accepts_model_interpretation_without_custom_parsing(text, raw, token, venue):
    intent = make_intent(token=token, target_evidence=raw, context=venue)
    assert intent_errors(intent, text) == []


def test_evidence_is_validated_without_mutating_proposal():
    event = make_event(evidence_text="invented P042 to counter 2")
    result = validate_event(event, [make_segment()])
    assert result.type == "UNCERTAIN"
    assert result.ambiguity_reason == "Evidence is not a verbatim span of the source."
    assert event.type == "CALL"


@pytest.mark.parametrize(
    "changes",
    [
        {"source_segment_ids": []},
        {"source_segment_ids": ["missing"]},
        {"source_segment_ids": ["s1", "s1"]},
        {"evidence_text": ""},
        {"token_raw": "042", "token_normalized": "042"},
        {"token_raw": None},
        {"token_normalized": None},
        {"ambiguity_reason": "May be negated"},
    ],
)
def test_invalid_evidence_is_uncertain(changes):
    assert validate_event(make_event(**changes), [make_segment()]).type == "UNCERTAIN"


@pytest.mark.parametrize(
    ("text", "raw", "token", "counter"),
    [
        ("P042 to counter 2", "P042", "P042", "2"),
        ("P042 to counter two", "P042", "P042", "2"),
        ("പി പൂജ്യം നാല് രണ്ട് കൗണ്ടർ പത്ത്", "പി പൂജ്യം നാല് രണ്ട്", "P042", "10"),
        ("A007 is called", "A007", "A007", None),
        ("പത്ത്", "പത്ത്", "10", None),
        ("ten", "ten", "10", None),
        ("दस", "दस", "10", None),
        ("பத்து", "பத்து", "10", None),
        ("١٠", "١٠", "10", None),
        ("one zero", "one zero", "10", None),
        ("Q7", "Q7", "Q7", None),
        ("AB/12345 to counter 24", "AB/12345", "AB/12345", "24"),
        ("7 to counter eleven", "7", "7", "11"),
        ("blue whale to desk C", "blue whale", "BLUE WHALE", "C"),
    ],
)
def test_evidence_accepts_model_interpretation_without_custom_parsing(text, raw, token, counter):
    event = make_event(token_raw=raw, token_normalized=token, counter=counter, evidence_text=text)
    assert validate_event(event, [make_segment(text=text)]) == event


def test_split_phrase_requires_ordered_unique_segments():
    segments = [make_segment(text="P zero four"), make_segment(id="s2", text="two to counter 2")]
    event = make_event(
        token_raw="P zero four two",
        evidence_text="P zero four two to counter 2",
        source_segment_ids=["s1", "s2"],
    )
    assert validate_event(event, segments).type == "CALL"
    reversed_event = event.model_copy(update={"source_segment_ids": ["s2", "s1"]})
    assert validate_event(reversed_event, segments).type == "UNCERTAIN"
