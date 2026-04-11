from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from vicecity.constants import (
    ARMS_DEAL_JAIL_SECONDS,
    ARMS_DEAL_TIMEOUT_SECONDS,
    DRUG_RUN_CONFIG,
    OPERATION_COOLDOWN_SECONDS,
)
from vicecity.exceptions import InvalidStateError
from vicecity.models.cinematic import ActionResult, BustNegotiationContext
from vicecity.utils.time import isoformat, utcnow
from vicecity.views.arms_deal import ArmsDealView

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class OperationsService:
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        self.random = random.Random()
        self.active_negotiations: set[str] = set()

    async def _raise_if_on_cooldown(self, guild_id: int, user_id: int) -> None:
        retry_after = await self.bot.city_service.operation_cooldown_retry_after(  # type: ignore[union-attr]
            guild_id,
            user_id,
            OPERATION_COOLDOWN_SECONDS,
        )
        if retry_after > 0:
            raise commands.CommandOnCooldown(commands.Cooldown(1, OPERATION_COOLDOWN_SECONDS), retry_after, commands.BucketType.user)

    async def _validate_operation_member(self, member: discord.Member) -> dict:
        player = await self.bot.repo.get_player(member.guild.id, member.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need to join Vice City first with !join.")
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
            operation_fee = 100 if int(player["heat"]) >= 3 else 0
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
                await self.bot.city_service.post_news(member.guild.id, "Street Operation", description, "success")  # type: ignore[union-attr]
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
        if requester_player["gang_id"] != teammate_player["gang_id"]:
            raise InvalidStateError("Arms deals only work with a teammate from your gang.")
        if requester_player["rank"] not in ("Lieutenant", "Capo", "Boss"):
            raise commands.MissingPermissions(["rank:Lieutenant"])
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
                    await self.bot.repo.credit_wallet(requester.guild.id, participant.id, 350)
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
                await self.bot.city_service.post_news(  # type: ignore[union-attr]
                    requester.guild.id,
                    "Arms Deal Cleared",
                    f"{requester.mention} and {teammate.mention} moved product without getting caught.",
                    "success",
                )
                return ActionResult(
                    embed=self.bot.embed_factory.success(
                        "Arms Deal Complete",
                        f"{requester.mention} and {teammate.mention} each earned **350**.",
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

    async def resolve_bust_negotiation(
        self,
        member: discord.Member,
        context: BustNegotiationContext,
        approach: str,
        plea_text: str,
    ) -> discord.Embed:
        if context.user_id != member.id or context.guild_id != member.guild.id:
            raise InvalidStateError("That negotiation does not belong to you.")
        if context.token not in self.active_negotiations:
            raise InvalidStateError("That negotiation already played out.")
        self.active_negotiations.remove(context.token)
        result = await self.bot.gemini_service.generate_bust_negotiation(  # type: ignore[union-attr]
            member_name=context.member_name,
            gang_name=context.gang_name,
            operation_name=context.operation_name,
            risk=context.risk,
            approach=approach,
            plea_text=plea_text,
            allowed_outcomes=context.allowed_outcomes,
        )
        summary: str
        if result.outcome == "reduced_fine":
            refund = min(context.fine_amount, max(50, context.fine_amount // 2))
            new_wallet = await self.bot.repo.credit_wallet(member.guild.id, member.id, refund)
            summary = f"The cops shaved the hit and refunded **{refund}** Racks. Wallet: **{new_wallet}**."
            embed = self.bot.embed_factory.reward(result.headline, f"{result.scene}\n\n> {result.officer_line}\n\n{summary}")
            await self.bot.city_service.post_news(  # type: ignore[union-attr]
                member.guild.id,
                "Backroom Deal",
                f"{member.mention} talked their way into a softer landing after a bust.",
                "reward",
            )
            return embed
        if result.outcome == "extra_heat":
            new_heat = await self.bot.heat_service.apply_heat(  # type: ignore[union-attr]
                member.guild.id,
                member.id,
                1,
                reason="Bust negotiation backfire",
            )
            summary = f"The room turned ugly. {member.mention} picked up **+1 Heat** and is now at **{new_heat}**."
            return self.bot.embed_factory.danger(result.headline, f"{result.scene}\n\n> {result.officer_line}\n\n{summary}")
        summary = "The desk stays cold. The original bust stands exactly as written."
        return self.bot.embed_factory.danger(result.headline, f"{result.scene}\n\n> {result.officer_line}\n\n{summary}")
