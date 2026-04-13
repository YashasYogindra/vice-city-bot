"""Deterministic interrogation scoring for bust negotiations."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

APPROACH_BASE_SCORES: Final[dict[str, int]] = {
    "plead": 40,
    "bribe": 50,
    "bluff": 30,
    "threaten": 20,
}

RANK_MODIFIERS: Final[dict[str, int]] = {
    "Street Rat": 0,
    "Soldier": 5,
    "Capo": 8,
    "Boss": 10,
}

OUTCOME_THRESHOLD_SUCCESS: Final[int] = 60
OUTCOME_THRESHOLD_NEUTRAL: Final[int] = 40
RANDOM_RANGE: Final[int] = 10
MAX_QUALITY_BONUS: Final[int] = 20


@dataclass(frozen=True, slots=True)
class InterrogationScore:
    approach_base: int
    heat_modifier: int
    rank_modifier: int
    quality_bonus: int
    random_factor: int
    total: int
    outcome: str


def calculate_interrogation_score(
    approach: str,
    heat: int,
    rank: str,
    quality_bonus: int = 0,
    rng: random.Random | None = None,
) -> InterrogationScore:
    """Calculate a deterministic-leaning interrogation outcome.

    Score components:
        - approach_base:   plead=40, bribe=50, bluff=30, threaten=20
        - heat_modifier:   (10 - heat * 5)  =>  heat=0: +10, heat=5: -15
        - rank_modifier:   Street Rat=0, Soldier=+5, Capo=+8, Boss=+10
        - quality_bonus:   0-20 (from AI rating if available)
        - random_factor:   randint(-10, 10)

    Outcome thresholds:
        - total >= 60  =>  reduced_fine
        - total >= 40  =>  deal_rejected
        - total <  40  =>  extra_heat
    """
    r = rng or random.Random()

    approach_base = APPROACH_BASE_SCORES.get(approach.lower(), 30)
    heat_modifier = 10 - (heat * 5)
    rank_mod = RANK_MODIFIERS.get(rank, 0)
    quality = max(0, min(MAX_QUALITY_BONUS, quality_bonus))
    rand_factor = r.randint(-RANDOM_RANGE, RANDOM_RANGE)

    total = approach_base + heat_modifier + rank_mod + quality + rand_factor

    if total >= OUTCOME_THRESHOLD_SUCCESS:
        outcome = "reduced_fine"
    elif total >= OUTCOME_THRESHOLD_NEUTRAL:
        outcome = "deal_rejected"
    else:
        outcome = "extra_heat"

    return InterrogationScore(
        approach_base=approach_base,
        heat_modifier=heat_modifier,
        rank_modifier=rank_mod,
        quality_bonus=quality,
        random_factor=rand_factor,
        total=total,
        outcome=outcome,
    )
