from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from sinbot.utils import autocomplete
from sinbot.utils.checks import require_joined_player
from sinbot.views.action_hub import OperateSelectView, QuickActionsView
from sinbot.views.negotiation import BustNegotiationView
from sinbot import gifs

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class OperationsCog(commands.Cog):
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "SinBot") -> "OperationsCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    @commands.hybrid_group(name="operate", invoke_without_command=True)
    @require_joined_player()
    async def operate(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard(
                "Operations",
                "Choose a risk level below for a drug run, or use `/operate arms @teammate` for a crew move.",
            ),
            view=OperateSelectView(self.bot, ctx.author.id),
        )

    @operate.command(name="drug")
    @app_commands.autocomplete(risk=autocomplete.risk_levels)
    @require_joined_player()
    async def operate_drug(self, ctx: commands.Context, risk: str) -> None:
        if ctx.interaction is not None:
            await ctx.defer()
        result = await self.bot.operations_service.run_drug_operation(ctx.author, risk)  # type: ignore[arg-type, union-attr]
        file = None
        if self.bot.visual_service is not None and result.media_key:
            file = await self.bot.visual_service.build_event_banner(result.media_key, subtitle=f"{risk.title()} risk")
            if result.bust_context is not None and gifs.DRUG_RUN_BUSTED:
                result.embed.set_image(url=gifs.DRUG_RUN_BUSTED)
            elif result.bust_context is None and gifs.DRUG_RUN_SUCCESS:
                result.embed.set_image(url=gifs.DRUG_RUN_SUCCESS)
            elif file is not None:
                result.embed.set_image(url=f"attachment://{file.filename}")
        view: discord.ui.View = QuickActionsView(self.bot, ctx.author.id)
        if result.bust_context is not None:
            view = BustNegotiationView(self.bot, ctx.author.id, result.bust_context)
        kwargs = {"embed": result.embed, "view": view}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @operate.command(name="arms")
    @require_joined_player()
    async def operate_arms(self, ctx: commands.Context, teammate: discord.Member) -> None:
        if ctx.interaction is not None:
            await ctx.defer()
        result = await self.bot.operations_service.run_arms_deal(ctx.author, teammate, ctx.channel)  # type: ignore[arg-type, union-attr]
        file = None
        if self.bot.visual_service is not None and result.media_key:
            file = await self.bot.visual_service.build_event_banner(result.media_key, subtitle=teammate.display_name)
            if "stung" in result.embed.description.lower() and gifs.ARMS_DEAL_BUSTED:
                result.embed.set_image(url=gifs.ARMS_DEAL_BUSTED)
            elif gifs.ARMS_DEAL_SUCCESS:
                result.embed.set_image(url=gifs.ARMS_DEAL_SUCCESS)
            elif file is not None:
                result.embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": result.embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)
