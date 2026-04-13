from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from sinbot.constants import (
    FIGHT_BASE_HP,
    FIGHT_DRAW_DAMAGE,
    FIGHT_RELOAD_BONUS_DAMAGE,
    FIGHT_ROUNDS,
    FIGHT_WIN_DAMAGE,
)


class FightAction(str, Enum):
    PUNCH = "punch"     # Rock
    KICK = "kick"       # Scissors
    DEFEND = "defend"   # Paper
    RELOAD = "reload"   # Gamble


class RoundOutcome(str, Enum):
    P1_WIN = "p1_win"
    P2_WIN = "p2_win"
    DRAW = "draw"


# Win matrix: action -> set of actions it beats
_BEATS: Final[dict[FightAction, set[FightAction]]] = {
    FightAction.PUNCH: {FightAction.KICK, FightAction.RELOAD},
    FightAction.KICK: {FightAction.DEFEND, FightAction.RELOAD},
    FightAction.DEFEND: {FightAction.PUNCH, FightAction.RELOAD},
    FightAction.RELOAD: set(),  # Reload loses to everything
}


@dataclass
class RoundResult:
    round_number: int
    p1_action: FightAction
    p2_action: FightAction
    outcome: RoundOutcome
    p1_damage_dealt: int
    p2_damage_dealt: int
    p1_hp_after: int
    p2_hp_after: int
    flavor_text: str


@dataclass
class FightState:
    p1_id: int
    p2_id: int
    p1_hp: int = FIGHT_BASE_HP
    p2_hp: int = FIGHT_BASE_HP
    p1_reloaded: bool = False
    p2_reloaded: bool = False
    rounds_played: int = 0
    max_rounds: int = FIGHT_ROUNDS
    history: list[RoundResult] = field(default_factory=list)

    @property
    def is_over(self) -> bool:
        return self.p1_hp <= 0 or self.p2_hp <= 0 or self.rounds_played >= self.max_rounds

    @property
    def winner_id(self) -> int | None:
        if self.p1_hp <= 0:
            return self.p2_id
        if self.p2_hp <= 0:
            return self.p1_id
        if self.p1_hp == self.p2_hp:
            return None
        return self.p1_id if self.p1_hp > self.p2_hp else self.p2_id

    @property
    def loser_id(self) -> int | None:
        winner = self.winner_id
        if winner is None:
            return None
        return self.p2_id if winner == self.p1_id else self.p1_id


# Flavor text templates
_PUNCH_WINS = [
    "A haymaker lands flush on the chin!",
    "Brass knuckles connect — the crowd roars!",
    "A right hook sends them stumbling backward!",
]
_KICK_WINS = [
    "A spinning heel kick catches them clean!",
    "Steel-toed boot meets ribcage — beautiful!",
    "A devastating low kick buckles their knee!",
]
_DEFEND_WINS = [
    "They caught the punch and twisted — counter!",
    "A perfect block opens up a crushing counter!",
    "Defense turns to offense in a vicious reversal!",
]
_RELOAD_PUNISH = [
    "They tried to reload — big mistake, left wide open!",
    "Caught reloading! They ate the full force of it!",
    "No time to reload when fists are already flying!",
]
_DRAW_TEXTS = [
    "They clash in the middle — neither gives an inch!",
    "Both fighters trade equal blows — the crowd gasps!",
    "A stalemate! Steel meets steel!",
]

import random as _random


