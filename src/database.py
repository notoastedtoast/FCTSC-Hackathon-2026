"""PostgreSQL persistence with an embedded test-only repository."""

import asyncio
from contextlib import closing, nullcontext
from datetime import datetime
import json
from secrets import token_hex
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, ContextManager, Literal, cast

import psycopg
from psycopg import Connection
from psycopg.types.json import Jsonb

from .schemas import (
    AiCallLog,
    AiCallUsage,
    AnalyzeRequest,
    AnalyzeResponse,
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


@dataclass(frozen=True)
class AnalysisRequestClaim:
    status: Literal["claimed", "pending", "completed", "conflict"]
    response: AnalyzeResponse | None = None


class DatabaseError(RuntimeError):
    """Raised when an analysis cannot be persisted."""


class _SqliteTestRepository:
    """Embedded repository retained only for deterministic offline tests."""

    def __init__(self, database_path: str | Path) -> None:
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

    async def claim_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> AnalysisRequestClaim:
        if self._is_in_memory:
            return self._claim_analysis_request_sync(
                session_id, request_id, request_hash
            )
        return await asyncio.to_thread(
            self._claim_analysis_request_sync, session_id, request_id, request_hash
        )

    async def save_idempotent(
        self,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
        session_id: str,
        request_id: str,
        request_hash: str,
        response: AnalyzeResponse,
    ) -> None:
        if self._is_in_memory:
            self._save_idempotent_sync(
                request,
                analysis,
                session_id,
                request_id,
                request_hash,
                response,
            )
            return
        await asyncio.to_thread(
            self._save_idempotent_sync,
            request,
            analysis,
            session_id,
            request_id,
            request_hash,
            response,
        )

    async def release_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> None:
        if self._is_in_memory:
            self._release_analysis_request_sync(session_id, request_id, request_hash)
            return
        await asyncio.to_thread(
            self._release_analysis_request_sync, session_id, request_id, request_hash
        )

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
                self._insert_analysis(connection, record_id, request, analysis)
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to save the scam analysis") from exc

        return record_id

    def _claim_analysis_request_sync(
        self, session_id: str, request_id: str, request_hash: str
    ) -> AnalysisRequestClaim:
        try:
            with self._connection() as connection:
                self._create_schema(connection)
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO analysis_requests (
                        session_id, request_id, request_hash, status, response_json
                    ) VALUES (?, ?, ?, 'pending', NULL)
                    """,
                    (session_id, request_id, request_hash),
                )
                if cursor.rowcount == 1:
                    connection.commit()
                    return AnalysisRequestClaim(status="claimed")

                row = connection.execute(
                    """
                    SELECT request_hash, status, response_json,
                           updated_at <= datetime('now', '-60 seconds')
                    FROM analysis_requests
                    WHERE session_id = ? AND request_id = ?
                    """,
                    (session_id, request_id),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    raise sqlite3.DatabaseError("Analysis request claim disappeared")
                if row[0] != request_hash:
                    connection.rollback()
                    return AnalysisRequestClaim(status="conflict")
                if row[1] == "completed" and row[2]:
                    connection.rollback()
                    return AnalysisRequestClaim(
                        status="completed",
                        response=AnalyzeResponse.model_validate_json(row[2]),
                    )
                if bool(row[3]):
                    connection.execute(
                        """
                        UPDATE analysis_requests
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = ? AND request_id = ?
                        """,
                        (session_id, request_id),
                    )
                    connection.commit()
                    return AnalysisRequestClaim(status="claimed")
                connection.rollback()
                return AnalysisRequestClaim(status="pending")
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise DatabaseError("Unable to claim an analysis request") from exc

    def _save_idempotent_sync(
        self,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
        session_id: str,
        request_id: str,
        request_hash: str,
        response: AnalyzeResponse,
    ) -> None:
        try:
            with self._connection() as connection:
                self._create_schema(connection)
                self._insert_analysis(connection, response.id, request, analysis)
                cursor = connection.execute(
                    """
                    UPDATE analysis_requests
                    SET status = 'completed', response_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND request_id = ?
                      AND request_hash = ? AND status = 'pending'
                    """,
                    (
                        response.model_dump_json(),
                        session_id,
                        request_id,
                        request_hash,
                    ),
                )
                if cursor.rowcount != 1:
                    raise sqlite3.DatabaseError("Analysis request was not claimed")
                connection.commit()
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to save an idempotent scam analysis") from exc

    def _release_analysis_request_sync(
        self, session_id: str, request_id: str, request_hash: str
    ) -> None:
        try:
            with self._connection() as connection, connection:
                self._create_schema(connection)
                connection.execute(
                    """
                    DELETE FROM analysis_requests
                    WHERE session_id = ? AND request_id = ?
                      AND request_hash = ? AND status = 'pending'
                    """,
                    (session_id, request_id, request_hash),
                )
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError("Unable to release an analysis request") from exc

    @staticmethod
    def _insert_analysis(
        connection: sqlite3.Connection,
        record_id: str,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
    ) -> None:
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

    def connect_for_tests(self) -> sqlite3.Connection:
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
        _ = connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_requests (
                session_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'completed')),
                response_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, request_id)
            )
            """
        )


