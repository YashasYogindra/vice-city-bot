from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from sinbot.services.fighting import FightAction, FightEngine, FightState, RoundOutcome
from sinbot.utils.checks import require_joined_player
from sinbot.views.action_hub import QuickActionsView

if TYPE_CHECKING:
    from sinbot.bot import SinBot

from sinbot import gifs


class FightActionView(discord.ui.View):
    """Interactive buttons for a fight round."""

    def __init__(self, fighter_id: int, *, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)
        self.fighter_id = fighter_id
        self.chosen_action: FightAction | None = None
        self.event = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.fighter_id:
            await interaction.response.send_message("This isn't your fight!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Punch", emoji="👊", style=discord.ButtonStyle.danger)
    async def punch(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.chosen_action = FightAction.PUNCH
        await interaction.response.defer()
        self.event.set()

    @discord.ui.button(label="Kick", emoji="🦶", style=discord.ButtonStyle.danger)
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.chosen_action = FightAction.KICK
        await interaction.response.defer()
        self.event.set()

    @discord.ui.button(label="Defend", emoji="🛡️", style=discord.ButtonStyle.primary)
    async def defend(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.chosen_action = FightAction.DEFEND
        await interaction.response.defer()
        self.event.set()

    @discord.ui.button(label="Reload", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def reload(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.chosen_action = FightAction.RELOAD
        await interaction.response.defer()
        self.event.set()


class FightChallengeView(discord.ui.View):
    """Accept/decline a fight challenge."""

    def __init__(self, challenger_id: int, target_id: int, *, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.accepted: bool | None = None
        self.event = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", emoji="⚔️", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.accepted = True
        await interaction.response.defer()
        self.event.set()

    @discord.ui.button(label="Decline", emoji="❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.accepted = False
        await interaction.response.defer()
        self.event.set()


class FightingCog(commands.Cog):
    def __init__(self, bot: "SinBot") -> None:
        self.bot = bot
        self.engine = FightEngine()
        self.active_fights: set[int] = set()  # user IDs currently in a fight

    @classmethod
    async def create(cls, bot: "SinBot") -> "FightingCog":
        return cls(bot)

    async def cog_load(self) -> None:
        return None

    @commands.hybrid_command(name="fight")
    @require_joined_player()
    async def fight(self, ctx: commands.Context, opponent: discord.Member, wager: int = 0) -> None:
        """Challenge another player to a Dank Memer-style PvP fight."""
        if ctx.interaction is not None:
            await ctx.defer()
        if opponent.id == ctx.author.id:
            raise commands.CheckFailure("You can't fight yourself, champ.")
        if opponent.bot:
            raise commands.CheckFailure("Bots don't bleed.")
        if ctx.author.id in self.active_fights or opponent.id in self.active_fights:
            raise commands.CheckFailure("One of you is already in a fight!")

        # Validate both players
        p1 = await self.bot.repo.get_player(ctx.guild.id, ctx.author.id)  # type: ignore[union-attr]
        p2 = await self.bot.repo.get_player(ctx.guild.id, opponent.id)  # type: ignore[union-attr]
        if p1 is None or not p1["is_joined"] or p2 is None or not p2["is_joined"]:
            raise commands.CheckFailure("Both fighters need city profiles.")

        if wager > 0:
            if int(p1["wallet"]) < wager:
                raise commands.CheckFailure(f"You only have **{p1['wallet']}** Racks.")
            if int(p2["wallet"]) < wager:
                raise commands.CheckFailure(f"{opponent.mention} only has **{p2['wallet']}** Racks.")

        # Send challenge
        challenge_view = FightChallengeView(ctx.author.id, opponent.id)
        wager_text = f" for **{wager}** Racks" if wager > 0 else ""
        challenge_embed = self.bot.embed_factory.danger(
            "⚔️ Fight Challenge",
            f"{ctx.author.mention} challenges {opponent.mention} to a street fight{wager_text}!\n\n"
            f"**Rules:** Best of 5 rounds • 100 HP each\n"
            f"**Moves:** 👊 Punch > 🦶 Kick > 🛡️ Defend > 👊 Punch\n"
            f"🔄 Reload loses to everything BUT doubles next attack damage!",
        )
        if gifs.FIGHT_CHALLENGE:
            challenge_embed.set_image(url=gifs.FIGHT_CHALLENGE)
        await ctx.send(embed=challenge_embed, view=challenge_view)
        await challenge_view.event.wait()

        if not challenge_view.accepted:
            await ctx.send(embed=self.bot.embed_factory.standard("Fight Declined", f"{opponent.mention} walked away."))
            return

        # Lock fighters
        self.active_fights.add(ctx.author.id)
        self.active_fights.add(opponent.id)
        try:
            state = self.engine.create_fight(ctx.author.id, opponent.id)
            await self._run_fight(ctx, state, ctx.author, opponent, wager)
        finally:
            self.active_fights.discard(ctx.author.id)
            self.active_fights.discard(opponent.id)

    async def _run_fight(
        self,
        ctx: commands.Context,
        state: FightState,
        p1: discord.Member,
        p2: discord.Member,
        wager: int,
    ) -> None:
        """Execute the fight loop round by round."""
        p1_vest_qty = await self.bot.repo.get_inventory_item(ctx.guild.id, p1.id, "vest")  # type: ignore[union-attr]
        p2_vest_qty = await self.bot.repo.get_inventory_item(ctx.guild.id, p2.id, "vest")  # type: ignore[union-attr]
        p1_vest_active = p1_vest_qty > 0
        p2_vest_active = p2_vest_qty > 0
        if p1_vest_active:
            await self.bot.repo.adjust_inventory(ctx.guild.id, p1.id, "vest", -1)  # type: ignore[union-attr]
        if p2_vest_active:
            await self.bot.repo.adjust_inventory(ctx.guild.id, p2.id, "vest", -1)  # type: ignore[union-attr]
        if p1_vest_active or p2_vest_active:
            armor_lines = []
            if p1_vest_active:
                armor_lines.append(f"{p1.mention} equipped a vest (first incoming hit gets absorbed).")
            if p2_vest_active:
                armor_lines.append(f"{p2.mention} equipped a vest (first incoming hit gets absorbed).")
            await ctx.send(embed=self.bot.embed_factory.standard("Armor Equipped", "\n".join(armor_lines)))

        while not state.is_over:
            round_num = state.rounds_played + 1
            # Create action views for both players
            p1_view = FightActionView(p1.id, timeout=30.0)
            p2_view = FightActionView(p2.id, timeout=30.0)

            round_embed = self.bot.embed_factory.standard(
                f"⚔️ Round {round_num}/{state.max_rounds}",
                f"{p1.mention} {self.engine.health_bar(state.p1_hp)}\n"
                f"{p2.mention} {self.engine.health_bar(state.p2_hp)}\n\n"
                f"**Choose your move!** (30 seconds)",
            )

            # Ask P1 to pick via DM
            try:
                p1_dm = await p1.create_dm()
                await p1_dm.send(embed=round_embed, view=p1_view)
            except discord.HTTPException:
                await ctx.send(embed=self.bot.embed_factory.danger("Fight Cancelled", f"{p1.mention} has DMs closed."))
                return
            try:
                p2_dm = await p2.create_dm()
                await p2_dm.send(embed=round_embed, view=p2_view)
            except discord.HTTPException:
                await ctx.send(embed=self.bot.embed_factory.danger("Fight Cancelled", f"{p2.mention} has DMs closed."))
                return

            # Wait for both to choose (30s timeout)
            done, pending = await asyncio.wait(
                [asyncio.create_task(p1_view.event.wait()), asyncio.create_task(p2_view.event.wait())],
                timeout=30.0,
                return_when=asyncio.ALL_COMPLETED,
            )
            for task in pending:
                task.cancel()

            # Default to defend if they didn't pick
            p1_action = p1_view.chosen_action or FightAction.DEFEND
            p2_action = p2_view.chosen_action or FightAction.DEFEND

            # Resolve round
            pre_p1_hp = state.p1_hp
            pre_p2_hp = state.p2_hp
            result = self.engine.resolve_round(state, p1_action, p2_action)

            armor_notes: list[str] = []
            if p1_vest_active and state.p1_hp < pre_p1_hp:
                absorbed = min(15, pre_p1_hp - state.p1_hp)
                state.p1_hp += absorbed
                result.p1_hp_after = state.p1_hp
                p1_vest_active = False
                armor_notes.append(f"🧥 {p1.display_name}'s vest absorbed {absorbed} damage.")
            if p2_vest_active and state.p2_hp < pre_p2_hp:
                absorbed = min(15, pre_p2_hp - state.p2_hp)
                state.p2_hp += absorbed
                result.p2_hp_after = state.p2_hp
                p2_vest_active = False
                armor_notes.append(f"🧥 {p2.display_name}'s vest absorbed {absorbed} damage.")

            # Build result embed
            outcome_line = ""
            if result.outcome == RoundOutcome.P1_WIN:
                outcome_line = f"💥 {p1.display_name} lands a hit! (-{result.p1_damage_dealt} HP)"
            elif result.outcome == RoundOutcome.P2_WIN:
                outcome_line = f"💥 {p2.display_name} lands a hit! (-{result.p2_damage_dealt} HP)"
            else:
                outcome_line = f"💫 Both fighters trade blows! (-{result.p1_damage_dealt} HP each)"

            result_embed = self.bot.embed_factory.standard(
                f"⚔️ Round {result.round_number} Result",
                f"{p1.display_name}: {p1_action.value.upper()} vs {p2.display_name}: {p2_action.value.upper()}\n\n"
                f"{outcome_line}\n"
                f"*{result.flavor_text}*\n\n"
                f"{p1.mention} {self.engine.health_bar(result.p1_hp_after)}\n"
                f"{p2.mention} {self.engine.health_bar(result.p2_hp_after)}",
            )
            if armor_notes:
                result_embed.add_field(name="Armor", value="\n".join(armor_notes), inline=False)
            if gifs.FIGHT_ROUND:
                result_embed.set_image(url=gifs.FIGHT_ROUND)
            await ctx.send(embed=result_embed)
            await asyncio.sleep(2)

        # Fight is over — determine winner
        winner_id = state.winner_id
        if winner_id is None:
            await ctx.send(embed=self.bot.embed_factory.standard("Fight Over — Draw!", "Neither fighter could finish the other. It's a draw!"))
            return

        winner = p1 if winner_id == p1.id else p2
        loser = p2 if winner_id == p1.id else p1
        winner_hp = state.p1_hp if winner_id == p1.id else state.p2_hp

        # Handle wager
        wager_text = ""
        if wager > 0:
            try:
                await self.bot.repo.debit_wallet(ctx.guild.id, loser.id, wager)  # type: ignore[union-attr]
                await self.bot.repo.credit_wallet(ctx.guild.id, winner.id, wager)  # type: ignore[union-attr]
                wager_text = f"\n💰 **{winner.display_name}** takes **{wager}** Racks from {loser.display_name}!"
            except Exception:
                wager_text = "\n💰 Wager payout failed (insufficient funds)."

        # Award XP
        await self.bot.city_service.award_xp(ctx.guild.id, winner.id, 50)  # type: ignore[union-attr]

        final_embed = self.bot.embed_factory.reward(
            "⚔️ Fight Over!",
            f"🏆 **{winner.display_name}** wins with {self.engine.health_bar(winner_hp)} remaining!\n"
            f"{wager_text}\n\n"
            f"**Round Summary:**\n"
            + "\n".join(
                f"R{r.round_number}: {r.p1_action.value} vs {r.p2_action.value} → "
                f"{'P1 Win' if r.outcome == RoundOutcome.P1_WIN else 'P2 Win' if r.outcome == RoundOutcome.P2_WIN else 'Draw'}"
                for r in state.history
            ),
        )
        if gifs.FIGHT_KNOCKOUT:
            final_embed.set_image(url=gifs.FIGHT_KNOCKOUT)
        await ctx.send(embed=final_embed, view=QuickActionsView(self.bot, ctx.author.id))

        # Post news
        await self.bot.city_service.post_news(  # type: ignore[union-attr]
            ctx.guild.id,  # type: ignore[union-attr]
            "Street Fight",
            f"{winner.mention} knocked out {loser.mention} in a {len(state.history)}-round brawl!"
            + (f" {wager} Racks changed hands." if wager > 0 else ""),
            "danger",
        )
