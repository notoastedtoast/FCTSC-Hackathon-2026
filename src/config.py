"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from typing import Final

from dotenv import load_dotenv


DEFAULT_AI_SESSION_CALL_LIMIT: Final[int] = 10
DEFAULT_DATABASE_URL: Final[str] = "sqlite:///app.db"
DEFAULT_GOOGLE_MODEL: Final[str] = "gemini-3.5-flash"
DEFAULT_GOOGLE_FALLBACK_MODEL: Final[str] = "gemini-3.1-flash-lite"
DEFAULT_GROQ_MODEL: Final[str] = "openai/gpt-oss-20b"


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is unavailable."""


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    google_model: str
    google_fallback_model: str = DEFAULT_GOOGLE_FALLBACK_MODEL
    groq_api_key: str | None = None
    groq_model: str = DEFAULT_GROQ_MODEL
    database_url: str = ""
    ai_session_call_limit: int = DEFAULT_AI_SESSION_CALL_LIMIT


def load_database_url() -> str:
    """Load the configured database URL or use a local SQLite database."""
    load_dotenv()
    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
        or DEFAULT_DATABASE_URL
    )
    if not database_url.startswith(("postgresql://", "postgres://", "sqlite:///")):
        raise ConfigurationError(
            "DATABASE_URL must be a PostgreSQL or SQLite connection string"
        )
    return database_url


def load_settings() -> Settings:
    """Load .env values, then validate the settings required to serve requests."""
    load_dotenv()

    # GEMINI_API_KEY keeps the original prototype's configuration working.
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = (
        os.getenv("GOOGLE_MODEL")
        or os.getenv("GEMINI_MODEL")
        or DEFAULT_GOOGLE_MODEL
    )
    fallback_model = (
        os.getenv("GOOGLE_FALLBACK_MODEL")
        or os.getenv("GEMINI_FALLBACK_MODEL")
        or DEFAULT_GOOGLE_FALLBACK_MODEL
    )
    if not api_key:
        raise ConfigurationError(
            "Missing required configuration: GOOGLE_API_KEY (or GEMINI_API_KEY). "
            "Set these values in .env or the environment."
        )

    raw_call_limit = os.getenv("AI_SESSION_CALL_LIMIT")
    try:
        call_limit = (
            int(raw_call_limit)
            if raw_call_limit
            else DEFAULT_AI_SESSION_CALL_LIMIT
        )
    except ValueError as exc:
        raise ConfigurationError("AI_SESSION_CALL_LIMIT must be an integer") from exc
    if call_limit < 1:
        raise ConfigurationError("AI_SESSION_CALL_LIMIT must be at least 1")

    return Settings(
        google_api_key=api_key,
        google_model=model,
        google_fallback_model=fallback_model,
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL,
        database_url=load_database_url(),
        ai_session_call_limit=call_limit,
    )
