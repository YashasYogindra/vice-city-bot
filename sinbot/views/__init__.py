"""Discord UI views for SinBot."""
from __future__ import annotations

import discord


def disable_all_items(view: discord.ui.View) -> None:
    """Disable all interactive children (buttons/selects) on a view."""
    for child in view.children:
        if isinstance(child, (discord.ui.Button, discord.ui.Select)):
            child.disabled = True
