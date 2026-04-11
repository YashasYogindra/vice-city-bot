from __future__ import annotations

import discord

from vicecity.constants import EMBED_DANGER, EMBED_REWARD, EMBED_STANDARD, EMBED_SUCCESS, FOOTER_TEXT


class EmbedFactory:
    def _make(self, *, title: str, description: str, color: int) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=FOOTER_TEXT)
        embed.timestamp = discord.utils.utcnow()
        return embed

    def standard(self, title: str, description: str) -> discord.Embed:
        return self._make(title=title, description=description, color=EMBED_STANDARD)

    def reward(self, title: str, description: str) -> discord.Embed:
        return self._make(title=title, description=description, color=EMBED_REWARD)

    def danger(self, title: str, description: str) -> discord.Embed:
        return self._make(title=title, description=description, color=EMBED_DANGER)

    def success(self, title: str, description: str) -> discord.Embed:
        return self._make(title=title, description=description, color=EMBED_SUCCESS)
