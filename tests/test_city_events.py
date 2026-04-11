"""Tests for the City Event Director system.

Covers:
- Repository: create, load, expire, and replace active city events.
- Effects: verify each of the 4 event types applies deterministic modifiers.
- Gemini fallback: event generation works with no API key.
- Embed builder: verify embed output for each event type.
"""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from vicecity.models.events import CityEvent, CityEventEffect, GeminiCityEventResult
from vicecity.repositories.database import Database
from vicecity.repositories.game_repository import GameRepository
from vicecity.services.city_events import CityEventDirectorService
from vicecity.services.gemini_service import GeminiService
from vicecity.utils.embeds import EmbedFactory
from vicecity.utils.time import isoformat, utcnow


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_events.db"


@pytest.fixture()
def run(event_loop):
    """Shortcut to run an async function synchronously."""
    return event_loop.run_until_complete


@pytest.fixture()
def repo(db_path: Path, run) -> GameRepository:
    db = Database(db_path)
    run(db.connect())
    repository = GameRepository(db)
    run(repository.initialize())
    yield repository
    run(db.close())


# ── Repository Tests ────────────────────────────────────────────


GUILD_ID = 123456789


class FakeScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}

    def add_job(self, func: Any, trigger: str, **kwargs: Any) -> None:
        self.jobs[str(kwargs["id"])] = {"func": func, "trigger": trigger, **kwargs}


class ActiveEventRepo:
    def __init__(self) -> None:
        self.active_event: CityEvent | None = None

    async def get_active_city_event(self, guild_id: int) -> CityEvent | None:
        return self.active_event if guild_id == GUILD_ID else None


class TestCityEventRepository:
    def test_no_active_event_initially(self, repo: GameRepository, run) -> None:
        result = run(repo.get_active_city_event(GUILD_ID))
        assert result is None

    def test_replace_creates_event(self, repo: GameRepository, run) -> None:
        now = utcnow()
        effect = CityEventEffect(operation_success_delta=-15, operation_heat_delta=1)
        event = run(
            repo.replace_active_city_event(
                GUILD_ID,
                event_key="police_sweep",
                headline="Police Sweep",
                description="Cops are everywhere.",
                effect=effect,
                starts_at=isoformat(now) or "",
                ends_at=isoformat(now + timedelta(hours=4)) or "",
            )
        )
        assert event.event_key == "police_sweep"
        assert event.headline == "Police Sweep"
        assert event.effect.operation_success_delta == -15
        assert event.effect.operation_heat_delta == 1

    def test_get_active_returns_created_event(self, repo: GameRepository, run) -> None:
        now = utcnow()
        effect = CityEventEffect(casino_payout_multiplier=1.5)
        run(
            repo.replace_active_city_event(
                GUILD_ID,
                event_key="casino_rush",
                headline="Casino Rush",
                description="The house is throwing money.",
                effect=effect,
                starts_at=isoformat(now) or "",
                ends_at=isoformat(now + timedelta(hours=4)) or "",
            )
        )
        loaded = run(repo.get_active_city_event(GUILD_ID))
        assert loaded is not None
        assert loaded.event_key == "casino_rush"
        assert loaded.effect.casino_payout_multiplier == 1.5

    def test_expired_event_not_returned(self, repo: GameRepository, run) -> None:
        now = utcnow()
        effect = CityEventEffect()
        run(
            repo.replace_active_city_event(
                GUILD_ID,
                event_key="harbor_shipment",
                headline="Harbor Shipment",
                description="Fresh cargo.",
                effect=effect,
                starts_at=isoformat(now - timedelta(hours=5)) or "",
                ends_at=isoformat(now - timedelta(hours=1)) or "",
            )
        )
        loaded = run(repo.get_active_city_event(GUILD_ID))
        assert loaded is None

    def test_replace_deletes_previous_event(self, repo: GameRepository, run) -> None:
        now = utcnow()
        effect_a = CityEventEffect(shop_discount_percent=25)
        run(
            repo.replace_active_city_event(
                GUILD_ID,
                event_key="black_market_sale",
                headline="Sale A",
                description="First sale.",
                effect=effect_a,
                starts_at=isoformat(now) or "",
                ends_at=isoformat(now + timedelta(hours=4)) or "",
            )
        )
        effect_b = CityEventEffect(casino_payout_multiplier=1.5)
        run(
            repo.replace_active_city_event(
                GUILD_ID,
                event_key="casino_rush",
                headline="Rush B",
                description="Second event.",
                effect=effect_b,
                starts_at=isoformat(now) or "",
                ends_at=isoformat(now + timedelta(hours=4)) or "",
            )
        )
        loaded = run(repo.get_active_city_event(GUILD_ID))
        assert loaded is not None
        assert loaded.event_key == "casino_rush"


