from __future__ import annotations

from dataclasses import dataclass

import discord


@dataclass(slots=True)
class BustNegotiationContext:
    token: str
    guild_id: int
    user_id: int
    member_name: str
    gang_name: str
    operation_name: str
    risk: str
    fine_amount: int
    heat_after_bust: int
    jail_seconds: int = 0
    allowed_outcomes: tuple[str, ...] = ("reduced_fine", "extra_heat", "deal_rejected")


@dataclass(slots=True)
class ActionResult:
    embed: discord.Embed
    media_key: str | None = None
    bust_context: BustNegotiationContext | None = None


@dataclass(slots=True)
class GroqNegotiationResult:
    outcome: str
    headline: str
    scene: str
    officer_line: str


@dataclass(slots=True)
class GroqNarrationResult:
    headline: str
    lines: list[str]


@dataclass(slots=True)
class GroqInformantTipResult:
    headline: str
    tip: str
    nudge: str


@dataclass(slots=True)
class InformantTipSeed:
    focus: str
    facts: list[str]
    fallback_headline: str
    fallback_tip: str
    fallback_nudge: str
    media_key: str = "informant"
