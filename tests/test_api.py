import os
from hashlib import sha256
import unittest
from unittest.mock import patch

import httpx
from dotenv import load_dotenv
import tests._logging  # noqa: F401

from src.analyzer import AnalysisError, ScamAnalyzer
from src.characters import CharacterSpec
from src.config import DEFAULT_GOOGLE_MODEL, Settings
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
    async def test_lifespan_builds_repository_from_postgresql_url(self) -> None:
        database_url = "postgresql://test:test@localhost:5432/scamcheck"
        repository = AnalysisRepository(":memory:")
        analyzer = StubAnalyzer()
        app = create_app(
            settings=Settings(
                google_api_key="test-key",
                google_model="gemini-test",
                database_url=database_url,
            ),
            analyzer=analyzer,
        )

        with patch("src.main.AnalysisRepository", return_value=repository) as factory:
            async with app.router.lifespan_context(app):
                self.assertIs(app.state.repository, repository)

        factory.assert_called_once_with(database_url)

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

    async def test_analyze_initializes_services_without_lifespan_startup(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
                confidence=0.2,
                reasoning="Ordinary conversation.",
                scenarios=scenario_assessments(),
            )
        )
        repository = AnalysisRepository(":memory:")
        self.addCleanup(repository.close)
        app = create_app()

        with (
            patch(
                "src.main.load_settings",
                return_value=Settings(
                    google_api_key="test-key",
                    google_model="gemini-test",
                    database_url=":memory:",
                ),
            ),
            patch("src.main.ScamAnalyzer", return_value=analyzer),
            patch("src.main.AnalysisRepository", return_value=repository),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                response = await client.post("/analyze", json={"text": "Hello from Hanoi"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detective"]["risk_level"], "safe")
        self.assertEqual(analyzer.requests, [AnalyzeRequest(text="Hello from Hanoi")])

    async def test_root_serves_integrated_frontend_and_logo(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            page = await client.get("/")
            logo = await client.get("/scamcheck-logo.png")
            detective_avatar = await client.get("/detective-avatar.png")
            psychologist_avatar = await client.get("/psychologist-avatar.png")
            styles = await client.get("/styles.css")
            script = await client.get("/app.js")
            offline_analyzer = await client.get("/offline-analyzer.js")
            service_worker = await client.get("/service-worker.js")
            health = await client.get("/health")

        self.assertEqual(page.status_code, 200)
        self.assertIn("text/html", page.headers["content-type"])
        self.assertIn("ScamCheck - Kiểm tra nội dung đáng ngờ", page.text)
        self.assertEqual(logo.status_code, 200)
        self.assertEqual(logo.headers["content-type"], "image/png")
        self.assertTrue(logo.content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(detective_avatar.status_code, 200)
        self.assertEqual(detective_avatar.headers["content-type"], "image/png")
        self.assertTrue(detective_avatar.content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(psychologist_avatar.status_code, 200)
        self.assertEqual(psychologist_avatar.headers["content-type"], "image/png")
        self.assertTrue(psychologist_avatar.content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(styles.status_code, 200)
        self.assertIn("text/css", styles.headers["content-type"])
        self.assertIn(":root", styles.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("text/javascript", script.headers["content-type"])
        self.assertIn("requestJson('/analyze'", script.text)
        self.assertIn("'X-ScamCheck-Request-ID'", script.text)
        self.assertEqual(offline_analyzer.status_code, 200)
        self.assertIn("text/javascript", offline_analyzer.headers["content-type"])
        self.assertIn("ScamCheckOffline", offline_analyzer.text)
        self.assertEqual(service_worker.status_code, 200)
        self.assertIn("text/javascript", service_worker.headers["content-type"])
        self.assertEqual(service_worker.headers["service-worker-allowed"], "/")
        self.assertEqual(service_worker.headers["cache-control"], "no-cache")
        self.assertIn('"/offline-analyzer.js"', service_worker.text)
        self.assertNotIn("/analyze", service_worker.text)
        self.assertEqual(health.json(), {"status": "ok"})

    async def test_character_chat_endpoint_is_not_exposed(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        self.assertFalse(
            any("/characters/" in path for path in app.openapi()["paths"])
        )
        self.assertNotIn("/guide/", app.openapi()["paths"])

    async def test_manual_link_inspection_endpoint_is_not_exposed(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        self.assertNotIn("/links/inspect", app.openapi()["paths"])

    async def test_scam_catalog_lists_filters_and_returns_details(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            all_types = await client.get("/scam-types")
            bank_types = await client.get("/scam-types", params={"group": "fake_bank"})
            detail = await client.get("/scam-types/bank-account-lock")
            missing = await client.get("/scam-types/not-found")

        self.assertEqual(all_types.status_code, 200)
        self.assertGreaterEqual(len(all_types.json()), 12)
        self.assertEqual(bank_types.status_code, 200)
        self.assertGreaterEqual(len(bank_types.json()), 2)
        self.assertTrue(all(item["group"] == "fake_bank" for item in bank_types.json()))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], "bank-account-lock")
        self.assertTrue(detail.json()["example_message"])
        self.assertEqual(missing.status_code, 404)

    async def test_practice_api_is_not_exposed(self) -> None:
        analyzer = StubAnalyzer()
        app = create_app(analyzer=analyzer, repository=self.repository)

        self.assertFalse(
            any(path.startswith("/practice-messages") for path in app.openapi()["paths"])
        )

    async def test_get_analysis_returns_stored_record_by_id(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="suspicious",
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
                risk_level="dangerous",
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
        self.assertEqual(response_payload["detective"]["risk_level"], "dangerous")
        self.assertEqual(response_payload["detective"]["confidence"], 0.91)
        self.assertEqual(
            response_payload["detective"]["scenarios"],
            scenario_payload("credential_or_otp_theft"),
        )
        self.assertEqual(response_payload["character"]["title"], "Cô tâm lý")
        self.assertEqual(response_payload["usage"], {"used": 2, "limit": 10})
        self.assertEqual(response_payload["deterministic_findings"], [])
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

    async def test_repeated_request_id_replays_without_another_ai_call(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
                confidence=0.12,
                reasoning="Ordinary conversation.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)
        headers = {"X-ScamCheck-Request-ID": "retry-request-0001"}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            first = await client.post(
                "/analyze", json={"text": "Hello from Hanoi"}, headers=headers
            )
            replay = await client.post(
                "/analyze", json={"text": "Hello from Hanoi"}, headers=headers
            )
            history = await client.get("/session/ai-calls")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(analyzer.events, ["detective"])
        self.assertEqual(history.json()["usage"], {"used": 1, "limit": 10})

    async def test_request_id_cannot_be_reused_for_different_content(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
                confidence=0.12,
                reasoning="Ordinary conversation.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)
        headers = {"X-ScamCheck-Request-ID": "retry-request-0002"}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            first = await client.post(
                "/analyze", json={"text": "First ordinary message"}, headers=headers
            )
            conflict = await client.post(
                "/analyze", json={"text": "Different ordinary message"}, headers=headers
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.headers["x-scamcheck-request-status"], "conflict"
        )
        self.assertEqual(analyzer.events, ["detective"])

    async def test_pending_request_id_returns_retryable_conflict_without_ai_call(
        self,
    ) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
                confidence=0.12,
                reasoning="Ordinary conversation.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)
        payload = AnalyzeRequest(text="Pending ordinary message", source="web")
        request_id = "retry-request-0003"
        request_hash = sha256(payload.model_dump_json().encode("utf-8")).hexdigest()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            await client.get("/health")
            session_id = client.cookies["scamcheck_session"]
            await self.repository.claim_analysis_request(
                session_id, request_id, request_hash
            )
            response = await client.post(
                "/analyze",
                json=payload.model_dump(),
                headers={"X-ScamCheck-Request-ID": request_id},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.headers["retry-after"], "2")
        self.assertEqual(response.headers["x-scamcheck-request-status"], "pending")
        self.assertEqual(analyzer.events, [])

    async def test_session_quota_stops_new_calls_and_exposes_usage(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="dangerous",
                confidence=0.8,
                reasoning="The sender requests an OTP.",
                scenarios=scenario_assessments("credential_or_otp_theft"),
            )
        )
        app = create_app(
            settings=Settings(
                google_api_key="test-key",
                google_model="gemini-test",
                ai_session_call_limit=2,
            ),
            analyzer=analyzer,
            repository=self.repository,
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            first = await client.post(
                "/analyze", json={"text": "Send your OTP now"}
            )
            blocked = await client.post(
                "/analyze", json={"text": "Send your OTP again"}
            )
            history = await client.get("/session/ai-calls")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["usage"], {"used": 2, "limit": 2})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("hết lượt", blocked.json()["detail"])
        self.assertEqual(blocked.headers["x-ai-calls-used"], "2")
        self.assertEqual(blocked.headers["x-ai-calls-limit"], "2")
        self.assertEqual(analyzer.events, ["detective", "character"])
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["usage"], {"used": 2, "limit": 2})
        calls = history.json()["calls"]
        self.assertEqual([call["kind"] for call in calls], ["detective", "character"])
        self.assertTrue(all(call["success"] for call in calls))
        self.assertTrue(all(call["summary"] for call in calls))
        with self.repository._connect() as connection:
            pending_claims = connection.execute(
                "SELECT COUNT(*) FROM analysis_requests WHERE status = 'pending'"
            ).fetchone()
        self.assertEqual(pending_claims, (0,))

    async def test_last_available_call_keeps_detective_and_skips_character(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="dangerous",
                confidence=0.8,
                reasoning="The sender requests an OTP.",
                scenarios=scenario_assessments("credential_or_otp_theft"),
            )
        )
        app = create_app(
            settings=Settings(
                google_api_key="test-key",
                google_model="gemini-test",
                ai_session_call_limit=1,
            ),
            analyzer=analyzer,
            repository=self.repository,
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/analyze", json={"text": "Send your OTP now"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["usage"], {"used": 1, "limit": 1})
        self.assertIsNone(response.json()["character"])
        self.assertIn("hết lượt AI", response.json()["character_notice"])
        self.assertEqual(analyzer.events, ["detective"])

    async def test_safe_provider_result_is_authoritative_and_skips_character(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
                confidence=0.99,
                reasoning="The provider classified the message as safe.",
                scenarios=scenario_assessments("credential_or_otp_theft"),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/analyze",
                json={"text": "Send your OTP and transfer money immediately"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detective"]["risk_level"], "safe")
        self.assertIsNone(response.json()["character"])
        self.assertIsNone(response.json()["character_notice"])
        self.assertEqual(analyzer.events, ["detective"])

    async def test_deterministic_findings_support_but_do_not_override_provider(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
                confidence=0.1,
                reasoning="Provider judged the full context safe.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/analyze",
                json={"text": "Vui lòng gửi mã OTP cho tôi để kiểm tra."},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["detective"]["risk_level"], "safe")
        self.assertTrue(payload["deterministic_findings"])
        self.assertIsNone(payload["character"])

    async def test_history_is_session_scoped_cached_and_can_be_hidden(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
                confidence=0.1,
                reasoning="No strong scam signals.",
                scenarios=scenario_assessments(),
            )
        )
        app = create_app(analyzer=analyzer, repository=self.repository)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as owner:
            analyzed = await owner.post(
                "/analyze",
                headers={"X-ScamCheck-Request-ID": "history-request-0001"},
                json={"text": "Lịch họp gia đình lúc 19 giờ tối nay."},
            )
            history = await owner.get("/history/")
            deleted = await owner.delete(f"/history/{analyzed.json()['id']}")
            hidden_history = await owner.get("/history/")

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as stranger:
            stranger_history = await stranger.get("/history/")

        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()), 1)
        self.assertEqual(history.json()[0]["response"], analyzed.json())
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(hidden_history.json(), [])
        self.assertEqual(stranger_history.json(), [])

    async def test_character_failure_keeps_detective_result(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="dangerous",
                confidence=0.8,
                reasoning="The message requests an OTP.",
                scenarios=scenario_assessments("credential_or_otp_theft"),
            ),
            character_error=ValueError("character response was invalid"),
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
            {
                "detail": (
                    "Chưa thể hoàn tất kiểm tra lúc này. "
                    "Bác vui lòng thử lại sau ít phút."
                )
            },
        )
        self.assertEqual(history.json()["usage"], {"used": 1, "limit": 10})
        self.assertFalse(history.json()["calls"][0]["success"])
        await analyzer.aclose()
        self.assertTrue(analyzer.closed)

    async def test_analyze_rejects_invalid_payloads(self) -> None:
        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
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
            async def save_idempotent(self, *args: object, **kwargs: object) -> None:
                raise DatabaseError("database unavailable")

        analyzer = StubAnalyzer(
            result=ScamAnalysis(
                risk_level="safe",
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
    model = os.getenv("GOOGLE_MODEL") or os.getenv("GEMINI_MODEL") or DEFAULT_GOOGLE_MODEL
    if not api_key:
        return None
    return Settings(google_api_key=api_key, google_model=model)


class LiveGeminiApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_uses_live_gemini_api(self) -> None:
        settings = _live_gemini_settings()
        if settings is None:
            self.skipTest("Set GOOGLE_API_KEY or GEMINI_API_KEY to run live Gemini tests")

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
            self.skipTest("Set GOOGLE_API_KEY or GEMINI_API_KEY to run live Gemini tests")

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
            self.skipTest("Set GOOGLE_API_KEY or GEMINI_API_KEY to run live Gemini tests")

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
            self.skipTest("Set GOOGLE_API_KEY or GEMINI_API_KEY to run live Gemini tests")

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
            self.skipTest("Set GOOGLE_API_KEY or GEMINI_API_KEY to run live Gemini tests")

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
