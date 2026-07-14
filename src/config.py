"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is unavailable."""


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    google_model: str


def load_settings() -> Settings:
    """Load .env values, then validate the settings required to serve requests."""
    load_dotenv()

    # GEMINI_API_KEY keeps the original prototype's configuration working.
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = os.getenv("GOOGLE_MODEL") or os.getenv("GEMINI_MODEL")
    missing = []
    if not api_key:
        missing.append("GOOGLE_API_KEY (or GEMINI_API_KEY)")
    if not model:
        missing.append("GOOGLE_MODEL (or GEMINI_MODEL)")

    if missing:
        raise ConfigurationError(
            "Missing required configuration: " + ", ".join(missing) + ". "
            "Set these values in .env or the environment."
        )

    return Settings(google_api_key=api_key, google_model=model)
