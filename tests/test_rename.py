"""Verify the package rename from vicecity to sinbot was done correctly."""
from __future__ import annotations

import importlib
import unittest


class TestRename(unittest.TestCase):
    def test_sinbot_package_imports(self) -> None:
        """All core sinbot modules should import without error."""
        modules = [
            "sinbot.bot",
            "sinbot.config",
            "sinbot.constants",
            "sinbot.exceptions",
            "sinbot.gifs",
            "sinbot.services.city",
            "sinbot.services.operations",
            "sinbot.services.groq_service",
            "sinbot.services.interrogation",
            "sinbot.views.action_hub",
            "sinbot.views.negotiation",
            "sinbot.utils.embeds",
            "sinbot.utils.locks",
            "sinbot.repositories.game_repository",
        ]
        for mod in modules:
            with self.subTest(module=mod):
                importlib.import_module(mod)

    def test_footer_text_is_sinbot(self) -> None:
        from sinbot.constants import FOOTER_TEXT
        self.assertEqual(FOOTER_TEXT, "SinBot")

    def test_bot_class_is_sinbot(self) -> None:
        from sinbot.bot import SinBot
        self.assertTrue(hasattr(SinBot, "setup_hook"))

    def test_error_class_is_sinbot_error(self) -> None:
        from sinbot.exceptions import SinBotError
        self.assertTrue(issubclass(SinBotError, Exception))

    def test_no_vicecity_references_in_constants(self) -> None:
        import sinbot.constants as c
        source = open(c.__file__).read()
        self.assertNotIn("Vice City OS", source)
        self.assertNotIn("vicecity", source.lower().replace("sinbot", ""))

    def test_capo_in_rank_order(self) -> None:
        from sinbot.constants import RANK_ORDER, RANK_THRESHOLDS
        self.assertIn("Capo", RANK_ORDER)
        rank_names = [r[0] for r in RANK_THRESHOLDS]
        self.assertIn("Capo", rank_names)

    def test_capo_threshold_between_soldier_and_boss(self) -> None:
        from sinbot.constants import RANK_THRESHOLDS
        thresholds = dict(RANK_THRESHOLDS)
        self.assertGreater(thresholds["Capo"], thresholds["Soldier"])
        self.assertLess(thresholds["Capo"], thresholds["Boss"])


if __name__ == "__main__":
    unittest.main()
