from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from vicecity.utils.checks import require_joined_player
from vicecity.views.action_hub import QuickActionsView

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class SocialCog(commands.Cog):
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "ViceCityBot") -> "SocialCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    @commands.hybrid_command(name="rat")
    @require_joined_player()
    async def rat(self, ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
        embed = await self.bot.social_service.rat_out(ctx.author, member, reason)  # type: ignore[arg-type, union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_group(name="vote", invoke_without_command=True)
    @require_joined_player()
    async def vote(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard("Votes", "Use `/vote exile @member` to cast an exile vote."),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @vote.command(name="exile")
    @require_joined_player()
    async def vote_exile(self, ctx: commands.Context, member: discord.Member) -> None:
        embed = await self.bot.social_service.vote_exile(ctx.author, member)  # type: ignore[arg-type, union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_group(name="challenge", invoke_without_command=True)
    @require_joined_player()
    async def challenge(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard("Leadership", "Use `/challenge boss` to start or join a leadership challenge."),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @challenge.command(name="boss")
    @require_joined_player()
    async def challenge_boss(self, ctx: commands.Context) -> None:
        embed = await self.bot.social_service.challenge_boss(ctx.author)  # type: ignore[arg-type, union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))
