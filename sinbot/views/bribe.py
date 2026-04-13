from __future__ import annotations

import discord

from sinbot.views import disable_all_items


class BribeDecisionView(discord.ui.View):
    def __init__(self, *, timeout: float = 300.0) -> None:
        super().__init__(timeout=timeout)
        self.choice: str | None = None
        self.message: discord.Message | None = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "accepted"
        await interaction.response.edit_message(view=self._disabled())
        self.stop()

    @discord.ui.button(label="Ignore", style=discord.ButtonStyle.secondary)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "ignored"
        await interaction.response.edit_message(view=self._disabled())
        self.stop()

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=self._disabled())
            except discord.HTTPException:
                pass

    def _disabled(self) -> "BribeDecisionView":
        disable_all_items(self)
        return self
