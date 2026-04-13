from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from sinbot.constants import CITY_CHANNELS, GANGS, TURF_NAMES
from sinbot.utils.time import isoformat, utcnow

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class BootstrapService:
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot

    async def ensure_guild_setup(self, guild: discord.Guild) -> None:
        settings = await self.bot.repo.ensure_guild_settings(guild.id)
        mayor_role = await self._ensure_mayor_role(guild, settings.get("mayor_role_id"))
        await self._ensure_owner_has_role(guild.owner, mayor_role)
        await self.bot.repo.update_guild_settings(guild.id, mayor_role_id=mayor_role.id, city_synced_at=isoformat(utcnow()))

        city_channels = await self._ensure_city_channels(guild)
        await self.bot.repo.update_guild_settings(guild.id, **city_channels)

        gang_records = await self._ensure_gangs(guild, mayor_role)
        await self._ensure_turfs(guild.id, gang_records)
        await self.bot.repo.ensure_player(guild.id, guild.owner_id, rank="Mayor", wallet=0, is_joined=0)

    async def _ensure_mayor_role(self, guild: discord.Guild, stored_role_id: int | None) -> discord.Role:
        role = guild.get_role(stored_role_id) if stored_role_id else None
        if role:
            return role
        existing = discord.utils.get(guild.roles, name=self.bot.config.mayor_role_name)
        if existing:
            return existing
        return await guild.create_role(name=self.bot.config.mayor_role_name, color=discord.Colour.red(), mentionable=True)

    async def _ensure_owner_has_role(self, owner: discord.Member, role: discord.Role) -> None:
        if role not in owner.roles:
            await owner.add_roles(role, reason="SinBot mayor setup")

    async def _ensure_city_channels(self, guild: discord.Guild) -> dict[str, int]:
        settings = await self.bot.repo.get_guild_settings(guild.id) or {}
        bindings: dict[str, int] = {}
        for setting_key, channel_name in CITY_CHANNELS.items():
            channel = guild.get_channel(settings.get(setting_key)) if settings.get(setting_key) else None
            if channel is None:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel is None:
                channel = await guild.create_text_channel(channel_name, reason="SinBot setup")
            bindings[setting_key] = channel.id
        return bindings

    async def _ensure_gangs(self, guild: discord.Guild, mayor_role: discord.Role) -> list[dict]:
        results: list[dict] = []
        bot_member = guild.me or guild.get_member(self.bot.user.id)  # type: ignore[arg-type]
        for gang in GANGS:
            record = await self.bot.repo.upsert_gang(guild.id, gang.name)
            role = guild.get_role(record.get("role_id")) if record.get("role_id") else None
            if role is None:
                role = discord.utils.get(guild.roles, name=gang.role_name)
            if role is None:
                role = await guild.create_role(name=gang.role_name, color=gang.color, mentionable=True)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                mayor_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            if bot_member is not None:
                overwrites[bot_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            channel = guild.get_channel(record.get("channel_id")) if record.get("channel_id") else None
            if channel is None:
                channel = discord.utils.get(guild.text_channels, name=gang.channel_name)
            if channel is None:
                channel = await guild.create_text_channel(
                    gang.channel_name,
                    overwrites=overwrites,
                    reason="SinBot gang setup",
                )
            else:
                await channel.edit(overwrites=overwrites)

            updated = await self.bot.repo.upsert_gang(
                guild.id,
                gang.name,
                role_id=role.id,
                channel_id=channel.id,
            )
            results.append(updated)
        return results

    async def _ensure_turfs(self, guild_id: int, gang_records: list[dict]) -> None:
        existing = await self.bot.repo.list_turfs(guild_id)
        if existing:
            return
        turf_names = list(TURF_NAMES)
        for index, turf_name in enumerate(turf_names):
            owner = gang_records[index % len(gang_records)]
            await self.bot.repo.create_turf(guild_id, turf_name, owner["id"])
