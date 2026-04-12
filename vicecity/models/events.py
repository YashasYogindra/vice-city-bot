from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CityEventEffect:
    operation_success_delta: int = 0
    operation_heat_delta: int = 0
    operation_payout_multiplier: float = 1.0
    shop_discount_percent: int = 0
    casino_payout_multiplier: float = 1.0

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "CityEventEffect":
        data = payload or {}
        return cls(
            operation_success_delta=int(data.get("operation_success_delta", 0)),
            operation_heat_delta=int(data.get("operation_heat_delta", 0)),
            operation_payout_multiplier=float(data.get("operation_payout_multiplier", 1.0)),
            shop_discount_percent=int(data.get("shop_discount_percent", 0)),
            casino_payout_multiplier=float(data.get("casino_payout_multiplier", 1.0)),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "operation_success_delta": self.operation_success_delta,
            "operation_heat_delta": self.operation_heat_delta,
            "operation_payout_multiplier": self.operation_payout_multiplier,
            "shop_discount_percent": self.shop_discount_percent,
            "casino_payout_multiplier": self.casino_payout_multiplier,
        }


@dataclass(frozen=True, slots=True)
class CityEvent:
    guild_id: int
    event_key: str
    headline: str
    description: str
    effect: CityEventEffect
    starts_at: datetime
    ends_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class GroqCityEventResult:
    headline: str
    description: str
    broadcast: str
