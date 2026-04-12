from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from apscheduler.jobstores.base import JobLookupError

from vicecity.constants import CITY_EVENT_DURATION_HOURS, RACKS_EMOJI
from vicecity.models.events import CityEvent, CityEventEffect, GroqCityEventResult
from vicecity.utils.time import isoformat, utcnow

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


@dataclass(frozen=True, slots=True)
class CityEventDefinition:
    key: str
    name: str
    media_key: str
    color_kind: str
    vibe: str
    mechanics: tuple[str, ...]
    effect: CityEventEffect


class CityEventDirectorService:
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        self.random = random.Random()
        self.catalog: dict[str, CityEventDefinition] = {
            "police_sweep": CityEventDefinition(
                key="police_sweep",
                name="Police Sweep",
                media_key="event_police_sweep",
                color_kind="danger",
                vibe="sirens, checkpoints, detectives flooding every hot corner",
                mechanics=(
                    "Operations lose 15 success chance.",
                    "Operations generate +1 extra Heat.",
                ),
                effect=CityEventEffect(operation_success_delta=-15, operation_heat_delta=1),
            ),
            "black_market_sale": CityEventDefinition(
                key="black_market_sale",
                name="Black Market Sale",
                media_key="event_black_market_sale",
                color_kind="reward",
                vibe="dealers slashing prices before sunrise and moving stock fast",
                mechanics=("Black market prices are 25 percent lower.",),
                effect=CityEventEffect(shop_discount_percent=25),
            ),
            "casino_rush": CityEventDefinition(
                key="casino_rush",
                name="Casino Rush",
                media_key="event_casino_rush",
                color_kind="reward",
                vibe="packed tables, loud floors, and a house throwing money around to keep the room electric",
                mechanics=("Casino payouts are boosted by 50 percent.",),
                effect=CityEventEffect(casino_payout_multiplier=1.5),
            ),
            "harbor_shipment": CityEventDefinition(
                key="harbor_shipment",
                name="Harbor Shipment",
                media_key="event_harbor_shipment",
                color_kind="reward",
                vibe="fresh cargo flooding the docks and every courier in the city smelling fast money",
                mechanics=("Operation payouts are boosted by 40 percent.",),
                effect=CityEventEffect(operation_payout_multiplier=1.4),
            ),
        }

    def _job_id(self, guild_id: int) -> str:
        return f"city-event:{guild_id}"

    async def get_active_event(self, guild_id: int) -> CityEvent | None:
        return await self.bot.repo.get_active_city_event(guild_id)

    async def ensure_active_event(self, guild_id: int) -> CityEvent:
        active = await self.get_active_event(guild_id)
        if active is not None:
            self._schedule_rotation(guild_id, active.ends_at)
            return active
        return await self.activate_random_event(guild_id, announce=True)

    async def activate_random_event(self, guild_id: int, *, announce: bool, exclude_key: str | None = None) -> CityEvent:
        choices = [definition for definition in self.catalog.values() if definition.key != exclude_key]
        definition = self.random.choice(choices or list(self.catalog.values()))
        return await self.trigger_event(guild_id, definition.key, announce=announce)

    async def trigger_event(self, guild_id: int, event_key: str, *, announce: bool = True) -> CityEvent:
        if event_key not in self.catalog:
            raise ValueError(f"Unknown city event: {event_key}")
        definition = self.catalog[event_key]
        now = utcnow()
        ends_at = now + timedelta(hours=CITY_EVENT_DURATION_HOURS)
        fallback = GroqCityEventResult(
            headline=definition.name,
            description=f"{definition.name} is live in Vice City. {' '.join(definition.mechanics)}",
            broadcast=f"{definition.name} just hit the city. {' '.join(definition.mechanics)}",
        )
        copy = await self.bot.groq_service.generate_city_event_copy(  # type: ignore[union-attr]
            event_name=definition.name,
            vibe=definition.vibe,
            mechanics=list(definition.mechanics),
            fallback=fallback,
        )
        event = await self.bot.repo.replace_active_city_event(
            guild_id,
            event_key=definition.key,
            headline=copy.headline,
            description=copy.description,
            effect=definition.effect,
            starts_at=isoformat(now) or "",
            ends_at=isoformat(ends_at) or "",
        )
        self._schedule_rotation(guild_id, event.ends_at)
        if announce:
            await self._announce_event(event, broadcast=copy.broadcast)
        if self.bot.city_service is not None:
            await self.bot.city_service.refresh_vault(guild_id)
        return event

    async def rotate_event(self, guild_id: int) -> None:
        active = await self.get_active_event(guild_id)
        exclude_key = active.event_key if active is not None else None
        await self.activate_random_event(guild_id, announce=True, exclude_key=exclude_key)

    def _schedule_rotation(self, guild_id: int, run_at) -> None:
        self.bot.scheduler.add_job(
            self.rotate_event,
            "date",
            run_date=run_at,
            id=self._job_id(guild_id),
            replace_existing=True,
            kwargs={"guild_id": guild_id},
        )

    def cancel_rotation(self, guild_id: int) -> None:
        try:
            self.bot.scheduler.remove_job(self._job_id(guild_id))
        except JobLookupError:
            pass

    def event_definition(self, event_key: str) -> CityEventDefinition:
        return self.catalog[event_key]

    def describe_effects(self, event: CityEvent) -> list[str]:
        definition = self.event_definition(event.event_key)
        return list(definition.mechanics)

    def effect_summary(self, event: CityEvent | None) -> str:
        if event is None:
            return "No live city event."
        remaining = discord.utils.format_dt(event.ends_at, style="R")
        return f"**{self.event_definition(event.event_key).name}** until {remaining}"

    async def build_city_event_embed(self, guild_id: int) -> tuple[discord.Embed, discord.File | None]:
        active = await self.get_active_event(guild_id)
        if active is None:
            embed = self.bot.embed_factory.standard("City Event", "Vice City is between citywide incidents right now.")
            return embed, None
        definition = self.event_definition(active.event_key)
        embed_factory = {
            "danger": self.bot.embed_factory.danger,
            "reward": self.bot.embed_factory.reward,
            "success": self.bot.embed_factory.success,
            "standard": self.bot.embed_factory.standard,
        }.get(definition.color_kind, self.bot.embed_factory.standard)
        embed = embed_factory(active.headline, active.description)
        embed.add_field(name="Live Effect", value="\n".join(f"- {line}" for line in definition.mechanics), inline=False)
        embed.add_field(name="Window", value=f"Started {discord.utils.format_dt(active.starts_at, style='R')}", inline=True)
        embed.add_field(name="Ends", value=discord.utils.format_dt(active.ends_at, style="R"), inline=True)
        file = None
        if self.bot.visual_service is not None:
            file = await self.bot.visual_service.build_event_banner(definition.media_key, subtitle=definition.name)
            if file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        return embed, file

    async def get_active_effect(self, guild_id: int) -> CityEventEffect:
        active = await self.get_active_event(guild_id)
        return active.effect if active is not None else CityEventEffect()

    def apply_shop_price_effect(self, base_price: int, effect: CityEventEffect) -> int:
        discounted = base_price * max(0, 100 - effect.shop_discount_percent) // 100
        return max(1, discounted)

    def apply_operation_payout_effect(self, base_payout: int, effect: CityEventEffect) -> int:
        return max(0, int(round(base_payout * effect.operation_payout_multiplier)))

    def apply_casino_payout_effect(self, base_payout: int, effect: CityEventEffect) -> int:
        return max(0, int(round(base_payout * effect.casino_payout_multiplier)))

    def apply_operation_success_effect(self, base_success: int, effect: CityEventEffect) -> int:
        return max(5, min(95, base_success + effect.operation_success_delta))

    def apply_operation_heat_effect(self, base_heat: int, effect: CityEventEffect) -> int:
        return max(0, base_heat + effect.operation_heat_delta)

    async def _announce_event(self, event: CityEvent, *, broadcast: str) -> None:
        definition = self.event_definition(event.event_key)
        await self.bot.repo.add_news_event(event.guild_id, event.headline, broadcast, definition.color_kind)
        channel = await self.bot.city_service.get_configured_channel(event.guild_id, "news_channel_id")  # type: ignore[union-attr]
        if channel is None:
            return
        embed, file = await self.build_city_event_embed(event.guild_id)
        if file is not None:
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)
        if self.bot.city_service is not None:
            await self.bot.city_service.refresh_vault(event.guild_id)

    def price_note(self, event: CityEvent | None) -> str | None:
        if event is None or event.effect.shop_discount_percent <= 0:
            return None
        return f"{definition_name(self.catalog[event.event_key])}: {event.effect.shop_discount_percent}% off"


def definition_name(definition: CityEventDefinition) -> str:
    return definition.name
