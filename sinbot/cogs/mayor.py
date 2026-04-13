from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from sinbot.utils import autocomplete
from sinbot.utils.checks import require_city_admin, require_mayor, require_joined_player
from sinbot.utils.time import isoformat, utcnow
from sinbot.views.action_hub import QuickActionsView
from sinbot import gifs

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class MayorCog(commands.Cog):
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot

    @classmethod
    async def create(cls, bot: "SinBot") -> "MayorCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        if ctx.guild:
            await self.bot.city_service.update_boss_activity(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]

    def _get_mayor(self, guild: discord.Guild) -> discord.Member:
        """Return the guild owner (mayor). Raises if unavailable."""
        mayor = guild.owner
        if mayor is None:
            raise commands.CheckFailure("The Mayor could not be found.")
        return mayor

    @commands.hybrid_group(name="mayor", invoke_without_command=True)
    @require_mayor()
    async def mayor(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard(
                "Mayor Commands",
                "Use tax, crackdown, pardon, and reward to control city pressure and treasury flow.",
            ),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @mayor.command(name="tax")
    @require_mayor()
    async def mayor_tax(self, ctx: commands.Context, tax_rate: int) -> None:
        tax_rate = max(0, min(20, tax_rate))
        await self.bot.repo.update_guild_settings(ctx.guild.id, tax_rate=tax_rate)  # type: ignore[union-attr]
        await self.bot.city_service.refresh_vault(ctx.guild.id)  # type: ignore[union-attr]
        embed = self.bot.embed_factory.standard("Tax Updated", f"City tax is now **{tax_rate}%**.")
        if gifs.MAYOR_TAX:
            embed.set_image(url=gifs.MAYOR_TAX)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @mayor.command(name="crackdown")
    @require_mayor()
    async def mayor_crackdown(self, ctx: commands.Context, hours: int) -> None:
        guild = ctx.guild
        if guild is None:
            raise commands.CheckFailure("This command can only be used in a server.")
        crackdown_until = utcnow() + timedelta(hours=max(0, hours))
        await self.bot.repo.update_guild_settings(guild.id, crackdown_until=isoformat(crackdown_until))  # type: ignore[union-attr]
        await self.bot.city_service.refresh_vault(guild.id)  # type: ignore[union-attr]
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            guild.id,
            "Police Crackdown",
            f"The Mayor deployed a crackdown for **{hours}** hour(s).",
            "danger",
        )
        embed = self.bot.embed_factory.danger("Crackdown Deployed", f"Operations now gain extra Heat for **{hours}** hour(s).")
        if gifs.CRACKDOWN:
            embed.set_image(url=gifs.CRACKDOWN)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @mayor.command(name="pardon")
    @require_joined_player()
    async def mayor_pardon(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        """Request a mayoral pardon for a jailed member. The Mayor must accept or decline."""
        guild = ctx.guild
        if guild is None:
            raise commands.CheckFailure("This command can only be used in a server.")

        mayor = self._get_mayor(guild)

        # If the mayor is running this command, allow direct pardon (backward compat)
        if ctx.author.id == mayor.id:
            if member is None:
                raise commands.CheckFailure("Usage: `/mayor pardon @member` — specify who to pardon.")
            jail = await self.bot.repo.get_active_jail_for_user(guild.id, member.id)  # type: ignore[union-attr]
            if jail is None:
                raise commands.CheckFailure("That member is not currently jailed.")
            await self.bot.heat_service.release_jail(jail["id"], guild.id, member.id, announce=False)  # type: ignore[union-attr]
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                guild.id,
                "Mayoral Pardon",
                f"{member.mention} was pardoned by the Mayor.",
                "reward",
            )
            embed = self.bot.embed_factory.reward("Pardon Granted", f"{member.mention} is free to walk again.")
            if gifs.MAYOR_PARDON:
                embed.set_image(url=gifs.MAYOR_PARDON)
            elif gifs.BAIL_OUT:
                embed.set_image(url=gifs.BAIL_OUT)
            await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))
            return

        # Non-mayor: request a pardon for themselves or a specified member
        target = member or ctx.author
        if not isinstance(target, discord.Member):
            raise commands.CheckFailure("Could not resolve the target member.")

        jail = await self.bot.repo.get_active_jail_for_user(guild.id, target.id)  # type: ignore[union-attr]
        if jail is None:
            raise commands.CheckFailure(f"{target.mention} is not currently jailed.")

        # Send a DM to the mayor with accept/decline buttons
        from sinbot.views.pardon import PardonDecisionView
        view = PardonDecisionView(timeout=300)
        dm_embed = self.bot.embed_factory.standard(
            "🏛️ Pardon Request",
            f"{ctx.author.mention} is requesting a **Mayoral Pardon** for {target.mention}.\n\n"
            f"Use the buttons below to **accept** or **decline** this request.",
        )
        try:
            dm = await mayor.create_dm()
            message = await dm.send(embed=dm_embed, view=view)
            view.message = message
        except discord.HTTPException:
            raise commands.CheckFailure("The Mayor could not be reached by DM. Their DMs may be closed.")

        # Notify the requester that the request was sent
        pending_embed = self.bot.embed_factory.standard(
            "Pardon Request Sent",
            f"Your pardon request for {target.mention} has been sent to the Mayor.\n"
            f"Waiting for the Mayor to **accept** or **decline**...",
        )
        await ctx.send(embed=pending_embed, view=QuickActionsView(self.bot, ctx.author.id))

        # Wait for the mayor's decision
        await view.wait()

        if view.choice == "accepted":
            # Re-check jail status (may have expired while waiting)
            jail = await self.bot.repo.get_active_jail_for_user(guild.id, target.id)
            if jail is None:
                try:
                    await ctx.author.send(
                        embed=self.bot.embed_factory.standard(
                            "Pardon Moot",
                            f"{target.mention} is no longer in jail — the pardon is moot.",
                        )
                    )
                except discord.HTTPException:
                    pass
                return

            await self.bot.heat_service.release_jail(jail["id"], guild.id, target.id, announce=False)  # type: ignore[union-attr]
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                guild.id,
                "Mayoral Pardon",
                f"{target.mention} was pardoned by the Mayor (requested by {ctx.author.mention}).",
                "reward",
            )
            result_embed = self.bot.embed_factory.reward(
                "Pardon Granted",
                f"The Mayor accepted the pardon. {target.mention} is free to walk again.",
            )
            if gifs.MAYOR_PARDON:
                result_embed.set_image(url=gifs.MAYOR_PARDON)
            elif gifs.BAIL_OUT:
                result_embed.set_image(url=gifs.BAIL_OUT)
            # Notify requester
            try:
                await ctx.author.send(embed=result_embed)
            except discord.HTTPException:
                pass
            # Notify the pardoned person if different from requester
            if target.id != ctx.author.id:
                try:
                    await target.send(embed=result_embed)
                except discord.HTTPException:
                    pass
        else:
            status = "declined" if view.choice == "declined" else "expired (no response)"
            declined_embed = self.bot.embed_factory.danger(
                "Pardon Denied",
                f"The Mayor **{status}** the pardon request for {target.mention}.",
            )
            try:
                await ctx.author.send(embed=declined_embed)
            except discord.HTTPException:
                pass

    @mayor.command(name="reward")
    @app_commands.autocomplete(gang_name=autocomplete.gang_names)
    @require_mayor()
    async def mayor_reward(self, ctx: commands.Context, gang_name: str, amount: int) -> None:
        if amount <= 0:
            raise commands.CheckFailure("Reward amount must be greater than zero.")
        gang = await self.bot.repo.get_gang_by_name(ctx.guild.id, gang_name)  # type: ignore[union-attr]
        if gang is None:
            raise commands.CheckFailure("That gang does not exist.")
        await self.bot.repo.debit_treasury(ctx.guild.id, amount, allow_partial=False)  # type: ignore[union-attr]
        new_balance = await self.bot.repo.credit_gang_bank(gang["id"], amount)
        await self.bot.city_service.refresh_vault(ctx.guild.id)  # type: ignore[union-attr]
        embed = self.bot.embed_factory.reward(
            "Treasury Reward Sent",
            f"**{gang['name']}** received **{amount}**. New gang bank: **{new_balance}**.",
        )
        if gifs.TREASURY_REWARD:
            embed.set_image(url=gifs.TREASURY_REWARD)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_group(name="bribe", invoke_without_command=True)
    async def bribe(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard("Bribes", "Use `/bribe mayor <amount>` to make an offer."),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @bribe.command(name="mayor")
    async def bribe_mayor(self, ctx: commands.Context, amount: int) -> None:
        if ctx.interaction is not None:
            await ctx.defer(ephemeral=True)
        await self.bot.social_service.submit_bribe(ctx.author, amount)  # type: ignore[arg-type, union-attr]
        if ctx.interaction is not None:
            await ctx.send("done", ephemeral=True)
            return
        await ctx.send("done")

    @commands.hybrid_group(name="city", invoke_without_command=True)
    async def city(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=self.bot.embed_factory.standard(
                "City Commands",
                "Use `/city event` to check the live city event.",
            ),
            view=QuickActionsView(self.bot, ctx.author.id),
        )

    @city.group(name="event", invoke_without_command=True)
    async def city_event(self, ctx: commands.Context) -> None:
        """Show the active city-wide event, its gameplay modifier, and remaining duration."""
        if ctx.interaction is not None:
            await ctx.defer()
        embed, file = await self.bot.event_service.build_city_event_embed(ctx.guild.id)  # type: ignore[union-attr]
        if gifs.CITY_EVENT and not file:
            embed.set_image(url=gifs.CITY_EVENT)
        kwargs: dict = {"embed": embed, "view": QuickActionsView(self.bot, ctx.author.id)}
        if file is not None:
            kwargs["file"] = file
        await ctx.send(**kwargs)

    @city_event.command(name="trigger")
    @app_commands.autocomplete(event_key=autocomplete.city_event_keys)
    @require_city_admin()
    async def city_event_trigger(self, ctx: commands.Context, event_key: str) -> None:
        """Force a specific city event during a live demo (admin only)."""
        if ctx.interaction is not None:
            await ctx.defer()
        event = await self.bot.event_service.trigger_event(ctx.guild.id, event_key, announce=True)  # type: ignore[union-attr]
        definition = self.bot.event_service.event_definition(event_key)  # type: ignore[union-attr]
        embed = self.bot.embed_factory.success(
            "Event Triggered",
            f"**{definition.name}** is now live in the city until {discord.utils.format_dt(event.ends_at, style='R')}.",
        )
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))
