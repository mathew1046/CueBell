from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TargetIdentifier(StrictModel):
    value: str = Field(
        min_length=1,
        max_length=160,
        description="Exact identity: convert number words/native digits to ASCII digits "
        "and letters to uppercase. Preserve prefixes and leading zeros; never append digits.",
    )
    evidence_text: str = Field(
        min_length=1,
        max_length=300,
        description="Copy only the original identifier words/digits from the source, without "
        "labels. Preserve native script. Never substitute the normalized value or a translation.",
    )


class MonitoringTask(StrictModel):
    subject: str = Field(min_length=1, max_length=300)
    condition: str = Field(min_length=1, max_length=600)
    summary: str = Field(
        min_length=1,
        max_length=600,
        description="Short subject and trigger in the request's language, "
        "not an English translation.",
    )
    request_evidence: str = Field(
        min_length=1,
        max_length=1500,
        description="Copy request exactly, including punctuation. "
        "No introductory text or translation.",
    )
    identifiers: list[TargetIdentifier] = Field(
        max_length=12,
        description="Every required number/code/name. Include numbers expressed as words; "
        "empty only when the task has no specific identity.",
    )


class Intent(StrictModel):
    intent: Literal["monitor_event", "monitor_announcement", "unsupported", "unclear"] = Field(
        description="unsupported for non-speech sounds or unavailable actions; unclear if subject "
        "or trigger is missing; otherwise monitor_event. Never select legacy monitor_announcement.",
    )
    context: str | None
    token: str | None = Field(description="Legacy queue field. Null for monitor_event tasks.")
    alert_preferences: list[Literal["visual", "vibration", "sound"]] = Field(
        description='Default exactly ["visual","vibration","sound"]. Explicit silent/no-sound: '
        '["visual","vibration"]. Explicit visual-only: ["visual"]. Always include visual.',
    )
    clarification: str | None
    # Exact substring of the user's request that names the target.
    target_evidence: str | None = Field(
        description="Legacy queue field. Null for monitor_event, unclear and unsupported. "
        "For legacy monitor_announcement only: copy the exact identifier words, without labels."
    )
    task: MonitoringTask | None = Field(
        default=None,
        description="Required for monitor_event. Null for unclear/unsupported with a relevant "
        "clarification in the request's language.",
    )


class Segment(StrictModel):
    id: str
    text: str
    received_at: float


class ProposedEvent(StrictModel):
    type: Literal["CALL", "CORRECT", "REPEAT", "CANCEL", "OTHER", "UNCERTAIN"]
    token_raw: str | None
    token_normalized: str | None
    counter: str | None
    replaces_event_id: str | None
    evidence_text: str
    source_segment_ids: list[str]
    ambiguity_reason: str | None


class StopListeningRequest(StrictModel):
    evidence_text: str = Field(
        description="Verbatim source span expressing a request to stop CueBell."
    )
    source_segment_ids: list[str]


class Extraction(StrictModel):
    events: list[ProposedEvent]
    stop_request: StopListeningRequest | None = Field(
        default=None,
        description="A clear user intent to stop or pause CueBell's current listening, in any "
        "language or phrasing, including indirect requests. Null for negation, quotations, "
        "hypotheticals, queue cancellations, unrelated conversation, or ambiguous intent.",
    )


class EventObservation(StrictModel):
    type: Literal["MATCH", "CORRECT", "CANCEL", "OTHER", "UNCERTAIN"]
    condition_met: bool
    summary: str = Field(max_length=600)
    subject_evidence: str | None
    condition_evidence: str | None
    identifiers: list[TargetIdentifier] = Field(max_length=12)
    location: str | None = Field(max_length=300)
    replaces_event_id: str | None
    evidence_text: str = Field(max_length=4000)
    source_segment_ids: list[str]
    ambiguity_reason: str | None


class EventExtraction(StrictModel):
    events: list[EventObservation]
    stop_request: StopListeningRequest | None = None


class PairRequest(StrictModel):
    access_code: str | None = Field(default=None, min_length=1, max_length=256)


class IntentRequest(StrictModel):
    text: str = Field(min_length=1, max_length=1500)
    consent_to_text_processing: bool


class ConfirmRequest(StrictModel):
    proposal_id: str = Field(min_length=1, max_length=64)


class ControlRequest(StrictModel):
    action: Literal["pause", "resume", "stop", "acknowledge"]
    alert_id: str | None = Field(default=None, max_length=128)
