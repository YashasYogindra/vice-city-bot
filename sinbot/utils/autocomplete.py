from __future__ import annotations

from collections.abc import Iterable

import discord
from discord import app_commands

from sinbot.constants import BLACK_MARKET_ITEMS, DRUG_RUN_CONFIG, HEIST_ROLES


def _choices(values: Iterable[str], current: str) -> list[app_commands.Choice[str]]:
    current_lower = current.lower().strip()
    filtered = [
        value
        for value in values
        if not current_lower or current_lower in value.lower()
    ]
    return [app_commands.Choice(name=value.title(), value=value) for value in filtered[:25]]


async def risk_levels(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return _choices(DRUG_RUN_CONFIG.keys(), current)


async def item_names(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return _choices(BLACK_MARKET_ITEMS.keys(), current)


async def heist_roles(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return _choices(HEIST_ROLES, current)


async def turf_names(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    bot = interaction.client
    guild_id = interaction.guild_id
    if guild_id is None or not hasattr(bot, "repo"):
        return []
    turfs = await bot.repo.list_turfs(guild_id)
    return _choices((turf["name"] for turf in turfs), current)


async def gang_names(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    bot = interaction.client
    guild_id = interaction.guild_id
    if guild_id is None or not hasattr(bot, "repo"):
        return []
    gangs = await bot.repo.list_gangs(guild_id)
    return _choices((gang["name"] for gang in gangs), current)


async def city_event_keys(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    bot = interaction.client
    event_service = getattr(bot, "event_service", None)
    if event_service is None:
        return []
    values = [definition.key for definition in event_service.catalog.values()]
    return _choices(values, current)
