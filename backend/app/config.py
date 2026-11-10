from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    gnani_api_key: str = ""
    # Prisma v3 detects per utterance; a list prioritizes languages, not a restriction.
    gnani_language_code: str = "indic-auto"
    text_provider: Literal["openai_fallback", "gnani_evon"] = "openai_fallback"
    openai_api_key: str = ""
    openai_model: str = ""
    evon_api_key: str = ""
    evon_base_url: str = ""
    evon_model: str = "gnani/gnani-evon-v3.3-30B-A3B"
    evon_timeout_seconds: float = Field(default=12, gt=0, le=15)
    evon_setup_timeout_seconds: float = Field(default=130, gt=0, le=130)
    demo_access_code: str = ""
    allow_app_sessions: bool = False
    allow_insecure_local: bool = False
    max_sessions: int = Field(default=8, ge=1, le=100)
    session_ttl_seconds: int = Field(default=14400, ge=60, le=86400)
    correction_grace_seconds: float = Field(default=1.2, ge=0.2, le=10)
    request_pause_seconds: float = Field(default=3.5, ge=1, le=15)
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
        if self.text_provider == "gnani_evon":
            return bool(self.evon_api_key and self.evon_base_url and self.evon_model)
        return bool(self.openai_api_key and self.openai_model)
