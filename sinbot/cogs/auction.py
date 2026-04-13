from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from sinbot.utils.checks import require_mayor
from sinbot.utils.time import utcnow
from sinbot.views.action_hub import QuickActionsView
from sinbot import gifs

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class AuctionView(discord.ui.View):
    """Interactive view for bidding in the Harbour Auction."""

    def __init__(self, bot: "SinBot", guild_id: int, auction_id: str, timeout: float = 180.0) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id
        self.auction_id = auction_id
        self.top_bidder_id: int | None = None
        self.current_bid: int = 100
        self.event = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        player = await self.bot.repo.get_player(interaction.guild_id or self.guild_id, interaction.user.id)
        if player is None or not player["is_joined"]:
            await interaction.response.send_message("Only joined players can bid.", ephemeral=True)
            return False
        return True

    async def handle_bid(self, interaction: discord.Interaction, amount: int) -> None:
        if interaction.is_expired():
            return
        if self.top_bidder_id == interaction.user.id:
            await interaction.response.send_message("You already hold the top bid!", ephemeral=True)
            return
        player = await self.bot.repo.get_player(self.guild_id, interaction.user.id)
        if player is None or int(player["wallet"]) < amount:
            await interaction.response.send_message("You don't have enough Racks for that bid.", ephemeral=True)
            return
        if amount <= self.current_bid:
            await interaction.response.send_message(f"You must bid more than **{self.current_bid}**.", ephemeral=True)
            return
        self.top_bidder_id = interaction.user.id
        self.current_bid = amount
        await interaction.response.send_message(f"You bid **{amount}** Racks!", ephemeral=True)

    @discord.ui.button(label="+50 Racks", emoji="💰", style=discord.ButtonStyle.primary)
    async def bid_50(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.handle_bid(interaction, self.current_bid + 50)

    @discord.ui.button(label="+100 Racks", emoji="💸", style=discord.ButtonStyle.success)
    async def bid_100(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.handle_bid(interaction, self.current_bid + 100)

    @discord.ui.button(label="+500 Racks", emoji="🛑", style=discord.ButtonStyle.danger)
    async def bid_500(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.handle_bid(interaction, self.current_bid + 500)


class AuctionCog(commands.Cog):
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot
        self.active_auctions: set[int] = set()

    @classmethod
    async def create(cls, bot: "SinBot") -> "AuctionCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    @commands.hybrid_command(name="auction")
    @require_mayor()
    async def auction(self, ctx: commands.Context) -> None:
        """(Mayor Only) Trigger a black market weapons auction."""
        if ctx.interaction is not None:
            await ctx.defer()
        if ctx.guild.id in self.active_auctions:
            raise commands.CheckFailure("An auction is already active in this city.")

        self.active_auctions.add(ctx.guild.id)
        try:
            embed = self.bot.embed_factory.reward(
                "Harbour Auction Live",
                "A crate of **5 Weapons** was seized at the docks. The Mayor has opened an auction!\n\n"
                "**Starting Bid:** 200 Racks\n"
                "**Time limit:** 2 minutes. Highest bidder takes it all."
            )
            if gifs.AUCTION_START:
                embed.set_image(url=gifs.AUCTION_START)
            view = AuctionView(self.bot, ctx.guild.id, "harbour", timeout=120.0)
            msg = await ctx.send(embed=embed, view=view)

            # Wait for timeout (2 minutes)
            await asyncio.sleep(120.0)
            view.stop()

            # Resolve
            if view.top_bidder_id is None:
                await msg.reply(embed=self.bot.embed_factory.standard("Auction Closed", "Nobody bid. The crate goes into evidence."))
            else:
                winner = ctx.guild.get_member(view.top_bidder_id)
                w_name = winner.mention if winner else f"<@{view.top_bidder_id}>"
                try:
                    await self.bot.repo.debit_wallet(ctx.guild.id, view.top_bidder_id, view.current_bid)
                    await self.bot.repo.adjust_inventory(ctx.guild.id, view.top_bidder_id, "weapon", 5)
                    embed = self.bot.embed_factory.success(
                        "Auction Sold!",
                        f"Sold to {w_name} for **{view.current_bid}** Racks! They received 5 weapons."
                    )
                    if gifs.AUCTION_SOLD:
                        embed.set_image(url=gifs.AUCTION_SOLD)
                    await msg.reply(embed=embed)
                    await self.bot.city_service.post_news(  # type: ignore[union-attr]
                        ctx.guild.id,
                        "Auction Winner",
                        f"{w_name} dominated the harbour auction, taking home 5 weapons.",
                        "success",
                        image_url=gifs.AUCTION_SOLD
                    )
                except Exception:
                    await msg.reply("The transaction failed. The winner must have spent their Racks elsewhere.")
        finally:
            self.active_auctions.discard(ctx.guild.id)
