from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from vicecity.models.cinematic import GroqInformantTipResult
from vicecity.services.city import CityService
from vicecity.services.groq_service import GroqService
from vicecity.services.visuals import VisualService


class GroqServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_informant_tip_returns_fallback_without_api_key(self) -> None:
        bot = SimpleNamespace(config=SimpleNamespace(groq_api_key=None, groq_model="groq-2.0-flash"))
        service = GroqService(bot)
        fallback = GroqInformantTipResult(
            headline="Street Contact",
            tip="The block feels wrong tonight.",
            nudge="Move before everyone else smells it.",
        )

        result = await service.generate_informant_tip(
            focus="War smoke",
            facts=["The Serpents are fighting the Wolves over Downtown."],
            fallback=fallback,
        )

        self.assertEqual(result, fallback)

    async def test_informant_tip_invalid_json_uses_fallback(self) -> None:
        bot = SimpleNamespace(config=SimpleNamespace(groq_api_key="test-key", groq_model="groq-2.0-flash"))
        service = GroqService(bot)
        service._generate_json_text = AsyncMock(return_value="this is not json")  # type: ignore[method-assign]
        fallback = GroqInformantTipResult(
            headline="Street Contact",
            tip="A fat vault always leaks a rumor.",
            nudge="Hit the soft edge, not the loud door.",
        )

        result = await service.generate_informant_tip(
            focus="Soft underbelly",
            facts=["The Serpents have the largest gang bank in the city."],
            fallback=fallback,
        )

        self.assertEqual(result, fallback)

    async def test_heist_narration_returns_fallback_without_api_key(self) -> None:
        bot = SimpleNamespace(config=SimpleNamespace(groq_api_key=None, groq_model="groq-2.0-flash"))
        service = GroqService(bot)

        result = await service.generate_heist_narration(
            phase="launch",
            gang_name="Serpents",
            crew_names=["Nyx", "Rico", "June"],
        )

        self.assertEqual(result.headline, "Casino Job Live")
        self.assertTrue(result.lines)


class CityServiceTipTests(unittest.TestCase):
    def test_choose_informant_seed_prefers_active_war(self) -> None:
        service = CityService(SimpleNamespace())
        snapshot = {
            "treasury_balance": 1200,
            "tax_rate": 10,
            "gangs": [
                {"id": 1, "name": "Serpents", "bank_balance": 1500, "member_count": 2, "turf_count": 3, "turfs": ["Downtown"]},
                {"id": 2, "name": "Wolves", "bank_balance": 600, "member_count": 3, "turf_count": 2, "turfs": ["Docks"]},
            ],
            "wars": [
                {"id": 5, "attacker_name": "Serpents", "defender_name": "Wolves", "turf_name": "Downtown"},
            ],
            "wanted": [],
            "news": [],
        }

        seed = service.choose_informant_seed(snapshot)

        self.assertEqual(seed.focus, "War smoke")
        self.assertIn("Downtown", seed.fallback_tip)
        self.assertIn("Serpents", " ".join(seed.facts))


class VisualServiceTests(unittest.TestCase):
    def test_resolve_font_path_prefers_weighted_candidates(self) -> None:
        service = VisualService(SimpleNamespace())
        service.font_candidates = (
            Path("/fonts/Vice-Regular.ttf"),
            Path("/fonts/Vice-Bold.ttf"),
        )

        def fake_exists(path: Path) -> bool:
            return path.name in {"Vice-Regular.ttf", "Vice-Bold.ttf"}

        with patch("pathlib.Path.exists", new=fake_exists):
            bold_font = service._resolve_font_path(bold=True)
            regular_font = service._resolve_font_path(bold=False)

        self.assertIsNotNone(bold_font)
        self.assertIsNotNone(regular_font)
        self.assertEqual(bold_font.name, "Vice-Bold.ttf")
        self.assertEqual(regular_font.name, "Vice-Regular.ttf")
