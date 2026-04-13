"""Tests for drug operation mechanics."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from sinbot.constants import (
    ARMS_DEAL_PAYOUT,
    CAPO_COOLDOWN_REDUCTION,
    DRUG_RUN_CONFIG,
    OPERATION_COOLDOWN_SECONDS,
    OPERATION_FEE_HIGH_HEAT,
)
from sinbot.repositories.database import Database
from sinbot.repositories.game_repository import GameRepository
from sinbot.utils.embeds import EmbedFactory


class TestDrugRunConfig(unittest.TestCase):
    def test_low_risk_has_highest_success(self) -> None:
        self.assertGreater(DRUG_RUN_CONFIG["low"]["success_rate"], DRUG_RUN_CONFIG["medium"]["success_rate"])

    def test_high_risk_has_lowest_success(self) -> None:
        self.assertLess(DRUG_RUN_CONFIG["high"]["success_rate"], DRUG_RUN_CONFIG["medium"]["success_rate"])

    def test_high_risk_has_highest_payout(self) -> None:
        self.assertGreater(DRUG_RUN_CONFIG["high"]["payout"], DRUG_RUN_CONFIG["low"]["payout"])

    def test_heat_penalty_increases_with_risk(self) -> None:
        self.assertLess(DRUG_RUN_CONFIG["low"]["heat_fail"], DRUG_RUN_CONFIG["high"]["heat_fail"])


class TestHeatSuccessModifier(unittest.TestCase):
    def test_heat_reduces_success_rate(self) -> None:
        base = DRUG_RUN_CONFIG["medium"]["success_rate"]
        heat = 3
        heat_penalty = max(0, heat - 1) * 5
        adjusted = max(10, base - heat_penalty)
        self.assertLess(adjusted, base)

    def test_success_rate_floor_at_10(self) -> None:
        base = DRUG_RUN_CONFIG["low"]["success_rate"]
        heat = 20  # extreme heat
        heat_penalty = max(0, heat - 1) * 5
        adjusted = max(10, base - heat_penalty)
        self.assertEqual(adjusted, 10)


class TestConstants(unittest.TestCase):
    def test_operation_fee_is_positive(self) -> None:
        self.assertGreater(OPERATION_FEE_HIGH_HEAT, 0)

    def test_arms_deal_payout_is_positive(self) -> None:
        self.assertGreater(ARMS_DEAL_PAYOUT, 0)

    def test_capo_cooldown_reduction_is_fraction(self) -> None:
        self.assertGreater(CAPO_COOLDOWN_REDUCTION, 0)
        self.assertLess(CAPO_COOLDOWN_REDUCTION, 1)

    def test_capo_cooldown_is_shorter(self) -> None:
        normal = OPERATION_COOLDOWN_SECONDS
        reduced = int(normal * CAPO_COOLDOWN_REDUCTION)
        self.assertLess(reduced, normal)


class TestOperationStatsColumns(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = Database(Path(":memory:"))
        await self.db.connect()
        self.repo = GameRepository(self.db)
        await self.repo.initialize()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_operations_columns_exist(self) -> None:
        await self.repo.ensure_guild_settings(1)
        await self.repo.ensure_player(1, 100, wallet=500, is_joined=1)
        player = await self.repo.get_player(1, 100)
        self.assertIn("operations_success", player)
        self.assertIn("operations_failed", player)
        self.assertEqual(player["operations_success"], 0)
        self.assertEqual(player["operations_failed"], 0)

    async def test_operations_stats_can_be_updated(self) -> None:
        await self.repo.ensure_guild_settings(1)
        await self.repo.ensure_player(1, 100, wallet=500, is_joined=1)
        await self.repo.update_player(1, 100, operations_success=5, operations_failed=2)
        player = await self.repo.get_player(1, 100)
        self.assertEqual(player["operations_success"], 5)
        self.assertEqual(player["operations_failed"], 2)


if __name__ == "__main__":
    unittest.main()
