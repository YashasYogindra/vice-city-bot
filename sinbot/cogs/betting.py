from __future__ import annotations

import asyncio
import os
import random
from typing import Literal
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from sinbot.utils.checks import require_joined_player
from sinbot.views.action_hub import QuickActionsView
from sinbot import gifs

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class BettingCog(commands.Cog):
    """IPL match fetcher and team betting commands."""

    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot
        # In a real app we'd fetch these from an API, e.g., cricapi.com
        self.upcoming_matches = [
            {"id": "match_1", "team1": "CSK", "team2": "MI", "status": "upcoming"},
            {"id": "match_2", "team1": "RCB", "team2": "KKR", "status": "upcoming"},
        ]
        # Active bets: {user_id: {"team": "CSK", "amount": 100}}
        self.active_bets: dict[int, dict[str, str | int]] = {}
        self.cricket_data_source = "mock"
        self.cricket_data_note = "No live API call yet."

    @classmethod
    async def create(cls, bot: "SinBot") -> "BettingCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    @commands.hybrid_group(name="bet", invoke_without_command=True)
    async def bet(self, ctx: commands.Context) -> None:
        """IPL Betting Command Group."""
        await ctx.send("Use `/bet ipl` to fetch the current IPL match, then `/bet place team1 <amount>` or `/bet place team2 <amount>`.")

    async def _fetch_ipl_matches(self) -> list[dict[str, str]]:
        api_key = (os.getenv("CRICKET_API_KEY") or "").strip()
        if not api_key:
            self.cricket_data_source = "mock"
            self.cricket_data_note = "CRICKET_API_KEY is not set; showing fallback fixtures."
            return self.upcoming_matches  # fallback to mock

        import aiohttp
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.cricapi.com/v1/currentMatches",
                    params={"apikey": api_key, "offset": 0},
                ) as resp:
                    if resp.status != 200:
                        self.cricket_data_source = "mock"
                        self.cricket_data_note = f"Live API returned HTTP {resp.status}; showing fallback fixtures."
                        return self.upcoming_matches

                    data = await resp.json(content_type=None)
                    if str(data.get("status", "")).lower() != "success":
                        reason = data.get("reason") or "Unknown API error"
                        self.cricket_data_source = "mock"
                        self.cricket_data_note = f"Live API error: {reason}. Showing fallback fixtures."
                        return self.upcoming_matches

                    matches: list[dict[str, str]] = []
                    for row in data.get("data", []) or []:
                        if row.get("matchEnded") is True:
                            continue

                        teams = row.get("teams") if isinstance(row.get("teams"), list) else None
                        if teams and len(teams) >= 2:
                            team1 = str(teams[0]).strip()
                            team2 = str(teams[1]).strip()
                        else:
                            name = str(row.get("name") or "")
                            if " vs " in name:
                                left, right = name.split(" vs ", 1)
                                team1 = left.strip()
                                team2 = right.split(",", 1)[0].strip()
                            else:
                                continue

                        status = "live" if row.get("matchStarted") else "upcoming"
                        matches.append(
                            {
                                "id": str(row.get("id") or f"{team1}_{team2}"),
                                "team1": team1,
                                "team2": team2,
                                "status": status,
                            }
                        )

                    if matches:
                        self.upcoming_matches = matches[:5]
                        live_count = len([m for m in self.upcoming_matches if m["status"] == "live"])
                        self.cricket_data_source = "live"
                        self.cricket_data_note = (
                            f"Loaded {len(self.upcoming_matches)} live fixtures from CricAPI"
                            + (f" ({live_count} currently in progress)." if live_count else ".")
                        )
                    else:
                        self.cricket_data_source = "mock"
                        self.cricket_data_note = "Live API returned no active fixtures; showing fallback fixtures."
        except Exception:
            self.bot.logger.exception("Failed to fetch live cricket data")
            self.cricket_data_source = "mock"
            self.cricket_data_note = "Live API request failed; showing fallback fixtures."

        return self.upcoming_matches

    @bet.command(name="ipl")
    @require_joined_player()
    async def bet_ipl(self, ctx: commands.Context) -> None:
        """Fetch one IPL match and show team options for betting."""
        matches = await self._fetch_ipl_matches()
        if not matches:
            await ctx.send(embed=self.bot.embed_factory.standard("IPL Match Fetcher", "No upcoming matches right now."))
            return

        match = matches[0]
        badge = "🔴 LIVE" if match.get("status") == "live" else "🟢 UPCOMING"
        embed = self.bot.embed_factory.standard(
            "IPL Match Fetcher",
            (
                f"🏏 **{match['team1']}** vs **{match['team2']}** ({badge})\n\n"
                "Bet syntax:\n"
                "`/bet place team1 <amount>`\n"
                "`/bet place team2 <amount>`\n\n"
                "Payout is 2x on win."
            ),
        )
        source_label = "Live API" if self.cricket_data_source == "live" else "Fallback"
        embed.add_field(name="Data Source", value=f"{source_label}: {self.cricket_data_note}", inline=False)
        if gifs.BET_IPL:
            embed.set_image(url=gifs.BET_IPL)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @bet.command(name="place")
    @app_commands.choices(
        team_pick=[
            app_commands.Choice(name="Team 1", value="team1"),
            app_commands.Choice(name="Team 2", value="team2"),
        ]
    )
    @require_joined_player()
    async def bet_place(self, ctx: commands.Context, team_pick: str, amount: int) -> None:
        """Place a bet on Team 1 or Team 2 from the fetched match."""
        if ctx.interaction is not None:
            await ctx.defer()
        if amount < 100:
            raise commands.CheckFailure("Minimum bet is 100 Racks.")

        matches = await self._fetch_ipl_matches()
        if not matches:
            raise commands.CheckFailure("No IPL match is available to bet on right now.")

        match = matches[0]
        pick = team_pick.strip().lower()
        if pick in {"1", "team 1"}:
            pick = "team1"
        elif pick in {"2", "team 2"}:
            pick = "team2"
        if pick not in {"team1", "team2"}:
            raise commands.CheckFailure("Pick `team1` or `team2`.")
        selected_team = match["team1"] if pick == "team1" else match["team2"]

        if ctx.author.id in self.active_bets:
            raise commands.CheckFailure("You already have an active bet.")

        # Charge the user
        await self.bot.repo.debit_wallet(ctx.guild.id, ctx.author.id, amount)  # type: ignore[union-attr]
        self.active_bets[ctx.author.id] = {
            "team": selected_team,
            "amount": amount,
            "match_id": match.get("id", "unknown"),
        }
        
        embed = self.bot.embed_factory.success(
            "Bet Placed",
            (
                f"You placed a **{amount}** Rack bet on **{selected_team}**.\n"
                f"Fixture: **{match['team1']}** vs **{match['team2']}**"
            ),
        )
        if gifs.BET_PLACE:
            embed.set_image(url=gifs.BET_PLACE)
        await ctx.send(
            embed=embed,
            view=QuickActionsView(self.bot, ctx.author.id)
        )

    @commands.hybrid_command(name="bets")
    @require_joined_player()
    async def bets(self, ctx: commands.Context) -> None:
        """View your active bet."""
        if ctx.author.id not in self.active_bets:
            await ctx.send(embed=self.bot.embed_factory.standard("Active Bets", "You have no active bets."))
            return
        bet = self.active_bets[ctx.author.id]
        embed = self.bot.embed_factory.standard(
            "Your Active Bet",
            f"You bet **{bet['amount']}** Racks on **{bet['team']}**.\n\n"
            "*Matches resolve periodically in the background.*"
        )
        if gifs.BET_VIEW:
            embed.set_image(url=gifs.BET_VIEW)
        await ctx.send(embed=embed, view=QuickActionsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="resolvebets")
    @commands.has_permissions(administrator=True)
    async def resolvebets(self, ctx: commands.Context, winner: str) -> None:
        """(Admin) Resolve all active bets for a given winning team."""
        if ctx.interaction is not None:
            await ctx.defer()
        winner = winner.upper()
        count = 0
        total_payout = 0
        to_remove = []
        
        for user_id, bet in self.active_bets.items():
            if bet["team"] == winner:
                amount = int(bet["amount"])
                payout = amount * 2
                try:
                    await self.bot.repo.credit_wallet(ctx.guild.id, user_id, payout)  # type: ignore[union-attr]
                    count += 1
                    total_payout += payout
                    user = ctx.guild.get_member(user_id)
                    try:
                        if user:
                            await user.send(f"🏏 **IPL Result:** {winner} WON! Your bet hit and you won **{payout}** Racks!")
                    except Exception:
                        pass
                except Exception:
                    pass
            to_remove.append(user_id)
        
        for uid in to_remove:
            self.active_bets.pop(uid, None)
            
        embed = self.bot.embed_factory.reward(
            "Bets Resolved",
            f"Resolved bets for **{winner}**! Paid out **{total_payout}** Racks across {count} winners."
        )
        if gifs.BET_WIN:
            embed.set_image(url=gifs.BET_WIN)
        await ctx.send(embed=embed)
