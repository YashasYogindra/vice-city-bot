from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from vicecity.exceptions import InvalidStateError
from vicecity.repositories.database import Database
from vicecity.repositories.game_repository import GameRepository
from vicecity.services.city import CityService
from vicecity.utils.embeds import EmbedFactory
from vicecity.utils.locks import MemberLockManager


class DailyStreakTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = Database(Path(":memory:"))
        await self.db.connect()
        self.repo = GameRepository(self.db)
        await self.repo.initialize()
        await self.repo.ensure_guild_settings(1)
        await self.repo.ensure_player(1, 100, wallet=100, is_joined=1)
        self.bot = SimpleNamespace(
            repo=self.repo,
            scheduler=SimpleNamespace(timezone=timezone.utc),
            member_locks=MemberLockManager(),
            embed_factory=EmbedFactory(),
        )
        self.service = CityService(self.bot)

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_first_daily_claim_starts_streak(self) -> None:
        claim_time = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
        with (
            patch("vicecity.services.city.utcnow", return_value=claim_time),
            patch("vicecity.repositories.game_repository.utcnow", return_value=claim_time),
        ):
            embed = await self.service.claim_daily_reward(1, 100)

        player = await self.repo.get_player(1, 100)
        self.assertIsNotNone(player)
        self.assertEqual(player["wallet"], 350)
        self.assertEqual(player["daily_streak"], 1)
        self.assertEqual(embed.title, "Daily Streak Claimed")

    async def test_consecutive_claim_increases_streak_and_reward(self) -> None:
        first_claim = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
        second_claim = datetime(2026, 4, 11, 9, 0, tzinfo=timezone.utc)
        with (
            patch("vicecity.services.city.utcnow", return_value=first_claim),
            patch("vicecity.repositories.game_repository.utcnow", return_value=first_claim),
        ):
            await self.service.claim_daily_reward(1, 100)
        with (
            patch("vicecity.services.city.utcnow", return_value=second_claim),
            patch("vicecity.repositories.game_repository.utcnow", return_value=second_claim),
        ):
            await self.service.claim_daily_reward(1, 100)

        player = await self.repo.get_player(1, 100)
        self.assertIsNotNone(player)
        self.assertEqual(player["wallet"], 650)
        self.assertEqual(player["daily_streak"], 2)

    async def test_missed_day_resets_streak(self) -> None:
        first_claim = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
        reset_claim = datetime(2026, 4, 13, 9, 0, tzinfo=timezone.utc)
        with (
            patch("vicecity.services.city.utcnow", return_value=first_claim),
            patch("vicecity.repositories.game_repository.utcnow", return_value=first_claim),
        ):
            await self.service.claim_daily_reward(1, 100)
        with (
            patch("vicecity.services.city.utcnow", return_value=reset_claim),
            patch("vicecity.repositories.game_repository.utcnow", return_value=reset_claim),
        ):
            embed = await self.service.claim_daily_reward(1, 100)

        player = await self.repo.get_player(1, 100)
        self.assertIsNotNone(player)
        self.assertEqual(player["wallet"], 600)
        self.assertEqual(player["daily_streak"], 1)
        self.assertIn("streak restarted", embed.description)

    async def test_daily_claim_uses_local_timezone_boundaries(self) -> None:
        self.bot.scheduler.timezone = timezone(timedelta(hours=5, minutes=30))
        first_claim = datetime(2026, 4, 10, 20, 0, tzinfo=timezone.utc)
        blocked_claim = datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc)
        next_local_day_claim = datetime(2026, 4, 11, 19, 0, tzinfo=timezone.utc)
        with (
            patch("vicecity.services.city.utcnow", return_value=first_claim),
            patch("vicecity.repositories.game_repository.utcnow", return_value=first_claim),
        ):
            await self.service.claim_daily_reward(1, 100)
        with (
            patch("vicecity.services.city.utcnow", return_value=blocked_claim),
            patch("vicecity.repositories.game_repository.utcnow", return_value=blocked_claim),
        ):
            with self.assertRaises(InvalidStateError):
                await self.service.claim_daily_reward(1, 100)
        with (
            patch("vicecity.services.city.utcnow", return_value=next_local_day_claim),
            patch("vicecity.repositories.game_repository.utcnow", return_value=next_local_day_claim),
        ):
            await self.service.claim_daily_reward(1, 100)

        player = await self.repo.get_player(1, 100)
        self.assertIsNotNone(player)
        self.assertEqual(player["daily_streak"], 2)
