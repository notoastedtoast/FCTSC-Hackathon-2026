import json
from copy import deepcopy
from unittest.mock import AsyncMock, call, patch

import httpx
from pydantic import ValidationError

from src.schema import Analysis, DETECTIVE, DetectiveAnalysis
from src.wrapper import DELIMITER

from .gemini_test_case import GeminiTestCase
from .mock_gemini import GEMINI_RESPONSE_STRUCTURE


class GeminiWrapperTests(GeminiTestCase):
    async def test_analysis_returns_categorical_risk_level(self) -> None:
        for score, expected in ((0.1, "low"), (0.5, "medium"), (0.9, "high")):
            with self.subTest(score=score):
                analysis = Analysis(
                    success=True,
                    analysis=DetectiveAnalysis(
                        risk_level=score,
                        reasoning="",
                        suggestions=[],
                        excerpts={},
                    ),
                )
                self.assertEqual(analysis.model_dump()["risk_level"], expected)

    async def test_can_generate_same_prompt_more_than_once(self) -> None:
        first = DetectiveAnalysis(
            risk_level=0.1,
            reasoning="First response",
            suggestions=[],
            excerpts={},
        )
        second = DetectiveAnalysis(
            risk_level=0.2,
            reasoning="Second response",
            suggestions=[],
            excerpts={},
        )
        self.mock_gemini.add_analysis(first)
        self.mock_gemini.add_analysis(second)

        first_result = await self.gemini.generate(DETECTIVE, "same message")
        second_result = await self.gemini.generate(DETECTIVE, "same message")

        self.assertEqual(first_result, first)
        self.assertEqual(second_result, second)
        self.assertEqual(len(self.mock_gemini.requests), 2)

    async def test_keeps_trusted_prompt_out_of_user_content(self) -> None:
        expected = DetectiveAnalysis(
            risk_level=0.1,
            reasoning="Safe.",
            suggestions=[],
            excerpts={},
        )
        self.mock_gemini.add_analysis(expected)

        await self.gemini.generate(DETECTIVE, "untrusted message")

        payload = self.mock_gemini.request_json()
        self.assertEqual(
            payload["systemInstruction"]["parts"][0]["text"],
            DETECTIVE.system_instruction + DELIMITER + DETECTIVE.prompt,
        )
        self.assertEqual(
            payload["contents"][0]["parts"][0]["text"],
            "untrusted message",
        )

    async def test_retries_after_rate_limit(self) -> None:
        await self.gemini.close()
        self.gemini = await self.mock_gemini.create_wrapper(
            api_keys=["first-key", "second-key", "third-key"],
        )
        expected = DetectiveAnalysis(
            risk_level=0.9,
            reasoning="Rate-limit retry succeeded",
            suggestions=["Wait before retrying"],
            excerpts={},
        )
        self.mock_gemini.add_response(status_code=429)
        self.mock_gemini.add_response(status_code=429)
        self.mock_gemini.add_analysis(expected)

        with self.assertLogs("src.wrapper", level="WARNING") as logs:
            with patch("src.wrapper.asyncio.sleep", new_callable=AsyncMock) as sleep:
                actual = await self.gemini.generate(DETECTIVE, "message")

        self.assertEqual(actual, expected)
        self.assertEqual(sleep.await_args_list, [call(1), call(2)])
        self.assertEqual(
            [
                record.getMessage()
                for record in logs.records
                if "rate limit" in record.getMessage().lower()
            ],
            [
                "Gemini API rate limit reached for API key index 0",
                "Gemini API rate limit reached for API key index 1",
            ],
        )
        self.assertEqual(len(self.mock_gemini.requests), 3)
        self.assertEqual(
            self.mock_gemini.requests[0].headers["x-goog-api-key"],
            "first-key",
        )
        self.assertEqual(
            self.mock_gemini.requests[1].headers["x-goog-api-key"],
            "second-key",
        )
        self.assertEqual(
            self.mock_gemini.requests[2].headers["x-goog-api-key"],
            "third-key",
        )

    async def test_raises_after_three_rate_limits(self) -> None:
        await self.gemini.close()
        self.gemini = await self.mock_gemini.create_wrapper(
            api_keys=["first-key", "second-key", "third-key"],
        )
        for _ in range(3):
            self.mock_gemini.add_response(status_code=429)

        with patch("src.wrapper.asyncio.sleep", new_callable=AsyncMock) as sleep:
            with self.assertRaises(httpx.HTTPStatusError):
                await self.gemini.generate(DETECTIVE, "message")

        self.assertEqual(sleep.await_args_list, [call(1), call(2), call(4)])
        self.assertEqual(len(self.mock_gemini.requests), 3)
        self.assertEqual(
            [request.headers["x-goog-api-key"] for request in self.mock_gemini.requests],
            ["first-key", "second-key", "third-key"],
        )

    async def test_raises_for_malformed_structured_output(self) -> None:
        response = deepcopy(GEMINI_RESPONSE_STRUCTURE)
        response["candidates"][0]["content"]["parts"].append(
            {
                "text": json.dumps(
                    {
                        "risk_level": 2,
                        "reasoning": "Invalid risk level",
                        "suggestions": [],
                        "excerpts": {},
                    }
                ),
            }
        )
        self.mock_gemini.add_response(response)

        with self.assertRaises(ValidationError):
            await self.gemini.generate(DETECTIVE, "message")

        self.assertEqual(len(self.mock_gemini.requests), 1)
