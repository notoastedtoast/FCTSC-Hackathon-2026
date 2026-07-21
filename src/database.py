"""Basic asynchronous adapter for sqlite3."""

import asyncio
import json
import sqlite3
from collections.abc import Mapping, Sequence
from os import PathLike
from typing import Any, Self, TypedDict
from uuid import uuid4

from .schema import Analysis

type Parameters = Sequence[Any] | Mapping[str, Any]

# Keep only a small, replayable history per browser session.
MAX_HISTORY_PER_SESSION = 10


class HistoryEntry(TypedDict):
    """Shape returned to the API layer for one saved history item."""
    id: str
    message: str
    analysis: dict[str, Any]
    guide_output: str | None
    created_at: str


class AsyncSQLite:
    """Run basic sqlite3 operations without blocking the event loop."""

    def __init__(self, database: str | PathLike[str]) -> None:
        self.database = database
        self.connection: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> Self:
        """Open the SQLite connection lazily on first use."""
        if self.connection is None:
            self.connection = await asyncio.to_thread(
                sqlite3.connect,
                self.database,
                check_same_thread=False,
            )
        return self

    def _get_connection(self) -> sqlite3.Connection:
        """Fail fast when a query is attempted before connect()."""
        if self.connection is None:
            raise RuntimeError("Database is not connected")
        return self.connection

    async def execute(
        self,
        query: str,
        parameters: Parameters = (),
    ) -> int:
        """Execute a statement and return its affected row count."""

        connection = self._get_connection()
        async with self._lock:
            cursor = await asyncio.to_thread(
                connection.execute,
                query,
                parameters,
            )
            rowcount = cursor.rowcount
            await asyncio.to_thread(cursor.close)
            return rowcount

    async def fetchall(
        self,
        query: str,
        parameters: Parameters = (),
    ) -> list[tuple[Any, ...]]:
        """Fetch rows through the same lock used by writes."""
        connection = self._get_connection()
        async with self._lock:
            cursor = await asyncio.to_thread(
                connection.execute,
                query,
                parameters,
            )
            rows = await asyncio.to_thread(cursor.fetchall)
            await asyncio.to_thread(cursor.close)
            return rows

    async def commit(self) -> None:
        """Commit the current transaction from the event loop safely."""
        connection = self._get_connection()
        async with self._lock:
            await asyncio.to_thread(connection.commit)

    async def close(self) -> None:
        """Close the shared SQLite connection cleanly."""
        if self.connection is not None:
            async with self._lock:
                await asyncio.to_thread(self.connection.close)
                self.connection = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    message TEXT NOT NULL,
    analysis TEXT NOT NULL,
    guide_output TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS history_session_id
ON history (session_id, id DESC);
"""

# Prepared SQL strings keep route code simple and avoid inline SQL duplication.
INSERT_HISTORY = """
INSERT INTO history (public_id, session_id, message, analysis)
VALUES (?, ?, ?, ?)
"""

TRIM_HISTORY = """
DELETE FROM history
WHERE session_id = ?
  AND id IN (
      SELECT id
      FROM history
      WHERE session_id = ?
      ORDER BY id DESC
      LIMIT -1 OFFSET ?
  )
"""

SELECT_HISTORY = """
SELECT public_id, message, analysis, guide_output, created_at
FROM history
WHERE session_id = ?
ORDER BY id DESC
"""

SELECT_HISTORY_ITEM = """
SELECT public_id, message, analysis, guide_output, created_at
FROM history
WHERE public_id = ?
"""

DELETE_HISTORY = "DELETE FROM history WHERE public_id = ? AND session_id = ?"
UPDATE_HISTORY_GUIDE = "UPDATE history SET guide_output = ? WHERE public_id = ?"


class HistoryDatabase(AsyncSQLite):
    """Persistent, session-scoped analysis history."""

    async def connect(self) -> Self:
        """Open SQLite and ensure the history table exists."""
        await super().connect()
        connection = self._get_connection()
        async with self._lock:
            await asyncio.to_thread(connection.executescript, SCHEMA)
            await asyncio.to_thread(connection.commit)
        return self

    async def save_analysis(
        self,
        session_id: str,
        message: str,
        analysis: Analysis,
    ) -> str:
        """Save one finished analysis and trim the session to the latest entries."""
        connection = self._get_connection()
        history_id = str(uuid4())

        def save() -> None:
            connection.execute(
                INSERT_HISTORY,
                (history_id, session_id, message, analysis.model_dump_json()),
            )
            connection.execute(
                TRIM_HISTORY,
                (session_id, session_id, MAX_HISTORY_PER_SESSION),
            )
            connection.commit()

        async with self._lock:
            await asyncio.to_thread(save)
        return history_id

    async def get_history(self, session_id: str) -> list[HistoryEntry]:
        """Return newest-first history for a single browser session."""
        rows = await self.fetchall(
            SELECT_HISTORY,
            (session_id,),
        )
        return [
            {
                "id": row[0],
                "message": row[1],
                "analysis": json.loads(row[2]),
                "guide_output": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    async def get_history_item(self, history_id: str) -> HistoryEntry | None:
        """Return one history row or None when it does not exist."""
        rows = await self.fetchall(SELECT_HISTORY_ITEM, (history_id,))
        if not rows:
            return None
        row = rows[0]
        return {
            "id": row[0],
            "message": row[1],
            "analysis": json.loads(row[2]),
            "guide_output": row[3],
            "created_at": row[4],
        }

    async def save_guide_output(self, history_id: str, guide_output: str) -> None:
        """Attach the generated calming guide to an existing history record."""
        await self.execute(UPDATE_HISTORY_GUIDE, (guide_output, history_id))
        await self.commit()

    async def delete_history(self, session_id: str, history_id: str) -> bool:
        """Delete one item only if the session owns it."""
        deleted = await self.execute(DELETE_HISTORY, (history_id, session_id))
        await self.commit()
        return deleted > 0
