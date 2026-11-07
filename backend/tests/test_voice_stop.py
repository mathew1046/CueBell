import pytest

from app.models import StopListeningRequest
from app.validation import grounded_stop_request
from tests.conftest import make_segment


@pytest.mark.parametrize(
    "text",
    [
        "stop",
        "I am leaving now; there is no need to keep an ear out for me",
        "ഇനി എനിക്ക് വേണ്ടി കേൾക്കേണ്ട",
        "अब मेरी बात सुनना बंद कर दो",
        "Ya no necesito que sigas escuchando",
        "もう聞かなくていいです",
        "لم أعد بحاجة إلى الاستماع",
    ],
)
def test_stop_provenance_has_no_language_or_keyword_rules(text):
    # This tests grounding, not live semantic accuracy: intent is a model judgment.
    segment = make_segment(text=text)
    request = StopListeningRequest(evidence_text=text, source_segment_ids=[segment.id])
    assert grounded_stop_request(request, [segment])


def test_split_stop_request_is_grounded_in_chronological_sources():
    window = [
        make_segment(text="There is no need"),
        make_segment(id="s2", text="to listen anymore"),
    ]
    request = StopListeningRequest(
        evidence_text="There is no need to listen anymore", source_segment_ids=["s1", "s2"]
    )
    assert grounded_stop_request(request, window)


@pytest.mark.parametrize(
    ("evidence", "sources"),
    [
        ("stop", []),
        ("stop", ["unknown"]),
        ("stop", ["s1", "unknown"]),
        ("stop", ["s1", "s1"]),
        ("stop", ["s2", "s1"]),
        ("invented evidence", ["s1", "s2"]),
        ("", ["s2"]),
        (" ", ["s2"]),
        ("stop", ["s1"]),
        ("stop", ["s1", "s2"]),
    ],
)
def test_unknown_duplicate_out_of_order_or_old_evidence_cannot_stop(evidence, sources):
    window = [make_segment(text="stop"), make_segment(id="s2", text="P042 to counter 2")]
    request = StopListeningRequest(evidence_text=evidence, source_segment_ids=sources)
    assert not grounded_stop_request(request, window)
