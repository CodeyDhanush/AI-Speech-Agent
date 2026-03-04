"""
Enterprise Voice AI Gateway — Configuration
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────
    app_name: str = Field("Enterprise Voice Gateway", env="APP_NAME")
    company_name: str = Field("Acme Corp", env="COMPANY_NAME")
    secret_key: str = Field("change-me-in-production", env="SECRET_KEY")
    port: int = Field(8000, env="PORT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    base_url: str = Field("http://localhost:8000", env="BASE_URL")

    # ── Twilio Removed ────────────────────────────────────

    # ── OpenAI ────────────────────────────────────────────
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")

    # ── Voice ─────────────────────────────────────────────
    whisper_model: str = Field("base", env="WHISPER_MODEL")
    max_call_duration: int = Field(300, env="MAX_CALL_DURATION")   # seconds
    recording_timeout: int = Field(5, env="RECORDING_TIMEOUT")

    # ── Database ──────────────────────────────────────────
    database_url: str = Field("sqlite+aiosqlite:///./voice_gateway.db", env="DATABASE_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
