from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord

from sinbot.views import disable_all_items

if TYPE_CHECKING:
    from sinbot.bot import SinBot


class ArmsDealView(discord.ui.View):
    def __init__(self, bot: "SinBot", requester_id: int, teammate_id: int, *, timeout: float = 300.0) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.requester_id = requester_id
        self.teammate_id = teammate_id
        self.accepted: bool | None = None
        self.event = asyncio.Event()
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.teammate_id:
            await interaction.response.send_message(
                embed=self.bot.embed_factory.danger("Not Your Deal", "Only the invited teammate can respond."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.accepted = True
        await interaction.response.edit_message(view=self._disabled())
        self.event.set()
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.accepted = False
        await interaction.response.edit_message(view=self._disabled())
        self.event.set()
        self.stop()

    async def on_timeout(self) -> None:
        self.accepted = None
        if self.message:
            try:
                await self.message.edit(view=self._disabled())
            except discord.HTTPException:
                pass
        self.event.set()

    def _disabled(self) -> "ArmsDealView":
        disable_all_items(self)
        return self
