from __future__ import annotations

import unittest
from pathlib import Path

from vicecity.exceptions import InsufficientFundsError
from vicecity.repositories.database import Database
from vicecity.repositories.game_repository import GameRepository


class FinanceRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = Database(Path(":memory:"))
        await self.db.connect()
        self.repo = GameRepository(self.db)
        await self.repo.initialize()
        await self.repo.ensure_guild_settings(1)
        self.gang = await self.repo.upsert_gang(1, "Serpents")
        await self.repo.ensure_player(1, 100, gang_id=self.gang["id"], wallet=1000, is_joined=1)
        await self.repo.ensure_player(1, 200, gang_id=self.gang["id"], wallet=500, is_joined=1)

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_wallet_transfer_updates_both_sides(self) -> None:
        source_balance, target_balance = await self.repo.transfer_wallet(1, 100, 200, 250)
        self.assertEqual(source_balance, 750)
        self.assertEqual(target_balance, 750)

    async def test_gang_bank_cannot_go_negative(self) -> None:
        with self.assertRaises(InsufficientFundsError):
            await self.repo.debit_gang_bank(self.gang["id"], 1)

    async def test_treasury_partial_withdrawal_pays_remaining(self) -> None:
        await self.repo.credit_treasury(1, 120)
        payout, balance = await self.repo.debit_treasury(1, 500, allow_partial=True)
        self.assertEqual(payout, 120)
        self.assertEqual(balance, 0)

    async def test_wallet_debit_raises_insufficient_funds(self) -> None:
        with self.assertRaises(InsufficientFundsError):
            await self.repo.debit_wallet(1, 200, 999)