class _PostgresRepository:
    """Persist analyses in PostgreSQL using short-lived serverless-safe connections."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._initialized = False
        self._initialization_lock = Lock()

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def save(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str:
        return await asyncio.to_thread(self._save_sync, request, analysis)

    async def claim_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> AnalysisRequestClaim:
        return await asyncio.to_thread(
            self._claim_analysis_request_sync, session_id, request_id, request_hash
        )

    async def save_idempotent(
        self,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
        session_id: str,
        request_id: str,
        request_hash: str,
        response: AnalyzeResponse,
    ) -> None:
        await asyncio.to_thread(
            self._save_idempotent_sync,
            request,
            analysis,
            session_id,
            request_id,
            request_hash,
            response,
        )

    async def release_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> None:
        await asyncio.to_thread(
            self._release_analysis_request_sync, session_id, request_id, request_hash
        )

    async def get(self, record_id: str) -> StoredAnalysis | None:
        return await asyncio.to_thread(self._get_sync, record_id)

    async def reserve_ai_call(
        self, session_id: str, kind: str, input_length: int, limit: int
    ) -> AiCallReservation | None:
        return await asyncio.to_thread(
            self._reserve_ai_call_sync, session_id, kind, input_length, limit
        )

    async def complete_ai_call(
        self, call_id: str, success: bool, summary: str
    ) -> None:
        await asyncio.to_thread(self._complete_ai_call_sync, call_id, success, summary)

    async def get_ai_calls(
        self, session_id: str, limit: int
    ) -> tuple[AiCallUsage, list[AiCallLog]]:
        return await asyncio.to_thread(self._get_ai_calls_sync, session_id, limit)

    def close(self) -> None:
        """Connections are scoped to operations, so there is no client pool to close."""

    def _connect(self) -> Connection[Any]:
        return psycopg.connect(
            self._database_url,
            connect_timeout=5,
            prepare_threshold=None,
        )

    def _ensure_schema(self, connection: Connection[Any]) -> None:
        if self._initialized:
            return
        with self._initialization_lock:
            if self._initialized:
                return
            self._create_schema(connection)
            connection.commit()
            self._initialized = True

    def _initialize_sync(self) -> None:
        try:
            with self._connect() as connection:
                self._create_schema(connection)
            self._initialized = True
        except (OSError, psycopg.Error) as exc:
            raise DatabaseError("Unable to initialize the analysis database") from exc

    def _save_sync(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str:
        record_id = token_hex(16)
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                self._insert_analysis(connection, record_id, request, analysis)
        except (OSError, psycopg.Error) as exc:
            raise DatabaseError("Unable to save the scam analysis") from exc
        return record_id

    def _claim_analysis_request_sync(
        self, session_id: str, request_id: str, request_hash: str
    ) -> AnalysisRequestClaim:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                inserted = connection.execute(
                    """
                    INSERT INTO analysis_requests (
                        session_id, request_id, request_hash, status, response_json
                    ) VALUES (%s, %s, %s, 'pending', NULL)
                    ON CONFLICT (session_id, request_id) DO NOTHING
                    RETURNING request_id
                    """,
                    (session_id, request_id, request_hash),
                ).fetchone()
                if inserted is not None:
                    return AnalysisRequestClaim(status="claimed")

                row = connection.execute(
                    """
                    SELECT request_hash, status, response_json,
                           updated_at <= CURRENT_TIMESTAMP - INTERVAL '60 seconds'
                    FROM analysis_requests
                    WHERE session_id = %s AND request_id = %s
                    FOR UPDATE
                    """,
                    (session_id, request_id),
                ).fetchone()
                if row is None:
                    raise psycopg.DatabaseError("Analysis request claim disappeared")
                if row[0] != request_hash:
                    return AnalysisRequestClaim(status="conflict")
                if row[1] == "completed" and row[2] is not None:
                    return AnalysisRequestClaim(
                        status="completed",
                        response=AnalyzeResponse.model_validate(row[2]),
                    )
                if bool(row[3]):
                    connection.execute(
                        """
                        UPDATE analysis_requests
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s AND request_id = %s
                        """,
                        (session_id, request_id),
                    )
                    return AnalysisRequestClaim(status="claimed")
                return AnalysisRequestClaim(status="pending")
        except (OSError, psycopg.Error, ValueError) as exc:
            raise DatabaseError("Unable to claim an analysis request") from exc

    def _save_idempotent_sync(
        self,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
        session_id: str,
        request_id: str,
        request_hash: str,
        response: AnalyzeResponse,
    ) -> None:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                self._insert_analysis(connection, response.id, request, analysis)
                cursor = connection.execute(
                    """
                    UPDATE analysis_requests
                    SET status = 'completed', response_json = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = %s AND request_id = %s
                      AND request_hash = %s AND status = 'pending'
                    """,
                    (
                        Jsonb(response.model_dump(mode="json")),
                        session_id,
                        request_id,
                        request_hash,
                    ),
                )
                if cursor.rowcount != 1:
                    raise psycopg.DatabaseError("Analysis request was not claimed")
        except (OSError, psycopg.Error) as exc:
            raise DatabaseError("Unable to save an idempotent scam analysis") from exc

    def _release_analysis_request_sync(
        self, session_id: str, request_id: str, request_hash: str
    ) -> None:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                connection.execute(
                    """
                    DELETE FROM analysis_requests
                    WHERE session_id = %s AND request_id = %s
                      AND request_hash = %s AND status = 'pending'
                    """,
                    (session_id, request_id, request_hash),
                )
        except (OSError, psycopg.Error) as exc:
            raise DatabaseError("Unable to release an analysis request") from exc

    @staticmethod
    def _insert_analysis(
        connection: Connection[Any],
        record_id: str,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
    ) -> None:
        connection.execute(
            """
            INSERT INTO analyses (
                id, message_text, source, confidence, reasoning, indicators,
                indicator_evidence, actions, risk_level, scenarios
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record_id,
                request.text,
                request.source,
                analysis.confidence,
                analysis.reasoning,
                Jsonb(analysis.indicators),
                Jsonb([item.model_dump(mode="json") for item in analysis.indicator_evidence]),
                Jsonb(analysis.actions),
                analysis.provider_risk_level,
                Jsonb([item.model_dump(mode="json") for item in analysis.scenarios]),
            ),
        )

    def _get_sync(self, record_id: str) -> StoredAnalysis | None:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                row = connection.execute(
                    """
                    SELECT id, message_text, source, confidence, reasoning,
                           indicators, indicator_evidence, actions, risk_level,
                           scenarios, created_at
                    FROM analyses
                    WHERE id = %s
                    """,
                    (record_id,),
                ).fetchone()
        except (OSError, psycopg.Error) as exc:
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
                indicators=row[5],
                indicator_evidence=row[6],
                actions=row[7],
                risk_level=cast(
                    Literal["safe", "suspicious", "dangerous"] | None, row[8]
                ),
                scenarios=row[9],
                created_at=row[10],
            )
        except (TypeError, ValueError) as exc:
            raise DatabaseError("Stored scam analysis is invalid") from exc

    def _reserve_ai_call_sync(
        self, session_id: str, kind: str, input_length: int, limit: int
    ) -> AiCallReservation | None:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (session_id,),
                )
                row = connection.execute(
                    "SELECT COUNT(*) FROM ai_calls WHERE session_id = %s",
                    (session_id,),
                ).fetchone()
                if row is None:
                    raise psycopg.DatabaseError("AI call count was unavailable")
                used = int(row[0])
                if used >= limit:
                    return None
                call_id = token_hex(16)
                connection.execute(
                    """
                    INSERT INTO ai_calls (
                        id, session_id, kind, input_length, success, summary
                    ) VALUES (%s, %s, %s, %s, NULL, %s)
                    """,
                    (call_id, session_id, kind, input_length, "Đang xử lý."),
                )
                return AiCallReservation(
                    call_id=call_id,
                    usage=AiCallUsage(used=used + 1, limit=limit),
                )
        except (OSError, psycopg.Error) as exc:
            raise DatabaseError("Unable to reserve an AI call") from exc

    def _complete_ai_call_sync(
        self, call_id: str, success: bool, summary: str
    ) -> None:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                connection.execute(
                    "UPDATE ai_calls SET success = %s, summary = %s WHERE id = %s",
                    (success, summary[:500] or "Không có tóm tắt.", call_id),
                )
        except (OSError, psycopg.Error) as exc:
            raise DatabaseError("Unable to complete an AI call log") from exc

    def _get_ai_calls_sync(
        self, session_id: str, limit: int
    ) -> tuple[AiCallUsage, list[AiCallLog]]:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                rows = connection.execute(
                    """
                    SELECT id, created_at, kind, input_length, success, summary
                    FROM ai_calls
                    WHERE session_id = %s
                    ORDER BY created_at, id
                    """,
                    (session_id,),
                ).fetchall()
        except (OSError, psycopg.Error) as exc:
            raise DatabaseError("Unable to retrieve AI call logs") from exc

        calls = [
            AiCallLog(
                id=row[0],
                created_at=row[1],
                kind=cast(Literal["detective", "character"], row[2]),
                input_length=row[3],
                success=row[4],
                summary=row[5],
            )
            for row in rows
        ]
        return AiCallUsage(used=len(calls), limit=limit), calls

    @staticmethod
    def _create_schema(connection: Connection[Any]) -> None:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('scamcheck-schema-v1', 0))"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id VARCHAR(32) PRIMARY KEY,
                message_text TEXT NOT NULL,
                source VARCHAR(100),
                confidence DOUBLE PRECISION NOT NULL
                    CHECK (confidence >= 0 AND confidence <= 1),
                reasoning TEXT NOT NULL,
                indicators JSONB NOT NULL,
                indicator_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
                actions JSONB NOT NULL DEFAULT '[]'::jsonb,
                risk_level TEXT CHECK (
                    risk_level IS NULL OR risk_level IN ('safe', 'suspicious', 'dangerous')
                ),
                scenarios JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for statement in (
            "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS scenarios JSONB NOT NULL DEFAULT '[]'::jsonb",
            "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS indicator_evidence JSONB NOT NULL DEFAULT '[]'::jsonb",
            "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS actions JSONB NOT NULL DEFAULT '[]'::jsonb",
            "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS risk_level TEXT",
        ):
            connection.execute(statement)

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
            "UPDATE analyses SET scenarios = %s WHERE scenarios = '[]'::jsonb",
            (Jsonb(legacy_scenarios),),
        )
        connection.execute(
            "UPDATE analyses SET actions = %s WHERE actions = '[]'::jsonb",
            (Jsonb(DEFAULT_ACTIONS),),
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_calls (
                id VARCHAR(32) PRIMARY KEY,
                session_id VARCHAR(32) NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('detective', 'character')),
                input_length INTEGER NOT NULL CHECK (input_length >= 0),
                success BOOLEAN,
                summary TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ai_calls_session_id ON ai_calls(session_id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_requests (
                session_id VARCHAR(32) NOT NULL,
                request_id VARCHAR(64) NOT NULL,
                request_hash VARCHAR(64) NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'completed')),
                response_json JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, request_id)
            )
            """
        )
        for table in ("analyses", "ai_calls", "analysis_requests"):
            connection.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


class AnalysisRepository:
    """Select PostgreSQL at runtime and an embedded backend only for `:memory:` tests."""

    def __init__(self, database_url: str | Path) -> None:
        value = str(database_url)
        if value == ":memory:":
            self._backend: _PostgresRepository | _SqliteTestRepository = (
                _SqliteTestRepository(value)
            )
        elif value.startswith(("postgresql://", "postgres://")):
            self._backend = _PostgresRepository(value)
        else:
            raise DatabaseError("Database URL must use PostgreSQL")

    async def initialize(self) -> None:
        await self._backend.initialize()

    async def save(self, request: AnalyzeRequest, analysis: ScamAnalysis) -> str:
        return await self._backend.save(request, analysis)

    async def claim_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> AnalysisRequestClaim:
        return await self._backend.claim_analysis_request(
            session_id, request_id, request_hash
        )

    async def save_idempotent(
        self,
        request: AnalyzeRequest,
        analysis: ScamAnalysis,
        session_id: str,
        request_id: str,
        request_hash: str,
        response: AnalyzeResponse,
    ) -> None:
        await self._backend.save_idempotent(
            request, analysis, session_id, request_id, request_hash, response
        )

    async def release_analysis_request(
        self, session_id: str, request_id: str, request_hash: str
    ) -> None:
        await self._backend.release_analysis_request(
            session_id, request_id, request_hash
        )

    async def get(self, record_id: str) -> StoredAnalysis | None:
        return await self._backend.get(record_id)

    async def reserve_ai_call(
        self, session_id: str, kind: str, input_length: int, limit: int
    ) -> AiCallReservation | None:
        return await self._backend.reserve_ai_call(
            session_id, kind, input_length, limit
        )

    async def complete_ai_call(
        self, call_id: str, success: bool, summary: str
    ) -> None:
        await self._backend.complete_ai_call(call_id, success, summary)

    async def get_ai_calls(
        self, session_id: str, limit: int
    ) -> tuple[AiCallUsage, list[AiCallLog]]:
        return await self._backend.get_ai_calls(session_id, limit)

    def close(self) -> None:
        backend = getattr(self, "_backend", None)
        if backend is not None:
            backend.close()

    def _connect(self) -> sqlite3.Connection:
        """Expose only the embedded test connection to legacy-schema tests."""
        if not isinstance(self._backend, _SqliteTestRepository):
            raise RuntimeError("Raw connections are unavailable for PostgreSQL runtime use")
        return self._backend.connect_for_tests()

    def __del__(self) -> None:
        self.close()
