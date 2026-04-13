from __future__ import annotations

import asyncio
import unittest

from sinbot.exceptions import ConcurrentActionError
from sinbot.utils.locks import MemberLockManager


class MemberLockManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_acquire_for_same_member_is_rejected(self) -> None:
        manager = MemberLockManager()

        async with manager.acquire(42):
            with self.assertRaises(ConcurrentActionError):
                async with manager.acquire(42):
                    self.fail("second acquire should not succeed")

    async def test_acquire_many_rejects_when_any_member_is_busy(self) -> None:
        manager = MemberLockManager()

        async with manager.acquire(42):
            with self.assertRaises(ConcurrentActionError):
                async with manager.acquire_many([42, 84]):
                    self.fail("acquire_many should not succeed when one member is locked")

    async def test_locks_release_after_context_exit(self) -> None:
        manager = MemberLockManager()

        async with manager.acquire_many([1, 2]):
            pass

        async with manager.acquire(1):
            await asyncio.sleep(0)
