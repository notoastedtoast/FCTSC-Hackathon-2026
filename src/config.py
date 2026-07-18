"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv


DEFAULT_DATABASE_PATH: Final[Path] = Path.cwd() / "app.db"


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is unavailable."""


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    google_model: str
    database_path: str = str(DEFAULT_DATABASE_PATH)


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

    return Settings(
        google_api_key=api_key,
        google_model=model,
        database_path=os.getenv("DATABASE_PATH") or str(DEFAULT_DATABASE_PATH),
    )
