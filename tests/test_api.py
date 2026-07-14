import os
import unittest

import httpx
from dotenv import load_dotenv
import tests._logging  # noqa: F401

from src.analyzer import AnalysisError, ScamAnalyzer
from src.config import Settings
from src.database import AnalysisRepository, DatabaseError
from src.main import create_app
from src.schemas import (
    AnalyzeRequest,
    SCAM_SCENARIOS,
    ScamAnalysis,
    ScamScenarioAssessment,
)


def scenario_assessments(
    detected_scenario: str | None = None,
) -> list[ScamScenarioAssessment]:
    return [
        ScamScenarioAssessment(
            scenario=scenario,
            detected=scenario == detected_scenario,
            confidence=0.9 if scenario == detected_scenario else 0.05,
            evidence=(
                "Có bằng chứng cụ thể."
                if scenario == detected_scenario
                else "Không có bằng chứng."
            ),
        )
        for scenario in SCAM_SCENARIOS
    ]


def scenario_payload(detected_scenario: str | None = None) -> list[dict[str, object]]:
    return [
        assessment.model_dump(mode="json")
        for assessment in scenario_assessments(detected_scenario)
    ]


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
    def setUp(self) -> None:
        self.repository = AnalysisRepository(":memory:")
        self.addCleanup(self.repository.close)

    async def test_health_returns_ok(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)
        app.state.analyzer = analyzer

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        await analyzer.aclose()
        self.assertTrue(analyzer.closed)

    async def test_get_analysis_returns_stored_record_by_id(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                confidence=0.84,
                reasoning="The sender impersonates a bank.",
                indicators=["Impersonation"],
                scenarios=scenario_assessments("authority_or_business_impersonation"),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            create_response = await client.post(
                "/analyze",
                json={"text": "Your bank account is locked", "source": "email"},
            )
            analysis_id = create_response.json()["id"]
            response = await client.get(f"/analyses/{analysis_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {key: value for key, value in response.json().items() if key != "created_at"},
            {
                "confidence": 0.84,
                "reasoning": "The sender impersonates a bank.",
                "indicators": ["Impersonation"],
                "scenarios": scenario_payload("authority_or_business_impersonation"),
                "id": analysis_id,
                "text": "Your bank account is locked",
                "source": "email",
            },
        )
        self.assertTrue(response.json()["created_at"])

    async def test_get_analysis_returns_404_for_unknown_id(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(f"/analyses/{'f' * 32}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Scam analysis not found"})

    async def test_analyze_delegates_request_and_returns_analysis(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                confidence=0.91,
                reasoning="The message creates urgency and requests credentials.",
                indicators=["Urgency", "Credential request"],
                scenarios=scenario_assessments("credential_or_otp_theft"),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)
        app.state.analyzer = analyzer

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/analyze",
                json={"text": "Act now and send your password", "source": "sms"},
            )

        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        self.assertRegex(response_payload["id"], r"^[0-9a-f]{32}$")
        self.assertEqual(
            response_payload,
            {
                "confidence": 0.91,
                "reasoning": "The message creates urgency and requests credentials.",
                "indicators": ["Urgency", "Credential request"],
                "scenarios": scenario_payload("credential_or_otp_theft"),
                "id": response_payload["id"],
            },
        )
        self.assertEqual(
            analyzer.requests,
            [AnalyzeRequest(text="Act now and send your password", source="sms")],
        )
        with self.repository._connect() as connection:
            with connection:
                stored = connection.execute(
                    """
                    SELECT message_text, source, confidence, reasoning, indicators
                    FROM analyses
                    WHERE id = ?
                    """,
                    (response.json()["id"],),
                ).fetchone()
        self.assertEqual(
            stored,
            (
                "Act now and send your password",
                "sms",
                0.91,
                "The message creates urgency and requests credentials.",
                '["Urgency", "Credential request"]',
            ),
        )
        await analyzer.aclose()
        self.assertTrue(analyzer.closed)

    async def test_analyze_converts_provider_failure_to_502(self) -> None:
        analyzer = StubAnalyzer(error=AnalysisError("provider unavailable"))
        app = create_app(analyzer=analyzer, repository=self.repository)
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
            result=ScamAnalysis(
                confidence=0.1,
                reasoning="Looks safe.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)
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

    async def test_analyze_converts_database_failure_to_503(self) -> None:
        class FailingRepository(AnalysisRepository):
            async def save(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> int:
                raise DatabaseError("database unavailable")

        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                confidence=0.2,
                reasoning="No strong scam signals.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(
            analyzer=analyzer,
            repository=FailingRepository(":memory:"),
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/analyze", json={"text": "Hello"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Unable to save scam analysis at this time"},
        )


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
        app = create_app(analyzer=analyzer, repository=AnalysisRepository(":memory:"))
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
            self.assertEqual(len(payload["scenarios"]), 12)
            self.assertEqual(
                [assessment["scenario"] for assessment in payload["scenarios"]],
                list(SCAM_SCENARIOS),
            )
        finally:
            await analyzer.aclose()

    async def test_analyze_rejects_invalid_payloads_with_live_gemini_api(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY/GEMINI_API_KEY and GOOGLE_MODEL/GEMINI_MODEL to run live Gemini tests")

        analyzer = ScamAnalyzer(settings)
        app = create_app(analyzer=analyzer, repository=AnalysisRepository(":memory:"))
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
