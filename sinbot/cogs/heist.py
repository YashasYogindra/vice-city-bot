from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from sinbot.exceptions import HeistDMValidationError
from sinbot.utils import autocomplete
from sinbot.utils.checks import require_joined_player
from sinbot.views.action_hub import HeistRoleSelectView, QuickActionsView
from sinbot import gifs

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class HeistCog(commands.Cog):
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "SinBot") -> "HeistCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is not None:
            return
        await self.bot.heist_service.capture_dm_response(message)  # type: ignore[union-attr]

    @commands.hybrid_group(name="heist", invoke_without_command=True)
    @require_joined_player()
    async def heist(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard(
                "Heists",
                "Plan the Casino Job, fill hacker/driver/inside, and let the city watch it unfold live.",
            ),
            view=HeistRoleSelectView(self.bot),
        )

    @heist.command(name="plan")
    @require_joined_player()
    async def heist_plan(self, ctx: commands.Context, target: str = "casino") -> None:
        if target.lower() != "casino":
            raise commands.CheckFailure("The only available heist target is the casino.")
        heist = await self.bot.heist_service.create_heist(ctx.author)  # type: ignore[arg-type, union-attr]
        channel = ctx.guild.get_channel(heist["planning_channel_id"])  # type: ignore[union-attr]
        embed = self.bot.embed_factory.success(
            "Heist Planned",
            f"Planning channel created: {channel.mention if channel else 'unknown channel'}. Fill the crew there.",
        )
        if gifs.HEIST_PLAN:
            embed.set_image(url=gifs.HEIST_PLAN)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @heist.command(name="join")
    @app_commands.autocomplete(role_name=autocomplete.heist_roles)
    @require_joined_player()
    async def heist_join(self, ctx: commands.Context, role_name: str) -> None:
        heist = await self.bot.heist_service.join_role(ctx.author, role_name)  # type: ignore[arg-type, union-attr]
        embed = self.bot.embed_factory.success(
            "Heist Role Claimed",
            f"You joined the Casino Job as **{role_name.lower()}**. Heist #{heist['id']}.",
        )
        if gifs.HEIST_JOIN:
            embed.set_image(url=gifs.HEIST_JOIN)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @heist.command(name="go")
    @require_joined_player()
    async def heist_go(self, ctx: commands.Context) -> None:
        try:
            await self.bot.heist_service.launch_heist(ctx.author, status_channel_id=ctx.channel.id)  # type: ignore[arg-type, union-attr]
        except HeistDMValidationError as exc:
            failed_mentions = ", ".join(f"<@{user_id}>" for user_id in exc.failed_user_ids)
            await ctx.send(
                embed=self.bot.embed_factory.danger(
                    "Heist Cancelled",
                    f"These crew members have DMs disabled: {failed_mentions}.",
                ),
                view=QuickActionsView(self.bot, ctx.author.id),
            )
            return
        file = None
        embed = self.bot.embed_factory.danger(
            "Heist Launched",
            "DM prompts were sent to the crew. Vice City news is now watching the run in real time.",
        )
        if self.bot.visual_service is not None:
            file = await self.bot.visual_service.build_event_banner("heist_live", subtitle="Crew in motion")
            if gifs.HEIST_PLANNING:
                embed.set_image(url=gifs.HEIST_PLANNING)
            elif file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)
