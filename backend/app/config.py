from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    gnani_api_key: str = ""
    gnani_language_code: str = "ml-IN,en-IN"
    openai_api_key: str = ""
    openai_model: str = ""
    demo_access_code: str = ""
    allow_insecure_local: bool = False
    max_sessions: int = Field(default=8, ge=1, le=100)
    session_ttl_seconds: int = Field(default=14400, ge=60, le=86400)
    correction_grace_seconds: float = Field(default=1.2, ge=0.2, le=10)

    @property
    def model_ready(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)
