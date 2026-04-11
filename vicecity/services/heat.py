from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING

from apscheduler.jobstores.base import JobLookupError

from vicecity.constants import HEAT_FIVE_GRACE_SECONDS, HEAT_FIVE_JAIL_SECONDS, LAY_LOW_SECONDS
from vicecity.utils.time import isoformat, parse_datetime, utcnow

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class HeatService:
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        self.random = random.Random()

    async def rehydrate_active_jails(self, guild_id: int) -> None:
        for jail in await self.bot.repo.list_active_jails(guild_id):
            release_at = parse_datetime(jail["release_at"])
            if release_at is None:
                continue
            if release_at <= utcnow():
                await self.release_jail(jail["id"], guild_id, jail["user_id"], announce=False)
            else:
                self.schedule_jail_release(jail["id"], guild_id, jail["user_id"], release_at)

    async def release_expired_jails(self, guild_id: int) -> None:
        for jail in await self.bot.repo.list_active_jails(guild_id):
            release_at = parse_datetime(jail["release_at"])
            if release_at and release_at <= utcnow():
                await self.release_jail(jail["id"], guild_id, jail["user_id"], announce=True)

    async def jail_player(self, guild_id: int, user_id: int, reason: str, duration_seconds: int, *, announce: bool = True) -> None:
        release_at = utcnow() + timedelta(seconds=duration_seconds)
        jail_id = await self.bot.repo.create_jail_record(guild_id, user_id, reason, isoformat(release_at))
        await self.bot.repo.update_player(guild_id, user_id, jailed_until=isoformat(release_at))
        self.schedule_jail_release(jail_id, guild_id, user_id, release_at)
        if announce:
            assert self.bot.city_service is not None
            mention = await self.bot.city_service.describe_player(guild_id, user_id)
            hours = duration_seconds / 3600
            duration_text = f"{hours:g} hour" + ("" if hours == 1 else "s")
            await self.bot.city_service.post_news(
                guild_id,
                "Arrest Made",
                f"{mention} was jailed for **{duration_text}**. Reason: {reason}.",
                "danger",
            )

    def schedule_jail_release(self, jail_id: int, guild_id: int, user_id: int, release_at) -> None:
        self.bot.scheduler.add_job(
            self.release_jail,
            "date",
            run_date=release_at,
            id=f"jail:{jail_id}",
            replace_existing=True,
            kwargs={"jail_id": jail_id, "guild_id": guild_id, "user_id": user_id, "announce": True},
        )

    async def release_jail(self, jail_id: int, guild_id: int, user_id: int, announce: bool = True) -> None:
        try:
            self.bot.scheduler.remove_job(f"jail:{jail_id}")
        except JobLookupError:
            pass
        await self.bot.repo.release_jail_record(jail_id)
        await self.bot.repo.update_player(guild_id, user_id, jailed_until=None)
        if announce:
            assert self.bot.city_service is not None
            mention = await self.bot.city_service.describe_player(guild_id, user_id)
            await self.bot.city_service.post_news(
                guild_id,
                "Release Notice",
                f"{mention} walked out of lockup and back into Vice City.",
                "success",
            )

    async def get_crackdown_bonus(self, guild_id: int) -> int:
        settings = await self.bot.repo.ensure_guild_settings(guild_id)
        crackdown_until = parse_datetime(settings.get("crackdown_until"))
        return 1 if crackdown_until and crackdown_until > utcnow() else 0

    async def apply_heat(self, guild_id: int, user_id: int, delta: int, *, reason: str) -> int:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise RuntimeError("Player not found.")
        previous_heat = int(player["heat"])
        new_heat = max(0, min(5, previous_heat + delta))
        extra_fields: dict[str, object] = {"heat": new_heat, "last_heat_change_at": isoformat(utcnow())}
        if previous_heat < 4 <= new_heat:
            extra_fields["pending_income_penalties"] = int(player["pending_income_penalties"]) + 1
        await self.bot.repo.update_player(guild_id, user_id, **extra_fields)
        if new_heat >= 5 and previous_heat < 5:
            await self._handle_most_wanted_entry(guild_id, user_id)
        await self.bot.city_service.refresh_wanted_board(guild_id)  # type: ignore[union-attr]
        return new_heat

    async def reduce_heat(self, guild_id: int, user_id: int, amount: int, *, reason: str) -> int:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise RuntimeError("Player not found.")
        new_heat = max(0, int(player["heat"]) - amount)
        await self.bot.repo.update_player(guild_id, user_id, heat=new_heat, last_heat_change_at=isoformat(utcnow()))
        if new_heat < 5:
            try:
                self.bot.scheduler.remove_job(f"heat5:{guild_id}:{user_id}")
            except JobLookupError:
                pass
        await self.bot.city_service.refresh_wanted_board(guild_id)  # type: ignore[union-attr]
        return new_heat

    async def _handle_most_wanted_entry(self, guild_id: int, user_id: int) -> None:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None or not player.get("gang_id"):
            return

        all_turfs = await self.bot.repo.list_turfs(guild_id)
        turfs = [turf for turf in all_turfs if turf["owner_gang_id"] == player["gang_id"]]
        rivals = [gang for gang in await self.bot.repo.list_gangs(guild_id) if gang["id"] != player["gang_id"]]
        if turfs and rivals:
            turf_counts = {gang["id"]: len([turf for turf in all_turfs if turf["owner_gang_id"] == gang["id"]]) for gang in rivals}
            lost_turf = self.random.choice(turfs)
            rival = min(rivals, key=lambda gang: turf_counts.get(gang["id"], 0))
            current_gang = await self.bot.repo.get_gang(player["gang_id"])
            await self.bot.repo.update_turf_owner(lost_turf["id"], rival["id"])
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                guild_id,
                "Turf Seized",
                f"A police dragnet ripped **{lost_turf['name']}** away from **{current_gang['name'] if current_gang else 'its owners'}** and handed it to **{rival['name']}**.",
                "danger",
            )

        grace_at = utcnow() + timedelta(seconds=HEAT_FIVE_GRACE_SECONDS)
        self.bot.scheduler.add_job(
            self._resolve_most_wanted_grace,
            "date",
            run_date=grace_at,
            id=f"heat5:{guild_id}:{user_id}",
            replace_existing=True,
            kwargs={"guild_id": guild_id, "user_id": user_id},
        )
        mention = await self.bot.city_service.describe_player(guild_id, user_id)  # type: ignore[union-attr]
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            guild_id,
            "Most Wanted",
            f"{mention} hit Heat 5. They have one minute to lawyer up before the city locks them down.",
            "danger",
        )
        channel = await self.bot.city_service.get_configured_channel(guild_id, "wanted_channel_id")  # type: ignore[union-attr]
        if channel is not None and self.bot.visual_service is not None:
            try:
                poster_embed, poster_file = await self.bot.visual_service.build_wanted_poster(
                    guild_id,
                    user_id,
                    reason="Heat 5 triggered an immediate citywide manhunt.",
                )
                banner_file = await self.bot.visual_service.build_event_banner("heat_5", subtitle="Most Wanted")
                if banner_file is not None:
                    poster_embed.set_thumbnail(url=f"attachment://{banner_file.filename}")
                    await channel.send(files=[banner_file, poster_file], embed=poster_embed)
                else:
                    await channel.send(file=poster_file, embed=poster_embed)
            except Exception:
                pass

    async def _resolve_most_wanted_grace(self, guild_id: int, user_id: int) -> None:
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            return
        if int(player["heat"]) < 5:
            return
        if await self.bot.city_service.member_is_jailed(guild_id, user_id):  # type: ignore[union-attr]
            return
        await self.jail_player(guild_id, user_id, "Reached Heat 5", HEAT_FIVE_JAIL_SECONDS, announce=True)

    async def run_hourly_decay(self, guild_id: int) -> None:
        players = await self.bot.repo.list_joined_players(guild_id)
        now = utcnow()
        for player in players:
            if int(player["heat"]) <= 0:
                continue
            last_operation = parse_datetime(player.get("last_operation_at"))
            if last_operation is None or (now - last_operation).total_seconds() >= LAY_LOW_SECONDS:
                await self.reduce_heat(guild_id, player["user_id"], 1, reason="Lay low")
