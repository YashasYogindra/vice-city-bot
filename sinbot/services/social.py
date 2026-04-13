from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from sinbot.constants import BOSS_CHALLENGE_XP, RAT_PAYOUT_MAX
from sinbot.exceptions import InvalidStateError
from sinbot.utils.time import isoformat, parse_datetime, utcnow
from sinbot.views.bribe import BribeDecisionView
from sinbot import gifs

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class SocialService:
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot

    async def rat_out(self, reporter: discord.Member, target: discord.Member, reason: str) -> discord.Embed:
        reporter_player = await self.bot.repo.get_player(reporter.guild.id, reporter.id)
        target_player = await self.bot.repo.get_player(target.guild.id, target.id)
        if reporter_player is None or target_player is None or not reporter_player["is_joined"] or not target_player["is_joined"]:
            raise InvalidStateError("Both members need city profiles for a rat report.")

        # AI Verification via Logs
        recent_news = await self.bot.repo.list_news_events(reporter.guild.id, limit=10)
        logs_text = "\n".join([f"- {event['title']}: {event['description']}" for event in recent_news])
        is_true = True
        if self.bot.groq_service is not None and logs_text:
            try:
                is_true = await self.bot.groq_service.verify_rat_report(
                    target_name=target.display_name,
                    accusation=reason,
                    logs=logs_text,
                )
            except Exception:
                self.bot.logger.debug("Groq rat verification failed, defaulting to true", exc_info=True)

        if not is_true:
            # False rat — punish the reporter
            await self.bot.heat_service.apply_heat(reporter.guild.id, reporter.id, 2, reason="False rat report")  # type: ignore[union-attr]
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                reporter.guild.id,
                "False Informant",
                f"{reporter.mention} filed a bogus rat report against {target.mention} and got hit with +2 Heat.",
                "danger",
                image_url=gifs.RAT_FALSE_TIP
            )
            embed = self.bot.embed_factory.danger(
                "Bogus Intel",
                "The cops checked the logs. Your story didn't match the street chatter.\n"
                "**+2 Heat** applied to you for wasting their time."
            )
            if gifs.RAT_FALSE_TIP:
                embed.set_image(url=gifs.RAT_FALSE_TIP)
            return embed

        # True rat — standard flow
        await self.bot.heat_service.apply_heat(reporter.guild.id, target.id, 2, reason="Rat report")  # type: ignore[union-attr]
        await self.bot.city_service.adjust_violence(reporter.guild.id, 1)  # type: ignore[union-attr]
        payout, treasury_balance = await self.bot.repo.debit_treasury(reporter.guild.id, RAT_PAYOUT_MAX, allow_partial=True)
        if payout:
            await self.bot.repo.credit_wallet(reporter.guild.id, reporter.id, payout)
        if reporter_player["gang_id"] == target_player["gang_id"]:
            await self.bot.repo.update_player(
                reporter.guild.id,
                reporter.id,
                trust_score=int(reporter_player["trust_score"]) - 1,
            )
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            reporter.guild.id,
            "Rat Report Filed",
            f"{reporter.mention} ratted on {target.mention}: *{reason}*.\nTreasury payout: **{payout}** | Treasury left: **{treasury_balance}**",
            "danger",
            image_url=gifs.RAT_SUCCESS
        )
        embed = self.bot.embed_factory.reward(
            "Rat Report Submitted",
            f"{target.mention} gained +2 Heat. You collected **{payout}** from the city treasury.",
        )
        if gifs.RAT_SUCCESS:
            embed.set_image(url=gifs.RAT_SUCCESS)
        return embed

    async def vote_exile(self, voter: discord.Member, target: discord.Member) -> discord.Embed:
        voter_player = await self.bot.repo.get_player(voter.guild.id, voter.id)
        target_player = await self.bot.repo.get_player(target.guild.id, target.id)
        if voter_player is None or target_player is None:
            raise InvalidStateError("Both players must exist in the city.")
        if voter_player["gang_id"] != target_player["gang_id"]:
            raise InvalidStateError("You can only vote to exile someone from your own gang.")
        if voter_player["gang_id"] is None:
            raise InvalidStateError("That member is not in a gang.")

        vote = await self.bot.repo.get_active_vote(voter.guild.id, "exile", voter_player["gang_id"], target.id)
        if vote is None:
            vote_id = await self.bot.repo.create_vote(voter.guild.id, "exile", target.id, voter_player["gang_id"], voter.id)
            vote = await self.bot.repo.get_vote(vote_id)
        existing_votes = await self.bot.repo.list_vote_entries(vote["id"])
        if any(entry["voter_user_id"] == voter.id for entry in existing_votes):
            raise InvalidStateError("You already voted on this exile.")
        await self.bot.repo.cast_vote(vote["id"], voter.id, "yes")
        existing_votes = await self.bot.repo.list_vote_entries(vote["id"])
        gang_members = await self.bot.repo.list_joined_players(voter.guild.id, voter_player["gang_id"])
        threshold = max(1, len(gang_members) // 2 + 1)
        votes_for = len([entry for entry in existing_votes if entry["vote"] == "yes"])
        if votes_for >= threshold:
            await self._exile_member(voter.guild, target_player, target)
            await self.bot.repo.update_vote(vote["id"], status="resolved")
            return self.bot.embed_factory.danger("Exile Passed", f"{target.mention} has been thrown out of the gang.")
        return self.bot.embed_factory.standard(
            "Exile Vote Recorded",
            f"Vote count: **{votes_for}/{threshold}** to exile {target.mention}.",
        )

    async def _exile_member(self, guild: discord.Guild, player: dict, member: discord.Member | None = None) -> None:
        gangs = await self.bot.repo.list_gangs(guild.id)
        counts = await self.bot.repo.count_joined_players_by_gang(guild.id)
        eligible_gangs = [gang for gang in gangs if gang["id"] != player["gang_id"]]
        destination = min(eligible_gangs, key=lambda gang: counts.get(gang["id"], 0))
        old_gang = await self.bot.repo.get_gang(player["gang_id"])
        if old_gang and old_gang.get("boss_user_id") == player["user_id"]:
            await self.bot.repo.upsert_gang(guild.id, old_gang["name"], boss_user_id=None)
        await self.bot.repo.update_player(
            guild.id,
            player["user_id"],
            gang_id=destination["id"],
            rank="Street Rat",
            xp=0,
            trust_score=0,
        )
        member = member or guild.get_member(player["user_id"])
        if member:
            if old_gang and old_gang.get("role_id"):
                old_role = guild.get_role(old_gang["role_id"])
                if old_role and old_role in member.roles:
                    await member.remove_roles(old_role, reason="SinBot exile")
            new_role = guild.get_role(destination["role_id"]) if destination.get("role_id") else None
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role, reason="SinBot exile reassignment")
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            guild.id,
            "Gang Exile",
            f"<@{player['user_id']}> was exiled from **{old_gang['name'] if old_gang else 'their gang'}** and dumped into **{destination['name']}**.",
            "danger",
        )

    async def challenge_boss(self, challenger: discord.Member) -> discord.Embed:
        player = await self.bot.repo.get_player(challenger.guild.id, challenger.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need a city profile to vote on leadership.")
        gang = await self.bot.repo.get_gang(player["gang_id"])
        if gang is None:
            raise InvalidStateError("You need to be in a gang to challenge the boss.")
        boss_user_id = gang.get("boss_user_id")
        last_active = parse_datetime(gang["last_boss_active_at"]) if gang.get("last_boss_active_at") else None
        vote = await self.bot.repo.get_active_vote(challenger.guild.id, "boss_challenge", gang["id"], boss_user_id or 0)

        if boss_user_id is None and int(player["xp"]) >= BOSS_CHALLENGE_XP:
            await self.bot.repo.update_player(challenger.guild.id, challenger.id, rank="Boss")
            await self.bot.repo.upsert_gang(
                challenger.guild.id,
                gang["name"],
                boss_user_id=challenger.id,
                last_boss_active_at=isoformat(utcnow()),
            )
            return self.bot.embed_factory.success("Boss Crowned", f"{challenger.mention} now runs **{gang['name']}**.")

        if boss_user_id is None:
            raise InvalidStateError("There is no boss to challenge yet.")
        if last_active and (utcnow() - last_active).total_seconds() < 12 * 60 * 60:
            raise InvalidStateError("The current Boss is still active. No leadership challenge yet.")
        if vote is None and player["rank"] not in ("Soldier", "Boss"):
            raise commands.MissingPermissions(["rank:Soldier"])
        if vote is None:
            vote_id = await self.bot.repo.create_vote(
                challenger.guild.id,
                "boss_challenge",
                boss_user_id,
                gang["id"],
                challenger.id,
                metadata={"challenger_user_id": challenger.id},
            )
            vote = await self.bot.repo.get_vote(vote_id)
        entries = await self.bot.repo.list_vote_entries(vote["id"])
        if any(entry["voter_user_id"] == challenger.id for entry in entries):
            raise InvalidStateError("You already voted in this leadership challenge.")
        await self.bot.repo.cast_vote(vote["id"], challenger.id, "yes")
        entries = await self.bot.repo.list_vote_entries(vote["id"])
        gang_members = await self.bot.repo.list_joined_players(challenger.guild.id, gang["id"])
        threshold = max(1, len(gang_members) // 2 + 1)
        votes_for = len([entry for entry in entries if entry["vote"] == "yes"])
        if votes_for >= threshold:
            old_boss = await self.bot.repo.get_player(challenger.guild.id, boss_user_id)
            if old_boss:
                await self.bot.repo.update_player(challenger.guild.id, boss_user_id, rank="Soldier")
            await self.bot.repo.update_player(challenger.guild.id, challenger.id, rank="Boss")
            await self.bot.repo.upsert_gang(
                challenger.guild.id,
                gang["name"],
                boss_user_id=challenger.id,
                last_boss_active_at=isoformat(utcnow()),
            )
            await self.bot.repo.update_vote(vote["id"], status="resolved")
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                challenger.guild.id,
                "Leadership Coup",
                f"{challenger.mention} took control of **{gang['name']}** after a successful gang vote.",
                "reward",
            )
            return self.bot.embed_factory.success("Leadership Changed", f"{challenger.mention} is the new Boss.")
        return self.bot.embed_factory.standard(
            "Challenge Vote Logged",
            f"Leadership votes: **{votes_for}/{threshold}** in favor of {challenger.mention}.",
        )

    async def submit_bribe(self, member: discord.Member, amount: int) -> discord.Embed:
        if amount <= 0:
            raise InvalidStateError("Bribe amount must be greater than zero.")
        player = await self.bot.repo.get_player(member.guild.id, member.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need a city wallet before you can bribe the Mayor.")
        mayor = member.guild.owner
        if mayor is None:
            raise InvalidStateError("The Mayor could not be found.")
        bribe_id = await self.bot.repo.create_bribe(member.guild.id, member.id, mayor.id, amount)
        view = BribeDecisionView(timeout=300)
        embed = self.bot.embed_factory.standard(
            "Mayor Bribe",
            f"{member.mention} is offering **{amount}** for your attention.\nUse the buttons below to accept or ignore it.",
        )
        try:
            dm = await mayor.create_dm()
            message = await dm.send(embed=embed, view=view)
            view.message = message
        except discord.HTTPException:
            await self.bot.repo.update_bribe(bribe_id, status="undeliverable")
            raise InvalidStateError("The Mayor could not be reached by DM.")

        # Process the mayor decision without blocking the command response.
        asyncio.create_task(self._finalize_bribe(member, mayor, amount, bribe_id, view))
        return self.bot.embed_factory.standard("Bribe Sent", "The Mayor has been notified. What happens next is up to them.")

    async def _finalize_bribe(
        self,
        member: discord.Member,
        mayor: discord.Member,
        amount: int,
        bribe_id: int,
        view: BribeDecisionView,
    ) -> None:
        try:
            await view.wait()
            if view.choice == "accepted":
                mayor_profile = await self.bot.repo.ensure_player(member.guild.id, mayor.id, rank="Mayor", is_joined=0, wallet=0)
                try:
                    await self.bot.repo.debit_wallet(member.guild.id, member.id, amount)
                except Exception:
                    await self.bot.repo.update_bribe(bribe_id, status="failed")
                    try:
                        await member.send(
                            embed=self.bot.embed_factory.danger(
                                "Bribe Failed",
                                "The Mayor accepted, but you no longer had enough cash to pay the bribe.",
                            )
                        )
                    except discord.HTTPException:
                        pass
                    return
                await self.bot.repo.credit_wallet(member.guild.id, mayor_profile["user_id"], amount)
                await self.bot.repo.update_bribe(bribe_id, status="accepted")
                try:
                    await member.send(
                        embed=self.bot.embed_factory.reward(
                            "Bribe Accepted",
                            f"The Mayor accepted your **{amount}** Racks bribe.",
                        )
                    )
                except discord.HTTPException:
                    pass
                return

            status = "ignored" if view.choice == "ignored" else "expired"
            await self.bot.repo.update_bribe(bribe_id, status=status)
        except Exception:
            self.bot.logger.exception("Failed to finalize bribe request", exc_info=True)
