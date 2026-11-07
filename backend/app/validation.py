"""Validate source evidence, not venue formats or multilingual number semantics.

The text model interprets identifiers in both setup and announcement extraction.
There are no handwritten token grammars, number dictionaries, or counter ranges.
"""

import re

from .models import Intent, ProposedEvent, Segment, StopListeningRequest


def exact_span(phrase: str, text: str) -> bool:
    """Require a complete source span rather than part of another identifier."""
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def intent_errors(intent: Intent, request: str) -> list[str]:
    errors = []
    if intent.intent != "monitor_announcement":
        errors.append("Only queue-token monitoring is supported.")
    if not intent.target_evidence or not exact_span(intent.target_evidence, request):
        errors.append("The target must be grounded in your request.")
    if not intent.token or not intent.token.strip():
        errors.append("Which token should I monitor?")
    if not ({"vibration", "sound", "visual"} & set(intent.alert_preferences)):
        errors.append("Specify visual, vibration, or sound alerts.")
    if intent.clarification:
        errors.append(intent.clarification)
    return errors


def validate_event(event: ProposedEvent, window: list[Segment]) -> ProposedEvent:
    by_id = {segment.id: segment for segment in window}
    sources = [by_id[sid] for sid in event.source_segment_ids if sid in by_id]
    text = " ".join(segment.text for segment in sources)
    reason = None
    if not sources or len(sources) != len(event.source_segment_ids):
        reason = "Unknown source segment."
    elif event.source_segment_ids != [
        segment.id for segment in window if segment.id in event.source_segment_ids
    ]:
        reason = "Source segments must be unique and chronological."
    elif not event.evidence_text or event.evidence_text not in text:
        reason = "Evidence is not a verbatim span of the source."
    elif event.type not in {"OTHER", "UNCERTAIN"}:
        if not event.token_raw or not exact_span(event.token_raw, event.evidence_text):
            reason = "Token has no exact evidence span."
        elif not event.token_normalized or not event.token_normalized.strip():
            reason = "No token was interpreted."
        elif event.ambiguity_reason:
            reason = event.ambiguity_reason
    if reason:
        return event.model_copy(update={"type": "UNCERTAIN", "ambiguity_reason": reason})
    return event.model_copy()


def grounded_stop_request(request: StopListeningRequest, window: list[Segment]) -> bool:
    """Validate provenance only; the model, not a phrase matcher, interprets the intent."""
    if not window or window[-1].id not in request.source_segment_ids:
        return False
    sources = [segment for segment in window if segment.id in request.source_segment_ids]
    return (
        [segment.id for segment in sources] == request.source_segment_ids
        and bool(request.evidence_text.strip())
        and request.evidence_text in " ".join(segment.text for segment in sources)
        # Don't accept old evidence with a newly appended but unrelated source ID.
        and request.evidence_text not in " ".join(segment.text for segment in sources[:-1])
    )
