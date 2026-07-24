import os
from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, skipUnless
from unittest.mock import AsyncMock

import httpx
from dotenv import load_dotenv

from src.database import HistoryDatabase
from src.schema import Analysis


load_dotenv(override=True)
HAS_GEMINI_API_KEY = bool(
    os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
)


def create_live_analyze_test(
    message: str,
    *,
    session_id: str,
    risk_level: tuple[float, float],
    minimum_suggestions: int,
    excerpts: tuple[int, int],
) -> Callable[["LiveAnalyzeAPITests"], Awaitable[None]]:
    """Create a live /analyze/ test with inclusive result bounds."""

    minimum_risk, maximum_risk = risk_level
    minimum_excerpts, maximum_excerpts = excerpts
    if not 0 <= minimum_risk <= maximum_risk <= 1:
        raise ValueError("risk_level bounds must be ordered values from 0 to 1")
    if minimum_suggestions < 0:
        raise ValueError("minimum_suggestions must be non-negative")
    if not 0 <= minimum_excerpts <= maximum_excerpts:
        raise ValueError("excerpt bounds must be ordered non-negative values")
    async def test(case: "LiveAnalyzeAPITests") -> None:
        response = await case.client.post(
            "/analyze/",
            json=message,
            headers={"cookie": f"session_id={session_id}"},
        )
        context = f"Input: {message}\nResponse: {response.text}"

        case.assertEqual(
            response.status_code,
            200,
            context,
        )
        result = Analysis.model_validate(response.json())
        case.assertTrue(result.success, context)
        case.assertIsNotNone(result.analysis, context)
        analysis = result.analysis
        assert analysis is not None

        case.assertGreaterEqual(analysis.risk_level, minimum_risk, context)
        case.assertLessEqual(analysis.risk_level, maximum_risk, context)
        case.assertGreaterEqual(
            len(analysis.suggestions), minimum_suggestions, context
        )
        case.assertGreaterEqual(len(analysis.excerpts), minimum_excerpts, context)
        case.assertLessEqual(len(analysis.excerpts), maximum_excerpts, context)

        if analysis.risk_level > 0.5:
            case.assertGreater(
                len(analysis.suggestions),
                0,
                f"High-risk analyses must include at least one suggestion\n{context}",
            )
        if analysis.risk_level < 0.05:
            case.assertFalse(
                analysis.excerpts,
                f"Very-low-risk analyses must not include excerpts\n{context}",
            )

        case.database.save_analysis.assert_awaited_once()
        case.database.save_analysis.reset_mock()

    test.__doc__ = f"Input: {message}"
    return test


@skipUnless(HAS_GEMINI_API_KEY, "A Gemini API key is required for live API tests")
class LiveAnalyzeAPITests(IsolatedAsyncioTestCase):
    """Exercise /analyze/ using the real configured Gemini API."""

    async def asyncSetUp(self) -> None:
        from src import main

        self.main = main
        self.database = AsyncMock(spec=HistoryDatabase)
        self._original_overrides = main.app.dependency_overrides.copy()

        async def get_real_client():
            return main.client

        async def get_mock_database():
            return self.database

        main.app.dependency_overrides[main.get_client] = get_real_client
        main.app.dependency_overrides[main.get_database] = get_mock_database
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await self.main.client.close()
        self.main.app.dependency_overrides.clear()
        self.main.app.dependency_overrides.update(self._original_overrides)

    async def test_inputs_from_json(self) -> None:
        for index, live_input in enumerate(LIVE_INPUTS, start=1):
            print(f"[online {index}/{len(LIVE_INPUTS)}]", flush=True)
            with self.subTest(index=index, message=live_input["input"]):
                try:
                    test = create_live_analyze_test(
                        live_input["input"],
                        session_id=f"live-test-{index}",
                        risk_level=(
                            live_input["risk_level"]["min"],
                            live_input["risk_level"]["max"],
                        ),
                        minimum_suggestions=live_input["recommendations"]["min"],
                        excerpts=(
                            live_input["excerpts"]["min"],
                            live_input["excerpts"]["max"],
                        ),
                    )
                    await test(self)
                finally:
                    self.database.save_analysis.reset_mock()

LIVE_FIXTURE = json.loads(
    Path(__file__).with_name("live_inputs.json").read_text(encoding="utf-8")
)
LIVE_INPUTS = LIVE_FIXTURE["cases"]
