from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from vicecity.utils import autocomplete
from vicecity.utils.checks import require_joined_player
from vicecity.utils.time import utcnow
from vicecity.views.action_hub import GuideView, HelpNavView, QuickActionsView, ShopSelectView, build_guide_embed, build_help_embed

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class CoreCog(commands.Cog):
    TIP_COOLDOWN_SECONDS = 90.0

    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        self.tip_cooldowns: dict[tuple[int, int], float] = {}

    @classmethod
    async def create(cls, bot: "ViceCityBot") -> "CoreCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    @commands.hybrid_command(name="join")
    async def join(self, ctx: commands.Context) -> None:
        player = await self.bot.city_service.join_city(ctx.author)  # type: ignore[arg-type, union-attr]
        gang = await self.bot.repo.get_gang(player["gang_id"])
        file = None
        if self.bot.visual_service is not None:
            file = await self.bot.visual_service.build_event_banner("join", subtitle=gang["name"] if gang else "")
        embed = self.bot.embed_factory.success(
            "You Joined Vice City",
            f"You were assigned to **{gang['name'] if gang else 'Unknown'}** and started with **500** Racks.",
        )
        if file is not None:
            embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @commands.hybrid_command(name="profile")
    async def profile(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        if ctx.interaction is not None:
            await ctx.defer()
        if self.bot.visual_service is None:
            embed = await self.bot.city_service.build_profile_embed(ctx.guild.id, target.id)  # type: ignore[union-attr]
            await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))
            return
        embed, file = await self.bot.visual_service.build_profile_card(ctx.guild.id, target.id)  # type: ignore[union-attr]
        await ctx.send(embed=embed, file=file, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="wallet")
    @require_joined_player()
    async def wallet(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_wallet_embed(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="daily")
    @require_joined_player()
    async def daily(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.claim_daily_reward(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_group(name="gang", invoke_without_command=True)
    @require_joined_player()
    async def gang(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_gang_embed(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @gang.command(name="deposit")
    @require_joined_player()
    async def gang_deposit(self, ctx: commands.Context, amount: int) -> None:
        wallet_balance, bank_balance = await self.bot.city_service.deposit_to_gang(ctx.guild.id, ctx.author.id, amount)  # type: ignore[union-attr]
        await ctx.send(
            embed=self.bot.embed_factory.reward(
                "Gang Deposit",
                f"Deposited **{amount}**. Wallet: **{wallet_balance}** | Gang bank: **{bank_balance}**.",
            ),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @gang.command(name="withdraw")
    @require_joined_player()
    async def gang_withdraw(self, ctx: commands.Context, amount: int) -> None:
        wallet_balance, bank_balance = await self.bot.city_service.withdraw_from_gang(ctx.guild.id, ctx.author.id, amount)  # type: ignore[union-attr]
        await ctx.send(
            embed=self.bot.embed_factory.reward(
                "Gang Withdrawal",
                f"Withdrew **{amount}**. Wallet: **{wallet_balance}** | Gang bank: **{bank_balance}**.",
            ),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @commands.hybrid_command(name="map")
    @require_joined_player()
    async def city_map(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_map_embed(ctx.guild.id)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="news")
    async def news(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_news_embed(ctx.guild.id)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="wanted")
    async def wanted(self, ctx: commands.Context) -> None:
        if ctx.interaction is not None:
            await ctx.defer()
        embed, file = await self.bot.city_service.build_wanted_embed(ctx.guild.id)  # type: ignore[union-attr]
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @commands.hybrid_command(name="leaderboard")
    async def leaderboard(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_leaderboard_embed(ctx.guild.id)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="pay")
    @require_joined_player()
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        if amount <= 0:
            raise commands.CheckFailure("Amount must be greater than zero.")
        target = await self.bot.repo.get_player(ctx.guild.id, member.id)  # type: ignore[union-attr]
        if target is None or not target["is_joined"]:
            raise commands.CheckFailure("That member has not joined Vice City yet.")
        await self.bot.repo.transfer_wallet(ctx.guild.id, ctx.author.id, member.id, amount)  # type: ignore[union-attr]
        await ctx.send(
            embed=self.bot.embed_factory.reward("Payment Sent", f"You sent **{amount}** Racks to {member.mention}."),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @commands.hybrid_command(name="shop")
    async def shop(self, ctx: commands.Context) -> None:
        embed = self.bot.city_service.build_shop_embed()  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=ShopSelectView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="buy")
    @app_commands.autocomplete(item_name=autocomplete.item_names)
    @require_joined_player()
    async def buy(self, ctx: commands.Context, item_name: str) -> None:
        embed = await self.bot.city_service.buy_item(ctx.guild.id, ctx.author.id, item_name)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
        await ctx.send(embed=build_help_embed(), view=HelpNavView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="guide")
    async def guide(self, ctx: commands.Context) -> None:
        await ctx.send(embed=build_guide_embed(), view=GuideView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="tip")
    @require_joined_player()
    async def tip(self, ctx: commands.Context) -> None:
        if not self.bot.config.disable_cooldowns:
            key = (ctx.guild.id if ctx.guild is not None else 0, ctx.author.id)
            now_timestamp = utcnow().timestamp()
            last_used = self.tip_cooldowns.get(key)
            if last_used is not None:
                retry_after = self.TIP_COOLDOWN_SECONDS - (now_timestamp - last_used)
                if retry_after > 0:
                    raise commands.CommandOnCooldown(
                        commands.Cooldown(1, self.TIP_COOLDOWN_SECONDS),
                        retry_after,
                        commands.BucketType.user,
                    )
            self.tip_cooldowns[key] = now_timestamp

        if ctx.interaction is not None:
            await ctx.defer()
        embed, media_key = await self.bot.city_service.build_tip_embed(ctx.guild.id)  # type: ignore[union-attr]
        file = None
        if self.bot.visual_service is not None and media_key:
            file = await self.bot.visual_service.build_event_banner(media_key, subtitle="Informant line")
            if file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @commands.hybrid_command(name="advise")
    @require_joined_player()
    async def advise(self, ctx: commands.Context) -> None:
        """Ask your gang's AI consigliere for strategic advice based on the full game state."""
        if ctx.interaction is not None:
            await ctx.defer()
        brief = await self.bot.city_service.build_consigliere_brief(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        result = await self.bot.groq_service.generate_consigliere_advice(brief=brief)  # type: ignore[union-attr]
        gang_name = brief.get("your_gang", {}).get("name", "Your Gang")
        embed = self.bot.embed_factory.standard(
            f"🤵 {gang_name} Consigliere",
            f"**{result['headline']}**\n\n{result['advice']}",
        )
        embed.add_field(name="📌 Recommended Move", value=result["move"], inline=False)
        # Add a compact game-state summary so the player sees what the AI sees
        your_gang = brief.get("your_gang", {})
        embed.add_field(
            name="Your Gang Intel",
            value=(
                f"Bank: **{your_gang.get('bank_balance', 0)}** | "
                f"Turfs: **{your_gang.get('turf_count', 0)}** | "
                f"Crew: **{your_gang.get('member_count', 0)}** | "
                f"Avg Heat: **{your_gang.get('average_heat', 0)}**"
            ),
            inline=False,
        )
        rival_lines = []
        for rival in brief.get("rivals", [])[:3]:
            rival_lines.append(
                f"**{rival['name']}** — Bank: {rival.get('bank_balance', 0)} | "
                f"Turfs: {rival.get('turf_count', 0)} | Crew: {rival.get('member_count', 0)}"
            )
        if rival_lines:
            embed.add_field(name="Rival Intel", value="\n".join(rival_lines), inline=False)
        active_war = brief.get("active_war")
        if active_war:
            embed.add_field(
                name="⚔️ Active War",
                value=(
                    f"**{active_war['your_side'].title()}** at **{active_war['turf_name']}** "
                    f"vs **{active_war['opponent_name']}**"
                ),
                inline=False,
            )
        city_event = brief.get("city_event")
        if city_event:
            embed.add_field(
                name="🌆 City Event",
                value=f"**{city_event['name']}** — {', '.join(city_event.get('effects', []))}",
                inline=False,
            )
        file = None
        if self.bot.visual_service is not None:
            file = await self.bot.visual_service.build_event_banner("informant", subtitle="Consigliere")
            if file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)
