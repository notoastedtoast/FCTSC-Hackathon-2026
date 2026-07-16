import os
import unittest

import httpx
from dotenv import load_dotenv
import tests._logging  # noqa: F401

from src.analyzer import AnalysisError, CharacterError, ScamAnalyzer
from src.characters import CharacterSpec
from src.config import Settings
from src.database import AnalysisRepository, DatabaseError
from src.main import create_app
from src.schemas import (
    AnalyzeRequest,
    CharacterReply,
    DetectiveResult,
    SCAM_SCENARIOS,
    ScamAnalysis,
)
from tests.factories import scenario_assessments, scenario_payload


class StubAnalyzer:
    def __init__(
        self,
        result: ScamAnalysis | None = None,
        error: Exception | None = None,
        character_error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.character_error = character_error
        self.requests: list[AnalyzeRequest] = []
        self.detective_results: list[DetectiveResult] = []
        self.events: list[str] = []
        self.closed = False

    async def analyze(self, request: AnalyzeRequest) -> ScamAnalysis:
        self.events.append("detective")
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    async def respond(
        self,
        character: CharacterSpec,
        detective: DetectiveResult,
    ) -> CharacterReply:
        self.events.append("character")
        self.detective_results.append(detective)
        if self.character_error is not None:
            raise self.character_error
        return CharacterReply(
            character_id=character.character_id,
            title=character.title,
            message="Cô hiểu sự thúc ép này dễ làm bác lo. Bác cứ chậm lại để nhìn rõ chiêu tạo áp lực.",
        )

    async def aclose(self) -> None:
        self.closed = True


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = AnalysisRepository(":memory:")
        self.addCleanup(self.repository.close)

    async def test_health_returns_ok(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        await analyzer.aclose()
        self.assertTrue(analyzer.closed)

    async def test_character_chat_endpoint_is_not_exposed(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        self.assertFalse(
            any("/characters/" in path for path in app.openapi()["paths"])
        )

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
                "indicator_evidence": [],
                "actions": [
                    "Không trả lời, chuyển tiền hoặc cung cấp thông tin nhạy cảm.",
                    "Tự liên hệ tổ chức hoặc người gửi qua kênh chính thức.",
                    "Lưu lại tin nhắn và nhờ người tin cậy kiểm tra nếu còn phân vân.",
                ],
                "main_categories": ["authority_or_business_impersonation"],
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
                "id": response_payload["id"],
                "detective": {
                    "confidence": 0.91,
                    "reasoning": "The message creates urgency and requests credentials.",
                    "indicators": ["Urgency", "Credential request"],
                    "indicator_evidence": [],
                    "actions": [
                        "Không trả lời, chuyển tiền hoặc cung cấp thông tin nhạy cảm.",
                        "Tự liên hệ tổ chức hoặc người gửi qua kênh chính thức.",
                        "Lưu lại tin nhắn và nhờ người tin cậy kiểm tra nếu còn phân vân.",
                    ],
                    "main_categories": ["credential_or_otp_theft"],
                    "scenarios": scenario_payload("credential_or_otp_theft"),
                    "title": "Thám tử",
                    "risk_level": "dangerous",
                },
                "character": {
                    "character_id": "calming-guide",
                    "title": "Cô tâm lý",
                    "message": "Cô hiểu sự thúc ép này dễ làm bác lo. Bác cứ chậm lại để nhìn rõ chiêu tạo áp lực.",
                },
                "character_notice": None,
                "usage": {"used": 2, "limit": 10},
            },
        )
        self.assertEqual(
            analyzer.requests,
            [AnalyzeRequest(text="Act now and send your password", source="sms")],
        )
        self.assertEqual(analyzer.events, ["detective", "character"])
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

    async def test_session_quota_stops_new_ai_calls_and_exposes_audit_history(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                confidence=0.8,
                reasoning="The sender requests an OTP.",
                scenarios=scenario_assessments("credential_or_otp_theft"),
            )
        )
        settings = Settings(
            google_api_key="test-key",
            google_model="gemini-test",
            ai_session_call_limit=2,
        )
        app = create_app(settings=settings, analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            first = await client.post("/analyze", json={"text": "Send your OTP now"})
            blocked = await client.post("/analyze", json={"text": "Another message"})
            history = await client.get("/session/ai-calls")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["usage"], {"used": 2, "limit": 2})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("call limit", blocked.json()["detail"])
        self.assertEqual(blocked.headers["x-ai-calls-used"], "2")
        self.assertEqual(analyzer.events, ["detective", "character"])
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["usage"], {"used": 2, "limit": 2})
        calls = history.json()["calls"]
        self.assertEqual([call["kind"] for call in calls], ["detective", "character"])
        self.assertEqual([call["input_length"] for call in calls], [17, 17])
        self.assertTrue(all(call["success"] for call in calls))
        self.assertTrue(all(call["summary"] for call in calls))

    async def test_safe_analysis_does_not_call_character(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                confidence=0.02,
                reasoning="Ordinary conversation.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/analyze", json={"text": "Lunch at noon?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detective"]["risk_level"], "safe")
        self.assertIsNone(response.json()["character"])
        self.assertIsNone(response.json()["character_notice"])
        self.assertEqual(analyzer.events, ["detective"])

    async def test_character_failure_keeps_detective_result(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                confidence=0.8,
                reasoning="The message requests an OTP.",
                scenarios=scenario_assessments("credential_or_otp_theft"),
            ),
            character_error=CharacterError("unavailable"),
        )
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/analyze", json={"text": "Send your OTP now"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detective"]["risk_level"], "dangerous")
        self.assertIsNone(response.json()["character"])
        self.assertIn("bác", response.json()["character_notice"])
        self.assertEqual(analyzer.events, ["detective", "character"])

    async def test_analyze_converts_provider_failure_to_502(self) -> None:
        analyzer = StubAnalyzer(error=AnalysisError("provider unavailable"))
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/analyze", json={"text": "Hello"})
            history = await client.get("/session/ai-calls")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"detail": "Unable to complete scam analysis at this time"},
        )
        self.assertEqual(history.json()["usage"], {"used": 1, "limit": 10})
        self.assertFalse(history.json()["calls"][0]["success"])
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
            async def save(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str:
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
            detective = payload["detective"]
            self.assertIsInstance(detective["confidence"], float)
            self.assertGreaterEqual(detective["confidence"], 0.0)
            self.assertLessEqual(detective["confidence"], 1.0)
            self.assertIsInstance(detective["reasoning"], str)
            self.assertGreater(len(detective["reasoning"].strip()), 0)
            self.assertIsInstance(detective["indicators"], list)
            self.assertGreater(len(detective["indicators"]), 0)
            self.assertIsInstance(detective["main_categories"], list)
            self.assertLessEqual(len(detective["main_categories"]), 4)
            self.assertEqual(len(detective["scenarios"]), 12)
            self.assertEqual(
                [assessment["scenario"] for assessment in detective["scenarios"]],
                list(SCAM_SCENARIOS),
            )
            self.assertEqual(detective["title"], "Thám tử")
            if detective["risk_level"] != "safe":
                self.assertTrue(payload["character"] or payload["character_notice"])
        finally:
            await analyzer.aclose()

    async def test_analyze_rejects_invalid_payloads_with_live_gemini_api(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY/GEMINI_API_KEY and GOOGLE_MODEL/GEMINI_MODEL to run live Gemini tests")

        analyzer = ScamAnalyzer(settings)
        app = create_app(analyzer=analyzer, repository=AnalysisRepository(":memory:"))

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

    async def test_live_normal_sms_is_safe_without_character_follow_up(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY/GEMINI_API_KEY and GOOGLE_MODEL/GEMINI_MODEL to run live Gemini tests")

        analyzer = ScamAnalyzer(settings)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    create_app(analyzer=analyzer, repository=AnalysisRepository(":memory:"))
                ),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/analyze",
                    json={"text": "Hey, are we still meeting for coffee at 3?", "source": "sms"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["detective"]["risk_level"], "safe")
            self.assertIsNone(payload["character"])
        finally:
            await analyzer.aclose()

    async def test_live_normal_email_is_safe_without_character_follow_up(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY/GEMINI_API_KEY and GOOGLE_MODEL/GEMINI_MODEL to run live Gemini tests")

        analyzer = ScamAnalyzer(settings)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    create_app(analyzer=analyzer, repository=AnalysisRepository(":memory:"))
                ),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "text": "Hi team, the meeting notes are attached. Thanks, Linh.",
                        "source": "email",
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["detective"]["risk_level"], "safe")
            self.assertIsNone(payload["character"])
        finally:
            await analyzer.aclose()

    async def test_live_ambiguous_delivery_message_stays_in_allowed_range(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY/GEMINI_API_KEY and GOOGLE_MODEL/GEMINI_MODEL to run live Gemini tests")

        analyzer = ScamAnalyzer(settings)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    create_app(analyzer=analyzer, repository=AnalysisRepository(":memory:"))
                ),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "text": "Your package is delayed; view the status at https://shipping-update.example/status.",
                        "source": "email",
                    },
                )

            self.assertEqual(response.status_code, 200)
            risk_level = response.json()["detective"]["risk_level"]
            self.assertIn(risk_level, {"suspicious", "dangerous"})
        finally:
            await analyzer.aclose()


if __name__ == "__main__":
    unittest.main()
