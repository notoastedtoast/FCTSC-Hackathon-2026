import os
import unittest
from unittest.mock import patch

from src.config import (
    ConfigurationError,
    DEFAULT_AI_SESSION_CALL_LIMIT,
    DEFAULT_DATABASE_URL,
    DEFAULT_GOOGLE_FALLBACK_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_GROQ_MODEL,
    load_database_url,
    load_settings,
)


class ConfigurationTests(unittest.TestCase):
    def test_settings_default_to_local_sqlite_when_database_is_unset(self) -> None:
        with (
            patch("src.config.load_dotenv"),
            patch.dict(
                os.environ,
                {"GOOGLE_API_KEY": "test-key"},
                clear=True,
            ),
        ):
            settings = load_settings()

        self.assertEqual(settings.database_url, DEFAULT_DATABASE_URL)

    def test_session_call_limit_defaults_and_accepts_positive_override(self) -> None:
        base_environment = {
            "GOOGLE_API_KEY": "test-key",
            "GOOGLE_MODEL": "gemini-test",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/scamcheck",
        }
        with (
            patch("src.config.load_dotenv"),
            patch.dict(os.environ, base_environment, clear=True),
        ):
            default_settings = load_settings()
        with (
            patch("src.config.load_dotenv"),
            patch.dict(
                os.environ,
                {**base_environment, "AI_SESSION_CALL_LIMIT": "7"},
                clear=True,
            ),
        ):
            custom_settings = load_settings()

        self.assertEqual(
            default_settings.ai_session_call_limit,
            DEFAULT_AI_SESSION_CALL_LIMIT,
        )
        self.assertEqual(custom_settings.ai_session_call_limit, 7)

    def test_session_call_limit_rejects_invalid_values(self) -> None:
        for value in ("0", "-1", "not-a-number"):
            with self.subTest(value=value):
                with (
                    patch("src.config.load_dotenv"),
                    patch.dict(
                        os.environ,
                        {
                            "GOOGLE_API_KEY": "test-key",
                            "GOOGLE_MODEL": "gemini-test",
                            "DATABASE_URL": "postgresql://test:test@localhost:5432/scamcheck",
                            "AI_SESSION_CALL_LIMIT": value,
                        },
                        clear=True,
                    ),
                ):
                    with self.assertRaises(ConfigurationError):
                        load_settings()

    def test_database_url_accepts_postgresql_sqlite_and_local_default(self) -> None:
        with (
            patch("src.config.load_dotenv"),
            patch.dict(
                os.environ,
                {"SUPABASE_DB_URL": "postgres://test:test@localhost/postgres"},
                clear=True,
            ),
        ):
            database_url = load_database_url()

        self.assertEqual(database_url, "postgres://test:test@localhost/postgres")

        for environment, expected in (
            ({}, DEFAULT_DATABASE_URL),
            ({"DATABASE_URL": "sqlite:///custom.db"}, "sqlite:///custom.db"),
        ):
            with self.subTest(environment=environment):
                with (
                    patch("src.config.load_dotenv"),
                    patch.dict(os.environ, environment, clear=True),
                ):
                    self.assertEqual(load_database_url(), expected)

        with (
            patch("src.config.load_dotenv"),
            patch.dict(
                os.environ,
                {"DATABASE_URL": "mysql://test:test@localhost/scamcheck"},
                clear=True,
            ),
        ):
            with self.assertRaises(ConfigurationError):
                load_database_url()

    def test_model_uses_documented_default(self) -> None:
        with (
            patch("src.config.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "GEMINI_API_KEY": "test-key",
                    "DATABASE_URL": "postgresql://test:test@localhost/postgres",
                },
                clear=True,
            ),
        ):
            settings = load_settings()

        self.assertEqual(settings.google_model, DEFAULT_GOOGLE_MODEL)
        self.assertEqual(
            settings.google_fallback_model, DEFAULT_GOOGLE_FALLBACK_MODEL
        )
        self.assertEqual(settings.groq_model, DEFAULT_GROQ_MODEL)
        self.assertIsNone(settings.groq_api_key)

    def test_provider_fallbacks_accept_environment_overrides(self) -> None:
        with (
            patch("src.config.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "test-key",
                    "GOOGLE_MODEL": "gemini-primary",
                    "GOOGLE_FALLBACK_MODEL": "gemini-secondary",
                    "GROQ_API_KEY": "groq-test-key",
                    "GROQ_MODEL": "groq-test-model",
                    "DATABASE_URL": "postgresql://test:test@localhost/postgres",
                },
                clear=True,
            ),
        ):
            settings = load_settings()

        self.assertEqual(settings.google_model, "gemini-primary")
        self.assertEqual(settings.google_fallback_model, "gemini-secondary")
        self.assertEqual(settings.groq_api_key, "groq-test-key")
        self.assertEqual(settings.groq_model, "groq-test-model")


if __name__ == "__main__":
    unittest.main()
