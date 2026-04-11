from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from discord.ext import commands

from vicecity.constants import RANK_ORDER

if False:  # pragma: no cover
    from vicecity.bot import ViceCityBot


T = TypeVar("T")


def _missing_rank(required_rank: str) -> commands.MissingPermissions:
    return commands.MissingPermissions([f"rank:{required_rank}"])


def require_rank(required_rank: str) -> Callable[[T], T]:
    async def predicate(ctx: commands.Context) -> bool:
        bot: "ViceCityBot" = ctx.bot  # type: ignore[assignment]
        player = await bot.repo.get_player(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        if player is None:
            raise _missing_rank(required_rank)
        player_rank = player["rank"]
        if RANK_ORDER.get(player_rank, -1) < RANK_ORDER[required_rank]:
            raise _missing_rank(required_rank)
        return True

    return commands.check(predicate)


def require_joined_player() -> Callable[[T], T]:
    async def predicate(ctx: commands.Context) -> bool:
        bot: "ViceCityBot" = ctx.bot  # type: ignore[assignment]
        player = await bot.repo.get_player(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        if player is None or not player["is_joined"]:
            raise commands.CheckFailure("You must use /join first.")
        return True

    return commands.check(predicate)


def require_mayor() -> Callable[[T], T]:
    async def predicate(ctx: commands.Context) -> bool:
        bot: "ViceCityBot" = ctx.bot  # type: ignore[assignment]
        settings = await bot.repo.get_guild_settings(ctx.guild.id)  # type: ignore[union-attr]
        if ctx.guild.owner_id == ctx.author.id:
            return True
        mayor_role_id = settings["mayor_role_id"] if settings else None
        if mayor_role_id and any(role.id == mayor_role_id for role in ctx.author.roles):  # type: ignore[attr-defined]
            return True
        raise commands.MissingPermissions(["rank:Mayor"])

    return commands.check(predicate)


def require_city_admin() -> Callable[[T], T]:
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild.owner_id == ctx.author.id:
            return True
        permissions = getattr(ctx.author, "guild_permissions", None)
        if permissions and (permissions.administrator or permissions.manage_guild):
            return True
        raise commands.MissingPermissions(["administrator"])

    return commands.check(predicate)
