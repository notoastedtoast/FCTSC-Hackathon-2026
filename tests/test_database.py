import json
from typing import Any, cast
import unittest
from unittest.mock import patch

import tests._logging  # noqa: F401

from src.database import (
    AnalysisRepository,
    DatabaseError,
    _PostgresRepository,
)
from src.schemas import AnalyzeRequest, ScamAnalysis
from tests.factories import scenario_assessments


class AnalysisRepositoryTests(unittest.IsolatedAsyncioTestCase):
    def test_runtime_repository_rejects_non_postgresql_storage(self) -> None:
        with self.assertRaises(DatabaseError):
            AnalysisRepository("app.db")

    def test_postgresql_connections_disable_prepared_statements(self) -> None:
        database_url = "postgresql://test:test@localhost:5432/scamcheck"
        repository = _PostgresRepository(database_url)

        with patch("src.database.psycopg.connect") as connect:
            repository._connect()

        connect.assert_called_once_with(
            database_url,
            connect_timeout=5,
            prepare_threshold=None,
        )

    def test_postgresql_schema_contains_migrations_and_enables_rls(self) -> None:
        class RecordingConnection:
            def __init__(self) -> None:
                self.statements: list[str] = []

            def execute(
                self, query: str, _parameters: object = None
            ) -> "RecordingConnection":
                self.statements.append(" ".join(query.split()))
                return self

        connection = RecordingConnection()
        _PostgresRepository._create_schema(cast(Any, connection))
        sql = "\n".join(connection.statements)

        self.assertIn("pg_advisory_xact_lock", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS analyses", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS ai_calls", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS analysis_requests", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS scenarios JSONB", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS indicator_evidence JSONB", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS actions JSONB", sql)
        self.assertIn("ALTER TABLE analyses ENABLE ROW LEVEL SECURITY", sql)
        self.assertIn("ALTER TABLE ai_calls ENABLE ROW LEVEL SECURITY", sql)
        self.assertIn("ALTER TABLE analysis_requests ENABLE ROW LEVEL SECURITY", sql)

    async def test_analysis_request_claims_are_session_scoped_and_releasable(self) -> None:
        repository = AnalysisRepository(":memory:")
        await repository.initialize()

        claimed = await repository.claim_analysis_request(
            "a" * 32, "request-key-0001", "hash-one"
        )
        pending = await repository.claim_analysis_request(
            "a" * 32, "request-key-0001", "hash-one"
        )
        conflict = await repository.claim_analysis_request(
            "a" * 32, "request-key-0001", "hash-two"
        )
        other_session = await repository.claim_analysis_request(
            "b" * 32, "request-key-0001", "hash-two"
        )
        await repository.release_analysis_request(
            "a" * 32, "request-key-0001", "hash-one"
        )
        reclaimed = await repository.claim_analysis_request(
            "a" * 32, "request-key-0001", "hash-two"
        )

        self.assertEqual(claimed.status, "claimed")
        self.assertEqual(pending.status, "pending")
        self.assertEqual(conflict.status, "conflict")
        self.assertEqual(other_session.status, "claimed")
        self.assertEqual(reclaimed.status, "claimed")

    async def test_ai_call_reservation_enforces_session_limit(self) -> None:
        repository = AnalysisRepository(":memory:")
        await repository.initialize()

        first = await repository.reserve_ai_call("a" * 32, "detective", 20, 2)
        second = await repository.reserve_ai_call("a" * 32, "character", 20, 2)
        blocked = await repository.reserve_ai_call("a" * 32, "detective", 20, 2)
        usage, calls = await repository.get_ai_calls("a" * 32, 2)

        assert first is not None
        assert second is not None
        self.assertEqual(first.usage.model_dump(), {"used": 1, "limit": 2})
        self.assertEqual(second.usage.model_dump(), {"used": 2, "limit": 2})
        self.assertIsNone(blocked)
        self.assertEqual(usage.model_dump(), {"used": 2, "limit": 2})
        self.assertEqual([call.kind for call in calls], ["detective", "character"])

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
        with repository._connect() as connection:
            request_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                ("analysis_requests",),
            ).fetchone()

        assert retrieved is not None
        self.assertEqual(request_table, ("analysis_requests",))
        self.assertEqual(len(retrieved.scenarios), 12)
        self.assertTrue(all(not assessment.detected for assessment in retrieved.scenarios))
        self.assertTrue(
            all("Bản ghi cũ" in assessment.evidence for assessment in retrieved.scenarios)
        )


if __name__ == "__main__":
    unittest.main()
