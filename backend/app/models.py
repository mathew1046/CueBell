from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Intent(StrictModel):
    intent: Literal["monitor_announcement", "unsupported", "unclear"]
    context: str | None
    token: str | None
    alert_preferences: list[Literal["visual", "vibration", "sound"]]
    clarification: str | None
    # Exact substring of the user's request that names the target.
    target_evidence: str | None = Field(
        description="Only the exact token identifier or spoken number words from the request, "
        "including its prefix if present. Exclude surrounding words such as token, pharmacy, "
        "or ടോക്കൺ. Example: pharmacy token 442 -> 442; token four hundred forty two -> "
        "four hundred forty two. Null if missing or ambiguous."
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


class Extraction(StrictModel):
    events: list[ProposedEvent]


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
