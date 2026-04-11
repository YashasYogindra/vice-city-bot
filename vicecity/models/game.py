from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BlackjackSession:
    guild_id: int
    user_id: int
    channel_id: int
    bet: int
    deck: list[str] = field(default_factory=list)
    player_hand: list[str] = field(default_factory=list)
    dealer_hand: list[str] = field(default_factory=list)
    message_id: int | None = None
    resolved: bool = False
