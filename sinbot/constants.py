from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import discord


EMBED_STANDARD: Final[int] = 0x8B0000
EMBED_REWARD: Final[int] = 0xFFD700
EMBED_DANGER: Final[int] = 0xFF0000
EMBED_SUCCESS: Final[int] = 0x00FF00
FOOTER_TEXT: Final[str] = "SinBot"

RACKS_EMOJI: Final[str] = "\U0001F4B0"
HEAT_EMOJI: Final[str] = "\U0001F525"
TURF_EMOJI: Final[str] = "\U0001F3D8\ufe0f"

DEFAULT_TAX_RATE: Final[int] = 10
MAX_TAX_RATE: Final[int] = 20
TURF_HOURLY_INCOME: Final[int] = 400
TURF_MEMBER_SPLIT_PERCENT: Final[int] = 50
RAT_PAYOUT_MAX: Final[int] = 300
DAILY_STREAK_BASE_REWARD: Final[int] = 250
DAILY_STREAK_BONUS_PER_DAY: Final[int] = 50
DAILY_STREAK_REWARD_CAP_DAYS: Final[int] = 7
CITY_EVENT_DURATION_HOURS: Final[int] = 4
HEAT_FIVE_GRACE_SECONDS: Final[int] = 60
HEAT_FIVE_JAIL_SECONDS: Final[int] = 6 * 60 * 60
WAR_DURATION_SECONDS: Final[int] = 30 * 60
WAR_MOBILIZATION_COST: Final[int] = 250
WAR_RANDOM_MIN: Final[float] = 0.85
WAR_RANDOM_MAX: Final[float] = 1.15
HEIST_PLANNING_SECONDS: Final[int] = 10 * 60
HEIST_EXECUTION_SECONDS: Final[int] = 60
ARMS_DEAL_TIMEOUT_SECONDS: Final[int] = 5 * 60
ARMS_DEAL_JAIL_SECONDS: Final[int] = 3 * 60 * 60
OPERATION_COOLDOWN_SECONDS: Final[int] = 30 * 60
BLACKJACK_TIMEOUT_SECONDS: Final[int] = 60
LAWYER_COOLDOWN_SECONDS: Final[int] = 24 * 60 * 60
LAY_LOW_SECONDS: Final[int] = 3 * 60 * 60


@dataclass(frozen=True, slots=True)
class GangDefinition:
    name: str
    role_name: str
    channel_name: str
    color: discord.Colour


GANGS: Final[tuple[GangDefinition, ...]] = (
    GangDefinition("Serpents", "The Serpents", "serpents-den", discord.Colour.dark_green()),
    GangDefinition("Wolves", "The Wolves", "wolf-pack", discord.Colour.dark_grey()),
    GangDefinition("Syndicate", "The Syndicate", "syndicate-hq", discord.Colour.dark_teal()),
    GangDefinition("Cartel", "The Cartel", "cartel-base", discord.Colour.dark_gold()),
)

CITY_CHANNELS: Final[dict[str, str]] = {
    "news_channel_id": "city-news",
    "city_hall_channel_id": "city-hall",
    "black_market_channel_id": "black-market",
    "turf_war_channel_id": "turf-war-zone",
    "wanted_channel_id": "wanted-board",
    "vault_channel_id": "vault",
}

RANK_ORDER: Final[dict[str, int]] = {
    "Street Rat": 0,
    "Soldier": 1,
    "Capo": 2,
    "Boss": 3,
    "Mayor": 99,
}

RANK_THRESHOLDS: Final[tuple[tuple[str, int], ...]] = (
    ("Street Rat", 0),
    ("Soldier", 1500),
    ("Capo", 3000),
    ("Boss", 5000),
)

CAPO_COOLDOWN_REDUCTION: Final[float] = 0.75

DRUG_RUN_CONFIG: Final[dict[str, dict[str, int]]] = {
    "low": {"success_rate": 80, "payout": 150, "heat_success": 1, "heat_fail": 2},
    "medium": {"success_rate": 60, "payout": 300, "heat_success": 2, "heat_fail": 3},
    "high": {"success_rate": 40, "payout": 600, "heat_success": 3, "heat_fail": 4},
}

BLACK_MARKET_ITEMS: Final[dict[str, dict[str, int]]] = {
    "weapon": {"price": 500},
    "burnerphone": {"price": 300},
    "lawyer": {"price": 800},
    "vest": {"price": 600},
    "scanner": {"price": 400},
    "medkit": {"price": 350},
}

VIOLENCE_SWEEP_THRESHOLD: Final[int] = 25
VIOLENCE_HOURLY_DECAY: Final[int] = 3
FIGHT_BASE_HP: Final[int] = 100
FIGHT_WIN_DAMAGE: Final[int] = 25
FIGHT_RELOAD_BONUS_DAMAGE: Final[int] = 50
FIGHT_DRAW_DAMAGE: Final[int] = 5
FIGHT_ROUNDS: Final[int] = 5
BAIL_MINIMUM: Final[int] = 500
OPERATION_FEE_HIGH_HEAT: Final[int] = 100
ARMS_DEAL_PAYOUT: Final[int] = 350
INITIAL_WALLET: Final[int] = 500
BOSS_CHALLENGE_XP: Final[int] = 6000

HEIST_ROLES: Final[tuple[str, ...]] = ("hacker", "driver", "inside")

HEAT_STATUS: Final[dict[int, tuple[str, str]]] = {
    1: ("On the radar", "Minor penalty to operation success rates."),
    2: ("Wanted", "Listed on the wanted board."),
    3: ("Hot", "Operations cost more Racks."),
    4: ("Fugitive", "Black market access is restricted and next payout is cut."),
    5: ("Most Wanted", "Auto-jail after a short grace period."),
}

TURF_NAMES: Final[tuple[str, ...]] = (
    "Docks",
    "Downtown",
    "Harbor",
    "Little Havana",
    "North Beach",
    "Old Town",
    "South Strip",
    "Vice Heights",
)
