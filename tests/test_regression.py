import json
from pathlib import Path
import unittest

import httpx
import tests._logging  # noqa: F401

from src.characters import CharacterSpec
from src.config import Settings
from src.database import AnalysisRepository
from src.main import create_app
from src.schemas import (
    AnalyzeRequest,
    CharacterReply,
    DetectiveResult,
    RiskLevel,
    ScamAnalysis,
)
from tests.factories import scenario_assessments


class RegressionAnalyzer:
    """Stable provider double so the corpus exercises API and local risk filtering."""

    async def analyze(self, _request: AnalyzeRequest) -> ScamAnalysis:
        return ScamAnalysis(
            confidence=0.01,
            reasoning="Không có tín hiệu từ nhà cung cấp mô phỏng.",
            scenarios=scenario_assessments(),
        )

    async def respond(
        self, character: CharacterSpec, _detective: DetectiveResult
    ) -> CharacterReply:
        return CharacterReply(
            character_id=character.character_id,
            title=character.title,
            message=(
                "Cô hiểu chiêu tạo áp lực này dễ làm bác lo. "
                "Bác cứ bình tĩnh và kiểm tra lại qua kênh chính thức nhé."
            ),
        )

    async def aclose(self) -> None:
        return None


class RegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_labeled_messages_match_api_risk_levels(self) -> None:
        cases = json.loads(
            (Path(__file__).with_name("labeled_messages.json")).read_text(
                encoding="utf-8"
            )
        )
        self.assertGreaterEqual(len(cases), 20)

        repository = AnalysisRepository(":memory:")
        self.addCleanup(repository.close)
        app = create_app(
            settings=Settings(
                google_api_key="test-key",
                google_model="gemini-test",
                ai_session_call_limit=100,
            ),
            analyzer=RegressionAnalyzer(),
            repository=repository,
        )

        rows: list[tuple[str, str, str, str]] = []
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            for case in cases:
                response = await client.post(
                    "/analyze",
                    json={"text": case["text"], "source": "regression"},
                )
                self.assertEqual(response.status_code, 200, case["id"])
                actual: RiskLevel = response.json()["detective"]["risk_level"]
                rows.append(
                    (
                        case["id"],
                        case["expected"],
                        actual,
                        "ĐÚNG" if actual == case["expected"] else "SAI",
                    )
                )

        widths = [
            max(len(title), *(len(row[index]) for row in rows))
            for index, title in enumerate(("Mẫu", "Nhãn", "Kết quả", "Đối chiếu"))
        ]
        header = " | ".join(
            title.ljust(widths[index])
            for index, title in enumerate(("Mẫu", "Nhãn", "Kết quả", "Đối chiếu"))
        )
        divider = "-+-".join("-" * width for width in widths)
        print("\nBẢNG HỒI QUY TIN NHẮN")
        print(header)
        print(divider)
        for row in rows:
            print(
                " | ".join(
                    value.ljust(widths[index]) for index, value in enumerate(row)
                )
            )

        failures = [row for row in rows if row[3] == "SAI"]
        self.assertEqual(failures, [], f"Có {len(failures)} mẫu sai nhãn")
