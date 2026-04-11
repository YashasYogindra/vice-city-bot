from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING

import discord

from vicecity.exceptions import InvalidStateError
from vicecity.models.game import BlackjackSession
from vicecity.views.arms_deal import ArmsDealView
from vicecity.views.blackjack import BlackjackView

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class CasinoService:
    SLOT_SYMBOLS = ["\U0001F352", "\U0001F514", "\U0001F48E", "7\ufe0f\u20e3", "\U0001F3B0", "\U0001F480"]
    CARD_SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]
    CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        self.random = random.Random()
        self.blackjack_sessions: dict[str, BlackjackSession] = {}

    async def _validate_player(self, member: discord.Member) -> dict:
        player = await self.bot.repo.get_player(member.guild.id, member.id)
        if player is None or not player["is_joined"]:
            raise InvalidStateError("You need to join Vice City before hitting the casino.")
        if await self.bot.city_service.member_is_jailed(member.guild.id, member.id):  # type: ignore[union-attr]
            raise InvalidStateError("The casino will not seat someone who is currently jailed.")
        return player

    async def play_slots(self, member: discord.Member, bet: int) -> discord.Embed:
        await self._validate_player(member)
        if bet <= 0:
            raise InvalidStateError("Your bet has to be greater than zero.")
        await self.bot.repo.debit_wallet(member.guild.id, member.id, bet)
        event_effect = await self.bot.event_service.get_active_effect(member.guild.id)  # type: ignore[union-attr]
        reels = [self.random.choice(self.SLOT_SYMBOLS) for _ in range(3)]
        result = " | ".join(reels)
        if "\U0001F480" in reels:
            balance_after = (await self.bot.repo.get_player(member.guild.id, member.id))["wallet"]
            extra_loss = min(int(balance_after), bet)
            if extra_loss:
                await self.bot.repo.debit_wallet(member.guild.id, member.id, extra_loss)
            embed = self.bot.embed_factory.danger(
                "Slots",
                f"```text\n{result}\n```\nA skull hit the reels and the house squeezed harder.",
            )
            embed.add_field(name="Damage", value=f"Lost **{bet + extra_loss}**", inline=True)
            embed.add_field(name="Read", value="Never chase a dead reel.", inline=True)
        elif len(set(reels)) == 1:
            payout = self.bot.event_service.apply_casino_payout_effect(bet * 10, event_effect)  # type: ignore[union-attr]
            await self.bot.repo.credit_wallet(member.guild.id, member.id, payout)
            embed = self.bot.embed_factory.reward(
                "Slots",
                f"```text\n{result}\n```\nAll three reels snapped into line.",
            )
            embed.add_field(name="Jackpot", value=f"Won **{payout}**", inline=True)
            embed.add_field(name="Street Read", value="Walk away before the machine remembers your name.", inline=True)
        elif len(set(reels)) == 2:
            payout = self.bot.event_service.apply_casino_payout_effect(bet * 2, event_effect)  # type: ignore[union-attr]
            await self.bot.repo.credit_wallet(member.guild.id, member.id, payout)
            embed = self.bot.embed_factory.reward(
                "Slots",
                f"```text\n{result}\n```\nTwo reels linked up and kicked back a fast payout.",
            )
            embed.add_field(name="Take", value=f"Won **{payout}**", inline=True)
            embed.add_field(name="Street Read", value="Decent hit. The house still thinks it owns you.", inline=True)
        else:
            embed = self.bot.embed_factory.danger(
                "Slots",
                f"```text\n{result}\n```\nThe reels smiled and kept every Rack you fed them.",
            )
            embed.add_field(name="Damage", value=f"Lost **{bet}**", inline=True)
            embed.add_field(name="Street Read", value="Cold machine. Bad room. Move tables.", inline=True)
        return embed

    async def flip_house(self, member: discord.Member, bet: int, choice: str) -> discord.Embed:
        await self._validate_player(member)
        if bet <= 0:
            raise InvalidStateError("Your bet has to be greater than zero.")
        choice = choice.lower()
        if choice not in {"heads", "tails"}:
            raise InvalidStateError("Pick either heads or tails.")
        await self.bot.repo.debit_wallet(member.guild.id, member.id, bet)
        result = self.random.choice(["heads", "tails"])
        if result == choice:
            event_effect = await self.bot.event_service.get_active_effect(member.guild.id)  # type: ignore[union-attr]
            payout = self.bot.event_service.apply_casino_payout_effect(bet * 2, event_effect)  # type: ignore[union-attr]
            await self.bot.repo.credit_wallet(member.guild.id, member.id, payout)
            return self.bot.embed_factory.reward("Coin Flip", f"It landed on **{result}**. You won **{payout}**.")
        return self.bot.embed_factory.danger("Coin Flip", f"It landed on **{result}**. You lost **{bet}**.")

    async def flip_challenge(
        self,
        requester: discord.Member,
        opponent: discord.Member,
        bet: int,
        channel: discord.abc.Messageable,
    ) -> discord.Embed:
        await self._validate_player(requester)
        await self._validate_player(opponent)
        if requester.id == opponent.id:
            raise InvalidStateError("You need someone else for a challenge flip.")
        invite = ArmsDealView(self.bot, requester.id, opponent.id, timeout=120)
        message = await channel.send(
            embed=self.bot.embed_factory.standard(
                "Coin Flip Challenge",
                f"{opponent.mention}, {requester.mention} challenged you for **{bet}**.",
            ),
            view=invite,
        )
        invite.message = message
        await invite.event.wait()
        if invite.accepted is not True:
            return self.bot.embed_factory.standard("Challenge Closed", "The challenge was declined or expired.")

        await self.bot.repo.debit_wallet(requester.guild.id, requester.id, bet)
        await self.bot.repo.debit_wallet(requester.guild.id, opponent.id, bet)
        winner = self.random.choice([requester, opponent])
        await self.bot.repo.credit_wallet(requester.guild.id, winner.id, bet * 2)
        return self.bot.embed_factory.reward(
            "Challenge Flip",
            f"{winner.mention} won the flip and walked away with **{bet * 2}**.",
        )

    async def start_blackjack(self, member: discord.Member, bet: int, channel: discord.TextChannel) -> discord.Message:
        await self._validate_player(member)
        if bet <= 0:
            raise InvalidStateError("Your bet has to be greater than zero.")
        await self.bot.repo.debit_wallet(member.guild.id, member.id, bet)
        deck = [f"{rank}{suit}" for suit in self.CARD_SUITS for rank in self.CARD_RANKS]
        self.random.shuffle(deck)
        session_id = uuid.uuid4().hex
        session = BlackjackSession(
            guild_id=member.guild.id,
            user_id=member.id,
            channel_id=channel.id,
            bet=bet,
            deck=deck,
            player_hand=[deck.pop(), deck.pop()],
            dealer_hand=[deck.pop(), deck.pop()],
        )
        self.blackjack_sessions[session_id] = session
        view = BlackjackView(self, member.id, session_id, timeout=60)
        embed = self._build_blackjack_embed(session, reveal_dealer=False)
        message = await channel.send(embed=embed, view=view)
        view.message = message
        session.message_id = message.id
        if self._is_blackjack(session.player_hand) or self._is_blackjack(session.dealer_hand):
            await self._finalize_blackjack(session_id, view=view)
        return message

    async def handle_blackjack_action(
        self,
        session_id: str,
        interaction: discord.Interaction,
        action: str,
        view: BlackjackView,
    ) -> None:
        session = self.blackjack_sessions.get(session_id)
        if session is None or session.resolved:
            await interaction.response.send_message(
                embed=self.bot.embed_factory.danger("Hand Closed", "That blackjack hand has already been resolved."),
                ephemeral=True,
            )
            return
        if action == "hit":
            session.player_hand.append(session.deck.pop())
            if self._score(session.player_hand) > 21:
                await self._finalize_blackjack(session_id, interaction=interaction, view=view)
                return
            await interaction.response.edit_message(embed=self._build_blackjack_embed(session, reveal_dealer=False), view=view)
            return
        await self._finalize_blackjack(session_id, interaction=interaction, view=view)

    async def auto_stand_blackjack(self, session_id: str, view: BlackjackView) -> None:
        session = self.blackjack_sessions.get(session_id)
        if session is None or session.resolved:
            return
        await self._finalize_blackjack(session_id, view=view, timed_out=True)

    async def _finalize_blackjack(
        self,
        session_id: str,
        *,
        interaction: discord.Interaction | None = None,
        view: BlackjackView | None = None,
        timed_out: bool = False,
    ) -> None:
        session = self.blackjack_sessions.get(session_id)
        if session is None or session.resolved:
            return
        session.resolved = True
        while self._score(session.dealer_hand) < 17:
            session.dealer_hand.append(session.deck.pop())

        player_score = self._score(session.player_hand)
        dealer_score = self._score(session.dealer_hand)
        guild = self.bot.get_guild(session.guild_id)
        if guild is None:
            self.blackjack_sessions.pop(session_id, None)
            return
        if player_score > 21:
            title = "Blackjack Loss"
            description = "You busted and lost your bet."
            color = self.bot.embed_factory.danger
        elif self._is_blackjack(session.player_hand) and not self._is_blackjack(session.dealer_hand):
            payout = int(session.bet * 2.5)
            await self.bot.repo.credit_wallet(guild.id, session.user_id, payout)
            title = "Blackjack"
            description = f"Natural blackjack. You won **{payout}**."
            color = self.bot.embed_factory.reward
        elif dealer_score > 21 or player_score > dealer_score:
            payout = session.bet * 2
            await self.bot.repo.credit_wallet(guild.id, session.user_id, payout)
            title = "Blackjack Win"
            description = f"You beat the dealer and won **{payout}**."
            color = self.bot.embed_factory.reward
        elif player_score == dealer_score:
            await self.bot.repo.credit_wallet(guild.id, session.user_id, session.bet)
            title = "Push"
            description = "The dealer matched you. Your bet was returned."
            color = self.bot.embed_factory.standard
        else:
            title = "Blackjack Loss"
            description = "The dealer held the better hand."
            color = self.bot.embed_factory.danger

        if timed_out:
            description = f"{description}\nYou took too long, so the bot auto-stood your hand."
        embed = color(title, description)
        result_embed = self._build_blackjack_embed(session, reveal_dealer=True)
        result_embed.title = embed.title
        result_embed.description = f"{embed.description}\n\n{result_embed.description}"
        if view:
            view.disable_all()
        if interaction:
            await interaction.response.edit_message(embed=result_embed, view=view)
        elif view and view.message:
            await view.message.edit(embed=result_embed, view=view)
        self.blackjack_sessions.pop(session_id, None)

    def _score(self, hand: list[str]) -> int:
        total = 0
        aces = 0
        for card in hand:
            rank = card[:-1]
            if rank == "A":
                aces += 1
                total += 11
            elif rank in {"J", "Q", "K"}:
                total += 10
            else:
                total += int(rank)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def _is_blackjack(self, hand: list[str]) -> bool:
        return len(hand) == 2 and self._score(hand) == 21

    def _build_blackjack_embed(self, session: BlackjackSession, *, reveal_dealer: bool) -> discord.Embed:
        dealer_hand = " | ".join(session.dealer_hand if reveal_dealer else [session.dealer_hand[0], "??"])
        player_hand = " | ".join(session.player_hand)
        embed = self.bot.embed_factory.standard("Blackjack", "Read the table, then hit or stand.")
        embed.add_field(
            name="Dealer",
            value=f"```text\n{dealer_hand}\n```\nScore: **{'?' if not reveal_dealer else self._score(session.dealer_hand)}**",
            inline=True,
        )
        embed.add_field(
            name="Player",
            value=f"```text\n{player_hand}\n```\nScore: **{self._score(session.player_hand)}**",
            inline=True,
        )
        embed.add_field(name="Bet", value=f"**{session.bet}**", inline=False)
        return embed
