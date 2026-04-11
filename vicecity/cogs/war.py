from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from vicecity.utils import autocomplete
from vicecity.utils.checks import require_joined_player
from vicecity.views.action_hub import QuickActionsView

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class WarCog(commands.Cog):
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "ViceCityBot") -> "WarCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    @commands.hybrid_command(name="attack")
    @app_commands.autocomplete(turf_name=autocomplete.turf_names)
    @require_joined_player()
    async def attack(self, ctx: commands.Context, *, turf_name: str) -> None:
        war = await self.bot.war_service.declare_war(ctx.author, turf_name)  # type: ignore[arg-type, union-attr]
        file = None
        embed = self.bot.embed_factory.danger(
            "Turf War Declared",
            f"Turf War #{war['id']} is live. Rally with `/assault` or `/defend`.",
        )
        if self.bot.visual_service is not None:
            file = await self.bot.visual_service.build_event_banner("turf_win", subtitle=turf_name)
            if file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @commands.hybrid_command(name="assault")
    @require_joined_player()
    async def assault(self, ctx: commands.Context) -> None:
        result = await self.bot.war_service.commit(ctx.author, "assault")  # type: ignore[arg-type, union-attr]
        embed = self.bot.embed_factory.standard(
            "Assault Committed",
            f"War #{result['war']['id']} | Power: **{result['power']:.2f}** | Weapons used: **{result['weapons_used']}**.",
        )
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="defend")
    @require_joined_player()
    async def defend(self, ctx: commands.Context) -> None:
        result = await self.bot.war_service.commit(ctx.author, "defend")  # type: ignore[arg-type, union-attr]
        embed = self.bot.embed_factory.standard(
            "Defense Committed",
            f"War #{result['war']['id']} | Power: **{result['power']:.2f}** | Weapons used: **{result['weapons_used']}**.",
        )
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))
