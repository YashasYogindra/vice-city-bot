from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from vicecity.utils.time import utcnow, format_duration

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class StatusCog(commands.Cog):
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "ViceCityBot") -> "StatusCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    @commands.hybrid_command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        """Show bot uptime, scheduler state, Gemini availability, and active city event."""
        uptime_seconds = (utcnow() - self.bot.start_time).total_seconds()
        uptime_text = format_duration(uptime_seconds)

        # Scheduler state
        scheduler = getattr(self.bot, "scheduler", None)
        if scheduler is not None and scheduler.running:
            pending_jobs = len(scheduler.get_jobs())
            scheduler_text = f"Running ({pending_jobs} job{'s' if pending_jobs != 1 else ''})"
        else:
            scheduler_text = "Stopped"

        # Gemini availability
        gemini_key = self.bot.config.gemini_api_key
        last_request = "Gemini service has not initialized."
        if self.bot.gemini_service is not None:
            last_request = self.bot.gemini_service.last_request_status
        if gemini_key:
            gemini_text = f"Enabled ({self.bot.config.gemini_model})\nLast request: {last_request}"
        else:
            gemini_text = f"Disabled (deterministic fallback active)\nLast request: {last_request}"

        # Guild sync target
        guild = self.bot.get_guild(self.bot.config.guild_id)
        guild_text = f"{guild.name} ({guild.id})" if guild else f"ID {self.bot.config.guild_id} (not cached)"

        # Active city event
        event_text = "No active event."
        if self.bot.event_service is not None and guild is not None:
            event = await self.bot.event_service.get_active_event(guild.id)
            if event is not None:
                remaining = discord.utils.format_dt(event.ends_at, style="R")
                definition = self.bot.event_service.event_definition(event.event_key)
                event_text = f"**{definition.name}** until {remaining}"

        embed = self.bot.embed_factory.standard(
            "Vice City OS Status",
            "System health and runtime state for judging confidence.",
        )
        embed.add_field(name="Uptime", value=uptime_text, inline=True)
        embed.add_field(name="Scheduler", value=scheduler_text, inline=True)
        embed.add_field(name="Gemini AI", value=gemini_text, inline=False)
        embed.add_field(name="Guild Target", value=guild_text, inline=False)
        embed.add_field(name="City Event", value=event_text, inline=False)
        await ctx.send(embed=embed)
