"""Credential-gated live provider checks using the authored rewrite corpus."""

import json
import os
from pathlib import Path
import unittest

import httpx
from dotenv import load_dotenv

from src.analyzer import ScamAnalyzer
from src.config import (
    DEFAULT_GOOGLE_FALLBACK_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_GROQ_MODEL,
    Settings,
)
from src.database import AnalysisRepository
from src.main import create_app
from src.schemas import AnalyzeResponse


load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
LIVE_FIXTURE = json.loads(
    Path(__file__).with_name("live_inputs.json").read_text(encoding="utf-8")
)


@unittest.skipUnless(API_KEY, "A Gemini API key is required for live API tests")
class LiveAnalyzeApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert API_KEY is not None
        settings = Settings(
            google_api_key=API_KEY,
            google_model=os.getenv("GOOGLE_MODEL")
            or os.getenv("GEMINI_MODEL")
            or DEFAULT_GOOGLE_MODEL,
            google_fallback_model=os.getenv("GOOGLE_FALLBACK_MODEL")
            or os.getenv("GEMINI_FALLBACK_MODEL")
            or DEFAULT_GOOGLE_FALLBACK_MODEL,
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL,
            ai_session_call_limit=100,
        )
        self.analyzer = ScamAnalyzer(settings)
        self.repository = AnalysisRepository(":memory:")
        self.app = create_app(
            settings=settings,
            analyzer=self.analyzer,
            repository=self.repository,
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await self.analyzer.aclose()
        self.repository.close()

    async def test_authored_live_inputs(self) -> None:
        for index, case in enumerate(LIVE_FIXTURE["cases"], start=1):
            with self.subTest(index=index, message=case["input"]):
                response = await self.client.post(
                    "/analyze",
                    headers={"X-ScamCheck-Request-ID": f"live-input-{index:04d}"},
                    json={"text": case["input"], "source": "live-test"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                result = AnalyzeResponse.model_validate(response.json())
                self.assertGreaterEqual(
                    result.detective.confidence, case["risk_level"]["min"]
                )
                self.assertLessEqual(
                    result.detective.confidence, case["risk_level"]["max"]
                )
                self.assertEqual(len(result.detective.actions), 3)
                self.assertGreaterEqual(
                    len(result.detective.indicator_evidence), case["excerpts"]["min"]
                )
                self.assertLessEqual(
                    len(result.detective.indicator_evidence), case["excerpts"]["max"]
                )


if __name__ == "__main__":
    unittest.main()
