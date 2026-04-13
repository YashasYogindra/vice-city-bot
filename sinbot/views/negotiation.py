from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from sinbot.exceptions import SinBotError
from sinbot.models.cinematic import BustNegotiationContext
from sinbot.views.action_hub import QuickActionsView, send_interaction_message

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class BustNegotiationModal(discord.ui.Modal):
    def __init__(
        self,
        bot: "SinBot",
        owner_id: int,
        context: BustNegotiationContext,
        approach: str,
    ) -> None:
        super().__init__(title=f"{approach.title()} Your Way Out")
        self.bot = bot
        self.owner_id = owner_id
        self.context = context
        self.approach = approach
        self.pitch = discord.ui.TextInput(
            label="Make your case",
            style=discord.TextStyle.paragraph,
            max_length=240,
            placeholder="Give the cops your smoothest Vice City speech...",
        )
        self.add_item(self.pitch)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await send_interaction_message(
                interaction,
                embed=self.bot.embed_factory.danger("Not Your Bust", "Only the busted player can negotiate this scene."),
                ephemeral=True,
            )
            return
        if not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer()
        embed = await self.bot.operations_service.resolve_bust_negotiation(  # type: ignore[union-attr]
            interaction.user,
            self.context,
            self.approach,
            self.pitch.value or "",
        )
        await interaction.followup.send(embed=embed, view=QuickActionsView(self.bot, interaction.user.id))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if isinstance(error, SinBotError):
            await send_interaction_message(
                interaction,
                embed=self.bot.embed_factory.danger("Negotiation Failed", str(error)),
                ephemeral=True,
            )
            return
        self.bot.logger.exception("Negotiation modal error", exc_info=error)
        await send_interaction_message(
            interaction,
            embed=self.bot.embed_factory.danger("Negotiation Failed", "Something went wrong in that scene."),
            ephemeral=True,
        )


class BustNegotiationView(discord.ui.View):
    def __init__(self, bot: "SinBot", owner_id: int, context: BustNegotiationContext) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.context = context

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await send_interaction_message(
            interaction,
            embed=self.bot.embed_factory.danger("Hands Off", "Only the busted player can use this negotiation."),
            ephemeral=True,
        )
        return False

    async def _start_interrogation(self, interaction: discord.Interaction, approach: str) -> None:
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.InteractionResponded:
                pass
            except discord.HTTPException:
                self.bot.logger.exception("Failed to defer negotiation interaction")
                return

        member: discord.Member | None
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
        else:
            member = None
            if interaction.guild is not None:
                member = interaction.guild.get_member(interaction.user.id)
                if member is None:
                    try:
                        member = await interaction.guild.fetch_member(interaction.user.id)
                    except discord.HTTPException:
                        member = None

        if member is None:
            await send_interaction_message(
                interaction,
                embed=self.bot.embed_factory.danger(
                    "Negotiation Failed",
                    "Could not resolve your server member profile for interrogation.",
                ),
                ephemeral=True,
            )
            return

        try:
            started, reason = await self.bot.operations_service.start_bust_interrogation(member, self.context, approach)  # type: ignore[union-attr]
        except Exception:
            self.bot.logger.exception("Negotiation startup failed")
            await send_interaction_message(
                interaction,
                embed=self.bot.embed_factory.danger(
                    "Negotiation Failed",
                    "Interrogation startup failed unexpectedly. Try again in a moment.",
                ),
                ephemeral=True,
            )
            return

        if started:
            await send_interaction_message(
                interaction,
                embed=self.bot.embed_factory.success(
                    "Interrogation Started",
                    "Officers are pulling you into an interrogation room. Check your DMs.",
                ),
                ephemeral=True,
            )
            return

        if reason == "expired":
            message = "This bust negotiation expired already. Trigger a new scene after your next bust."
        elif reason == "dm_closed":
            message = "Interrogation DM could not be delivered. Enable DMs from server members and try again on the next bust."
        elif reason == "context_mismatch":
            message = "That interrogation scene does not belong to your account."
        elif reason == "error":
            message = "Interrogation startup failed unexpectedly. Try again in a moment."
        else:
            message = "Interrogation could not be started."
        await send_interaction_message(
            interaction,
            embed=self.bot.embed_factory.danger("Negotiation Failed", message),
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if isinstance(error, SinBotError):
            await send_interaction_message(
                interaction,
                embed=self.bot.embed_factory.danger("Negotiation Failed", str(error)),
                ephemeral=True,
            )
            return
        self.bot.logger.exception("Negotiation view error", exc_info=error)
        await send_interaction_message(
            interaction,
            embed=self.bot.embed_factory.danger("Negotiation Failed", "Something went wrong in that interaction."),
            ephemeral=True,
        )

    @discord.ui.button(label="Plead", emoji="\U0001F97A", style=discord.ButtonStyle.secondary)
    async def plead(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._start_interrogation(interaction, "plead")

    @discord.ui.button(label="Bribe", emoji="\U0001F4B8", style=discord.ButtonStyle.success)
    async def bribe(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._start_interrogation(interaction, "bribe")

    @discord.ui.button(label="Bluff", emoji="\U0001F3AD", style=discord.ButtonStyle.primary)
    async def bluff(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._start_interrogation(interaction, "bluff")

    @discord.ui.button(label="Threaten", emoji="\U0001F52A", style=discord.ButtonStyle.danger)
    async def threaten(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._start_interrogation(interaction, "threaten")
