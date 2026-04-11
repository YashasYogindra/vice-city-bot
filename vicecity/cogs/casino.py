from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from discord.ext import commands

from vicecity.utils.checks import require_joined_player
from vicecity.views.action_hub import CasinoSelectView, QuickActionsView

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class CasinoCog(commands.Cog):
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "ViceCityBot") -> "CasinoCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    @commands.hybrid_group(name="casino", invoke_without_command=True)
    @require_joined_player()
    async def casino(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard(
                "Casino",
                "Pick a game from the selector below or use `/casino slots`, `/casino flip`, `/casino duel`, or `/casino blackjack`.",
            ),
            view=CasinoSelectView(self.bot, ctx.author.id),
        )

    @casino.command(name="slots")
    @require_joined_player()
    async def casino_slots(self, ctx: commands.Context, amount: int) -> None:
        embed = await self.bot.casino_service.play_slots(ctx.author, amount)  # type: ignore[arg-type, union-attr]
        file = None
        if self.bot.visual_service is not None:
            media_key = "slots_win" if embed.color == discord.Color(0xFFD700) else "slots_loss"
            file = await self.bot.visual_service.build_event_banner(media_key, subtitle="Slots")
            if file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @casino.command(name="flip")
    @require_joined_player()
    async def casino_flip(self, ctx: commands.Context, amount: int, choice: Literal["heads", "tails"]) -> None:
        embed = await self.bot.casino_service.flip_house(ctx.author, amount, choice)  # type: ignore[arg-type, union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @casino.command(name="duel")
    @require_joined_player()
    async def casino_duel(self, ctx: commands.Context, opponent: discord.Member, amount: int) -> None:
        embed = await self.bot.casino_service.flip_challenge(ctx.author, opponent, amount, ctx.channel)  # type: ignore[arg-type, union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @casino.command(name="blackjack")
    @require_joined_player()
    async def casino_blackjack(self, ctx: commands.Context, amount: int) -> None:
        await self.bot.casino_service.start_blackjack(ctx.author, amount, ctx.channel)  # type: ignore[arg-type, union-attr]
