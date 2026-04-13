from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from sinbot.exceptions import ConcurrentActionError

class MemberLockManager:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    async def _get_lock(self, user_id: int) -> asyncio.Lock:
        async with self._registry_lock:
            if user_id not in self._locks:
                self._locks[user_id] = asyncio.Lock()
            return self._locks[user_id]

    @asynccontextmanager
    async def acquire(self, user_id: int):
        lock = await self._get_lock(user_id)
        if lock.locked():
            raise ConcurrentActionError("That action is already running for this member.")
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()

    @asynccontextmanager
    async def acquire_many(self, user_ids: list[int]):
        ordered = sorted(set(user_ids))
        locks = [await self._get_lock(user_id) for user_id in ordered]
        if any(lock.locked() for lock in locks):
            raise ConcurrentActionError("One of those members is already busy with another operation.")
        for lock in locks:
            await lock.acquire()
        try:
            yield
        finally:
            for lock in reversed(locks):
                lock.release()
