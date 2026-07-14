import unittest
import json

import httpx
import tests._logging  # noqa: F401

from src.analyzer import AnalysisError, ScamAnalyzer
from src.config import Settings
from src.schemas import AnalyzeRequest, SCAM_SCENARIOS


def scenario_payload(detected_scenario: str | None = None) -> list[dict[str, object]]:
    return [
        {
            "scenario": scenario,
            "detected": scenario == detected_scenario,
            "confidence": 0.9 if scenario == detected_scenario else 0.05,
            "evidence": (
                "Có bằng chứng cụ thể."
                if scenario == detected_scenario
                else "Không có bằng chứng."
            ),
        }
        for scenario in SCAM_SCENARIOS
    ]


class AnalyzerTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_parses_structured_json_from_gemini_response(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertIn(":generateContent", str(request.url))
            self.assertEqual(request.headers.get("x-goog-api-key"), "test-key")
            payload = json.loads(request.content.decode("utf-8"))
            system_instruction = payload["systemInstruction"]["parts"][0]["text"]
            self.assertIn("digital scam detective", system_instruction)
            self.assertIn("Return concise qualitative findings in Vietnamese", system_instruction)
            generation_config = payload["generationConfig"]
            self.assertEqual(generation_config["responseMimeType"], "application/json")
            self.assertIn("responseSchema", generation_config)
            serialized_schema = json.dumps(generation_config["responseSchema"])
            self.assertNotIn('"$defs"', serialized_schema)
            self.assertNotIn('"$ref"', serialized_schema)
            self.assertNotIn('"enum"', serialized_schema)
            self.assertNotIn('"minItems"', serialized_schema)
            self.assertEqual(generation_config["temperature"], 0)
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "confidence": 0.91,
                                                "reasoning": (
                                                    "The message pressures the user "
                                                    "to act quickly."
                                                ),
                                                "indicators": ["Urgency", "Credential request"],
                                                "scenarios": scenario_payload(
                                                    "credential_or_otp_theft"
                                                ),
                                            }
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
        self.assertEqual(
            [assessment.scenario for assessment in result.scenarios],
            list(SCAM_SCENARIOS),
        )
        self.assertTrue(result.scenarios[3].detected)

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
