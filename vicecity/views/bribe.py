from __future__ import annotations

import discord


class BribeDecisionView(discord.ui.View):
    def __init__(self, *, timeout: float = 300.0) -> None:
        super().__init__(timeout=timeout)
        self.choice: str | None = None
        self.message: discord.Message | None = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "accepted"
        await interaction.response.edit_message(view=self._disable_all())
        self.stop()

    @discord.ui.button(label="Ignore", style=discord.ButtonStyle.secondary)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "ignored"
        await interaction.response.edit_message(view=self._disable_all())
        self.stop()

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=self._disable_all())
            except discord.HTTPException:
                pass

    def _disable_all(self) -> "BribeDecisionView":
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        return self
