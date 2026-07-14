import json
import unittest

import tests._logging  # noqa: F401

from src.database import AnalysisRepository
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


class AnalysisRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_persists_analysis_and_returns_generated_id(self) -> None:
        repository = AnalysisRepository(":memory:")
        await repository.initialize()

        first_id = await repository.save(
            AnalyzeRequest(text="Verify your account now", source="email"),
            ScamAnalysis(
                confidence=0.88,
                reasoning="The message pressures the recipient to act.",
                indicators=["Urgency", "Suspicious link"],
                scenarios=scenario_assessments("malicious_fake_links"),
            ),
        )
        second_id = await repository.save(
            AnalyzeRequest(text="Lunch at noon?"),
            ScamAnalysis(
                confidence=0.02,
                reasoning="Ordinary conversation.",
                scenarios=scenario_assessments(),
            ),
        )
        retrieved = await repository.get(first_id)

        self.assertRegex(first_id, r"^[0-9a-f]{32}$")
        self.assertRegex(second_id, r"^[0-9a-f]{32}$")
        self.assertNotEqual(first_id, second_id)
        with repository._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    message_text,
                    source,
                    confidence,
                    reasoning,
                    indicators,
                    scenarios,
                    created_at
                FROM analyses
                WHERE id = ?
                """,
                (first_id,),
            ).fetchone()

        assert row is not None
        self.assertEqual(row[0], "Verify your account now")
        self.assertEqual(row[1], "email")
        self.assertEqual(row[2], 0.88)
        self.assertEqual(row[3], "The message pressures the recipient to act.")
        self.assertEqual(json.loads(row[4]), ["Urgency", "Suspicious link"])
        self.assertEqual(len(json.loads(row[5])), 12)
        self.assertTrue(json.loads(row[5])[0]["detected"])
        self.assertTrue(row[6])
        assert retrieved is not None
        self.assertEqual(retrieved.id, first_id)
        self.assertEqual(retrieved.text, "Verify your account now")
        self.assertEqual(retrieved.source, "email")
        self.assertEqual(retrieved.indicators, ["Urgency", "Suspicious link"])
        self.assertEqual(len(retrieved.scenarios), 12)
        self.assertTrue(retrieved.scenarios[0].detected)
        self.assertIsNotNone(retrieved.created_at)

    async def test_get_returns_none_for_unknown_id(self) -> None:
        repository = AnalysisRepository(":memory:")
        result = await repository.get("f" * 32)

        self.assertIsNone(result)

    async def test_initialize_migrates_records_created_before_scenario_assessments(self) -> None:
        repository = AnalysisRepository(":memory:")
        with repository._connect() as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE analyses (
                        id TEXT PRIMARY KEY,
                        message_text TEXT NOT NULL,
                        source TEXT,
                        confidence REAL NOT NULL,
                        reasoning TEXT NOT NULL,
                        indicators TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                        INSERT INTO analyses (
                            id, message_text, source, confidence, reasoning, indicators
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                    ("0" * 31 + "1", "Old message", "sms", 0.5, "Old result", "[]"),
                )

        await repository.initialize()
        retrieved = await repository.get("0" * 31 + "1")

        assert retrieved is not None
        self.assertEqual(len(retrieved.scenarios), 12)
        self.assertTrue(all(not assessment.detected for assessment in retrieved.scenarios))
        self.assertTrue(
            all("Bản ghi cũ" in assessment.evidence for assessment in retrieved.scenarios)
        )


if __name__ == "__main__":
    unittest.main()