# ── Effect Tests ────────────────────────────────────────────────


class TestCityEventEffects:
    """Verify each event type has deterministic, bounded modifiers."""

    def test_police_sweep_reduces_success(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        effect = CityEventEffect(operation_success_delta=-15, operation_heat_delta=1)
        # Use class method directly (no bot arg needed for pure functions)
        result = CityEventDirectorService.apply_operation_success_effect(None, 80, effect)  # type: ignore[arg-type]
        assert result == 65
        assert result >= 5  # bounded minimum

    def test_police_sweep_adds_heat(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        effect = CityEventEffect(operation_heat_delta=1)
        result = CityEventDirectorService.apply_operation_heat_effect(None, 2, effect)  # type: ignore[arg-type]
        assert result == 3

    def test_black_market_sale_discounts_price(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        effect = CityEventEffect(shop_discount_percent=25)
        result = CityEventDirectorService.apply_shop_price_effect(None, 500, effect)  # type: ignore[arg-type]
        assert result == 375

    def test_casino_rush_boosts_payout(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        effect = CityEventEffect(casino_payout_multiplier=1.5)
        result = CityEventDirectorService.apply_casino_payout_effect(None, 200, effect)  # type: ignore[arg-type]
        assert result == 300

    def test_harbor_shipment_boosts_op_payout(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        effect = CityEventEffect(operation_payout_multiplier=1.4)
        result = CityEventDirectorService.apply_operation_payout_effect(None, 150, effect)  # type: ignore[arg-type]
        assert result == 210

    def test_no_event_is_identity(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        identity = CityEventEffect()
        assert CityEventDirectorService.apply_operation_success_effect(None, 60, identity) == 60  # type: ignore[arg-type]
        assert CityEventDirectorService.apply_operation_payout_effect(None, 300, identity) == 300  # type: ignore[arg-type]
        assert CityEventDirectorService.apply_shop_price_effect(None, 500, identity) == 500  # type: ignore[arg-type]
        assert CityEventDirectorService.apply_casino_payout_effect(None, 200, identity) == 200  # type: ignore[arg-type]
        assert CityEventDirectorService.apply_operation_heat_effect(None, 2, identity) == 2  # type: ignore[arg-type]

    def test_success_bounded_floor(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        extreme = CityEventEffect(operation_success_delta=-100)
        result = CityEventDirectorService.apply_operation_success_effect(None, 50, extreme)  # type: ignore[arg-type]
        assert result == 5  # minimum floor

    def test_success_bounded_ceiling(self) -> None:
        from vicecity.services.city_events import CityEventDirectorService

        extreme = CityEventEffect(operation_success_delta=100)
        result = CityEventDirectorService.apply_operation_success_effect(None, 50, extreme)  # type: ignore[arg-type]
        assert result == 95  # maximum ceiling


# ── Gemini Fallback Tests ───────────────────────────────────────


class TestGeminiFallback:
    """Verify event copy generation works without an API key."""

    def test_fallback_produces_valid_copy(self) -> None:
        fallback = GeminiCityEventResult(
            headline="Police Sweep",
            description="Police Sweep is live. Operations lose 15 success chance. Operations generate +1 extra Heat.",
            broadcast="Police Sweep just hit the city. Operations lose 15 success chance.",
        )
        assert fallback.headline == "Police Sweep"
        assert "Operations" in fallback.description
        assert len(fallback.broadcast) > 0

    def test_all_event_types_have_fallback_copy(self) -> None:
        bot = SimpleNamespace(
            repo=SimpleNamespace(),
            scheduler=FakeScheduler(),
            city_service=None,
            embed_factory=EmbedFactory(),
            visual_service=None,
        )
        service = CityEventDirectorService(bot)  # type: ignore[arg-type]
        assert set(service.catalog) == {"police_sweep", "black_market_sale", "casino_rush", "harbor_shipment"}

    def test_trigger_event_uses_fallback_without_api_key(self, repo: GameRepository, run) -> None:
        bot = SimpleNamespace(
            config=SimpleNamespace(gemini_api_key=None, gemini_model="gemini-2.0-flash"),
            repo=repo,
            scheduler=FakeScheduler(),
            city_service=None,
            embed_factory=EmbedFactory(),
            visual_service=None,
        )
        bot.gemini_service = GeminiService(bot)  # type: ignore[attr-defined]
        service = CityEventDirectorService(bot)  # type: ignore[arg-type]

        event = run(service.trigger_event(GUILD_ID, "police_sweep", announce=False))

        assert event.event_key == "police_sweep"
        assert event.headline == "Police Sweep"
        assert event.effect.operation_success_delta == -15
        assert bot.gemini_service.last_request_status == "Fallback used: GEMINI_API_KEY is not set."
        assert f"city-event:{GUILD_ID}" in bot.scheduler.jobs


class TestCityEventEmbeds:
    def test_embed_builder_returns_embed_for_each_event_type(self, run) -> None:
        repo = ActiveEventRepo()
        bot = SimpleNamespace(
            repo=repo,
            scheduler=FakeScheduler(),
            city_service=None,
            embed_factory=EmbedFactory(),
            visual_service=None,
        )
        service = CityEventDirectorService(bot)  # type: ignore[arg-type]
        now = utcnow()

        for definition in service.catalog.values():
            repo.active_event = CityEvent(
                guild_id=GUILD_ID,
                event_key=definition.key,
                headline=definition.name,
                description=f"{definition.name} is live.",
                effect=definition.effect,
                starts_at=now,
                ends_at=now + timedelta(hours=4),
                created_at=now,
            )

            embed, file = run(service.build_city_event_embed(GUILD_ID))

            assert embed.title == definition.name
            assert embed.description == f"{definition.name} is live."
            assert any(field.name == "Live Effect" for field in embed.fields)
            assert file is None


# ── CityEventEffect Model Tests ────────────────────────────────


class TestCityEventEffectModel:
    def test_from_payload_defaults(self) -> None:
        effect = CityEventEffect.from_payload(None)
        assert effect.operation_success_delta == 0
        assert effect.operation_heat_delta == 0
        assert effect.operation_payout_multiplier == 1.0
        assert effect.shop_discount_percent == 0
        assert effect.casino_payout_multiplier == 1.0

    def test_from_payload_partial(self) -> None:
        effect = CityEventEffect.from_payload({"shop_discount_percent": 25})
        assert effect.shop_discount_percent == 25
        assert effect.operation_success_delta == 0

    def test_roundtrip(self) -> None:
        original = CityEventEffect(
            operation_success_delta=-15,
            operation_heat_delta=1,
            operation_payout_multiplier=1.4,
            shop_discount_percent=25,
            casino_payout_multiplier=1.5,
        )
        payload = original.to_payload()
        restored = CityEventEffect.from_payload(payload)
        assert restored == original

    def test_json_roundtrip(self) -> None:
        original = CityEventEffect(casino_payout_multiplier=1.5)
        json_str = json.dumps(original.to_payload())
        restored = CityEventEffect.from_payload(json.loads(json_str))
        assert restored == original
