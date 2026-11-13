"""Validate source evidence, not venue formats or multilingual number semantics.

The text model interprets identifiers in both setup and announcement extraction.
There are no handwritten token grammars, number dictionaries, or counter ranges.
"""

import re
import unicodedata

from .models import (
    EventObservation,
    Intent,
    MonitoringTask,
    ProposedEvent,
    Segment,
    StopListeningRequest,
)


def exact_span(phrase: str, text: str) -> bool:
    """Require a complete source span rather than part of another identifier."""
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def literal_identifier_matches(value: str, evidence: str) -> bool:
    """Check unambiguous numeric literals; leave spoken-number semantics to the model."""
    evidence = unicodedata.normalize("NFKC", evidence).strip()
    if (
        evidence
        and all(c.isdecimal() or c.isascii() and c.isalpha() for c in evidence)
        and any(c.isdecimal() for c in evidence)
    ):
        literal = "".join(
            str(unicodedata.decimal(c)) if c.isdecimal() else c.upper() for c in evidence
        )
        return literal == value
    return True


def intent_errors(intent: Intent, request: str) -> list[str]:
    errors = []
    if intent.intent == "monitor_event":
        task = intent.task
        if not task or not all(
            value.strip() for value in (task.subject, task.condition, task.summary)
        ):
            errors.append("What should I listen for, and when should I alert you?")
        elif not exact_span(task.request_evidence, request) or any(
            not exact_span(identifier.evidence_text, request)
            or not literal_identifier_matches(identifier.value, identifier.evidence_text)
            for identifier in task.identifiers
        ):
            errors.append("The event must be grounded in your request. Please describe it again.")
    elif intent.intent == "monitor_announcement":
        # Compatibility with previously confirmed queue monitors, not the app's default task.
        if not intent.target_evidence or not exact_span(intent.target_evidence, request):
            errors.append("The target must be grounded in your request.")
        if not intent.token or not intent.token.strip():
            errors.append("Which token should I monitor?")
    elif not intent.clarification:
        errors.append("Describe an event I can hear in speech and alert you about.")
    if not ({"vibration", "sound", "visual"} & set(intent.alert_preferences)):
        errors.append("Specify visual, vibration, or sound alerts.")
    if intent.clarification:
        errors.append(intent.clarification)
    return errors


def validate_match(
    event: EventObservation, window: list[Segment], task: MonitoringTask
) -> EventObservation:
    sources = [segment for segment in window if segment.id in event.source_segment_ids]
    text = " ".join(segment.text for segment in sources)
    reason = None
    if not sources or [s.id for s in sources] != event.source_segment_ids:
        reason = "Source segments must be known, unique and chronological."
    elif not window or window[-1].id not in event.source_segment_ids:
        reason = "Event has no current source segment."
    elif not event.evidence_text.strip() or event.evidence_text not in text:
        reason = "Evidence is not a verbatim span of the source."
    elif event.evidence_text in " ".join(s.text for s in sources[:-1]):
        reason = "Event evidence is stale."
    elif event.location and event.location not in event.evidence_text:
        reason = "Location has no source evidence."
    elif any(not exact_span(i.evidence_text, event.evidence_text) for i in event.identifiers):
        reason = "Identifier has no exact source evidence."
    elif any(not literal_identifier_matches(i.value, i.evidence_text) for i in event.identifiers):
        reason = "Identifier does not agree with its literal source."
    elif event.type == "MATCH" or (event.type == "CORRECT" and event.condition_met):
        if not event.condition_met or not event.summary.strip():
            reason = "Requested event was not established."
        elif not event.subject_evidence or not exact_span(
            event.subject_evidence, event.evidence_text
        ):
            reason = "Subject has no exact source evidence."
        elif not event.condition_evidence or event.condition_evidence not in event.evidence_text:
            reason = "Requested condition has no source evidence."
        elif not {i.value for i in task.identifiers}.issubset({i.value for i in event.identifiers}):
            reason = "Announcement identifiers do not match the confirmed task."
        elif event.ambiguity_reason:
            reason = event.ambiguity_reason
    if reason:
        return event.model_copy(
            update={"type": "UNCERTAIN", "condition_met": False, "ambiguity_reason": reason}
        )
    return event.model_copy()


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
