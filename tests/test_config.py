import os
import unittest
from unittest.mock import patch

from src.schema import (
    DEFAULT_AI_SESSION_CALL_LIMIT,
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    Settings,
)


class ConfigurationTests(unittest.TestCase):
    def test_missing_optional_environment_values_use_safe_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_environment()

        self.assertEqual(settings.base_url, DEFAULT_GEMINI_BASE_URL)
        self.assertEqual(settings.api_keys, [])
        self.assertEqual(settings.model, DEFAULT_GEMINI_MODEL)
        self.assertEqual(
            settings.ai_session_call_limit,
            DEFAULT_AI_SESSION_CALL_LIMIT,
        )

    def test_environment_overrides_are_trimmed_and_preserved(self) -> None:
        environment = {
            "BASE_URL": "https://example.test/v1/",
            "GOOGLE_API_KEY": " first-key, second-key ",
            "GOOGLE_MODEL": "gemini-test",
            "AI_SESSION_CALL_LIMIT": "7",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_environment()

        self.assertEqual(settings.base_url, environment["BASE_URL"])
        self.assertEqual(settings.api_keys, ["first-key", "second-key"])
        self.assertEqual(settings.model, "gemini-test")
        self.assertEqual(settings.ai_session_call_limit, 7)


if __name__ == "__main__":
    unittest.main()
