from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected.")
        return self._connection

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.path.as_posix())
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._connection.execute("PRAGMA journal_mode = WAL")
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        async with self._lock:
            await self.connection.execute(query, params)
            await self.connection.commit()

    async def execute_fetchone(self, query: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
        async with self._lock:
            cursor = await self.connection.execute(query, params)
            row = await cursor.fetchone()
            await cursor.close()
            return row

    async def execute_fetchall(self, query: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        async with self._lock:
            cursor = await self.connection.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()
            return rows

    async def execute_insert(self, query: str, params: Sequence[Any] = ()) -> int:
        async with self._lock:
            cursor = await self.connection.execute(query, params)
            await self.connection.commit()
            lastrowid = cursor.lastrowid
            await cursor.close()
            return int(lastrowid)

    async def executescript(self, script: str) -> None:
        async with self._lock:
            await self.connection.executescript(script)
            await self.connection.commit()

    @asynccontextmanager
    async def transaction(self):
        async with self._lock:
            await self.connection.execute("BEGIN")
            try:
                yield self.connection
            except Exception:
                await self.connection.rollback()
                raise
            else:
                await self.connection.commit()