class FightEngine:
    """Pure game logic for the RPS + Reload fighting system."""

    def __init__(self) -> None:
        self.random = _random.Random()

    def create_fight(self, p1_id: int, p2_id: int) -> FightState:
        return FightState(p1_id=p1_id, p2_id=p2_id)

    def resolve_round(
        self,
        state: FightState,
        p1_action: FightAction,
        p2_action: FightAction,
    ) -> RoundResult:
        if state.is_over:
            raise ValueError("Fight is already over")

        state.rounds_played += 1
        outcome = self._determine_outcome(p1_action, p2_action)

        p1_damage = 0
        p2_damage = 0

        if outcome == RoundOutcome.P1_WIN:
            p1_damage = FIGHT_RELOAD_BONUS_DAMAGE if state.p1_reloaded else FIGHT_WIN_DAMAGE
            state.p2_hp = max(0, state.p2_hp - p1_damage)
        elif outcome == RoundOutcome.P2_WIN:
            p2_damage = FIGHT_RELOAD_BONUS_DAMAGE if state.p2_reloaded else FIGHT_WIN_DAMAGE
            state.p1_hp = max(0, state.p1_hp - p2_damage)
        else:
            p1_damage = FIGHT_DRAW_DAMAGE
            p2_damage = FIGHT_DRAW_DAMAGE
            state.p1_hp = max(0, state.p1_hp - p2_damage)
            state.p2_hp = max(0, state.p2_hp - p1_damage)

        # Track reload state
        state.p1_reloaded = p1_action == FightAction.RELOAD
        state.p2_reloaded = p2_action == FightAction.RELOAD

        flavor = self._pick_flavor(outcome, p1_action, p2_action)

        result = RoundResult(
            round_number=state.rounds_played,
            p1_action=p1_action,
            p2_action=p2_action,
            outcome=outcome,
            p1_damage_dealt=p1_damage,
            p2_damage_dealt=p2_damage,
            p1_hp_after=state.p1_hp,
            p2_hp_after=state.p2_hp,
            flavor_text=flavor,
        )
        state.history.append(result)
        return result

    def _determine_outcome(
        self,
        p1: FightAction,
        p2: FightAction,
    ) -> RoundOutcome:
        if p1 == p2:
            return RoundOutcome.DRAW
        if p2 in _BEATS.get(p1, set()):
            return RoundOutcome.P1_WIN
        if p1 in _BEATS.get(p2, set()):
            return RoundOutcome.P2_WIN
        return RoundOutcome.DRAW

    def _pick_flavor(
        self,
        outcome: RoundOutcome,
        p1_action: FightAction,
        p2_action: FightAction,
    ) -> str:
        if outcome == RoundOutcome.DRAW:
            return self.random.choice(_DRAW_TEXTS)
        winning_action = p1_action if outcome == RoundOutcome.P1_WIN else p2_action
        losing_action = p2_action if outcome == RoundOutcome.P1_WIN else p1_action
        if losing_action == FightAction.RELOAD:
            return self.random.choice(_RELOAD_PUNISH)
        if winning_action == FightAction.PUNCH:
            return self.random.choice(_PUNCH_WINS)
        if winning_action == FightAction.KICK:
            return self.random.choice(_KICK_WINS)
        if winning_action == FightAction.DEFEND:
            return self.random.choice(_DEFEND_WINS)
        return "A vicious exchange!"

    @staticmethod
    def health_bar(hp: int, max_hp: int = FIGHT_BASE_HP) -> str:
        """Render a text-based health bar: ████████░░ 80/100"""
        bar_length = 10
        filled = max(0, int(bar_length * hp / max_hp))
        empty = bar_length - filled
        if hp > max_hp * 0.6:
            color_emoji = "🟩"
        elif hp > max_hp * 0.3:
            color_emoji = "🟨"
        else:
            color_emoji = "🟥"
        return f"{color_emoji} {'█' * filled}{'░' * empty} {hp}/{max_hp}"

    @staticmethod
    def check_rank_auto_win(attacker_rank: str, defender_rank: str) -> bool:
        """If rank gap > 1 tier, higher rank auto-wins."""
        from sinbot.constants import RANK_ORDER
        a_level = RANK_ORDER.get(attacker_rank, 0)
        d_level = RANK_ORDER.get(defender_rank, 0)
        return abs(a_level - d_level) > 1
