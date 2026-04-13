"""Tests for social mechanics (rat, exile, boss challenge)."""
from __future__ import annotations

import unittest
from pathlib import Path

from sinbot.constants import BOSS_CHALLENGE_XP, RANK_ORDER, RANK_THRESHOLDS
from sinbot.repositories.database import Database
from sinbot.repositories.game_repository import GameRepository


class TestExileVoteThreshold(unittest.TestCase):
    def test_threshold_is_majority(self) -> None:
        for n in range(1, 10):
            threshold = max(1, n // 2 + 1)
            self.assertGreater(threshold, n / 2)

    def test_single_member_needs_one_vote(self) -> None:
        threshold = max(1, 1 // 2 + 1)
        self.assertEqual(threshold, 1)


class TestBossChallenge(unittest.TestCase):
    def test_boss_challenge_xp_constant(self) -> None:
        self.assertEqual(BOSS_CHALLENGE_XP, 6000)

    def test_boss_xp_exceeds_boss_rank_threshold(self) -> None:
        boss_threshold = dict(RANK_THRESHOLDS)["Boss"]
        self.assertGreaterEqual(BOSS_CHALLENGE_XP, boss_threshold)


class TestRankSystem(unittest.TestCase):
    def test_rank_order_is_ascending(self) -> None:
        order = [RANK_ORDER[r] for r in ("Street Rat", "Soldier", "Capo", "Boss")]
        self.assertEqual(order, sorted(order))

    def test_rank_thresholds_ascending(self) -> None:
        thresholds = [t[1] for t in RANK_THRESHOLDS]
        self.assertEqual(thresholds, sorted(thresholds))

    def test_capo_is_between_soldier_and_boss(self) -> None:
        thresholds = dict(RANK_THRESHOLDS)
        self.assertGreater(thresholds["Capo"], thresholds["Soldier"])
        self.assertLess(thresholds["Capo"], thresholds["Boss"])


class TestTrustScore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = Database(Path(":memory:"))
        await self.db.connect()
        self.repo = GameRepository(self.db)
        await self.repo.initialize()
        await self.repo.ensure_guild_settings(1)

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_trust_score_starts_at_zero(self) -> None:
        await self.repo.ensure_player(1, 100, wallet=500, is_joined=1)
        player = await self.repo.get_player(1, 100)
        self.assertEqual(player["trust_score"], 0)

    async def test_trust_score_can_decrease(self) -> None:
        await self.repo.ensure_player(1, 100, wallet=500, is_joined=1)
        await self.repo.update_player(1, 100, trust_score=-1)
        player = await self.repo.get_player(1, 100)
        self.assertEqual(player["trust_score"], -1)


if __name__ == "__main__":
    unittest.main()
