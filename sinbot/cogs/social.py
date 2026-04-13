from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from sinbot.utils.checks import require_joined_player
from sinbot.views.action_hub import QuickActionsView
from sinbot import gifs

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class SocialCog(commands.Cog):
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "SinBot") -> "SocialCog":
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
        if gifs.RAT_REPORT:
            embed.set_image(url=gifs.RAT_REPORT)
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
        if gifs.EXILE_VOTE:
            embed.set_image(url=gifs.EXILE_VOTE)
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
        if gifs.BOSS_CHALLENGE:
            embed.set_image(url=gifs.BOSS_CHALLENGE)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))
