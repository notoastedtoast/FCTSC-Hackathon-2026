import unittest

from src.analyzer import ScamAnalyzer
from src.config import Settings
from src.schemas import AnalyzeRequest
from tests.mock_gemini import MockGeminiAPI


def provider_payload(reasoning: str = "Không có dấu hiệu lừa đảo rõ ràng.") -> dict[str, object]:
    return {
        "risk_level": "safe",
        "confidence": 0.08,
        "reasoning": reasoning,
        "indicator_evidence": [],
        "actions": [
            "Không cung cấp thông tin nhạy cảm.",
            "Tự xác minh qua kênh chính thức.",
            "Nhờ người tin cậy kiểm tra nếu còn phân vân.",
        ],
        "scenarios": [],
    }


class MockGeminiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.mock = MockGeminiAPI()
        self.client = self.mock.client()
        self.analyzer = ScamAnalyzer(
            Settings(
                google_api_key="test-key",
                google_model="primary-test",
                google_fallback_model="secondary-test",
            ),
            client=self.client,
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_mock_server_exercises_real_gemini_adapter(self) -> None:
        self.mock.add_analysis(provider_payload())

        result = await self.analyzer.analyze(AnalyzeRequest(text="Xin chào Hà Nội"))

        self.assertEqual(result.provider_risk_level, "safe")
        self.assertEqual(len(self.mock.requests), 1)
        request = self.mock.request_json()
        self.assertIn("systemInstruction", request)
        self.assertIn("UNTRUSTED_MESSAGE_JSON", request["contents"][0]["parts"][0]["text"])

    async def test_invalid_primary_response_advances_to_secondary_model(self) -> None:
        self.mock.add_response({"candidates": []})
        self.mock.add_analysis(provider_payload("Mô hình dự phòng đã trả lời."))

        result = await self.analyzer.analyze(AnalyzeRequest(text="Tin nhắn bình thường"))

        self.assertEqual(result.reasoning, "Mô hình dự phòng đã trả lời.")
        self.assertEqual(len(self.mock.requests), 2)
        self.assertIn("primary-test", self.mock.requests[0].url.path)
        self.assertIn("secondary-test", self.mock.requests[1].url.path)


if __name__ == "__main__":
    unittest.main()
