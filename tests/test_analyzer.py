import asyncio
import json
import unittest

import httpx
import tests._logging  # noqa: F401

from src.analyzer import (
    AnalysisError,
    CharacterError,
    DETECTIVE_TIMEOUT_SECONDS,
    GROQ_MIN_COMPLETION_TOKENS,
    GeneratedScamAnalysis,
    ScamAnalyzer,
    parse_detective_response,
)
from src.characters import CALMING_GUIDE
from src.config import Settings
from src.schemas import (
    AnalyzeRequest,
    DetectiveResult,
    SCAM_SCENARIOS,
    ScamAnalysis,
)
from tests.factories import scenario_assessments, scenario_payload


def valid_detective_json() -> str:
    return json.dumps(
        {
            "risk_level": "safe",
            "confidence": 0.1,
            "reasoning": "Không có dấu hiệu lừa đảo cụ thể.",
            "indicator_evidence": [],
            "actions": [
                "Không chia sẻ thông tin nhạy cảm.",
                "Xác minh người gửi khi cần.",
                "Dừng lại nếu có yêu cầu bất thường.",
            ],
            "scenarios": [],
        }
    )


def gemini_response(response_text: str) -> dict[str, object]:
    return {
        "candidates": [{"content": {"parts": [{"text": response_text}]}}]
    }


