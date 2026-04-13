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
        self._pool_size = 1 if str(path) == ":memory:" else 5
        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
        self._active: list[aiosqlite.Connection] = []

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(self._pool_size):
            conn = await aiosqlite.connect(self.path.as_posix(), timeout=10.0, isolation_level=None)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.execute("PRAGMA journal_mode = WAL")
            await conn.execute("PRAGMA synchronous = NORMAL")
            await self._pool.put(conn)
            self._active.append(conn)

    async def close(self) -> None:
        for conn in self._active:
            await conn.close()
        self._active.clear()

    @asynccontextmanager
    async def get_connection(self):
        conn = await self._pool.get()
        try:
            yield conn
        finally:
            self._pool.put_nowait(conn)

    async def execute(self, query: str, params: Sequence[Any] = ()) -> None:
        async with self.get_connection() as conn:
            query_upper = query.lstrip().upper()
            is_write = query_upper.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))
            if is_write:
                await conn.execute("BEGIN IMMEDIATE")
            try:
                await conn.execute(query, params)
                if is_write:
                    await conn.commit()
            except Exception:
                if is_write:
                    await conn.rollback()
                raise

    async def execute_fetchone(self, query: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            await cursor.close()
            return row

    async def execute_fetchall(self, query: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()
            return rows

    async def execute_insert(self, query: str, params: Sequence[Any] = ()) -> int:
        async with self.get_connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await conn.execute(query, params)
                await conn.commit()
                lastrowid = cursor.lastrowid
                await cursor.close()
                return int(lastrowid)
            except Exception:
                await conn.rollback()
                raise

    async def executescript(self, script: str) -> None:
        async with self.get_connection() as conn:
            await conn.executescript(script)

    @asynccontextmanager
    async def transaction(self):
        async with self.get_connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                await conn.rollback()
                raise
            else:
                await conn.commit()
