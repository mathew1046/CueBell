from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    gnani_api_key: str = ""
    # Prisma v3 detects per utterance; a list prioritizes languages, not a restriction.
    gnani_language_code: str = "indic-auto"
    gnani_min_silence_ms: int | None = Field(default=None, ge=100, le=2000)
    gnani_vad_threshold: float | None = Field(default=None, ge=0, le=1)
    gnani_min_speech_ms: int | None = Field(default=None, ge=50, le=2000)
    gnani_min_segment_ms: int | None = Field(default=None, ge=100, le=1000)
    gnani_max_speech_s: int | None = Field(default=None, ge=5, le=120)
    openai_api_key: str = ""
    openai_model: str = ""
    # Omit unset provider options so baseline requests retain provider defaults.
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] | None = None
    openai_service_tier: Literal["auto", "default", "flex", "scale", "fast", "priority"] | None = (
        None
    )
    openai_verbosity: Literal["low", "medium", "high"] | None = None
    openai_prompt_cache_mode: Literal["implicit", "explicit"] | None = None
    openai_prompt_cache_ttl: Literal["30m", "12h"] | None = None
    openai_compact_input: bool = False
    openai_verbatim_location_hint: bool = False
    openai_max_output_tokens: int = Field(default=2000, ge=1, le=128000)
    optimized_scheduling: bool = False
    outbound_writer: bool = False
    outbound_queue_size: int = Field(default=64, ge=1, le=1024)
    demo_access_code: str = ""
    allow_app_sessions: bool = False
    allow_insecure_local: bool = False
    max_sessions: int = Field(default=8, ge=1, le=100)
    session_ttl_seconds: int = Field(default=14400, ge=60, le=86400)
    correction_grace_seconds: float = Field(default=1.2, ge=0.2, le=10)
    request_pause_seconds: float = Field(default=3.5, ge=1, le=15)
    request_speech_aware_completion: bool = False
    request_timeout_seconds: float = Field(default=90, ge=20, le=180)

    @field_validator("gnani_language_code")
    @classmethod
    def validate_gnani_language_code(cls, value: str) -> str:
        value = value.strip()
        if value == "indic-auto":
            return value
        codes = [code.strip() for code in value.split(",")]
        supported = {
            "bn-IN",
            "en-IN",
            "gu-IN",
            "hi-IN",
            "kn-IN",
            "ml-IN",
            "mr-IN",
            "pa-IN",
            "ta-IN",
            "te-IN",
        }
        if not 1 <= len(codes) <= 4 or any(code not in supported for code in codes):
            raise ValueError(
                "GNANI_LANGUAGE_CODE must be indic-auto or 1–4 supported Prisma v3 language codes."
            )
        return ",".join(codes)

    @property
    def model_ready(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)
