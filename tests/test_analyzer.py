import unittest
import json

import httpx

from src.analyzer import AnalysisError, ScamAnalyzer
from src.config import Settings
from src.schemas import AnalyzeRequest


class AnalyzerTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_parses_structured_json_from_gemini_response(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertIn(":generateContent", str(request.url))
            self.assertEqual(request.headers.get("x-goog-api-key"), "test-key")
            payload = json.loads(request.content.decode("utf-8"))
            generation_config = payload["generationConfig"]
            self.assertEqual(generation_config["responseMimeType"], "application/json")
            self.assertIn("responseSchema", generation_config)
            self.assertEqual(generation_config["temperature"], 0)
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": (
                                            '{"confidence":0.91,'
                                            '"reasoning":"The message pressures the user to act quickly.",'
                                            '"indicators":["Urgency","Credential request"]}'
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://generativelanguage.googleapis.com/v1beta/",
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(google_api_key="test-key", google_model="gemini-test"),
                client=client,
            )
            result = await analyzer.analyze(
                AnalyzeRequest(text="Act now and send your password", source="sms")
            )

        self.assertEqual(result.confidence, 0.91)
        self.assertEqual(result.indicators, ["Urgency", "Credential request"])

    async def test_analyze_raises_for_missing_text_content(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"candidates": [{"content": {"parts": [{}]}}]})
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://generativelanguage.googleapis.com/v1beta/",
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(google_api_key="test-key", google_model="gemini-test"),
                client=client,
            )
            with self.assertRaises(AnalysisError):
                await analyzer.analyze(AnalyzeRequest(text="hello"))
