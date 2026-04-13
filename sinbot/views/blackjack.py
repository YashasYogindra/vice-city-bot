from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from sinbot.views import disable_all_items

if TYPE_CHECKING:
    from sinbot.services.casino import CasinoService


class BlackjackView(discord.ui.View):
    def __init__(self, service: "CasinoService", user_id: int, session_id: str, *, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self.service = service
        self.user_id = user_id
        self.session_id = session_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=self.service.bot.embed_factory.danger("Not Your Hand", "Only the active player can use these buttons."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.service.handle_blackjack_action(self.session_id, interaction, "hit", self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.service.handle_blackjack_action(self.session_id, interaction, "stand", self)

    async def on_timeout(self) -> None:
        await self.service.auto_stand_blackjack(self.session_id, self)

    def disable_all(self) -> "BlackjackView":
        disable_all_items(self)
        return self