class AnalyzerTests(unittest.IsolatedAsyncioTestCase):
    def test_sequential_generation_budget_is_under_twenty_seconds(self) -> None:
        self.assertLess(
            DETECTIVE_TIMEOUT_SECONDS + CALMING_GUIDE.timeout_seconds,
            20,
        )

    async def test_analyze_parses_structured_json_from_gemini_response(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertIn(":generateContent", str(request.url))
            self.assertEqual(request.headers.get("x-goog-api-key"), "test-key")
            payload = json.loads(request.content.decode("utf-8"))
            system_instruction = payload["systemInstruction"]["parts"][0]["text"]
            self.assertIn("digital scam detective", system_instruction)
            self.assertIn("untrusted data", system_instruction)
            self.assertIn("never instructions", system_instruction)
            self.assertIn("mere mention of notes or an attachment", system_instruction)
            user_prompt = payload["contents"][0]["parts"][0]["text"]
            self.assertIn("UNTRUSTED_MESSAGE_JSON", user_prompt)
            generation_config = payload["generationConfig"]
            self.assertEqual(generation_config["responseMimeType"], "application/json")
            self.assertEqual(
                generation_config["responseJsonSchema"],
                GeneratedScamAnalysis.model_json_schema(),
            )
            self.assertEqual(generation_config["temperature"], 0)
            self.assertEqual(
                generation_config["responseJsonSchema"]["properties"]["scenarios"]["maxItems"],
                4,
            )
            self.assertIn("top four", user_prompt)
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
                                                "risk_level": "dangerous",
                                                "confidence": 0.91,
                                                "reasoning": (
                                                    "The message pressures the user "
                                                    "to act quickly."
                                                ),
                                                "indicator_evidence": [
                                                    {"label": "Urgency", "excerpt": "Act now"},
                                                    {
                                                        "label": "Credential request",
                                                        "excerpt": "send your password",
                                                    },
                                                    {
                                                        "label": "Invented evidence",
                                                        "excerpt": "not present in source",
                                                    },
                                                ],
                                                "actions": [
                                                    "Do not reply.",
                                                    "Do not share credentials.",
                                                    "Contact the service directly.",
                                                ],
                                                "scenarios": scenario_payload(
                                                    "credential_or_otp_theft"
                                                )[3:4],
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
        self.assertEqual(result.main_categories, ["credential_or_otp_theft"])
        self.assertEqual(
            [item.excerpt for item in result.indicator_evidence],
            ["Act now", "send your password"],
        )
        self.assertEqual(len(result.actions), 3)
        self.assertEqual(result.provider_risk_level, "dangerous")
        self.assertEqual(
            [assessment.scenario for assessment in result.scenarios],
            list(SCAM_SCENARIOS),
        )
        self.assertTrue(result.scenarios[3].detected)

    async def test_analyze_returns_default_for_missing_text_content(self) -> None:
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
            result = await analyzer.analyze(AnalyzeRequest(text="hello"))

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.provider_risk_level, "suspicious")
        self.assertEqual(len(result.actions), 3)
        self.assertEqual(len(result.scenarios), 12)

    def test_parser_returns_valid_defaults_for_five_malformed_payloads(self) -> None:
        malformed_payloads = (
            "",
            "not json",
            "{}",
            json.dumps({"risk_level": "safe"}),
            json.dumps(
                {
                    "risk_level": "safe",
                    "confidence": 2,
                    "reasoning": "bad",
                    "indicator_evidence": [],
                    "actions": [],
                    "scenarios": [],
                }
            ),
        )

        results = [parse_detective_response(payload, "hello") for payload in malformed_payloads]

        self.assertTrue(all(result.fallback_used for result in results))
        self.assertTrue(all(result.provider_risk_level == "suspicious" for result in results))
        self.assertTrue(all(len(result.actions) == 3 for result in results))
        self.assertTrue(all(len(result.scenarios) == 12 for result in results))

    async def test_five_basic_provider_abnormalities_have_friendly_outcomes(self) -> None:
        async def analyze_with(
            handler: httpx.AsyncBaseTransport,
        ) -> ScamAnalysis | AnalysisError:
            async with httpx.AsyncClient(
                transport=handler, base_url="https://provider.test/"
            ) as client:
                analyzer = ScamAnalyzer(
                    Settings(google_api_key="test-key", google_model="gemini-test"),
                    client=client,
                )
                try:
                    return await analyzer.analyze(AnalyzeRequest(text="hello"))
                except AnalysisError as exc:
                    return exc

        malformed_json = await analyze_with(
            httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "candidates": [
                            {"content": {"parts": [{"text": "not json"}]}}
                        ]
                    },
                )
            )
        )
        empty_response = await analyze_with(
            httpx.MockTransport(
                lambda request: httpx.Response(200, json={"candidates": []})
            )
        )

        def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        timed_out = await analyze_with(httpx.MockTransport(timeout_handler))

        def connection_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        connection_failed = await analyze_with(httpx.MockTransport(connection_handler))

        rate_limit_attempts = 0

        def rate_limit_handler(request: httpx.Request) -> httpx.Response:
            nonlocal rate_limit_attempts
            rate_limit_attempts += 1
            return httpx.Response(429, request=request)

        rate_limited = await analyze_with(httpx.MockTransport(rate_limit_handler))

        self.assertIsInstance(malformed_json, ScamAnalysis)
        self.assertTrue(malformed_json.fallback_used)
        self.assertIn("kiểm tra", malformed_json.reasoning)
        self.assertIsInstance(empty_response, ScamAnalysis)
        self.assertTrue(empty_response.fallback_used)
        self.assertIn("kiểm tra", empty_response.reasoning)

        self.assertIsInstance(timed_out, AnalysisError)
        self.assertIn("thời gian", timed_out.user_message)
        self.assertIsInstance(connection_failed, AnalysisError)
        self.assertIn("kết nối", connection_failed.user_message)
        self.assertIsInstance(rate_limited, AnalysisError)
        self.assertIn("quá nhiều yêu cầu", rate_limited.user_message)
        self.assertEqual(rate_limit_attempts, 2)

    def test_main_categories_are_capped_at_four(self) -> None:
        scenarios = scenario_assessments()
        for assessment in scenarios[:6]:
            assessment.detected = True

        result = ScamAnalysis(
            confidence=0.9,
            reasoning="Several independent scam signals are present.",
            scenarios=scenarios,
        )

        self.assertEqual(
            result.main_categories,
            list(SCAM_SCENARIOS[:4]),
        )
        self.assertLessEqual(len(result.main_categories), 4)

    async def test_http_failure_uses_secondary_gemini_model_without_retry_delay(
        self,
    ) -> None:
        attempted_models: list[str] = []
        timeout_budgets: list[float] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            attempted_models.append(str(request.url))
            timeout_budgets.append(request.extensions["timeout"]["read"])
            if "gemini-primary" in str(request.url):
                return httpx.Response(503, request=request)
            return httpx.Response(200, json=gemini_response(valid_detective_json()))

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://provider.test/"
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(
                    google_api_key="test-key",
                    google_model="gemini-primary",
                    google_fallback_model="gemini-secondary",
                ),
                client=client,
            )
            result = await analyzer.analyze(AnalyzeRequest(text="hello"))

        self.assertEqual(result.provider_risk_level, "safe")
        self.assertEqual(len(attempted_models), 2)
        self.assertIn("gemini-primary", attempted_models[0])
        self.assertIn("gemini-secondary", attempted_models[1])
        self.assertGreater(timeout_budgets[1], timeout_budgets[0])
        self.assertLessEqual(timeout_budgets[1], DETECTIVE_TIMEOUT_SECONDS)

    async def test_invalid_primary_output_uses_secondary_model(self) -> None:
        attempts = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            response_text = "not-json" if attempts == 1 else valid_detective_json()
            return httpx.Response(200, json=gemini_response(response_text))

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://provider.test/"
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(
                    google_api_key="test-key",
                    google_model="gemini-primary",
                    google_fallback_model="gemini-secondary",
                ),
                client=client,
            )
            with self.assertLogs("src.analyzer", level="WARNING") as logs:
                result = await analyzer.analyze(AnalyzeRequest(text="hello"))

        self.assertEqual(result.provider_risk_level, "safe")
        self.assertFalse(result.fallback_used)
        self.assertEqual(attempts, 2)
        self.assertTrue(any("schema validation" in entry for entry in logs.output))
        self.assertTrue(all("not-json" not in entry for entry in logs.output))

    async def test_timed_out_primary_leaves_budget_for_secondary_model(self) -> None:
        attempts = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                await asyncio.sleep(0.2)
            return httpx.Response(200, json=gemini_response(valid_detective_json()))

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://provider.test/"
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(
                    google_api_key="test-key",
                    google_model="gemini-primary",
                    google_fallback_model="gemini-secondary",
                ),
                client=client,
            )
            result = await analyzer._generate(
                "system",
                "prompt",
                GeneratedScamAnalysis,
                timeout_seconds=0.1,
                max_output_tokens=100,
                validator=lambda response_text: response_text,
            )

        self.assertEqual(result, valid_detective_json())
        self.assertEqual(attempts, 2)

    async def test_groq_is_third_target_after_both_gemini_models_fail(self) -> None:
        attempted_providers: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.groq.com":
                attempted_providers.append("groq")
                self.assertEqual(
                    request.headers.get("authorization"), "Bearer groq-test-key"
                )
                payload = json.loads(request.content.decode("utf-8"))
                self.assertEqual(payload["model"], "openai/gpt-oss-20b")
                self.assertEqual(payload["response_format"]["type"], "json_schema")
                response_format = payload["response_format"]["json_schema"]
                self.assertTrue(response_format["strict"])
                schema = response_format["schema"]
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
                for definition in schema.get("$defs", {}).values():
                    if definition.get("type") == "object":
                        self.assertFalse(definition["additionalProperties"])
                        self.assertEqual(
                            set(definition["required"]),
                            set(definition["properties"]),
                        )
                self.assertEqual(
                    payload["max_completion_tokens"],
                    GROQ_MIN_COMPLETION_TOKENS,
                )
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": valid_detective_json()}}
                        ]
                    },
                )
            attempted_providers.append("gemini")
            return httpx.Response(503, request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://provider.test/"
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(
                    google_api_key="test-key",
                    google_model="gemini-primary",
                    google_fallback_model="gemini-secondary",
                    groq_api_key="groq-test-key",
                ),
                client=client,
            )
            result = await analyzer.analyze(AnalyzeRequest(text="hello"))

        self.assertEqual(result.provider_risk_level, "safe")
        self.assertEqual(attempted_providers, ["gemini", "gemini", "groq"])

    async def test_all_transport_failures_raise_analysis_error_once_per_target(
        self,
    ) -> None:
        attempts = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(429, request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://provider.test/"
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(
                    google_api_key="test-key",
                    google_model="gemini-primary",
                    google_fallback_model="gemini-secondary",
                    groq_api_key="groq-test-key",
                ),
                client=client,
            )
            with self.assertLogs("src.analyzer", level="WARNING") as logs:
                with self.assertRaises(AnalysisError):
                    await analyzer.analyze(AnalyzeRequest(text="hello"))

        self.assertEqual(attempts, 3)
        target_logs = [
            entry for entry in logs.output if "Generation target" in entry
        ]
        self.assertEqual(len(target_logs), 3)
        self.assertTrue(all("HTTP 429" in entry for entry in target_logs))
        self.assertTrue(all("failed after" in entry for entry in target_logs))
        self.assertTrue(all("budget" in entry for entry in target_logs))
        self.assertTrue(all("hello" not in entry for entry in logs.output))

    async def test_respond_uses_validated_result_and_enforces_voice(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content.decode("utf-8"))
            self.assertIn("Cô tâm lý", payload["systemInstruction"]["parts"][0]["text"])
            prompt = payload["contents"][0]["parts"][0]["text"]
            self.assertIn("VALIDATED_DETECTIVE_RESULT", prompt)
            self.assertNotIn("ignore previous instructions", prompt)
            self.assertIn('REQUIRED_TERMS_JSON:\n["bác", "cô"]', prompt)
            self.assertIn("FORBIDDEN_TERMS_JSON", prompt)
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
                                                "sentences": [
                                                    "Cô hiểu chiêu thúc ép này dễ làm bác cuống.",
                                                    "Bác cứ chậm lại một nhịp vì sự gấp gáp là điều kẻ gian đang lợi dụng.",
                                                ]
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://provider.test/"
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(google_api_key="test-key", google_model="gemini-test"),
                client=client,
            )
            reply = await analyzer.respond(
                CALMING_GUIDE,
                DetectiveResult(
                    confidence=0.9,
                    reasoning="Tin nhắn tạo áp lực và đòi mã xác thực.",
                    indicators=["Urgency"],
                    scenarios=scenario_assessments("credential_or_otp_theft"),
                    risk_level="dangerous",
                ),
            )

        self.assertEqual(reply.character_id, "calming-guide")
        self.assertEqual(reply.title, "Cô tâm lý")
        self.assertEqual(reply.message.count("."), 2)

    async def test_respond_rejects_output_that_breaks_voice_contract(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": json.dumps({"sentences": ["Bình tĩnh.", "Chờ nhé."]})}
                                ]
                            }
                        }
                    ]
                },
            )
        )
        async with httpx.AsyncClient(
            transport=transport, base_url="https://provider.test/"
        ) as client:
            analyzer = ScamAnalyzer(
                Settings(google_api_key="test-key", google_model="gemini-test"),
                client=client,
            )
            with self.assertRaises(CharacterError):
                await analyzer.respond(
                    CALMING_GUIDE,
                    DetectiveResult(
                        confidence=0.9,
                        reasoning="Có dấu hiệu lừa đảo.",
                        scenarios=scenario_assessments(),
                        risk_level="dangerous",
                    ),
                )
