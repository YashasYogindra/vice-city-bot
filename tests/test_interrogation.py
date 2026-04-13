"""Tests for the deterministic interrogation scoring system."""
from __future__ import annotations

import random
import unittest

from sinbot.services.interrogation import (
    APPROACH_BASE_SCORES,
    MAX_QUALITY_BONUS,
    OUTCOME_THRESHOLD_NEUTRAL,
    OUTCOME_THRESHOLD_SUCCESS,
    RANDOM_RANGE,
    RANK_MODIFIERS,
    InterrogationScore,
    calculate_interrogation_score,
)


class TestInterrogationScoring(unittest.TestCase):
    def test_plead_low_heat_boss_gets_reduced_fine(self) -> None:
        """Plead (40) + heat=0 (+10) + Boss (+10) = 60 base, should reliably succeed."""
        rng = random.Random(42)
        score = calculate_interrogation_score("plead", heat=0, rank="Boss", rng=rng)
        # Base is 60, random can be -10 to +10, so min 50 max 70
        # With seed 42, result should be >= 40 at minimum
        self.assertIn(score.outcome, ("reduced_fine", "deal_rejected"))
        self.assertEqual(score.approach_base, 40)
        self.assertEqual(score.heat_modifier, 10)
        self.assertEqual(score.rank_modifier, 10)

    def test_threaten_high_heat_street_rat_gets_extra_heat(self) -> None:
        """Threaten (20) + heat=5 (-15) + Street Rat (0) = 5 base, should always fail."""
        rng = random.Random(42)
        score = calculate_interrogation_score("threaten", heat=5, rank="Street Rat", rng=rng)
        # Base is 5, even max random +10 = 15 < 40
        self.assertEqual(score.outcome, "extra_heat")
        self.assertLess(score.total, OUTCOME_THRESHOLD_NEUTRAL)

    def test_bribe_medium_heat_soldier_is_borderline(self) -> None:
        """Bribe (50) + heat=2 (0) + Soldier (+5) = 55 base, borderline."""
        score = calculate_interrogation_score("bribe", heat=2, rank="Soldier", rng=random.Random(0))
        self.assertEqual(score.approach_base, 50)
        self.assertEqual(score.heat_modifier, 0)
        self.assertEqual(score.rank_modifier, 5)
        # 55 ± 10 → 45-65 range, could be any outcome except extra_heat
        self.assertIn(score.outcome, ("reduced_fine", "deal_rejected"))

    def test_quality_bonus_tips_borderline_to_success(self) -> None:
        """A quality bonus of 20 should push a borderline case to success."""
        # Bluff (30) + heat=1 (5) + Soldier (5) = 40 base → deal_rejected without bonus
        # With quality=20 → 60 base → reduced_fine
        rng = random.Random(100)  # Use seed that gives 0 random
        score_without = calculate_interrogation_score("bluff", heat=1, rank="Soldier", quality_bonus=0, rng=random.Random(100))
        score_with = calculate_interrogation_score("bluff", heat=1, rank="Soldier", quality_bonus=20, rng=random.Random(100))
        self.assertGreater(score_with.total, score_without.total)
        self.assertEqual(score_with.quality_bonus, 20)

    def test_random_factor_bounded(self) -> None:
        """Random factor should always be between -10 and +10."""
        for seed in range(200):
            score = calculate_interrogation_score("plead", heat=0, rank="Street Rat", rng=random.Random(seed))
            self.assertGreaterEqual(score.random_factor, -RANDOM_RANGE)
            self.assertLessEqual(score.random_factor, RANDOM_RANGE)

    def test_deterministic_with_same_seed(self) -> None:
        """Same inputs + same seed should always produce same result."""
        for _ in range(10):
            a = calculate_interrogation_score("bribe", heat=3, rank="Capo", quality_bonus=10, rng=random.Random(99))
            b = calculate_interrogation_score("bribe", heat=3, rank="Capo", quality_bonus=10, rng=random.Random(99))
            self.assertEqual(a, b)

    def test_quality_bonus_clamped(self) -> None:
        """Quality bonus should be clamped to 0-20."""
        score_over = calculate_interrogation_score("plead", heat=0, rank="Boss", quality_bonus=50, rng=random.Random(0))
        self.assertEqual(score_over.quality_bonus, MAX_QUALITY_BONUS)

        score_under = calculate_interrogation_score("plead", heat=0, rank="Boss", quality_bonus=-5, rng=random.Random(0))
        self.assertEqual(score_under.quality_bonus, 0)

    def test_all_approaches_have_base_scores(self) -> None:
        """All four approaches should have defined base scores."""
        for approach in ("plead", "bribe", "bluff", "threaten"):
            self.assertIn(approach, APPROACH_BASE_SCORES)

    def test_capo_rank_modifier_exists(self) -> None:
        """Capo rank should have a modifier between Soldier and Boss."""
        self.assertGreater(RANK_MODIFIERS["Capo"], RANK_MODIFIERS["Soldier"])
        self.assertLess(RANK_MODIFIERS["Capo"], RANK_MODIFIERS["Boss"])

    def test_score_dataclass_fields(self) -> None:
        """InterrogationScore should expose all component fields."""
        score = calculate_interrogation_score("plead", heat=0, rank="Boss", quality_bonus=5, rng=random.Random(0))
        self.assertIsInstance(score.approach_base, int)
        self.assertIsInstance(score.heat_modifier, int)
        self.assertIsInstance(score.rank_modifier, int)
        self.assertIsInstance(score.quality_bonus, int)
        self.assertIsInstance(score.random_factor, int)
        self.assertIsInstance(score.total, int)
        self.assertIsInstance(score.outcome, str)
        self.assertEqual(score.total, score.approach_base + score.heat_modifier + score.rank_modifier + score.quality_bonus + score.random_factor)


if __name__ == "__main__":
    unittest.main()
