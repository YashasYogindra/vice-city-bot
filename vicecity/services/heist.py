from __future__ import annotations

import random
import string
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from apscheduler.jobstores.base import JobLookupError

from vicecity.constants import HEIST_EXECUTION_SECONDS, HEIST_PLANNING_SECONDS
from vicecity.exceptions import HeistDMValidationError, InvalidStateError
from vicecity.utils.time import isoformat, parse_datetime, utcnow
from vicecity.views.action_hub import HeistRoleSelectView

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class HeistService:
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        self.random = random.Random()

    async def create_heist(self, boss: discord.Member) -> dict:
        player = await self.bot.repo.get_player(boss.guild.id, boss.id)
        if player is None or player["rank"] != "Boss":
            raise InvalidStateError("Only a Boss can plan the Casino Job.")
        gang = await self.bot.repo.get_gang(player["gang_id"])
        if gang is None:
            raise InvalidStateError("You need a gang to plan a heist.")
        existing = await self.bot.repo.get_active_heist_for_gang(boss.guild.id, gang["id"])
        if existing:
            raise InvalidStateError("Your gang already has an active heist.")

        bot_member = boss.guild.me or boss.guild.get_member(self.bot.user.id)  # type: ignore[arg-type]
        overwrites = {
            boss.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            boss: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if bot_member is not None:
            overwrites[bot_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        channel = await boss.guild.create_text_channel(
            f"casino-plan-{gang['name'].lower()}",
            overwrites=overwrites,
            reason="Vice City OS heist planning",
        )
        launch_deadline = utcnow() + timedelta(seconds=HEIST_PLANNING_SECONDS)
        heist_id = await self.bot.repo.create_heist(
            boss.guild.id,
            gang["id"],
            boss.id,
            channel.id,
            isoformat(launch_deadline),
        )
        self.bot.scheduler.add_job(
            self.handle_planning_timeout,
            "date",
            run_date=launch_deadline,
            id=f"heist-plan:{heist_id}",
            replace_existing=True,
            kwargs={"heist_id": heist_id},
        )
        await channel.send(
            embed=self.bot.embed_factory.standard(
                "Casino Job Planning",
                "Fill the crew with the selector below or use `/heist join`, then launch with `/heist go`.",
            ),
            view=HeistRoleSelectView(self.bot),
        )
        return await self.bot.repo.get_heist(heist_id)  # type: ignore[return-value]

    async def join_role(self, member: discord.Member, role_name: str) -> dict:
        role_name = role_name.lower()
        if role_name not in {"hacker", "driver", "inside"}:
            raise InvalidStateError("Heist roles are hacker, driver, and inside.")
        player = await self.bot.repo.get_player(member.guild.id, member.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need a Vice City profile first.")
        gang = await self.bot.repo.get_gang(player["gang_id"])
        if gang is None:
            raise InvalidStateError("You are not in a gang.")
        heist = await self.bot.repo.get_active_heist_for_gang(member.guild.id, gang["id"])
        if heist is None or heist["status"] != "planning":
            raise InvalidStateError("Your gang is not planning a heist right now.")
        if parse_datetime(heist["launch_deadline"]) and parse_datetime(heist["launch_deadline"]) <= utcnow():
            await self.cancel_heist(heist["id"], "Crew assembly timed out", notify_boss=True)
            raise InvalidStateError("That heist timed out before you could join.")
        field_name = f"{role_name}_id"
        if heist.get(field_name):
            raise InvalidStateError(f"The {role_name} slot is already taken.")

        await self.bot.repo.update_heist(heist["id"], **{field_name: member.id})
        channel = member.guild.get_channel(heist["planning_channel_id"])
        if isinstance(channel, discord.TextChannel):
            await channel.set_permissions(member, read_messages=True, send_messages=True)
            await channel.send(
                embed=self.bot.embed_factory.success(
                    "Crew Locked In",
                    f"{member.mention} claimed the **{role_name}** role.",
                )
            )
        return await self.bot.repo.get_heist(heist["id"])  # type: ignore[return-value]

    async def launch_heist(self, boss: discord.Member) -> dict:
        player = await self.bot.repo.get_player(boss.guild.id, boss.id)
        if player is None or player["rank"] != "Boss":
            raise InvalidStateError("Only a Boss can launch the Casino Job.")
        heist = await self.bot.repo.get_active_heist_for_gang(boss.guild.id, player["gang_id"])
        if heist is None or heist["status"] != "planning":
            raise InvalidStateError("There is no planning-phase heist to launch.")
        if heist["boss_user_id"] != boss.id:
            raise InvalidStateError("Only the Boss who planned this heist can launch it.")
        if not all(heist.get(field) for field in ("hacker_id", "driver_id", "inside_id")):
            raise InvalidStateError("All three crew roles must be filled before launch.")

        failed = await self._validate_heist_dms(
            boss.guild,
            [heist["hacker_id"], heist["driver_id"], heist["inside_id"]],
        )
        if failed:
            await self.cancel_heist(heist["id"], "Crew DM validation failed", notify_boss=False)
            raise HeistDMValidationError(failed)

        execution_deadline = utcnow() + timedelta(seconds=HEIST_EXECUTION_SECONDS)
        hacker_code = "".join(self.random.sample(string.ascii_uppercase + string.digits, 6))
        hacker_answer = hacker_code[::-1]
        correct_route = self.random.choice(["A", "B", "C"])
        inside_window_start = utcnow() + timedelta(seconds=self.random.randint(10, 35))
        inside_window_end = inside_window_start + timedelta(seconds=5)
        treasury_snapshot = (await self.bot.repo.ensure_guild_settings(boss.guild.id))["treasury_balance"]
        heist = await self.bot.repo.update_heist(
            heist["id"],
            status="executing",
            execution_deadline=isoformat(execution_deadline),
            hacker_prompt=f"CRACK THE VAULT: Unscramble this code -> {hacker_code}. Reply with the reversed code.",
            hacker_answer=hacker_answer,
            driver_prompt=(
                "CHOOSE YOUR ROUTE:\n"
                "Route A - Scanner shows 2 police units nearby\n"
                "Route B - Informant says all clear, but unconfirmed\n"
                "Route C - Unknown. No intel available.\n"
                "Reply with A, B, or C."
            ),
            driver_answer=correct_route,
            inside_prompt="DISABLE THE CAMERAS. Type !cut when the window opens. Too early or too late and the cameras stay on.",
            inside_window_start=isoformat(inside_window_start),
            inside_window_end=isoformat(inside_window_end),
            treasury_snapshot=treasury_snapshot,
        )
        await self._send_heist_prompts(boss.guild, heist, is_reminder=False)
        await self.cleanup_planning_channel(boss.guild, heist)
        try:
            self.bot.scheduler.remove_job(f"heist-plan:{heist['id']}")
        except JobLookupError:
            pass
        self.bot.scheduler.add_job(
            self.resolve_heist,
            "date",
            run_date=execution_deadline,
            id=f"heist-exec:{heist['id']}",
            replace_existing=True,
            kwargs={"heist_id": heist["id"]},
        )
        self._schedule_live_updates(heist["id"])
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            boss.guild.id,
            "Casino Job Live",
            f"The casino vault is under attack by **{(await self.bot.repo.get_gang(player['gang_id']))['name']}**.",
            "danger",
        )
        await self.broadcast_live_update(heist["id"], phase="launch")
        return heist

    async def capture_dm_response(self, message: discord.Message) -> bool:
        heist = await self.bot.repo.find_active_heist_for_member(message.author.id)
        if heist is None:
            return False
        role = None
        if heist.get("hacker_id") == message.author.id:
            role = "hacker"
        elif heist.get("driver_id") == message.author.id:
            role = "driver"
        elif heist.get("inside_id") == message.author.id:
            role = "inside"
        if role is None:
            return False

        response_field = f"{role}_response"
        if heist.get(response_field):
            await message.channel.send(
                embed=self.bot.embed_factory.danger("Response Locked", "That heist role has already answered.")
            )
            return True

        if role == "hacker":
            success = message.content.strip().upper() == (heist.get("hacker_answer") or "").upper()
        elif role == "driver":
            success = message.content.strip().upper()[:1] == (heist.get("driver_answer") or "").upper()
        else:
            inside_start = parse_datetime(heist.get("inside_window_start"))
            inside_end = parse_datetime(heist.get("inside_window_end"))
            now = utcnow()
            success = (
                message.content.strip().lower() == "!cut"
                and inside_start is not None
                and inside_end is not None
                and inside_start <= now <= inside_end
            )

        await self.bot.repo.update_heist(
            heist["id"],
            **{
                response_field: message.content.strip(),
                f"{role}_success": 1 if success else 0,
            },
        )
        await message.channel.send(
            embed=(
                self.bot.embed_factory.success("Task Logged", "Your heist response is locked in.")
                if success
                else self.bot.embed_factory.danger("Task Logged", "Your response was recorded, but it may not have been the right move.")
            )
        )
        return True

    async def resolve_heist(self, heist_id: int) -> None:
        try:
            self.bot.scheduler.remove_job(f"heist-exec:{heist_id}")
        except JobLookupError:
            pass
        heist = await self.bot.repo.get_heist(heist_id)
        if heist is None or heist["status"] not in {"executing", "ready"}:
            return
        guild = await self.bot.city_service.get_guild(heist["guild_id"])  # type: ignore[union-attr]
        successes = sum(int(heist.get(flag) or 0) for flag in ("hacker_success", "driver_success", "inside_success"))
        crew_ids = [heist["hacker_id"], heist["driver_id"], heist["inside_id"]]
        success_ids = []
        if int(heist.get("hacker_success") or 0):
            success_ids.append(heist["hacker_id"])
        if int(heist.get("driver_success") or 0):
            success_ids.append(heist["driver_id"])
        if int(heist.get("inside_success") or 0):
            success_ids.append(heist["inside_id"])

        if successes == 3:
            treasury = (await self.bot.repo.ensure_guild_settings(guild.id))["treasury_balance"]
            payout_total, _ = await self.bot.repo.debit_treasury(guild.id, max(1, treasury * 30 // 100), allow_partial=True)
            each = payout_total // 3 if payout_total else 0
            for user_id in crew_ids:
                await self.bot.repo.credit_wallet(guild.id, user_id, each)
                await self.bot.city_service.award_xp(guild.id, user_id, 750)  # type: ignore[union-attr]
                await self.bot.heat_service.apply_heat(guild.id, user_id, 4, reason="Casino Job success")  # type: ignore[union-attr]
            outcome_title = "Casino Job Cracked"
            outcome_description = f"All three crew members got out with **{payout_total}** from the treasury."
            color_kind = "reward"
        elif successes == 2:
            treasury = (await self.bot.repo.ensure_guild_settings(guild.id))["treasury_balance"]
            payout_total, _ = await self.bot.repo.debit_treasury(guild.id, max(1, treasury * 15 // 100), allow_partial=True)
            each = payout_total // len(success_ids) if success_ids else 0
            for user_id in success_ids:
                await self.bot.repo.credit_wallet(guild.id, user_id, each)
                await self.bot.city_service.award_xp(guild.id, user_id, 300)  # type: ignore[union-attr]
                await self.bot.heat_service.apply_heat(guild.id, user_id, 2, reason="Partial Casino Job")  # type: ignore[union-attr]
            outcome_title = "Casino Job Partial"
            outcome_description = f"Two crew members landed the job for **{payout_total}**."
            color_kind = "reward"
        else:
            payout_total = 0
            for user_id in crew_ids:
                await self.bot.heat_service.jail_player(guild.id, user_id, "Failed Casino Job", 2 * 60 * 60, announce=False)  # type: ignore[union-attr]
            outcome_title = "Casino Job Failed"
            outcome_description = "The crew botched the job and all three are headed to lockup for two hours."
            color_kind = "danger"

        await self.bot.repo.update_heist(
            heist_id,
            status="resolved" if successes >= 2 else "timed_out" if successes == 0 else "resolved",
            resolved_at=isoformat(utcnow()),
        )
        await self.cleanup_planning_channel(guild, heist)
        await self.bot.city_service.post_news(guild.id, outcome_title, outcome_description, color_kind)  # type: ignore[union-attr]
        crew_results = []
        for role_name in ("hacker", "driver", "inside"):
            member = guild.get_member(heist.get(f"{role_name}_id"))
            crew_results.append(
                (
                    role_name,
                    member.display_name if member else role_name.title(),
                    bool(heist.get(f"{role_name}_success")),
                )
            )
        gang = await self.bot.repo.get_gang(heist["gang_id"])
        narration = await self.bot.groq_service.generate_heist_narration(  # type: ignore[union-attr]
            phase="recap",
            gang_name=gang["name"] if gang else "Unknown Crew",
            crew_names=[result[1] for result in crew_results],
            success_count=successes,
            payout_total=payout_total,
        )
        recap_description = f"{outcome_description}\n\n" + "\n".join(f"\u2022 {line}" for line in narration.lines)
        card_embed = self.bot.embed_factory.reward(outcome_title, recap_description)
        card_file = None
        if self.bot.visual_service is not None:
            card_embed, card_file = await self.bot.visual_service.build_heist_result_card(
                guild_id=guild.id,
                heist=heist,
                outcome_title=outcome_title,
                outcome_description=recap_description,
                payout_total=payout_total,
                crew_results=crew_results,
            )
        channel = await self.bot.city_service.get_configured_channel(guild.id, "news_channel_id")  # type: ignore[union-attr]
        if channel is not None:
            if card_file is not None:
                await channel.send(embed=card_embed, file=card_file)
            else:
                await channel.send(embed=card_embed)
        for user_id in crew_ids:
            member = guild.get_member(user_id)
            if member:
                try:
                    if card_file is not None and self.bot.visual_service is not None:
                        dm_embed, dm_file = await self.bot.visual_service.build_heist_result_card(
                            guild_id=guild.id,
                            heist=heist,
                            outcome_title=outcome_title,
                            outcome_description=recap_description,
                            payout_total=payout_total,
                            crew_results=crew_results,
                        )
                        await member.send(embed=dm_embed, file=dm_file)
                    else:
                        await member.send(embed=self.bot.embed_factory.standard(outcome_title, recap_description))
                except discord.HTTPException:
                    pass

    async def handle_planning_timeout(self, heist_id: int) -> None:
        heist = await self.bot.repo.get_heist(heist_id)
        if heist is None or heist["status"] != "planning":
            return
        await self.cancel_heist(heist_id, "Planning timed out", notify_boss=True, status="timed_out")

    async def cancel_heist(self, heist_id: int, reason: str, *, notify_boss: bool, status: str = "cancelled") -> None:
        heist = await self.bot.repo.get_heist(heist_id)
        if heist is None:
            return
        guild = await self.bot.city_service.get_guild(heist["guild_id"])  # type: ignore[union-attr]
        await self.bot.repo.update_heist(heist_id, status=status, cancel_reason=reason, resolved_at=isoformat(utcnow()))
        await self.cleanup_planning_channel(guild, heist)
        if notify_boss:
            boss = guild.get_member(heist["boss_user_id"])
            if boss:
                try:
                    await boss.send(embed=self.bot.embed_factory.danger("Heist Cancelled", reason))
                except discord.HTTPException:
                    pass

    async def cleanup_planning_channel(self, guild: discord.Guild, heist: dict) -> None:
        channel = guild.get_channel(heist.get("planning_channel_id")) if heist.get("planning_channel_id") else None
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.delete(reason="Vice City heist cleanup")
            except discord.HTTPException:
                pass
        await self.bot.repo.update_heist(heist["id"], planning_channel_id=None)

    async def rehydrate_active_heists(self, guild_id: int) -> None:
        guild = await self.bot.city_service.get_guild(guild_id)  # type: ignore[union-attr]
        for heist in await self.bot.repo.list_active_heists(guild_id):
            if heist["status"] == "planning":
                await self.cancel_heist(heist["id"], "Bot restarted during planning.", notify_boss=True)
                continue
            if heist["status"] == "executing":
                await self.cleanup_planning_channel(guild, heist)
                execution_deadline = parse_datetime(heist.get("execution_deadline"))
                if execution_deadline and execution_deadline > utcnow():
                    await self._send_heist_prompts(guild, heist, is_reminder=True)
                    self._schedule_live_updates(heist["id"])
                    self.bot.scheduler.add_job(
                        self.resolve_heist,
                        "date",
                        run_date=execution_deadline,
                        id=f"heist-exec:{heist['id']}",
                        replace_existing=True,
                        kwargs={"heist_id": heist["id"]},
                    )
                else:
                    await self.resolve_heist(heist["id"])

    def _schedule_live_updates(self, heist_id: int) -> None:
        now = utcnow()
        for seconds_from_now, phase in ((15, "breach"), (35, "escape")):
            run_at = now + timedelta(seconds=seconds_from_now)
            self.bot.scheduler.add_job(
                self.broadcast_live_update,
                "date",
                run_date=run_at,
                id=f"heist-live:{heist_id}:{phase}",
                replace_existing=True,
                kwargs={"heist_id": heist_id, "phase": phase},
            )

    async def broadcast_live_update(self, heist_id: int, *, phase: str) -> None:
        heist = await self.bot.repo.get_heist(heist_id)
        if heist is None or heist["status"] != "executing":
            return
        guild = await self.bot.city_service.get_guild(heist["guild_id"])  # type: ignore[union-attr]
        gang = await self.bot.repo.get_gang(heist["gang_id"])
        names = []
        for role in ("hacker_id", "driver_id", "inside_id"):
            member = guild.get_member(heist.get(role))
            if member is not None:
                names.append(member.display_name)
        narration = await self.bot.groq_service.generate_heist_narration(  # type: ignore[union-attr]
            phase=phase,
            gang_name=gang["name"] if gang else "Unknown Crew",
            crew_names=names,
        )
        channel = await self.bot.city_service.get_configured_channel(guild.id, "news_channel_id")  # type: ignore[union-attr]
        if channel is None:
            return
        embed = self.bot.embed_factory.danger(narration.headline, "\n".join(f"\u2022 {line}" for line in narration.lines))
        file = None
        if self.bot.visual_service is not None:
            file = await self.bot.visual_service.build_event_banner("heist_live", subtitle=phase.title())
            if file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        await channel.send(embed=embed, file=file) if file is not None else await channel.send(embed=embed)

    async def _validate_heist_dms(self, guild: discord.Guild, user_ids: list[int]) -> list[int]:
        failed: list[int] = []
        for user_id in user_ids:
            member = guild.get_member(user_id)
            if member is None:
                failed.append(user_id)
                continue
            try:
                await member.send(
                    embed=self.bot.embed_factory.standard(
                        "Heist DM Check",
                        "Vice City OS is verifying that your DMs are open for the Casino Job.",
                    )
                )
            except discord.HTTPException:
                failed.append(user_id)
        return failed

    async def _send_heist_prompts(self, guild: discord.Guild, heist: dict, *, is_reminder: bool) -> None:
        roles = [
            ("hacker_id", heist.get("hacker_prompt")),
            ("driver_id", heist.get("driver_prompt")),
            ("inside_id", heist.get("inside_prompt")),
        ]
        reminder_prefix = "Reminder:\n" if is_reminder else ""
        for field_name, prompt in roles:
            member = guild.get_member(heist[field_name])
            if member is None:
                continue
            try:
                await member.send(embed=self.bot.embed_factory.standard("Casino Job", f"{reminder_prefix}{prompt}"))
            except discord.HTTPException:
                pass
