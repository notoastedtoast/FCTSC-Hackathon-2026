"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv


DEFAULT_DATABASE_PATH: Final[Path] = Path.cwd() / "app.db"
DEFAULT_AI_SESSION_CALL_LIMIT: Final[int] = 10


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is unavailable."""


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    google_model: str
    database_path: str = str(DEFAULT_DATABASE_PATH)
    ai_session_call_limit: int = DEFAULT_AI_SESSION_CALL_LIMIT


def load_database_path() -> str:
    """Load the SQLite path without requiring analysis provider settings."""
    load_dotenv()
    return os.getenv("DATABASE_PATH") or str(DEFAULT_DATABASE_PATH)


def load_settings() -> Settings:
    """Load .env values, then validate the settings required to serve requests."""
    load_dotenv()

    # GEMINI_API_KEY keeps the original prototype's configuration working.
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = os.getenv("GOOGLE_MODEL") or os.getenv("GEMINI_MODEL")
    if not api_key or not model:
        missing = [
            label
            for value, label in (
                (api_key, "GOOGLE_API_KEY (or GEMINI_API_KEY)"),
                (model, "GOOGLE_MODEL (or GEMINI_MODEL)"),
            )
            if not value
        ]
        raise ConfigurationError(
            f"Missing required configuration: {', '.join(missing)}. "
            "Set these values in .env or the environment."
        )

    raw_call_limit = os.getenv("AI_SESSION_CALL_LIMIT")
    try:
        call_limit = int(raw_call_limit) if raw_call_limit else DEFAULT_AI_SESSION_CALL_LIMIT
    except ValueError as exc:
        raise ConfigurationError("AI_SESSION_CALL_LIMIT must be an integer") from exc
    if call_limit < 1:
        raise ConfigurationError("AI_SESSION_CALL_LIMIT must be at least 1")

    return Settings(
        google_api_key=api_key,
        google_model=model,
        database_path=os.getenv("DATABASE_PATH") or str(DEFAULT_DATABASE_PATH),
        ai_session_call_limit=call_limit,
    )
