from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from apscheduler.jobstores.base import JobLookupError

from sinbot.constants import WAR_DURATION_SECONDS, WAR_MOBILIZATION_COST, WAR_RANDOM_MAX, WAR_RANDOM_MIN
from sinbot.exceptions import InvalidStateError
from sinbot.utils.time import isoformat, parse_datetime, utcnow
from sinbot import gifs

if TYPE_CHECKING:
    import discord

    from sinbot.bot import SinBot


class WarService:
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot
        self.random = random.Random()

    async def rehydrate_active_wars(self, guild_id: int) -> None:
        for war in await self.bot.repo.list_active_wars(guild_id):
            resolve_at = parse_datetime(war["resolve_at"])
            if resolve_at is None:
                continue
            if resolve_at <= utcnow():
                await self.resolve_war(war["id"])
            else:
                self.bot.scheduler.add_job(
                    self.resolve_war,
                    "date",
                    run_date=resolve_at,
                    id=f"war:{war['id']}",
                    replace_existing=True,
                    kwargs={"war_id": war["id"]},
                )

    async def declare_war(self, actor: "discord.Member", turf_name: str) -> dict:
        player = await self.bot.repo.get_player(actor.guild.id, actor.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need to join the city first.")
        if not player.get("gang_id"):
            raise InvalidStateError("You need to join a gang before declaring turf wars.")
        if await self.bot.city_service.member_is_jailed(actor.guild.id, actor.id):  # type: ignore[union-attr]
            raise InvalidStateError("You cannot declare a war from jail.")
        gang = await self.bot.repo.get_gang(player["gang_id"])
        if gang is None:
            raise InvalidStateError("You are not assigned to a gang.")
        if await self.bot.repo.get_active_war_for_gang(actor.guild.id, gang["id"]):
            raise InvalidStateError("Your gang is already tied up in a turf war.")
        turf = await self.bot.repo.get_turf_by_name(actor.guild.id, turf_name)
        if turf is None:
            raise InvalidStateError("That turf does not exist.")
        if turf["owner_gang_id"] == gang["id"]:
            raise InvalidStateError("You already control that turf.")
        defender = await self.bot.repo.get_gang(turf["owner_gang_id"])
        if defender is None:
            raise InvalidStateError("That turf has no valid owner.")
        if await self.bot.repo.get_active_war_for_gang(actor.guild.id, defender["id"]):
            raise InvalidStateError("That gang is already fighting another turf war.")

        resolve_at = utcnow() + timedelta(seconds=WAR_DURATION_SECONDS)
        war_id = await self.bot.repo.create_war(actor.guild.id, gang["id"], defender["id"], turf["id"], isoformat(resolve_at))
        self.bot.scheduler.add_job(
            self.resolve_war,
            "date",
            run_date=resolve_at,
            id=f"war:{war_id}",
            replace_existing=True,
            kwargs={"war_id": war_id},
        )
        await self.bot.city_service.adjust_violence(actor.guild.id, 5)  # type: ignore[union-attr]
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            actor.guild.id,
            "Turf War Declared",
            f"**{gang['name']}** launched an attack on **{turf['name']}**, currently held by **{defender['name']}**.",
            "danger",
            image_url=gifs.WAR_DECLARE
        )
        zone = await self.bot.city_service.get_configured_channel(actor.guild.id, "turf_war_channel_id")  # type: ignore[union-attr]
        if zone:
            await zone.send(
                embed=self.bot.embed_factory.standard(
                    "War Zone Active",
                    f"Attackers: **{gang['name']}**\nDefenders: **{defender['name']}**\nTurf: **{turf['name']}**\nResolve: {discord.utils.format_dt(resolve_at, style='R')}",
                )
            )
        return await self.bot.repo.get_war(war_id)  # type: ignore[return-value]

    async def commit(self, member: "discord.Member", mode: str) -> dict:
        player = await self.bot.repo.get_player(member.guild.id, member.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need to join the city first.")
        if not player.get("gang_id"):
            raise InvalidStateError("You need to join a gang before committing to turf wars.")
        if await self.bot.city_service.member_is_jailed(member.guild.id, member.id):  # type: ignore[union-attr]
            raise InvalidStateError("You cannot fight while jailed.")

        war = await self.bot.repo.get_active_war_for_gang(member.guild.id, player["gang_id"])
        if war is None:
            raise InvalidStateError("Your gang has no active turf war right now.")
        desired_side = "attacker" if mode == "assault" else "defender"
        if desired_side == "attacker" and war["attacker_gang_id"] != player["gang_id"]:
            raise InvalidStateError("Your gang is defending right now, not attacking.")
        if desired_side == "defender" and war["defender_gang_id"] != player["gang_id"]:
            raise InvalidStateError("Your gang is attacking right now, not defending.")
        existing = await self.bot.repo.get_war_participant(war["id"], member.id)
        if existing:
            raise InvalidStateError("You are already committed to this turf war.")

        await self.bot.repo.debit_gang_bank(player["gang_id"], WAR_MOBILIZATION_COST)
        weapons = await self.bot.repo.get_inventory_item(member.guild.id, member.id, "weapon")
        if weapons:
            await self.bot.repo.adjust_inventory(member.guild.id, member.id, "weapon", -weapons)
        base_power = 1.0
        total_power = base_power * (1 + (0.25 * weapons))
        participant_id = await self.bot.repo.add_war_participant(
            war["id"],
            member.id,
            player["gang_id"],
            desired_side,
            weapons,
            base_power,
            total_power,
        )
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            member.guild.id,
            "War Commitment",
            f"{member.mention} joined the {desired_side} line for Turf War #{war['id']}.",
            "standard",
            image_url=gifs.WAR_JOIN
        )
        return {"participant_id": participant_id, "war": war, "power": total_power, "weapons_used": weapons}

    async def resolve_war(self, war_id: int) -> None:
        try:
            self.bot.scheduler.remove_job(f"war:{war_id}")
        except JobLookupError:
            pass
        war = await self.bot.repo.get_war(war_id)
        if war is None or war["status"] != "active":
            return
        participants = await self.bot.repo.list_war_participants(war_id)
        attackers = [row for row in participants if row["side"] == "attacker"]
        defenders = [row for row in participants if row["side"] == "defender"]
        attack_power = sum(row["total_power"] for row in attackers) * self.random.uniform(WAR_RANDOM_MIN, WAR_RANDOM_MAX)
        defend_power = sum(row["total_power"] for row in defenders) * self.random.uniform(WAR_RANDOM_MIN, WAR_RANDOM_MAX)
        
        # Tie-breaker logic: if difference is < 15%
        max_power = max(attack_power, defend_power, 1)
        if abs(attack_power - defend_power) / max_power < 0.15:
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                war["guild_id"], "Turf War Tie-Breaker!", "The battle was too close. The leaders are stepping up for a 1v1 duel to settle it.", "danger",
                image_url=gifs.FIGHT_CHALLENGE
            )
            # Find Bosses
            a_boss_row = await self.bot.repo.db.execute_fetchone("SELECT user_id FROM players WHERE gang_id = ? AND rank = 'Boss' LIMIT 1", (war["attacker_gang_id"],))
            d_boss_row = await self.bot.repo.db.execute_fetchone("SELECT user_id FROM players WHERE gang_id = ? AND rank = 'Boss' LIMIT 1", (war["defender_gang_id"],))
            a_id = a_boss_row["user_id"] if a_boss_row else (attackers[0]["user_id"] if attackers else 0)
            d_id = d_boss_row["user_id"] if d_boss_row else (defenders[0]["user_id"] if defenders else 0)
            
            from sinbot.services.fighting import FightAction, FightEngine
            engine = FightEngine()
            state = engine.create_fight(a_id, d_id)
            actions = list(FightAction)
            while not state.is_over:
                engine.resolve_round(state, self.random.choice(actions), self.random.choice(actions))
            
            attacker_wins = state.winner_id == a_id
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                war["guild_id"], "Tie-Breaker Complete", f"The Boss duel is over. {'Attackers' if attacker_wins else 'Defenders'} clinched the victory in a bloody 1v1.", "reward",
                image_url=gifs.FIGHT_KNOCKOUT
            )
        else:
            attacker_wins = attack_power > defend_power
            
        winner_gang_id = war["attacker_gang_id"] if attacker_wins else war["defender_gang_id"]
        loser_side = defenders if attacker_wins else attackers

        if attacker_wins:
            await self.bot.repo.update_turf_owner(war["turf_id"], war["attacker_gang_id"])
        await self.bot.repo.update_war(war_id, status="resolved", winner_gang_id=winner_gang_id)
        turf = await self.bot.repo.get_turf(war["turf_id"])
        winning_gang = await self.bot.repo.get_gang(winner_gang_id)

        for winner in (attackers if attacker_wins else defenders):
            await self.bot.city_service.award_xp(war["guild_id"], winner["user_id"], 200)  # type: ignore[union-attr]
        for loser in loser_side:
            await self.bot.heat_service.jail_player(  # type: ignore[union-attr]
                war["guild_id"],
                loser["user_id"],
                "Lost a turf war",
                60 * 60,
                announce=False,
            )
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            war["guild_id"],
            "Turf War Resolved",
            f"**{winning_gang['name'] if winning_gang else 'Unknown'}** took the field at **{turf['name'] if turf else 'Unknown Turf'}**.",
            "reward" if attacker_wins else "danger",
            image_url=gifs.WAR_VICTORY
        )
