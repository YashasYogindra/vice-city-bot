from __future__ import annotations

import asyncio
import random
import uuid
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from sinbot import gifs
from sinbot.constants import (
    ARMS_DEAL_JAIL_SECONDS,
    ARMS_DEAL_PAYOUT,
    ARMS_DEAL_TIMEOUT_SECONDS,
    CAPO_COOLDOWN_REDUCTION,
    DRUG_RUN_CONFIG,
    OPERATION_COOLDOWN_SECONDS,
    OPERATION_FEE_HIGH_HEAT,
)
from sinbot.exceptions import InvalidStateError
from sinbot.models.cinematic import ActionResult, BustNegotiationContext
from sinbot.services.interrogation import calculate_interrogation_score
from sinbot.utils.time import isoformat, utcnow
from sinbot.views.arms_deal import ArmsDealView

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class OperationsService:
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot
        self.random = random.Random()
        self.active_negotiations: set[str] = set()
        self._background_tasks: set[asyncio.Task[None]] = set()

    def _track_background_task(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.add(task)

        def _done(done_task: asyncio.Task[None]) -> None:
            self._background_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                return
            except Exception:
                self.bot.logger.exception("Bust interrogation task crashed")

        task.add_done_callback(_done)

    async def _raise_if_on_cooldown(self, guild_id: int, user_id: int) -> None:
        if self.bot.config.disable_cooldowns or OPERATION_COOLDOWN_SECONDS <= 0:
            return
        # Capo/Boss get reduced cooldown
        player = await self.bot.repo.get_player(guild_id, user_id)
        cooldown = OPERATION_COOLDOWN_SECONDS
        if player and player["rank"] in ("Capo", "Boss"):
            cooldown = int(cooldown * CAPO_COOLDOWN_REDUCTION)
        retry_after = await self.bot.city_service.operation_cooldown_retry_after(  # type: ignore[union-attr]
            guild_id,
            user_id,
            cooldown,
        )
        if retry_after > 0:
            raise commands.CommandOnCooldown(commands.Cooldown(1, cooldown), retry_after, commands.BucketType.user)

    async def _validate_operation_member(self, member: discord.Member) -> dict:
        player = await self.bot.repo.get_player(member.guild.id, member.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need to join the city first with /join.")
        if await self.bot.city_service.member_is_jailed(member.guild.id, member.id):  # type: ignore[union-attr]
            raise InvalidStateError("You cannot do that while jailed.")
        return player

    async def run_drug_operation(self, member: discord.Member, risk: str) -> ActionResult:
        risk = risk.lower()
        if risk not in DRUG_RUN_CONFIG:
            raise InvalidStateError("Risk must be low, medium, or high.")

        async with self.bot.member_locks.acquire(member.id):
            player = await self._validate_operation_member(member)
            await self._raise_if_on_cooldown(member.guild.id, member.id)
            config = DRUG_RUN_CONFIG[risk]
            heat_penalty = max(0, int(player["heat"]) - 1) * 5
            adjusted_success = max(10, config["success_rate"] - heat_penalty)
            operation_fee = OPERATION_FEE_HIGH_HEAT if int(player["heat"]) >= 3 else 0
            if operation_fee:
                await self.bot.repo.debit_wallet(member.guild.id, member.id, operation_fee)

            burnerphones = await self.bot.repo.get_inventory_item(member.guild.id, member.id, "burnerphone")
            anonymous = False
            if burnerphones > 0:
                await self.bot.repo.adjust_inventory(member.guild.id, member.id, "burnerphone", -1)
                anonymous = True

            # Apply active city event effects
            event_effect = await self.bot.event_service.get_active_effect(member.guild.id)  # type: ignore[union-attr]
            adjusted_success = self.bot.event_service.apply_operation_success_effect(adjusted_success, event_effect)  # type: ignore[union-attr]
            event_payout = self.bot.event_service.apply_operation_payout_effect(config["payout"], event_effect)  # type: ignore[union-attr]

            success = self.random.randint(1, 100) <= adjusted_success
            crackdown_bonus = 0 if anonymous else await self.bot.heat_service.get_crackdown_bonus(member.guild.id)  # type: ignore[union-attr]
            if success:
                new_balance = await self.bot.repo.credit_wallet(member.guild.id, member.id, event_payout)
                new_heat = int(player["heat"])
                heat_gain = config["heat_success"] + crackdown_bonus
                heat_gain = self.bot.event_service.apply_operation_heat_effect(heat_gain, event_effect)  # type: ignore[union-attr]
                if not anonymous:
                    new_heat = await self.bot.heat_service.apply_heat(  # type: ignore[union-attr]
                        member.guild.id,
                        member.id,
                        heat_gain,
                        reason=f"Drug run ({risk})",
                    )
                description = (
                    f"{member.mention if not anonymous else 'An anonymous runner'} pulled off a **{risk}** drug run.\n"
                    f"Wallet: **{new_balance}**\n"
                    f"Heat: **{new_heat}**"
                )
                embed = self.bot.embed_factory.success("Operation Successful", description)
                await self.bot.city_service.adjust_violence(member.guild.id, 1)  # type: ignore[union-attr]
                await self.bot.city_service.post_news(member.guild.id, "Street Operation", description, "success")  # type: ignore[union-attr]
                await self.bot.repo.update_player(member.guild.id, member.id, operations_success=int(player.get("operations_success", 0)) + 1)
                result = ActionResult(embed=embed, media_key="drug_success")
            else:
                refreshed = await self.bot.repo.get_player(member.guild.id, member.id)
                current_wallet = int(refreshed["wallet"])
                penalty = min(400, max(50, int(current_wallet * 0.15)))
                try:
                    new_balance = await self.bot.repo.debit_wallet(member.guild.id, member.id, penalty)
                except Exception:
                    new_balance = current_wallet
                new_heat = int(player["heat"])
                if not anonymous:
                    heat_gain = self.bot.event_service.apply_operation_heat_effect(  # type: ignore[union-attr]
                        config["heat_fail"] + crackdown_bonus,
                        event_effect,
                    )
                    new_heat = await self.bot.heat_service.apply_heat(  # type: ignore[union-attr]
                        member.guild.id,
                        member.id,
                        heat_gain,
                        reason=f"Failed drug run ({risk})",
                    )
                description = (
                    f"{member.mention if not anonymous else 'An anonymous runner'} got pinched on a **{risk}** drug run.\n"
                    f"Wallet: **{new_balance}**\n"
                    f"Heat: **{new_heat}**"
                )
                embed = self.bot.embed_factory.danger("Operation Failed", description)
                await self.bot.repo.update_player(member.guild.id, member.id, operations_failed=int(player.get("operations_failed", 0)) + 1)
                await self.bot.city_service.post_news(member.guild.id, "Bust", description, "danger")  # type: ignore[union-attr]
                token = uuid.uuid4().hex
                self.active_negotiations.add(token)
                gang_name = "Independent"
                if player.get("gang_id"):
                    gang = await self.bot.repo.get_gang(player["gang_id"])
                    if gang is not None:
                        gang_name = gang["name"]
                context = BustNegotiationContext(
                    token=token,
                    guild_id=member.guild.id,
                    user_id=member.id,
                    member_name=member.display_name,
                    gang_name=gang_name,
                    operation_name="drug run",
                    risk=risk,
                    fine_amount=penalty,
                    heat_after_bust=new_heat,
                    allowed_outcomes=("reduced_fine", "extra_heat", "deal_rejected"),
                )
                result = ActionResult(embed=embed, media_key="drug_bust", bust_context=context)

            await self.bot.repo.update_player(member.guild.id, member.id, last_operation_at=isoformat(utcnow()))
            return result

    async def run_arms_deal(self, requester: discord.Member, teammate: discord.Member, channel: discord.abc.Messageable) -> ActionResult:
        if requester.id == teammate.id:
            raise InvalidStateError("You need a second crew member for an arms deal.")
        requester_player = await self._validate_operation_member(requester)
        teammate_player = await self._validate_operation_member(teammate)
        if requester_player["rank"] not in ("Soldier", "Boss"):
            raise commands.MissingPermissions(["rank:Soldier"])
        await self._raise_if_on_cooldown(requester.guild.id, requester.id)
        await self._raise_if_on_cooldown(requester.guild.id, teammate.id)

        async with self.bot.member_locks.acquire_many([requester.id, teammate.id]):
            view = ArmsDealView(self.bot, requester.id, teammate.id, timeout=ARMS_DEAL_TIMEOUT_SECONDS)
            invite = self.bot.embed_factory.standard(
                "Arms Deal Invite",
                f"{teammate.mention}, {requester.mention} wants to run an arms deal with you.",
            )
            message = await channel.send(embed=invite, view=view)
            view.message = message
            await view.event.wait()
            if view.accepted is not True:
                return ActionResult(
                    embed=self.bot.embed_factory.danger("Deal Fell Through", "The arms deal never got off the ground."),
                    media_key="arms_bust",
                )

            success = self.random.randint(1, 100) <= 65
            crack_bonus = await self.bot.heat_service.get_crackdown_bonus(requester.guild.id)  # type: ignore[union-attr]
            participants = (requester, teammate)
            if success:
                for participant in participants:
                    await self.bot.repo.credit_wallet(requester.guild.id, participant.id, ARMS_DEAL_PAYOUT)
                    burnerphones = await self.bot.repo.get_inventory_item(requester.guild.id, participant.id, "burnerphone")
                    if burnerphones > 0:
                        await self.bot.repo.adjust_inventory(requester.guild.id, participant.id, "burnerphone", -1)
                    else:
                        await self.bot.heat_service.apply_heat(  # type: ignore[union-attr]
                            requester.guild.id,
                            participant.id,
                            2 + crack_bonus,
                            reason="Arms deal",
                        )
                    await self.bot.repo.update_player(requester.guild.id, participant.id, last_operation_at=isoformat(utcnow()))
                await self.bot.city_service.adjust_violence(requester.guild.id, 2)  # type: ignore[union-attr]
                await self.bot.city_service.post_news(  # type: ignore[union-attr]
                    requester.guild.id,
                    "Arms Deal Cleared",
                    f"{requester.mention} and {teammate.mention} moved product without getting caught.",
                    "success",
                )
                return ActionResult(
                    embed=self.bot.embed_factory.success(
                        "Arms Deal Complete",
                        f"{requester.mention} and {teammate.mention} each earned **{ARMS_DEAL_PAYOUT}**.",
                    ),
                    media_key="arms_success",
                )

            for participant in participants:
                await self.bot.repo.update_player(requester.guild.id, participant.id, last_operation_at=isoformat(utcnow()))
                await self.bot.heat_service.jail_player(  # type: ignore[union-attr]
                    requester.guild.id,
                    participant.id,
                    "Arms deal interception",
                    ARMS_DEAL_JAIL_SECONDS,
                    announce=False,
                )
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                requester.guild.id,
                "Arms Deal Intercepted",
                f"{requester.mention} and {teammate.mention} were picked up in a weapons sting.",
                "danger",
            )
            return ActionResult(
                embed=self.bot.embed_factory.danger(
                    "Arms Deal Failed",
                    f"{requester.mention} and {teammate.mention} were jailed for one hour.",
                ),
                media_key="arms_bust",
            )

    async def start_bust_interrogation(
        self,
        member: discord.Member,
        context: BustNegotiationContext,
        approach: str,
    ) -> tuple[bool, str]:
        if context.user_id != member.id or context.guild_id != member.guild.id:
            return False, "context_mismatch"
        if context.token not in self.active_negotiations:
            return False, "expired"
        try:
            dm_channel = await member.create_dm()
            embed = self.bot.embed_factory.danger(
                "Interrogation Room",
                f"The cops slide a stale coffee across the metal table. \"Start talking.\"\n\n"
                f"You chose to **{approach.upper()}**. You have 3 chances to make your case.\n"
                f"*Type your response below (you have 60 seconds per response).* "
            )
            if gifs.INTERROGATION:
                embed.set_image(url=gifs.INTERROGATION)
            await dm_channel.send(embed=embed)
        except discord.HTTPException:
            # User has DMs closed
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                member.guild.id,
                "Silent Treatment",
                f"{member.mention} refused to speak and accepted their full bust penalty.",
                "danger",
            )
            return False, "dm_closed"
        except Exception:
            self.bot.logger.exception("Failed to start bust interrogation DM")
            return False, "error"

        # Only consume the negotiation token after the opening DM is delivered.
        self.active_negotiations.discard(context.token)
        task = asyncio.create_task(self._run_bust_interrogation(member, context, approach, dm_channel))
        self._track_background_task(task)
        return True, "started"

    async def _run_bust_interrogation(
        self,
        member: discord.Member,
        context: BustNegotiationContext,
        approach: str,
        dm_channel: discord.DMChannel,
    ) -> None:
        try:
            chat_history = ""
            turns = 0
            max_turns = 3

            while turns < max_turns:
                try:
                    msg = await self.bot.wait_for(
                        "message",
                        check=lambda m: m.author.id == member.id and m.channel.id == dm_channel.id,
                        timeout=60.0,
                    )
                except discord.TimeoutError:
                    await dm_channel.send(
                        embed=self.bot.embed_factory.danger(
                            "Time's Up",
                            "The cops got tired of waiting and threw you in a cell. Standard bust applied.",
                        )
                    )
                    return

                turns += 1
                chat_history += f"Suspect: {msg.content}\n"
                is_final = turns == max_turns

                result = await self.bot.groq_service.generate_interrogation_turn(  # type: ignore[union-attr]
                    member_name=context.member_name,
                    gang_name=context.gang_name,
                    approach=approach,
                    chat_history=chat_history,
                    is_final=is_final,
                )

                chat_history += f"Officer: {result['officer_line']}\n"

                if not is_final:
                    await dm_channel.send(f"**Officer:** *\"{result['officer_line']}\"*")
                    continue

                # Deterministic scoring instead of AI-decided outcome
                player = await self.bot.repo.get_player(context.guild_id, context.user_id)
                quality_bonus = max(0, min(20, int(result.get("quality_score", 0))))
                score = calculate_interrogation_score(
                    approach=approach,
                    heat=int(player["heat"]) if player else context.heat_after_bust,
                    rank=str(player["rank"]) if player else "Street Rat",
                    quality_bonus=quality_bonus,
                    rng=self.random,
                )
                outcome = score.outcome
                summary = ""
                if outcome == "reduced_fine":
                    refund = min(context.fine_amount, max(50, context.fine_amount // 2))
                    new_wallet = await self.bot.repo.credit_wallet(member.guild.id, member.id, refund)
                    summary = f"The block bought your story. Refunded **{refund}** Racks. Wallet: **{new_wallet}**."
                    embed = self.bot.embed_factory.reward("Deal Struck", f"**Officer:** *\"{result['officer_line']}\"*\n\n{summary}")
                    await self.bot.city_service.post_news(  # type: ignore[union-attr]
                        member.guild.id,
                        "Backroom Deal",
                        f"{member.mention} talked their way into a softer landing.",
                        "reward",
                        image_url=gifs.INTERROGATION,
                    )
                elif outcome == "extra_heat":
                    new_heat = await self.bot.heat_service.apply_heat(member.guild.id, member.id, 1, reason="Interrogation failure")  # type: ignore[union-attr]
                    summary = f"You pushed too hard. **+1 Heat** applied. Current Heat: **{new_heat}**."
                    embed = self.bot.embed_factory.danger("Deal Rejected", f"**Officer:** *\"{result['officer_line']}\"*\n\n{summary}")
                else:
                    summary = "Your words fell on deaf ears. Original bust penalties stand."
                    embed = self.bot.embed_factory.danger("Deal Rejected", f"**Officer:** *\"{result['officer_line']}\"*\n\n{summary}")

                if gifs.INTERROGATION:
                    embed.set_image(url=gifs.INTERROGATION)
                await dm_channel.send(embed=embed)
                return
        except Exception:
            self.bot.logger.exception("Interrogation dialogue failed")
            try:
                await dm_channel.send(
                    embed=self.bot.embed_factory.danger(
                        "Interrogation Error",
                        "The interrogation scene glitched out. Your current bust penalties remain unchanged.",
                    )
                )
            except discord.HTTPException:
                pass
