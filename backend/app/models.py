from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TargetIdentifier(StrictModel):
    value: str = Field(min_length=1, max_length=160)
    evidence_text: str = Field(min_length=1, max_length=300)


class MonitoringTask(StrictModel):
    subject: str = Field(min_length=1, max_length=300)
    condition: str = Field(min_length=1, max_length=600)
    summary: str = Field(min_length=1, max_length=600)
    request_evidence: str = Field(min_length=1, max_length=1500)
    identifiers: list[TargetIdentifier] = Field(max_length=12)


class Intent(StrictModel):
    intent: Literal["monitor_event", "monitor_announcement", "unsupported", "unclear"]
    context: str | None
    token: str | None = Field(description="Legacy queue field. Null for monitor_event tasks.")
    alert_preferences: list[Literal["visual", "vibration", "sound"]]
    clarification: str | None
    # Exact substring of the user's request that names the target.
    target_evidence: str | None = Field(
        description="Legacy queue field; null for monitor_event. "
        "Only the exact token identifier or spoken number words from the request, "
        "including its prefix if present. Exclude surrounding words such as token, pharmacy, "
        "or ടോക്കൺ. Example: pharmacy token 442 -> 442; token four hundred forty two -> "
        "four hundred forty two. Null if missing or ambiguous."
    )
    task: MonitoringTask | None = None


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
