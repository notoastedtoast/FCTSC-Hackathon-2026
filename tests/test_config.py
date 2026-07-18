import os
import unittest
from unittest.mock import patch

from src.config import (
    ConfigurationError,
    DEFAULT_AI_SESSION_CALL_LIMIT,
    load_settings,
)


class ConfigurationTests(unittest.TestCase):
    def test_session_call_limit_defaults_and_accepts_positive_override(self) -> None:
        base_environment = {
            "GOOGLE_API_KEY": "test-key",
            "GOOGLE_MODEL": "gemini-test",
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
                            "AI_SESSION_CALL_LIMIT": value,
                        },
                        clear=True,
                    ),
                ):
                    with self.assertRaises(ConfigurationError):
                        load_settings()


if __name__ == "__main__":
    unittest.main()
