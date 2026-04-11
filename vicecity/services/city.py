from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from vicecity.constants import (
    DEFAULT_TAX_RATE,
    GANGS,
    HEAT_EMOJI,
    HEAT_STATUS,
    DAILY_STREAK_BASE_REWARD,
    DAILY_STREAK_BONUS_PER_DAY,
    DAILY_STREAK_REWARD_CAP_DAYS,
    LAWYER_COOLDOWN_SECONDS,
    RACKS_EMOJI,
    RANK_ORDER,
    RANK_THRESHOLDS,
    TURF_EMOJI,
    TURF_MEMBER_SPLIT_PERCENT,
    BLACK_MARKET_ITEMS,
)
from vicecity.exceptions import InvalidStateError
from vicecity.models.cinematic import GeminiInformantTipResult, InformantTipSeed
from vicecity.utils.time import isoformat, parse_datetime, utcnow

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class CityService:
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot

    def _daily_reward_amount(self, streak: int) -> int:
        capped_streak = max(1, min(streak, DAILY_STREAK_REWARD_CAP_DAYS))
        return DAILY_STREAK_BASE_REWARD + (capped_streak - 1) * DAILY_STREAK_BONUS_PER_DAY

    def _daily_claim_timezone(self) -> Any:
        scheduler = getattr(self.bot, "scheduler", None)
        return getattr(scheduler, "timezone", timezone.utc) or timezone.utc

    def get_daily_reward_status(self, player: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        current_time = now or utcnow()
        local_timezone = self._daily_claim_timezone()
        local_now = current_time.astimezone(local_timezone)
        stored_streak = max(0, int(player.get("daily_streak", 0)))
        last_claim = parse_datetime(player.get("last_daily_claim_at"))
        current_streak = 0
        claim_streak = 1
        can_claim = True
        next_claim_at: datetime | None = None
        missed_window = False

        if last_claim is not None:
            local_last_claim = last_claim.astimezone(local_timezone)
            day_gap = (local_now.date() - local_last_claim.date()).days
            if day_gap <= 0:
                can_claim = False
                current_streak = stored_streak
                claim_streak = max(1, stored_streak)
                next_claim_at = (local_now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                next_claim_at = next_claim_at.astimezone(timezone.utc)
            elif day_gap == 1:
                current_streak = stored_streak
                claim_streak = max(1, stored_streak + 1)
            else:
                missed_window = True

        reward_amount = self._daily_reward_amount(claim_streak)
        return {
            "can_claim": can_claim,
            "current_streak": current_streak,
            "claim_streak": claim_streak,
            "reward_amount": reward_amount,
            "next_claim_at": next_claim_at,
            "missed_window": missed_window,
        }

    def describe_daily_reward_status(self, player: dict[str, Any]) -> str:
        status = self.get_daily_reward_status(player)
        if status["can_claim"]:
            streak_text = f"{status['current_streak']}-day streak" if status["current_streak"] else "fresh streak"
            return f"Ready now for **{status['reward_amount']}** Racks ({streak_text})."
        next_claim_at = status["next_claim_at"]
        if next_claim_at is None:
            return "Claim status unavailable."
        return (
            f"Locked until {discord.utils.format_dt(next_claim_at, style='R')} "
            f"on a **{status['current_streak']}-day** streak."
        )

    async def get_guild(self, guild_id: int) -> discord.Guild:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise RuntimeError(f"Guild {guild_id} is not available.")
        return guild

    async def get_configured_channel(self, guild_id: int, setting_key: str) -> discord.TextChannel | None:
        guild = await self.get_guild(guild_id)
        settings = await self.bot.repo.get_guild_settings(guild_id)
        channel_id = settings.get(setting_key) if settings else None
        channel = guild.get_channel(channel_id) if channel_id else None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def post_news(self, guild_id: int, title: str, description: str, color_kind: str = "standard") -> None:
        await self.bot.repo.add_news_event(guild_id, title, description, color_kind)
        channel = await self.get_configured_channel(guild_id, "news_channel_id")
        if channel is None:
            return
        factory = self.bot.embed_factory
        embed = {
            "standard": factory.standard,
            "danger": factory.danger,
            "success": factory.success,
            "reward": factory.reward,
        }.get(color_kind, factory.standard)(title, description)
        await channel.send(embed=embed)

    async def refresh_wanted_board(self, guild_id: int) -> None:
        settings = await self.bot.repo.ensure_guild_settings(guild_id)
        channel = await self.get_configured_channel(guild_id, "wanted_channel_id")
        if channel is None:
            return
        wanted = await self.bot.repo.list_wanted_players(guild_id)
        if wanted:
            lines = []
            guild = await self.get_guild(guild_id)
            for row in wanted[:15]:
                member = guild.get_member(row["user_id"])
                status, consequence = HEAT_STATUS.get(row["heat"], ("Unknown", ""))
                lines.append(
                    f"{HEAT_EMOJI} **{row['heat']}** - {member.mention if member else row['user_id']} | {status} | {row.get('gang_name', 'No Gang')}"
                )
                if consequence:
                    lines.append(consequence)
        else:
            lines = ["Vice City is quiet for the moment."]

        embed = self.bot.embed_factory.danger("Wanted Board", "\n".join(lines))
        message = None
        if settings.get("wanted_message_id"):
            try:
                message = await channel.fetch_message(settings["wanted_message_id"])
            except discord.HTTPException:
                message = None
        if message:
            await message.edit(embed=embed)
        else:
            sent = await channel.send(embed=embed)
            await self.bot.repo.update_guild_settings(guild_id, wanted_message_id=sent.id)

    async def refresh_vault(self, guild_id: int) -> None:
        settings = await self.bot.repo.ensure_guild_settings(guild_id)
        channel = await self.get_configured_channel(guild_id, "vault_channel_id")
        if channel is None:
            return
        crackdown_until = parse_datetime(settings.get("crackdown_until"))
        crackdown_text = (
            discord.utils.format_dt(crackdown_until, style="R") if crackdown_until and crackdown_until > utcnow() else "None"
        )
        turfs = await self.bot.repo.list_turfs(guild_id)
        event_summary = "No active event."
        if self.bot.event_service is not None:
            event_summary = self.bot.event_service.effect_summary(
                await self.bot.event_service.get_active_event(guild_id)
            )
        embed = self.bot.embed_factory.standard(
            "City Vault",
            "\n".join(
                [
                    f"{RACKS_EMOJI} Treasury: **{settings.get('treasury_balance', 0)}**",
                    f"Tax Rate: **{settings.get('tax_rate', DEFAULT_TAX_RATE)}%**",
                    f"Crackdown: **{crackdown_text}**",
                    f"{TURF_EMOJI} Active Turfs: **{len(turfs)}**",
                ]
            ),
        )
        embed.add_field(name="Live Event", value=event_summary, inline=False)
        message = None
        if settings.get("vault_message_id"):
            try:
                message = await channel.fetch_message(settings["vault_message_id"])
            except discord.HTTPException:
                message = None
        if message:
            await message.edit(embed=embed)
        else:
            sent = await channel.send(embed=embed)
            await self.bot.repo.update_guild_settings(guild_id, vault_message_id=sent.id)

    async def schedule_hourly_cycle(self, guild_id: int) -> None:
        self.bot.scheduler.add_job(
            self.run_hourly_cycle,
            "interval",
            hours=1,
            id=f"hourly:{guild_id}",
            replace_existing=True,
            kwargs={"guild_id": guild_id},
        )

    async def run_hourly_cycle(self, guild_id: int) -> None:
        settings = await self.bot.repo.ensure_guild_settings(guild_id)
        gangs = await self.bot.repo.list_gangs(guild_id)
        turfs = await self.bot.repo.list_turfs(guild_id)
        by_owner: dict[int, list[dict[str, Any]]] = {}
        for turf in turfs:
            by_owner.setdefault(turf["owner_gang_id"], []).append(turf)

        summary_lines: list[str] = []
        for gang in gangs:
            gang_members = await self.bot.repo.list_joined_players(guild_id, gang["id"])
            gross = sum(turf["hourly_income"] for turf in by_owner.get(gang["id"], []))
            penalty_count = sum(max(0, int(member["pending_income_penalties"])) for member in gang_members)
            penalty_percent = min(50, penalty_count * 10)
            post_penalty = gross * (100 - penalty_percent) // 100
            tax = post_penalty * settings["tax_rate"] // 100
            distributable = max(0, post_penalty - tax)
            bank_share = distributable * TURF_MEMBER_SPLIT_PERCENT // 100
            member_pool = distributable - bank_share
            per_member = member_pool // len(gang_members) if gang_members else 0

            if bank_share:
                await self.bot.repo.credit_gang_bank(gang["id"], bank_share)
            if tax:
                await self.bot.repo.credit_treasury(guild_id, tax)
            for member in gang_members:
                if per_member:
                    await self.bot.repo.credit_wallet(guild_id, member["user_id"], per_member)
                if member["pending_income_penalties"]:
                    await self.bot.repo.update_player(guild_id, member["user_id"], pending_income_penalties=0)

            summary_lines.append(
                f"{TURF_EMOJI} **{gang['name']}** | Turfs: {len(by_owner.get(gang['id'], []))} | "
                f"Gross: {gross} | Tax: {tax} | Bank: {bank_share} | Members: {per_member}"
            )

        assert self.bot.heat_service is not None
        await self.bot.heat_service.run_hourly_decay(guild_id)
        await self.bot.heat_service.release_expired_jails(guild_id)
        await self.refresh_wanted_board(guild_id)
        await self.refresh_vault(guild_id)
        await self.post_news(
            guild_id,
            "Hourly Income Report",
            "\n".join(summary_lines) if summary_lines else "No gangs are active yet.",
            "reward",
        )

    async def join_city(self, member: discord.Member) -> dict[str, Any]:
        player = await self.bot.repo.get_player(member.guild.id, member.id)
        if player and player["is_joined"]:
            raise InvalidStateError("You have already joined Vice City.")

        gangs = await self.bot.repo.list_gangs(member.guild.id)
        if not gangs:
            raise RuntimeError("Gang setup has not completed yet.")
        counts = await self.bot.repo.count_joined_players_by_gang(member.guild.id)
        gang_priority = {gang.name: index for index, gang in enumerate(GANGS)}
        selected = min(gangs, key=lambda row: (counts.get(row["id"], 0), gang_priority.get(row["name"], 99)))

        player = await self.bot.repo.ensure_player(
            member.guild.id,
            member.id,
            gang_id=selected["id"],
            rank="Street Rat",
            wallet=500,
            heat=0,
            xp=0,
            is_joined=1,
        )
        player = await self.bot.repo.update_player(
            member.guild.id,
            member.id,
            gang_id=selected["id"],
            rank="Street Rat",
            wallet=500,
            heat=0,
            xp=0,
            is_joined=1,
        )
        role = member.guild.get_role(selected["role_id"]) if selected["role_id"] else None
        if role and role not in member.roles:
            await member.add_roles(role, reason="Vice City OS gang assignment")

        channel = member.guild.get_channel(selected["channel_id"]) if selected["channel_id"] else None
        welcome = self.bot.embed_factory.success(
            "Welcome To Vice City",
            f"{member.mention} joined **{selected['name']}** with {RACKS_EMOJI} 500 to their name.",
        )
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=welcome)
        await self.post_news(
            member.guild.id,
            "New Recruit",
            f"{member.mention} is now running with **{selected['name']}**.",
            "success",
        )
        return player

    async def recalculate_rank(self, guild_id: int, user_id: int) -> tuple[dict[str, Any], str | None]:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise RuntimeError("Player does not exist.")
        if player["rank"] == "Mayor":
            return player, None
        target_rank = "Street Rat"
        for rank_name, threshold in RANK_THRESHOLDS:
            if player["xp"] >= threshold:
                target_rank = rank_name

        gang = await self.bot.repo.get_gang(player["gang_id"]) if player.get("gang_id") else None
        if target_rank == "Boss" and gang and gang.get("boss_user_id") not in (None, user_id):
            target_rank = "Capo"

        previous = player["rank"]
        if target_rank != previous:
            await self.bot.repo.update_player(guild_id, user_id, rank=target_rank)
            player = await self.bot.repo.get_player(guild_id, user_id)  # type: ignore[assignment]
        if target_rank == "Boss" and gang and gang.get("boss_user_id") != user_id:
            await self.bot.repo.upsert_gang(guild_id, gang["name"], boss_user_id=user_id, last_boss_active_at=isoformat(utcnow()))
        return player, target_rank if previous != target_rank else None

    async def award_xp(self, guild_id: int, user_id: int, amount: int) -> tuple[dict[str, Any], str | None]:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise RuntimeError("Player does not exist.")
        await self.bot.repo.update_player(guild_id, user_id, xp=player["xp"] + amount)
        player, promoted = await self.recalculate_rank(guild_id, user_id)
        return player, promoted

    async def update_boss_activity(self, guild_id: int, user_id: int) -> None:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if not player or player["rank"] != "Boss" or not player["gang_id"]:
            return
        gang = await self.bot.repo.get_gang(player["gang_id"])
        if gang:
            await self.bot.repo.upsert_gang(
                guild_id,
                gang["name"],
                last_boss_active_at=isoformat(utcnow()),
                boss_user_id=user_id,
            )

    async def describe_player(self, guild_id: int, user_id: int) -> str:
        guild = await self.get_guild(guild_id)
        member = guild.get_member(user_id)
        return member.mention if member else f"<@{user_id}>"

    async def build_informant_snapshot(self, guild_id: int) -> dict[str, Any]:
        settings = await self.bot.repo.ensure_guild_settings(guild_id)
        gangs = await self.bot.repo.list_gangs(guild_id)
        member_counts = await self.bot.repo.count_joined_players_by_gang(guild_id)
        turfs = await self.bot.repo.list_turfs(guild_id)
        wars = await self.bot.repo.list_active_wars(guild_id)
        wanted = await self.bot.repo.list_wanted_players(guild_id)
        news = await self.bot.repo.list_news_events(guild_id, limit=4)

        gang_rows: list[dict[str, Any]] = []
        gang_by_id: dict[int, dict[str, Any]] = {}
        for gang in gangs:
            owned = [turf["name"] for turf in turfs if turf["owner_gang_id"] == gang["id"]]
            row = {
                "id": gang["id"],
                "name": gang["name"],
                "bank_balance": int(gang["bank_balance"]),
                "member_count": int(member_counts.get(gang["id"], 0)),
                "turf_count": len(owned),
                "turfs": owned,
            }
            gang_rows.append(row)
            gang_by_id[gang["id"]] = row

        turf_by_id = {turf["id"]: turf for turf in turfs}
        war_rows = [
            {
                "id": war["id"],
                "attacker_name": gang_by_id.get(war["attacker_gang_id"], {}).get("name", "Unknown"),
                "defender_name": gang_by_id.get(war["defender_gang_id"], {}).get("name", "Unknown"),
                "turf_name": turf_by_id.get(war["turf_id"], {}).get("name", "Unknown Turf"),
            }
            for war in wars
        ]
        wanted_rows = [
            {
                "user_id": row["user_id"],
                "gang_name": row.get("gang_name", "No Gang"),
                "heat": int(row["heat"]),
            }
            for row in wanted
        ]
        news_rows = [
            {
                "title": row["title"],
                "description": row["description"],
                "created_at": row.get("created_at"),
            }
            for row in news
        ]
        return {
            "treasury_balance": int(settings.get("treasury_balance", 0)),
            "tax_rate": int(settings.get("tax_rate", DEFAULT_TAX_RATE)),
            "gangs": gang_rows,
            "wars": war_rows,
            "wanted": wanted_rows,
            "news": news_rows,
        }

    def choose_informant_seed(self, snapshot: dict[str, Any]) -> InformantTipSeed:
        gangs = sorted(
            snapshot.get("gangs", []),
            key=lambda gang: (gang["bank_balance"], gang["turf_count"], -gang["member_count"]),
            reverse=True,
        )
        wars = snapshot.get("wars", [])
        wanted = sorted(snapshot.get("wanted", []), key=lambda row: row["heat"], reverse=True)
        treasury_balance = int(snapshot.get("treasury_balance", 0))
        news = snapshot.get("news", [])
        stretched = [
            gang
            for gang in snapshot.get("gangs", [])
            if gang["turf_count"] > 0 and (gang["member_count"] == 0 or gang["turf_count"] > gang["member_count"])
        ]

        if wars:
            front = wars[0]
            return InformantTipSeed(
                focus="War smoke",
                facts=[
                    f"{front['attacker_name']} is actively attacking {front['defender_name']} over {front['turf_name']}.",
                    "Active wars drain gang banks and pull bodies away from other turf.",
                    f"The city treasury is currently holding {treasury_balance} Racks.",
                ],
                fallback_headline="Street Contact",
                fallback_tip=(
                    f"{front['turf_name']} is too loud tonight. When {front['attacker_name']} and "
                    f"{front['defender_name']} start bleeding for the same block, somebody else's corner gets soft."
                ),
                fallback_nudge="Watch the war front, then move where the guards got thinner.",
            )

        if wanted and wanted[0]["heat"] >= 4:
            hottest = wanted[0]
            return InformantTipSeed(
                focus="Police pressure",
                facts=[
                    f"A player tied to {hottest['gang_name']} is currently at Heat {hottest['heat']}.",
                    "High-heat crews pull police eyes and make the rest of their operation shakier.",
                    f"City Hall is taxing at {snapshot.get('tax_rate', DEFAULT_TAX_RATE)} percent.",
                ],
                fallback_headline="Street Contact",
                fallback_tip=(
                    f"The cops are leaning hard on {hottest['gang_name']} tonight. When one face gets too hot, "
                    "the whole crew starts making sloppy decisions."
                ),
                fallback_nudge="A hunted crew is easier to read, and easier to hit.",
            )

        if gangs and stretched:
            rich = gangs[0]
            thin = sorted(stretched, key=lambda gang: (gang["member_count"], -gang["turf_count"], -gang["bank_balance"]))[0]
            if rich["bank_balance"] > 0:
                return InformantTipSeed(
                    focus="Soft underbelly",
                    facts=[
                        f"{rich['name']} currently has the fattest gang bank at {rich['bank_balance']} Racks.",
                        f"{thin['name']} is stretched across {thin['turf_count']} turfs with only {thin['member_count']} joined members.",
                        "Crews with wide turf lines and thin manpower are easier to pressure.",
                    ],
                    fallback_headline="Street Contact",
                    fallback_tip=(
                        f"{rich['name']} are sitting heavy, and {thin['name']} are spread thin. "
                        "Vice City loves rich pockets and tired lookouts."
                    ),
                    fallback_nudge="Go where the money is, or where the map is wider than the muscle.",
                )

        if treasury_balance >= 1000:
            return InformantTipSeed(
                focus="City Hall money",
                facts=[
                    f"The city treasury currently holds {treasury_balance} Racks.",
                    "A flush treasury means more room for rewards, pardons, and political pressure.",
                    f"Current tax rate is {snapshot.get('tax_rate', DEFAULT_TAX_RATE)} percent.",
                ],
                fallback_headline="Street Contact",
                fallback_tip="City Hall's vault sounds heavier than the streets right now. Heavy vaults make politicians brave and crooks curious.",
                fallback_nudge="When the mayor gets comfortable, the whole city starts playing harder.",
            )

        if news:
            latest = news[0]
            return InformantTipSeed(
                focus="Fresh rumor",
                facts=[
                    f"Recent city news headline: {latest['title']}.",
                    f"Recent city news detail: {latest['description']}",
                ],
                fallback_headline="Street Contact",
                fallback_tip=f"Word on the curb is still circling this: {latest['title']}. Vice City never talks about yesterday unless it still matters tonight.",
                fallback_nudge="Follow the loudest rumor. It usually leads to live money or live trouble.",
            )

        if gangs:
            leader = gangs[0]
            return InformantTipSeed(
                focus="Power map",
                facts=[
                    f"{leader['name']} controls {leader['turf_count']} turfs and has {leader['bank_balance']} Racks in the gang bank.",
                    "The strongest gang tends to create the most envy and the most targets.",
                ],
                fallback_headline="Street Contact",
                fallback_tip=f"{leader['name']} look like they're owning too much sky for one night. Crews that high up start forgetting where the ground is.",
                fallback_nudge="Power always draws a line around itself. Find the weak edge.",
            )

        return InformantTipSeed(
            focus="Quiet streets",
            facts=["Vice City is calm right now, with no standout wars or hot leads."],
            fallback_headline="Street Contact",
            fallback_tip="Too quiet. Vice City only goes silent when something ugly is about to wake up.",
            fallback_nudge="Stack cash, watch the news, and be ready to move first.",
        )

    async def build_tip_embed(self, guild_id: int) -> tuple[discord.Embed, str | None]:
        snapshot = await self.build_informant_snapshot(guild_id)
        seed = self.choose_informant_seed(snapshot)
        fallback = GeminiInformantTipResult(
            headline=seed.fallback_headline,
            tip=seed.fallback_tip,
            nudge=seed.fallback_nudge,
        )
        tip = await self.bot.gemini_service.generate_informant_tip(  # type: ignore[union-attr]
            focus=seed.focus,
            facts=seed.facts,
            fallback=fallback,
        )
        embed = self.bot.embed_factory.standard(tip.headline, tip.tip)
        pressure_tags: list[str] = []
        if snapshot.get("wars"):
            pressure_tags.append("war smoke")
        if snapshot.get("wanted"):
            pressure_tags.append("police heat")
        if int(snapshot.get("treasury_balance", 0)) >= 1000:
            pressure_tags.append("city hall money")
        if not pressure_tags:
            pressure_tags.append("quiet streets")
        embed.add_field(name="Focus", value=seed.focus.title(), inline=True)
        embed.add_field(name="Heat In The Air", value=", ".join(tag.title() for tag in pressure_tags), inline=True)
        embed.add_field(name="Street Read", value=tip.nudge, inline=False)
        return embed, seed.media_key

    async def build_profile_embed(self, guild_id: int, user_id: int) -> discord.Embed:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise InvalidStateError("That player does not have a Vice City profile yet.")
        guild = await self.get_guild(guild_id)
        member = guild.get_member(user_id)
        gang = await self.bot.repo.get_gang(player["gang_id"]) if player.get("gang_id") else None
        inventory = await self.bot.repo.list_inventory(guild_id, user_id)
        daily_status = self.describe_daily_reward_status(player)
        streak_status = self.get_daily_reward_status(player)
        description = "\n".join(
            [
                f"Member: {member.mention if member else user_id}",
                f"Gang: **{gang['name'] if gang else 'Independent'}**",
                f"Rank: **{player['rank']}**",
                f"{RACKS_EMOJI} Wallet: **{player['wallet']}**",
                f"{HEAT_EMOJI} Heat: **{player['heat']}**",
                f"XP: **{player['xp']}**",
                f"Daily Streak: **{streak_status['current_streak']}**",
                f"Street Drop: {daily_status}",
                f"Inventory: weapon={inventory.get('weapon', 0)}, burnerphone={inventory.get('burnerphone', 0)}",
            ]
        )
        return self.bot.embed_factory.standard("Profile", description)

    async def build_wallet_embed(self, guild_id: int, user_id: int) -> discord.Embed:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise InvalidStateError("That player does not have a Vice City profile yet.")
        daily_status = self.get_daily_reward_status(player)
        embed = self.bot.embed_factory.standard("Wallet", f"You have **{player['wallet']}** Racks.")
        embed.add_field(name="Heat", value=str(player["heat"]), inline=True)
        embed.add_field(name="Rank", value=str(player["rank"]), inline=True)
        embed.add_field(name="Daily Streak", value=str(daily_status["current_streak"]), inline=True)
        embed.add_field(name="Street Drop", value=self.describe_daily_reward_status(player), inline=False)
        return embed

    async def build_gang_embed(self, guild_id: int, user_id: int) -> discord.Embed:
        guild = await self.get_guild(guild_id)
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None or not player.get("gang_id"):
            raise InvalidStateError("You are not assigned to a gang.")
        gang = await self.bot.repo.get_gang(player["gang_id"])
        members = await self.bot.repo.list_joined_players(guild_id, player["gang_id"])
        turfs = [turf for turf in await self.bot.repo.list_turfs(guild_id) if turf["owner_gang_id"] == player["gang_id"]]
        active_war = await self.bot.repo.get_active_war_for_gang(guild_id, player["gang_id"])
        boss = guild.get_member(gang["boss_user_id"]) if gang and gang.get("boss_user_id") else None
        top_earners = sorted(members, key=lambda member: (member["xp"], member["wallet"]), reverse=True)[:3]
        hottest = sorted(members, key=lambda member: (member["heat"], member["xp"]), reverse=True)[:1]
        top_text = "\n".join(
            f"{guild.get_member(member['user_id']).mention if guild.get_member(member['user_id']) else member['user_id']} - XP {member['xp']}"
            for member in top_earners
        ) or "No active crew yet."
        turf_text = ", ".join(turf["name"] for turf in turfs[:5]) or "No turf under control."
        if len(turfs) > 5:
            turf_text += f" +{len(turfs) - 5} more"
        war_text = "No active turf war."
        if active_war:
            turf = await self.bot.repo.get_turf(active_war["turf_id"])
            side = "Attacking" if active_war["attacker_gang_id"] == player["gang_id"] else "Defending"
            war_text = f"{side} at {turf['name'] if turf else 'Unknown Turf'}"
        hot_member = hottest[0] if hottest else None
        hot_label = "Crew is keeping cool."
        if hot_member:
            member = guild.get_member(hot_member["user_id"])
            hot_label = f"{member.mention if member else hot_member['user_id']} | {HEAT_EMOJI} {hot_member['heat']}"
        embed = self.bot.embed_factory.standard(
            "Gang Overview",
            f"Vice City dossier for **{gang['name']}**.",
        )
        embed.add_field(name="Boss", value=boss.mention if boss else "Unclaimed", inline=True)
        embed.add_field(name="Bank", value=f"{RACKS_EMOJI} {gang['bank_balance']}", inline=True)
        embed.add_field(name="Turfs", value=f"{TURF_EMOJI} {len(turfs)}", inline=True)
        embed.add_field(name="Crew Size", value=str(len(members)), inline=True)
        embed.add_field(name="War Status", value=war_text, inline=True)
        embed.add_field(name="Hottest Crew Member", value=hot_label, inline=True)
        embed.add_field(name="Held Blocks", value=turf_text, inline=False)
        embed.add_field(name="Top Earners", value=top_text, inline=False)
        if boss is not None:
            embed.set_thumbnail(url=boss.display_avatar.url)
        return embed

    async def build_map_embed(self, guild_id: int) -> discord.Embed:
        gangs = await self.bot.repo.list_gangs(guild_id)
        turfs = await self.bot.repo.list_turfs(guild_id)
        wars = await self.bot.repo.list_active_wars(guild_id)
        embed = self.bot.embed_factory.standard(
            "Vice City Map",
            f"Turf control across the city. Active war fronts: **{len(wars)}**.",
        )
        for gang in gangs:
            owned = [turf["name"] for turf in turfs if turf["owner_gang_id"] == gang["id"]]
            embed.add_field(
                name=f"{gang['name']} | {TURF_EMOJI} {len(owned)} | {RACKS_EMOJI} {gang['bank_balance']}",
                value=", ".join(owned) if owned else "No turfs",
                inline=True,
            )
        if wars:
            war_lines: list[str] = []
            for war in wars[:3]:
                turf = await self.bot.repo.get_turf(war["turf_id"])
                war_lines.append(f"War #{war['id']} over {turf['name'] if turf else 'Unknown Turf'}")
            embed.add_field(name="Hot Zones", value="\n".join(war_lines), inline=False)
        return embed

    async def build_news_embed(self, guild_id: int, *, limit: int = 10) -> discord.Embed:
        entries = await self.bot.repo.list_news_events(guild_id, limit=limit)
        embed = self.bot.embed_factory.standard("City News", "Vice City's latest chatter, scoreboards, and blood in the water.")
        if self.bot.event_service is not None:
            active_event = await self.bot.event_service.get_active_event(guild_id)
            if active_event is not None:
                event_summary = self.bot.event_service.effect_summary(active_event)
                embed.add_field(name="Live City Event", value=event_summary, inline=False)
        if not entries:
            embed.add_field(name="Quiet Night", value="No news yet.", inline=False)
            return embed
        for entry in entries[:6]:
            created_at = parse_datetime(entry.get("created_at"))
            when = f" {discord.utils.format_dt(created_at, style='R')}" if created_at else ""
            summary = str(entry["description"])
            if len(summary) > 180:
                summary = summary[:177].rstrip() + "..."
            embed.add_field(name=f"{entry['title']}{when}", value=summary, inline=False)
        return embed

    async def build_wanted_embed(self, guild_id: int) -> tuple[discord.Embed, discord.File | None]:
        guild = await self.get_guild(guild_id)
        wanted = await self.bot.repo.list_wanted_players(guild_id)
        if not wanted:
            return self.bot.embed_factory.danger("Wanted Board", "No one is currently on the wanted board."), None
        lines = []
        poster_file: discord.File | None = None
        poster_target = next((row for row in wanted if int(row["heat"]) >= 5), wanted[0])
        for entry in wanted[:10]:
            member = guild.get_member(entry["user_id"])
            lines.append(
                f"{member.mention if member else entry['user_id']} | {HEAT_EMOJI} {entry['heat']} | {entry.get('gang_name', 'No Gang')}"
            )
        embed = self.bot.embed_factory.danger("Wanted Board", "\n".join(lines))
        if int(poster_target["heat"]) >= 5 and self.bot.visual_service is not None:
            embed, poster_file = await self.bot.visual_service.build_wanted_poster(
                guild_id,
                poster_target["user_id"],
                reason="Heat 5 pressure put the whole city on alert.",
            )
        return embed, poster_file

    async def build_leaderboard_embed(self, guild_id: int) -> discord.Embed:
        guild = await self.get_guild(guild_id)
        richest = await self.bot.repo.get_richest_players(guild_id, limit=5)
        gangs = await self.bot.repo.get_powerful_gangs(guild_id, limit=5)
        hottest = sorted(await self.bot.repo.list_joined_players(guild_id), key=lambda row: (row["heat"], row["xp"]), reverse=True)[:5]
        embed = self.bot.embed_factory.reward("Leaderboard", "Vice City's loudest names right now.")
        richest_text = "\n".join(
            f"{index}. {guild.get_member(player['user_id']).mention if guild.get_member(player['user_id']) else player['user_id']} - {RACKS_EMOJI} {player['wallet']}"
            for index, player in enumerate(richest, start=1)
        ) or "No players yet."
        gang_text = "\n".join(
            f"{index}. {gang['name']} - {TURF_EMOJI} {gang['turf_count']} | {RACKS_EMOJI} {gang['bank_balance']}"
            for index, gang in enumerate(gangs, start=1)
        ) or "No gangs yet."
        hot_text = "\n".join(
            f"{index}. {guild.get_member(player['user_id']).mention if guild.get_member(player['user_id']) else player['user_id']} - {HEAT_EMOJI} {player['heat']}"
            for index, player in enumerate(hottest, start=1)
        ) or "No one is drawing heat."
        embed.add_field(name="Richest Members", value=richest_text, inline=False)
        embed.add_field(name="Top Gangs", value=gang_text, inline=False)
        embed.add_field(name="Most Wanted Movers", value=hot_text, inline=False)
        if richest:
            member = guild.get_member(richest[0]["user_id"])
            if member is not None:
                embed.set_thumbnail(url=member.display_avatar.url)
        return embed

    def build_shop_embed(self, item_name: str | None = None) -> discord.Embed:
        selected = item_name.lower() if item_name else None
        embed = self.bot.embed_factory.standard("Black Market", "Pick your gear from the menu below.")
        for item, details in BLACK_MARKET_ITEMS.items():
            icon = "\U0001F52B" if item == "weapon" else "\U0001F4F1" if item == "burnerphone" else "\u2696\ufe0f"
            label = f"{icon} {item.title()}"
            value = f"{RACKS_EMOJI} {details['price']}"
            if selected == item:
                if item == "weapon":
                    value += "\nStackable boost for turf wars."
                elif item == "burnerphone":
                    value += "\nBurns on the next operation to hide the trail."
                else:
                    value += "\nInstantly knocks 2 Heat off if your cooldown is clear."
            embed.add_field(name=label, value=value, inline=True)
        return embed

    async def member_is_jailed(self, guild_id: int, user_id: int) -> bool:
        jail = await self.bot.repo.get_active_jail_for_user(guild_id, user_id)
        if not jail:
            return False
        release_at = parse_datetime(jail["release_at"])
        return bool(release_at and release_at > utcnow())

    async def operation_cooldown_retry_after(self, guild_id: int, user_id: int, cooldown_seconds: int) -> float:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if not player or not player.get("last_operation_at"):
            return 0
        last_operation = parse_datetime(player["last_operation_at"])
        if last_operation is None:
            return 0
        retry_at = last_operation.timestamp() + cooldown_seconds
        return max(0.0, retry_at - utcnow().timestamp())

    async def choose_heat_status_text(self, heat: int) -> str:
        status, consequence = HEAT_STATUS.get(heat, ("Unknown", ""))
        return f"{status}: {consequence}" if consequence else status

    async def deposit_to_gang(self, guild_id: int, user_id: int, amount: int) -> tuple[int, int]:
        if amount <= 0:
            raise InvalidStateError("Deposit amount must be greater than zero.")
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None or not player.get("gang_id"):
            raise InvalidStateError("You are not in a gang.")
        wallet_balance = await self.bot.repo.debit_wallet(guild_id, user_id, amount)
        bank_balance = await self.bot.repo.credit_gang_bank(player["gang_id"], amount)
        return wallet_balance, bank_balance

    async def withdraw_from_gang(self, guild_id: int, user_id: int, amount: int) -> tuple[int, int]:
        if amount <= 0:
            raise InvalidStateError("Withdraw amount must be greater than zero.")
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None or not player.get("gang_id"):
            raise InvalidStateError("You are not in a gang.")
        if player["rank"] not in ("Capo", "Boss"):
            raise commands.MissingPermissions(["rank:Capo"])
        bank_balance = await self.bot.repo.debit_gang_bank(player["gang_id"], amount)
        wallet_balance = await self.bot.repo.credit_wallet(guild_id, user_id, amount)
        return wallet_balance, bank_balance

    async def claim_daily_reward(self, guild_id: int, user_id: int) -> discord.Embed:
        async with self.bot.member_locks.acquire(user_id):
            player = await self.bot.repo.get_player(guild_id, user_id)
            if player is None or not player["is_joined"]:
                raise InvalidStateError("You need to join Vice City first.")

            status = self.get_daily_reward_status(player)
            if not status["can_claim"]:
                next_claim_at = status["next_claim_at"]
                if next_claim_at is None:
                    raise InvalidStateError("Today's street drop is already gone. Try again tomorrow.")
                raise InvalidStateError(
                    f"You already collected today's street drop. Next claim opens {discord.utils.format_dt(next_claim_at, style='R')}."
                )

            reward_amount = int(status["reward_amount"])
            new_streak = int(status["claim_streak"])
            updated_player = await self.bot.repo.claim_daily_reward(
                guild_id,
                user_id,
                amount=reward_amount,
                claimed_at=isoformat(utcnow()) or "",
                streak=new_streak,
            )

        next_status = self.get_daily_reward_status(updated_player)
        next_reward = self._daily_reward_amount(new_streak + 1)
        if status["missed_window"] and player.get("last_daily_claim_at"):
            description = f"You missed a day, so the streak restarted with **{reward_amount}** Racks."
        elif new_streak == 1:
            description = f"You pocketed **{reward_amount}** Racks from today's street drop."
        else:
            description = f"You kept the streak alive and collected **{reward_amount}** Racks."
        embed = self.bot.embed_factory.reward("Daily Streak Claimed", description)
        embed.add_field(name="Streak", value=f"{new_streak} day{'s' if new_streak != 1 else ''}", inline=True)
        embed.add_field(name="Wallet", value=f"{RACKS_EMOJI} {updated_player['wallet']}", inline=True)
        embed.add_field(name="Next Bonus", value=f"{RACKS_EMOJI} {next_reward}", inline=True)
        next_claim_at = next_status["next_claim_at"]
        if next_claim_at is not None:
            embed.add_field(name="Next Claim", value=discord.utils.format_dt(next_claim_at, style="R"), inline=False)
        return embed

    async def buy_item(self, guild_id: int, user_id: int, item_name: str) -> discord.Embed:
        item_name = item_name.lower()
        if item_name not in BLACK_MARKET_ITEMS:
            raise InvalidStateError("That item is not sold on the black market.")
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need to join Vice City first.")
        if int(player["heat"]) >= 4 and item_name != "lawyer":
            raise InvalidStateError("The black market shuts you out at Heat 4 and above.")
        if item_name == "lawyer":
            cooldown_until = parse_datetime(player.get("lawyer_cooldown_until"))
            if cooldown_until and cooldown_until > utcnow():
                raise InvalidStateError("You already used a lawyer recently. Wait for the cooldown.")

        base_price = BLACK_MARKET_ITEMS[item_name]["price"]
        final_price = base_price
        if self.bot.event_service is not None:
            event_effect = await self.bot.event_service.get_active_effect(guild_id)
            final_price = self.bot.event_service.apply_shop_price_effect(base_price, event_effect)
        await self.bot.repo.debit_wallet(guild_id, user_id, final_price)
        if item_name == "lawyer":
            new_heat = await self.bot.heat_service.reduce_heat(guild_id, user_id, 2, reason="Lawyer")  # type: ignore[union-attr]
            await self.bot.repo.update_player(
                guild_id,
                user_id,
                lawyer_cooldown_until=isoformat(utcnow() + timedelta(seconds=LAWYER_COOLDOWN_SECONDS)),
            )
            return self.bot.embed_factory.success(
                "Lawyer Retained",
                f"Your Heat dropped to **{new_heat}**. Paid **{final_price}** Racks.",
            )

        new_quantity = await self.bot.repo.adjust_inventory(guild_id, user_id, item_name, 1)
        return self.bot.embed_factory.reward(
            "Black Market Purchase",
            f"You bought **{item_name}** for **{final_price}** Racks. Inventory now: **{new_quantity}**.",
        )
