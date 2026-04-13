from __future__ import annotations

import discord

from sinbot.views import disable_all_items


class PardonDecisionView(discord.ui.View):
    """Sent to the Mayor via DM so they can accept or decline a pardon request."""

    def __init__(self, *, timeout: float = 300.0) -> None:
        super().__init__(timeout=timeout)
        self.choice: str | None = None
        self.message: discord.Message | None = None

    @discord.ui.button(label="Accept Pardon", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "accepted"
        await interaction.response.edit_message(view=self._disabled())
        self.stop()

    @discord.ui.button(label="Decline Pardon", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "declined"
        await interaction.response.edit_message(view=self._disabled())
        self.stop()

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=self._disabled())
            except discord.HTTPException:
                pass

    def _disabled(self) -> "PardonDecisionView":
        disable_all_items(self)
        return self
