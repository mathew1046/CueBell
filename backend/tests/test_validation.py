import pytest

from app.validation import intent_errors, normalize_token, validate_event
from tests.conftest import make_event, make_intent, make_segment


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("P042", "P042"),
        ("p 0 4 2", "P042"),
        ("A-0-0-7", "A007"),
        ("042", "042"),
        ("P zero four two", "P042"),
        ("A oh oh seven", "A007"),
        ("പി പൂജ്യം നാല് രണ്ട്", "P042"),
        ("എ പൂജ്യം പൂജ്യം ഏഴ്", "A007"),
        ("one hundred and twenty three", "123"),
        ("P two hundred nineteen", "P219"),
        ("നൂറ്റി ഇരുപത്തി മൂന്ന്", "123"),
        ("പി ഇരുനൂറ്റി പത്ത്", "P210"),
        ("തൊള്ളായിരത്തി തൊണ്ണൂറ്റി ഒമ്പത്", "999"),
        ("000", "000"),
        ("P42", None),
        ("42", None),
        ("forty two", None),
        ("Q042", None),
        ("P0042", None),
        ("1000", None),
        ("P042 and A007", None),
        ("", None),
        ("one hundred nineteen nine", None),
        ("twenty hundred", None),
        ("hundred", None),
        ("one hundred two hundred", None),
        ("P0🙂42", None),
        ("٠٤٢", None),
        ("പൂജ്യം നാല്", None),
        ("P infinity", None),
    ],
)
def test_normalize_token(raw, expected):
    assert normalize_token(raw) == expected


def test_intent_requires_grounded_prefix_and_leading_zeroes():
    assert intent_errors(make_intent(), "Vibrate for P042") == []
    assert intent_errors(make_intent(token="042", target_evidence="042"), "Vibrate for P042")
    assert intent_errors(make_intent(), "Vibrate for P0420")
    assert intent_errors(make_intent(token="P042", target_evidence="forty two"), "forty two")


@pytest.mark.parametrize(
    "changes",
    [
        {"intent": "unsupported"},
        {"context": "airport"},
        {"target_evidence": None},
        {"token": None},
        {"token": "P42"},
        {"alert_preferences": []},
        {"clarification": "Which token?"},
    ],
)
def test_intent_missing_and_unsupported_slots(changes):
    assert intent_errors(make_intent(**changes), "Vibrate for P042")


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
        {"token_normalized": "P420"},
        {"counter": "11"},
        {"counter": "4"},
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
    ],
)
def test_valid_evidence(text, raw, token, counter):
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
