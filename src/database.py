"""SQLite persistence for completed scam analyses."""

import asyncio
from contextlib import closing, nullcontext
from datetime import datetime
import json
from secrets import token_hex
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import ContextManager, Literal, cast

from .config import DEFAULT_DATABASE_PATH
from .schemas import (
    AiCallLog,
    AiCallUsage,
    AnalyzeRequest,
    DEFAULT_ACTIONS,
    SCAM_SCENARIOS,
    ScamAnalysis,
    StoredAnalysis,
)


AnalysisRow = tuple[str, str, str | None, float, str, str, str, str, str, str, str]
AiCallRow = tuple[str, str, str, int, int | None, str]


@dataclass(frozen=True)
class AiCallReservation:
    call_id: str
    usage: AiCallUsage


class DatabaseError(RuntimeError):
    """Raised when an analysis cannot be persisted."""


class AnalysisRepository:
    """Store completed analyses in a local SQLite database."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self._is_in_memory: bool = str(database_path) == ":memory:"
        self._database_path: str = (
            ":memory:" if self._is_in_memory else str(Path(database_path).expanduser())
        )
        self._memory_connection: sqlite3.Connection | None = (
            self._open_connection() if self._is_in_memory else None
        )

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

    async def reserve_ai_call(
        self, session_id: str, kind: str, input_length: int, limit: int
    ) -> AiCallReservation | None:
        if self._is_in_memory:
            return self._reserve_ai_call_sync(session_id, kind, input_length, limit)
        return await asyncio.to_thread(
            self._reserve_ai_call_sync, session_id, kind, input_length, limit
        )

    async def complete_ai_call(
        self, call_id: str, success: bool, summary: str
    ) -> None:
        if self._is_in_memory:
            self._complete_ai_call_sync(call_id, success, summary)
            return
        await asyncio.to_thread(self._complete_ai_call_sync, call_id, success, summary)

    async def get_ai_calls(
        self, session_id: str, limit: int
    ) -> tuple[AiCallUsage, list[AiCallLog]]:
        if self._is_in_memory:
            return self._get_ai_calls_sync(session_id, limit)
        return await asyncio.to_thread(self._get_ai_calls_sync, session_id, limit)

    def close(self) -> None:
        """Release the in-memory connection used by tests and local callers."""
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    def __del__(self) -> None:
        self.close()

    def _initialize_sync(self) -> None:
        try:
            with self._connection() as connection, connection:
                self._create_schema(connection)
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to initialize the analysis database") from exc

    def _save_sync(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str:
        try:
            with self._connection() as connection, connection:
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
                        indicator_evidence,
                        actions,
                        risk_level,
                        scenarios
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        request.text,
                        request.source,
                        analysis.confidence,
                        analysis.reasoning,
                        json.dumps(analysis.indicators, ensure_ascii=False),
                        json.dumps(
                            [item.model_dump() for item in analysis.indicator_evidence],
                            ensure_ascii=False,
                        ),
                        json.dumps(analysis.actions, ensure_ascii=False),
                        analysis.provider_risk_level,
                        json.dumps(
                            [item.model_dump() for item in analysis.scenarios],
                            ensure_ascii=False,
                        ),
                    ),
                )
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to save the scam analysis") from exc

        return record_id

    def _get_sync(self, record_id: str) -> StoredAnalysis | None:
        try:
            with self._connection() as connection, connection:
                # Keep this lazy initialization for callers without an app lifespan.
                self._create_schema(connection)
                row = cast(
                    AnalysisRow | None,
                    connection.execute(
                        """
                        SELECT
                            id,
                            message_text,
                            source,
                            confidence,
                            reasoning,
                            indicators,
                            indicator_evidence,
                            actions,
                            risk_level,
                            scenarios,
                            created_at
                        FROM analyses
                        WHERE id = ?
                        """,
                        (record_id,),
                    ).fetchone(),
                )
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
                indicator_evidence=json.loads(row[6]),
                actions=json.loads(row[7]),
                risk_level=cast(
                    Literal["safe", "suspicious", "dangerous"] | None, row[8]
                ),
                scenarios=json.loads(row[9]),
                created_at=datetime.fromisoformat(row[10]),
            )
        except (TypeError, ValueError) as exc:
            raise DatabaseError("Stored scam analysis is invalid") from exc

    def _reserve_ai_call_sync(
        self, session_id: str, kind: str, input_length: int, limit: int
    ) -> AiCallReservation | None:
        try:
            with self._connection() as connection:
                self._create_schema(connection)
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
                used = cast(
                    int,
                    connection.execute(
                        "SELECT COUNT(*) FROM ai_calls WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()[0],
                )
                if used >= limit:
                    connection.rollback()
                    return None
                call_id = token_hex(16)
                connection.execute(
                    """
                    INSERT INTO ai_calls (
                        id, session_id, kind, input_length, success, summary
                    ) VALUES (?, ?, ?, ?, NULL, ?)
                    """,
                    (call_id, session_id, kind, input_length, "Đang xử lý."),
                )
                connection.commit()
                return AiCallReservation(
                    call_id=call_id,
                    usage=AiCallUsage(used=used + 1, limit=limit),
                )
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to reserve an AI call") from exc

    def _complete_ai_call_sync(
        self, call_id: str, success: bool, summary: str
    ) -> None:
        try:
            with self._connection() as connection, connection:
                self._create_schema(connection)
                connection.execute(
                    "UPDATE ai_calls SET success = ?, summary = ? WHERE id = ?",
                    (success, summary[:500] or "Không có tóm tắt.", call_id),
                )
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to complete an AI call log") from exc

    def _get_ai_calls_sync(
        self, session_id: str, limit: int
    ) -> tuple[AiCallUsage, list[AiCallLog]]:
        try:
            with self._connection() as connection, connection:
                self._create_schema(connection)
                rows = cast(
                    list[AiCallRow],
                    connection.execute(
                        """
                        SELECT id, created_at, kind, input_length, success, summary
                        FROM ai_calls
                        WHERE session_id = ?
                        ORDER BY created_at, rowid
                        """,
                        (session_id,),
                    ).fetchall(),
                )
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to retrieve AI call logs") from exc

        calls = [
            AiCallLog(
                id=row[0],
                created_at=datetime.fromisoformat(row[1]),
                kind=cast(Literal["detective", "character"], row[2]),
                input_length=row[3],
                success=None if row[4] is None else bool(row[4]),
                summary=row[5],
            )
            for row in rows
        ]
        return AiCallUsage(used=len(calls), limit=limit), calls

    def _connect(self) -> sqlite3.Connection:
        """Return a raw connection for local diagnostics and backwards compatibility."""
        return self._memory_connection or self._open_connection()

    def _connection(self) -> ContextManager[sqlite3.Connection]:
        if self._memory_connection is not None:
            return nullcontext(self._memory_connection)
        return closing(self._open_connection())

    def _open_connection(self) -> sqlite3.Connection:
        if not self._is_in_memory:
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self._database_path,
            timeout=5,
            check_same_thread=not self._is_in_memory,
        )
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        _ = connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                message_text TEXT NOT NULL,
                source TEXT,
                confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                reasoning TEXT NOT NULL,
                indicators TEXT NOT NULL,
                indicator_evidence TEXT NOT NULL DEFAULT '[]',
                actions TEXT NOT NULL DEFAULT '[]',
                risk_level TEXT,
                scenarios TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(analyses)")}
        for column, definition in (
            ("scenarios", "TEXT NOT NULL DEFAULT '[]'"),
            ("indicator_evidence", "TEXT NOT NULL DEFAULT '[]'"),
            ("actions", "TEXT NOT NULL DEFAULT '[]'"),
            ("risk_level", "TEXT"),
        ):
            if column not in columns:
                connection.execute(f"ALTER TABLE analyses ADD COLUMN {column} {definition}")
        legacy_scenarios = [
            {
                "scenario": scenario,
                "detected": False,
                "confidence": 0,
                "evidence": "Bản ghi cũ chưa được đánh giá theo kịch bản này.",
            }
            for scenario in SCAM_SCENARIOS
        ]
        _ = connection.execute(
            "UPDATE analyses SET scenarios = ? WHERE scenarios = '[]'",
            (json.dumps(legacy_scenarios, ensure_ascii=False),),
        )
        _ = connection.execute(
            "UPDATE analyses SET actions = ? WHERE actions = '[]'",
            (json.dumps(DEFAULT_ACTIONS, ensure_ascii=False),),
        )
        _ = connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_calls (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('detective', 'character')),
                input_length INTEGER NOT NULL CHECK (input_length >= 0),
                success INTEGER CHECK (success IN (0, 1)),
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ = connection.execute(
            "CREATE INDEX IF NOT EXISTS ai_calls_session_id ON ai_calls(session_id)"
        )
