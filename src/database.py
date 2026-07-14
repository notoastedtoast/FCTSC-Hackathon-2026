"""SQLite persistence for completed scam analyses."""

import asyncio
from contextlib import closing, nullcontext
import json
from secrets import token_hex
import sqlite3
from pathlib import Path
from typing import ContextManager

from .config import DEFAULT_DATABASE_PATH
from .schemas import AnalyzeRequest, SCAM_SCENARIOS, ScamAnalysis, StoredAnalysis


class DatabaseError(RuntimeError):
    """Raised when an analysis cannot be persisted."""


class AnalysisRepository:
    """Store completed analyses in a local SQLite database."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self._is_in_memory = database_path == ":memory:"
        self._database_path = (
            ":memory:" if self._is_in_memory else str(Path(database_path).expanduser())
        )
        self._memory_connection = self._open_connection() if self._is_in_memory else None

    async def initialize(self) -> None:
        """Create the database and its schema when they do not exist."""
        if self._is_in_memory:
            self._initialize_sync()
            return
        await asyncio.to_thread(self._initialize_sync)

    async def save(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str:
        """Persist an analysis and return its generated primary key."""
        if self._is_in_memory:
            return self._save_sync(request, analysis)
        return await asyncio.to_thread(self._save_sync, request, analysis)

    async def get(self, record_id: str) -> StoredAnalysis | None:
        """Return a stored analysis by primary key, if it exists."""
        if self._is_in_memory:
            return self._get_sync(record_id)
        return await asyncio.to_thread(self._get_sync, record_id)

    def close(self) -> None:
        """Release the in-memory connection used by tests and local callers."""
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    def __del__(self) -> None:
        self.close()

    def _initialize_sync(self) -> None:
        try:
            self._create_parent_directory()
            with self._connection() as connection:
                with connection:
                    self._create_schema(connection)
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to initialize the analysis database") from exc

    def _save_sync(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str:
        try:
            self._create_parent_directory()
            with self._connection() as connection:
                with connection:
                    # Keep this lazy initialization for callers without an app lifespan.
                    self._create_schema(connection)
                    record_id = token_hex(16)
                    connection.execute(
                        """
                        INSERT INTO analyses (
                            id,
                            message_text,
                            source,
                            confidence,
                            reasoning,
                            indicators,
                            scenarios
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            request.text,
                            request.source,
                            analysis.confidence,
                            analysis.reasoning,
                            json.dumps(analysis.indicators, ensure_ascii=False),
                            json.dumps(
                                [scenario.model_dump() for scenario in analysis.scenarios],
                                ensure_ascii=False,
                            ),
                        ),
                    )
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to save the scam analysis") from exc

        return record_id

    def _get_sync(self, record_id: str) -> StoredAnalysis | None:
        try:
            self._create_parent_directory()
            with self._connection() as connection:
                with connection:
                    # Keep this lazy initialization for callers without an app lifespan.
                    self._create_schema(connection)
                    row = connection.execute(
                        """
                        SELECT
                            id,
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
                        (record_id,),
                    ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to retrieve the scam analysis") from exc

        if row is None:
            return None

        try:
            return StoredAnalysis(
                id=row[0],
                text=row[1],
                source=row[2],
                confidence=row[3],
                reasoning=row[4],
                indicators=json.loads(row[5]),
                scenarios=json.loads(row[6]),
                created_at=row[7],
            )
        except (TypeError, ValueError) as exc:
            raise DatabaseError("Stored scam analysis is invalid") from exc

    def _create_parent_directory(self) -> None:
        if not self._is_in_memory:
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        return self._memory_connection or self._open_connection()

    def _connection(self) -> ContextManager[sqlite3.Connection]:
        if self._memory_connection is not None:
            return nullcontext(self._memory_connection)
        return closing(self._open_connection())

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=5,
            check_same_thread=not self._is_in_memory,
        )
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                message_text TEXT NOT NULL,
                source TEXT,
                confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                reasoning TEXT NOT NULL,
                indicators TEXT NOT NULL,
                scenarios TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(analyses)").fetchall()
        }
        if "scenarios" not in columns:
            connection.execute(
                "ALTER TABLE analyses ADD COLUMN scenarios TEXT NOT NULL DEFAULT '[]'"
            )
            legacy_scenarios = [
                {
                    "scenario": scenario,
                    "detected": False,
                    "confidence": 0,
                    "evidence": "Bản ghi cũ chưa được đánh giá theo kịch bản này.",
                }
                for scenario in SCAM_SCENARIOS
            ]
            connection.execute(
                "UPDATE analyses SET scenarios = ? WHERE scenarios = '[]'",
                (json.dumps(legacy_scenarios, ensure_ascii=False),),
            )
