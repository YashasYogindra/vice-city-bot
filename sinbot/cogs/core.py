from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from sinbot.utils import autocomplete
from sinbot.utils.checks import require_joined_player
from sinbot.utils.time import utcnow
from sinbot.views.action_hub import GuideView, HelpNavView, QuickActionsView, ShopSelectView, build_guide_embed, build_help_embed

if TYPE_CHECKING:
    from sinbot.bot import SinBot

from sinbot import gifs


class CoreCog(commands.Cog):
    TIP_COOLDOWN_SECONDS = 90.0

    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot
        self.tip_cooldowns: dict[tuple[int, int], float] = {}

    @classmethod
    async def create(cls, bot: "SinBot") -> "CoreCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    def _assert_test_mode_enabled(self) -> None:
        if not self.bot.config.disable_cooldowns:
            raise commands.CheckFailure("Testing commands are disabled. Set DISABLE_COOLDOWNS=true to enable them.")

    @commands.hybrid_command(name="join")
    async def join(self, ctx: commands.Context) -> None:
        player = await self.bot.city_service.join_city(ctx.author)  # type: ignore[arg-type, union-attr]
        gang = await self.bot.repo.get_gang(player["gang_id"])
        file = None
        if self.bot.visual_service is not None:
            file = await self.bot.visual_service.build_event_banner("join", subtitle=gang["name"] if gang else "")
        embed = self.bot.embed_factory.success(
            "You Joined The City",
            f"You were assigned to **{gang['name'] if gang else 'Unknown'}** and started with **500** Racks.",
        )
        if gifs.JOIN_CITY:
            embed.set_image(url=gifs.JOIN_CITY)
        elif file is not None:
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
        if gifs.PROFILE_CARD:
            embed.set_thumbnail(url=gifs.PROFILE_CARD)
        await ctx.send(embed=embed, file=file, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="wallet")
    @require_joined_player()
    async def wallet(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_wallet_embed(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        if gifs.WALLET_VIEW:
            embed.set_image(url=gifs.WALLET_VIEW)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="daily")
    @require_joined_player()
    async def daily(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.claim_daily_reward(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        if gifs.DAILY_STREAK:
            embed.set_image(url=gifs.DAILY_STREAK)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_group(name="gang", invoke_without_command=True)
    @require_joined_player()
    async def gang(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_gang_embed(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        if gifs.GANG_VIEW:
            embed.set_image(url=gifs.GANG_VIEW)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @gang.command(name="deposit")
    @require_joined_player()
    async def gang_deposit(self, ctx: commands.Context, amount: int) -> None:
        wallet_balance, bank_balance = await self.bot.city_service.deposit_to_gang(ctx.guild.id, ctx.author.id, amount)  # type: ignore[union-attr]
        embed = self.bot.embed_factory.reward(
            "Gang Deposit",
            f"Deposited **{amount}**. Wallet: **{wallet_balance}** | Gang bank: **{bank_balance}**.",
        )
        if gifs.GANG_DEPOSIT:
            embed.set_image(url=gifs.GANG_DEPOSIT)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @gang.command(name="withdraw")
    @require_joined_player()
    async def gang_withdraw(self, ctx: commands.Context, amount: int) -> None:
        wallet_balance, bank_balance = await self.bot.city_service.withdraw_from_gang(ctx.guild.id, ctx.author.id, amount)  # type: ignore[union-attr]
        embed = self.bot.embed_factory.reward(
            "Gang Withdrawal",
            f"Withdrew **{amount}**. Wallet: **{wallet_balance}** | Gang bank: **{bank_balance}**.",
        )
        if gifs.GANG_WITHDRAW:
            embed.set_image(url=gifs.GANG_WITHDRAW)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="map")
    @require_joined_player()
    async def city_map(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_map_embed(ctx.guild.id)  # type: ignore[union-attr]
        if gifs.CITY_MAP:
            embed.set_image(url=gifs.CITY_MAP)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="news")
    async def news(self, ctx: commands.Context) -> None:
        embed = await self.bot.city_service.build_news_embed(ctx.guild.id)  # type: ignore[union-attr]
        if gifs.CITY_NEWS:
            embed.set_image(url=gifs.CITY_NEWS)
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
        if gifs.LEADERBOARD:
            embed.set_image(url=gifs.LEADERBOARD)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="pay")
    @require_joined_player()
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        if amount <= 0:
            raise commands.CheckFailure("Amount must be greater than zero.")
        target = await self.bot.repo.get_player(ctx.guild.id, member.id)  # type: ignore[union-attr]
        if target is None or not target["is_joined"]:
            raise commands.CheckFailure("That member has not joined the city yet.")
        await self.bot.repo.transfer_wallet(ctx.guild.id, ctx.author.id, member.id, amount)  # type: ignore[union-attr]
        embed = self.bot.embed_factory.reward("Payment Sent", f"You sent **{amount}** Racks to {member.mention}.")
        if gifs.PAY_SENT:
            embed.set_image(url=gifs.PAY_SENT)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="shop")
    async def shop(self, ctx: commands.Context) -> None:
        embed = self.bot.city_service.build_shop_embed()  # type: ignore[union-attr]
        if gifs.SHOP_VIEW:
            embed.set_image(url=gifs.SHOP_VIEW)
        await ctx.send(embed=embed, view=ShopSelectView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="buy")
    @app_commands.autocomplete(item_name=autocomplete.item_names)
    @require_joined_player()
    async def buy(self, ctx: commands.Context, item_name: str) -> None:
        embed = await self.bot.city_service.buy_item(ctx.guild.id, ctx.author.id, item_name)  # type: ignore[union-attr]
        if gifs.ITEM_BOUGHT:
            embed.set_image(url=gifs.ITEM_BOUGHT)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
        await ctx.send(embed=build_help_embed(), view=HelpNavView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="guide")
    async def guide(self, ctx: commands.Context) -> None:
        await ctx.send(embed=build_guide_embed(), view=GuideView(self.bot, ctx.author.id))

    @commands.hybrid_group(name="test", invoke_without_command=True)
    @require_joined_player()
    async def test_group(self, ctx: commands.Context) -> None:
        self._assert_test_mode_enabled()
        await ctx.send(
            embed=self.bot.embed_factory.standard(
                "Test Commands",
                "Use `/test xp <amount>` to set your XP and `/test gang <gang_name>` to switch your gang.",
            ),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @test_group.command(name="xp")
    @require_joined_player()
    async def test_set_xp(self, ctx: commands.Context, xp: int) -> None:
        self._assert_test_mode_enabled()
        if ctx.interaction is not None:
            await ctx.defer()
        embed = await self.bot.city_service.set_self_xp_for_testing(ctx.guild.id, ctx.author.id, xp)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @test_group.command(name="gang")
    @app_commands.autocomplete(gang_name=autocomplete.gang_names)
    @require_joined_player()
    async def test_switch_gang(self, ctx: commands.Context, gang_name: str) -> None:
        self._assert_test_mode_enabled()
        if not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("This command must be used in a server.")
        if ctx.interaction is not None:
            await ctx.defer()
        embed = await self.bot.city_service.switch_gang_for_testing(ctx.author, gang_name)  # type: ignore[union-attr]
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @test_group.command(name="jail")
    @require_joined_player()
    async def test_free_jail(self, ctx: commands.Context) -> None:
        """(Test mode) Immediately release yourself from jail."""
        self._assert_test_mode_enabled()
        if ctx.interaction is not None:
            await ctx.defer()
        jail = await self.bot.repo.get_active_jail_for_user(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        if jail is None:
            await ctx.send(
                embed=self.bot.embed_factory.standard("Not Jailed", "You are not currently in jail."),
                view=QuickActionsView(self.bot, ctx.author.id),
            )
            return
        await self.bot.heat_service.release_jail(jail["id"], ctx.guild.id, ctx.author.id, announce=False)  # type: ignore[union-attr]
        await ctx.send(
            embed=self.bot.embed_factory.success(
                "Released from Jail",
                "Test mode: you've been freed instantly. Heat remains — run `/test xp` to reset if needed.",
            ),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @test_group.command(name="heat")
    @require_joined_player()
    async def test_set_heat(self, ctx: commands.Context, heat: int) -> None:
        """(Test mode) Set your own heat level (0-5)."""
        self._assert_test_mode_enabled()
        if ctx.interaction is not None:
            await ctx.defer()
        heat = max(0, min(5, heat))
        await self.bot.repo.update_player(ctx.guild.id, ctx.author.id, heat=heat)  # type: ignore[union-attr]
        await ctx.send(
            embed=self.bot.embed_factory.standard(
                "Heat Updated",
                f"Your heat is now **{heat}**. Note: jailing is skipped in test mode.",
            ),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

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
            if gifs.STREET_TIP:
                embed.set_image(url=gifs.STREET_TIP)
            elif file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        kwargs = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @commands.hybrid_command(name="bail")
    @require_joined_player()
    async def bail(self, ctx: commands.Context, amount: int) -> None:
        """Pay Racks to exit jail early. Minimum bail: 500 Racks."""
        if ctx.interaction is not None:
            await ctx.defer()
        embed = await self.bot.city_service.bail_player(ctx.guild.id, ctx.author.id, amount)  # type: ignore[union-attr]
        if gifs.BAIL_OUT:
            embed.set_image(url=gifs.BAIL_OUT)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="tension")
    @require_joined_player()
    async def tension(self, ctx: commands.Context) -> None:
        """Check the city-wide violence level. High tension triggers a Police Sweep."""
        if ctx.interaction is not None:
            await ctx.defer()
        level = await self.bot.city_service.get_violence_level(ctx.guild.id)  # type: ignore[union-attr]
        from sinbot.constants import VIOLENCE_SWEEP_THRESHOLD
        bar_filled = min(10, int(10 * level / VIOLENCE_SWEEP_THRESHOLD))
        bar_empty = 10 - bar_filled
        if level >= VIOLENCE_SWEEP_THRESHOLD * 0.8:
            color_emoji = "🔴"
        elif level >= VIOLENCE_SWEEP_THRESHOLD * 0.5:
            color_emoji = "🟡"
        else:
            color_emoji = "🟢"
        bar = f"{color_emoji} {'█' * bar_filled}{'░' * bar_empty} {level}/{VIOLENCE_SWEEP_THRESHOLD}"
        embed = self.bot.embed_factory.standard(
            "🌡️ City Tension",
            f"**Violence Level:** {bar}\n\n"
            f"When violence hits **{VIOLENCE_SWEEP_THRESHOLD}**, a city-wide **Police Sweep** is auto-triggered.\n"
            f"Violence increases from: drug ops, arms deals, turf wars, heists, and rat reports.\n"
            f"It decays naturally every hour.",
        )
        if gifs.TENSION_METER:
            embed.set_image(url=gifs.TENSION_METER)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))
