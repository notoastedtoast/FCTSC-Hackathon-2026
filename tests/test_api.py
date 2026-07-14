import os
import unittest

import httpx
from dotenv import load_dotenv

from src.analyzer import AnalysisError, ScamAnalyzer
from src.config import Settings
from src.main import create_app
from src.schemas import AnalyzeRequest, ScamAnalysis


class StubAnalyzer:
    def __init__(self, result: ScamAnalysis | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.requests: list[AnalyzeRequest] = []
        self.closed = False

    async def analyze(self, request: AnalyzeRequest) -> ScamAnalysis:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    async def aclose(self) -> None:
        self.closed = True


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_returns_ok(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer)
        app.state.analyzer = analyzer

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        await analyzer.aclose()
        self.assertTrue(analyzer.closed)

    async def test_analyze_delegates_request_and_returns_analysis(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                confidence=0.91,
                reasoning="The message creates urgency and requests credentials.",
                indicators=["Urgency", "Credential request"],
            )
        )
        app = create_app(analyzer=analyzer)
        app.state.analyzer = analyzer

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/analyze",
                json={"text": "Act now and send your password", "source": "sms"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "confidence": 0.91,
                "reasoning": "The message creates urgency and requests credentials.",
                "indicators": ["Urgency", "Credential request"],
            },
        )
        self.assertEqual(
            analyzer.requests,
            [AnalyzeRequest(text="Act now and send your password", source="sms")],
        )
        await analyzer.aclose()
        self.assertTrue(analyzer.closed)

    async def test_analyze_converts_provider_failure_to_502(self) -> None:
        analyzer = StubAnalyzer(error=AnalysisError("provider unavailable"))
        app = create_app(analyzer=analyzer)
        app.state.analyzer = analyzer

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/analyze", json={"text": "Hello"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"detail": "Unable to complete scam analysis at this time"},
        )
        await analyzer.aclose()
        self.assertTrue(analyzer.closed)

    async def test_analyze_rejects_invalid_payloads(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(confidence=0.1, reasoning="Looks safe.")
        )
        app = create_app(analyzer=analyzer)
        app.state.analyzer = analyzer

        invalid_payloads = [
            {},
            {"text": "   "},
            {"text": "x" * 10_001},
            {"text": "hello", "source": "s" * 101},
        ]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            responses = [
                await client.post("/analyze", json=payload) for payload in invalid_payloads
            ]

        self.assertEqual([response.status_code for response in responses], [422] * 4)
        self.assertEqual(analyzer.requests, [])
        await analyzer.aclose()


def _live_gemini_settings() -> Settings | None:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = os.getenv("GOOGLE_MODEL") or os.getenv("GEMINI_MODEL")
    if not api_key or not model:
        return None
    return Settings(google_api_key=api_key, google_model=model)


class LiveGeminiApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_uses_live_gemini_api(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY/GEMINI_API_KEY and GOOGLE_MODEL/GEMINI_MODEL to run live Gemini tests")

        analyzer = ScamAnalyzer(settings)
        app = create_app(analyzer=analyzer)
        app.state.analyzer = analyzer

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "text": "Your account will be suspended today unless you confirm your password immediately.",
                        "source": "sms",
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIsInstance(payload["confidence"], float)
            self.assertGreaterEqual(payload["confidence"], 0.0)
            self.assertLessEqual(payload["confidence"], 1.0)
            self.assertIsInstance(payload["reasoning"], str)
            self.assertGreater(len(payload["reasoning"].strip()), 0)
            self.assertIsInstance(payload["indicators"], list)
            self.assertGreater(len(payload["indicators"]), 0)
        finally:
            await analyzer.aclose()

    async def test_analyze_rejects_invalid_payloads_with_live_gemini_api(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY/GEMINI_API_KEY and GOOGLE_MODEL/GEMINI_MODEL to run live Gemini tests")

        analyzer = ScamAnalyzer(settings)
        app = create_app(analyzer=analyzer)
        app.state.analyzer = analyzer

        invalid_payloads = [
            {},
            {"text": "   "},
            {"text": "x" * 10_001},
            {"text": "hello", "source": "s" * 101},
        ]

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                responses = [
                    await client.post("/analyze", json=payload) for payload in invalid_payloads
                ]

            self.assertEqual([response.status_code for response in responses], [422] * 4)
            self.assertTrue(all("detail" in response.json() for response in responses))
        finally:
            await analyzer.aclose()


if __name__ == "__main__":
    unittest.main()
