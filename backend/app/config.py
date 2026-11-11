from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    gnani_api_key: str = ""
    # Prisma v3 detects per utterance; a list prioritizes languages, not a restriction.
    gnani_language_code: str = "indic-auto"
    openai_api_key: str = ""
    openai_model: str = ""
    demo_access_code: str = ""
    allow_app_sessions: bool = False
    allow_insecure_local: bool = False
    web_origins: list[str] = Field(default_factory=list)
    max_sessions: int = Field(default=8, ge=1, le=100)
    session_ttl_seconds: int = Field(default=14400, ge=60, le=86400)
    correction_grace_seconds: float = Field(default=1.2, ge=0.2, le=10)
    request_pause_seconds: float = Field(default=3.5, ge=1, le=15)
    request_timeout_seconds: float = Field(default=90, ge=20, le=180)

    @field_validator("web_origins")
    @classmethod
    def validate_web_origins(cls, origins: list[str]) -> list[str]:
        """Accept exact secure browser origins, with loopback HTTP for local development."""
        for origin in origins:
            parsed = urlsplit(origin)
            local = parsed.scheme == "http" and parsed.hostname in {
                "localhost",
                "127.0.0.1",
                "[::1]",
                "::1",
            }
            if (
                not origin
                or (parsed.scheme != "https" and not local)
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError(
                    "WEB_ORIGINS must contain exact HTTPS origins without paths or wildcards."
                )
        return list(dict.fromkeys(origins))

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
