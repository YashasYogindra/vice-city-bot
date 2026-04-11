from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from vicecity.constants import BLACK_MARKET_ITEMS, DRUG_RUN_CONFIG, HEIST_ROLES
from vicecity.exceptions import ViceCityError

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


HELP_SECTIONS: dict[str, tuple[str, str]] = {
    "Getting Started": (
        "Getting Started",
        "1. Use `/join` or `!join` to enter Vice City.\n"
        "2. Open your dossier with `/profile`.\n"
        "3. Claim `/daily` to start building a streak bonus.\n"
        "4. Make money with `/operate drug` or the operation menu.\n"
        "5. Ask the streets for intel with `/tip`, then spend Racks in `/shop`.",
    ),
    "Street Intel": (
        "Street Intel",
        "Use `/tip` when you want a cryptic read on the city.\n"
        "The informant watches turf, gang banks, wanted heat, wars, and city politics, then whispers where the pressure is building.",
    ),
    "Operations": (
        "Operations",
        "Drug runs are your fastest early cash. Low risk is steady, high risk hits harder, and every bust raises Heat.\n"
        "Arms deals need a trusted teammate from your gang and can go very right or very wrong.",
    ),
    "Casino": (
        "Casino",
        "Use slots, house coin flips, challenge flips, or blackjack when you want to turn cash into drama.\n"
        "The house pays fast, but it also buries people fast.",
    ),
    "Turf Wars": (
        "Turf Wars",
        "Capos and Bosses can declare on enemy turf.\n"
        "Soldiers and up can commit to assault or defend, and gang-bank money fuels the whole push.",
    ),
    "Heat & Wanted": (
        "Heat & Wanted",
        "Heat tracks how badly the city wants you.\n"
        "Higher Heat makes operations rougher, blocks the black market, and at Heat 5 the city posts a wanted poster and starts the countdown.",
    ),
    "Heists": (
        "Heists",
        "Bosses plan the Casino Job, the crew fills hacker/driver/inside, and the bot turns it into a live crime scene.\n"
        "A clean crew steals from treasury. A bad crew goes to lockup.",
    ),
    "Mayor / City Hall": (
        "Mayor / City Hall",
        "The Mayor controls tax, crackdowns, pardons, and treasury rewards.\n"
        "If City Hall turns hostile, the whole economy feels it.",
    ),
}


async def send_interaction_message(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View | None = None,
    file: discord.File | None = None,
    ephemeral: bool = False,
) -> None:
    kwargs: dict[str, object] = {"embed": embed, "view": view}
    if file is not None:
        kwargs["file"] = file
    if interaction.response.is_done():
        await interaction.followup.send(ephemeral=ephemeral, **kwargs)
    else:
        await interaction.response.send_message(ephemeral=ephemeral, **kwargs)


def build_help_embed(category: str = "Getting Started") -> discord.Embed:
    title, description = HELP_SECTIONS.get(category, HELP_SECTIONS["Getting Started"])
    embed = discord.Embed(title=title, description=description, color=0x8B0000)
    embed.set_footer(text="Vice City OS")
    embed.timestamp = discord.utils.utcnow()
    for key in HELP_SECTIONS:
        marker = "\u2022" if key == category else "\u25E6"
        embed.add_field(name=key, value=f"{marker} Open this section", inline=True)
    return embed


def build_guide_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Vice City Guide",
        description=(
            "Vice City is a single-server gang simulation. You join a crew, run operations, manage Heat, "
            "fight over turf, and work your way up to major jobs."
        ),
        color=0x8B0000,
    )
    embed.set_footer(text="Vice City OS")
    embed.timestamp = discord.utils.utcnow()
    embed.add_field(name="First Money", value="Claim `/daily`, then use the operation menu and start with low-risk drug runs.", inline=False)
    embed.add_field(name="Street Intel", value="Use `/tip` to get a whispered read on where the city is soft, rich, or distracted.", inline=False)
    embed.add_field(name="Danger Meter", value="Heat is your wanted level. At Heat 5, the city comes down on you hard.", inline=False)
    embed.add_field(name="Big Goal", value="Rank up, support your gang, and pull the Casino Job.", inline=False)
    return embed


class OwnerLockedView(discord.ui.View):
    def __init__(self, bot: "ViceCityBot", owner_id: int | None = None, *, timeout: float = 180) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is None or interaction.user.id == self.owner_id:
            return True
        await send_interaction_message(
            interaction,
            embed=self.bot.embed_factory.danger("Not Your Panel", "This control belongs to someone else."),
            ephemeral=True,
        )
        return False

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if isinstance(error, ViceCityError):
            await send_interaction_message(
                interaction,
                embed=self.bot.embed_factory.danger("Action Blocked", str(error)),
                ephemeral=True,
            )
            return
        self.bot.logger.exception("UI interaction error", exc_info=error)
        await send_interaction_message(
            interaction,
            embed=self.bot.embed_factory.danger("City Interference", "Something went wrong in that interaction."),
            ephemeral=True,
        )


class QuickActionsView(OwnerLockedView):
    def __init__(self, bot: "ViceCityBot", owner_id: int) -> None:
        super().__init__(bot, owner_id=owner_id, timeout=180)

    @discord.ui.button(label="Profile", emoji="\U0001F4CB", style=discord.ButtonStyle.secondary, row=0)
    async def profile_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.guild_id is None or self.bot.visual_service is None:
            return
        embed, file = await self.bot.visual_service.build_profile_card(interaction.guild_id, interaction.user.id)
        await send_interaction_message(
            interaction,
            embed=embed,
            file=file,
            view=QuickActionsView(self.bot, interaction.user.id),
        )

    @discord.ui.button(label="Shop", emoji="\U0001F3EA", style=discord.ButtonStyle.primary, row=0)
    async def shop_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        embed = self.bot.city_service.build_shop_embed()  # type: ignore[union-attr]
        await send_interaction_message(
            interaction,
            embed=embed,
            view=ShopSelectView(self.bot, interaction.user.id),
        )

    @discord.ui.button(label="Operate", emoji="\U0001F489", style=discord.ButtonStyle.primary, row=0)
    async def operate_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        embed = self.bot.embed_factory.standard(
            "Pick Your Move",
            "Choose a risk level below to launch a drug run without typing the full command.",
        )
        await send_interaction_message(
            interaction,
            embed=embed,
            view=OperateSelectView(self.bot, interaction.user.id),
        )

    @discord.ui.button(label="Wanted", emoji="\U0001F6A8", style=discord.ButtonStyle.danger, row=0)
    async def wanted_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.guild_id is None:
            return
        embed, file = await self.bot.city_service.build_wanted_embed(interaction.guild_id)  # type: ignore[union-attr]
        await send_interaction_message(interaction, embed=embed, file=file, view=QuickActionsView(self.bot, interaction.user.id))

    @discord.ui.button(label="Help", emoji="\u2753", style=discord.ButtonStyle.secondary, row=0)
    async def help_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await send_interaction_message(
            interaction,
            embed=build_help_embed(),
            view=HelpNavView(self.bot, interaction.user.id),
        )

    @discord.ui.button(label="Tip", emoji="\U0001F50E", style=discord.ButtonStyle.secondary, row=1)
    async def tip_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.guild_id is None:
            return
        await interaction.response.defer()
        embed, media_key = await self.bot.city_service.build_tip_embed(interaction.guild_id)  # type: ignore[union-attr]
        file = None
        if self.bot.visual_service is not None and media_key:
            file = await self.bot.visual_service.build_event_banner(media_key, subtitle="Street intel")
            if file is not None:
                embed.set_image(url=f"attachment://{file.filename}")
        await send_interaction_message(
            interaction,
            embed=embed,
            file=file,
            view=QuickActionsView(self.bot, interaction.user.id),
        )

    @discord.ui.button(label="Daily", emoji="\U0001F4C6", style=discord.ButtonStyle.success, row=1)
    async def daily_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.guild_id is None:
            return
        embed = await self.bot.city_service.claim_daily_reward(interaction.guild_id, interaction.user.id)  # type: ignore[union-attr]
        await send_interaction_message(
            interaction,
            embed=embed,
            view=QuickActionsView(self.bot, interaction.user.id),
        )


class HelpNavView(OwnerLockedView):
    def __init__(self, bot: "ViceCityBot", owner_id: int | None = None) -> None:
        super().__init__(bot, owner_id=owner_id, timeout=240)
        row = 0
        for index, category in enumerate(HELP_SECTIONS):
            button = discord.ui.Button(
                label=category[:18],
                style=discord.ButtonStyle.secondary,
                row=row,
            )
            button.callback = self._make_callback(category)  # type: ignore[assignment]
            self.add_item(button)
            if index in {2, 5}:
                row += 1

    def _make_callback(self, category: str):
        async def callback(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(embed=build_help_embed(category), view=self)

        return callback


class GuideView(OwnerLockedView):
    @discord.ui.button(label="Open Help", emoji="\U0001F4D6", style=discord.ButtonStyle.primary)
    async def open_help(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await send_interaction_message(
            interaction,
            embed=build_help_embed(),
            view=HelpNavView(self.bot, interaction.user.id),
        )

    @discord.ui.button(label="Profile", emoji="\U0001F4CB", style=discord.ButtonStyle.secondary)
    async def profile(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.guild_id is None or self.bot.visual_service is None:
            return
        embed, file = await self.bot.visual_service.build_profile_card(interaction.guild_id, interaction.user.id)
        await send_interaction_message(interaction, embed=embed, file=file, view=QuickActionsView(self.bot, interaction.user.id))


class ShopItemSelect(discord.ui.Select):
    def __init__(self, parent: "ShopSelectView") -> None:
        options = [
            discord.SelectOption(
                label=item.title(),
                value=item,
                description=f"Costs {details['price']} Racks",
                emoji="\U0001F52B" if item == "weapon" else "\U0001F4F1" if item == "burnerphone" else "\u2696\ufe0f",
            )
            for item, details in BLACK_MARKET_ITEMS.items()
        ]
        super().__init__(placeholder="Choose an item", min_values=1, max_values=1, options=options)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent.selected_item = self.values[0]
        embed = self.parent.bot.city_service.build_shop_embed(self.parent.selected_item)  # type: ignore[union-attr]
        await interaction.response.edit_message(embed=embed, view=self.parent)


class ShopSelectView(OwnerLockedView):
    def __init__(self, bot: "ViceCityBot", owner_id: int) -> None:
        super().__init__(bot, owner_id=owner_id, timeout=180)
        self.selected_item = next(iter(BLACK_MARKET_ITEMS))
        self.add_item(ShopItemSelect(self))

    @discord.ui.button(label="Buy Selected", emoji="\U0001F4B8", style=discord.ButtonStyle.success, row=1)
    async def buy_selected(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.guild_id is None:
            return
        embed = await self.bot.city_service.buy_item(interaction.guild_id, interaction.user.id, self.selected_item)  # type: ignore[union-attr]
        await send_interaction_message(interaction, embed=embed, view=QuickActionsView(self.bot, interaction.user.id))


class OperateRiskSelect(discord.ui.Select):
    def __init__(self, parent: "OperateSelectView") -> None:
        options = [
            discord.SelectOption(
                label=risk.title(),
                value=risk,
                description=f"Payout {config['payout']} | Success {config['success_rate']}%",
            )
            for risk, config in DRUG_RUN_CONFIG.items()
        ]
        super().__init__(placeholder="Pick a risk level", min_values=1, max_values=1, options=options)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent.selected_risk = self.values[0]
        config = DRUG_RUN_CONFIG[self.parent.selected_risk]
        embed = self.parent.bot.embed_factory.standard(
            "Operation Loaded",
            (
                f"Risk: **{self.parent.selected_risk}**\n"
                f"Payout: **{config['payout']}**\n"
                f"Base success: **{config['success_rate']}%**"
            ),
        )
        await interaction.response.edit_message(embed=embed, view=self.parent)


class OperateSelectView(OwnerLockedView):
    def __init__(self, bot: "ViceCityBot", owner_id: int) -> None:
        super().__init__(bot, owner_id=owner_id, timeout=180)
        self.selected_risk = "low"
        self.add_item(OperateRiskSelect(self))

    @discord.ui.button(label="Run Drug Operation", emoji="\U0001F48A", style=discord.ButtonStyle.success, row=1)
    async def run_drug(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return
        result = await self.bot.operations_service.run_drug_operation(interaction.user, self.selected_risk)  # type: ignore[arg-type, union-attr]
        file = None
        if self.bot.visual_service is not None and result.media_key:
            file = await self.bot.visual_service.build_event_banner(result.media_key, subtitle=f"{self.selected_risk.title()} risk")
            if file:
                result.embed.set_image(url=f"attachment://{file.filename}")
        from vicecity.views.negotiation import BustNegotiationView

        follow_view: discord.ui.View = QuickActionsView(self.bot, interaction.user.id)
        if result.bust_context is not None:
            follow_view = BustNegotiationView(self.bot, interaction.user.id, result.bust_context)
        await send_interaction_message(interaction, embed=result.embed, file=file, view=follow_view)


class CasinoSelect(discord.ui.Select):
    def __init__(self, parent: "CasinoSelectView") -> None:
        options = [
            discord.SelectOption(label="Slots", value="slots", description="Fast volatility and loud payouts."),
            discord.SelectOption(label="Coin Flip", value="flip", description="Call heads or tails against the house."),
            discord.SelectOption(label="Blackjack", value="blackjack", description="Play a full hand with buttons."),
        ]
        super().__init__(placeholder="Browse casino games", min_values=1, max_values=1, options=options)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent.selected_game = self.values[0]
        copy = {
            "slots": "Use `/casino slots <amount>` or `!casino slots <amount>` for a fast spin.",
            "flip": "Use `/casino flip <amount> <heads|tails>` for the house, or mention a rival on prefix.",
            "blackjack": "Use `/casino blackjack <amount>` to start a live hand with hit/stand buttons.",
        }[self.parent.selected_game]
        embed = self.parent.bot.embed_factory.standard("Casino Floor", copy)
        await interaction.response.edit_message(embed=embed, view=self.parent)


class CasinoSelectView(OwnerLockedView):
    def __init__(self, bot: "ViceCityBot", owner_id: int) -> None:
        super().__init__(bot, owner_id=owner_id, timeout=180)
        self.selected_game = "slots"
        self.add_item(CasinoSelect(self))


class HeistRoleSelect(discord.ui.Select):
    def __init__(self, parent: "HeistRoleSelectView") -> None:
        options = [
            discord.SelectOption(label=role.title(), value=role, description=f"Claim the {role} slot.")
            for role in HEIST_ROLES
        ]
        super().__init__(placeholder="Claim a heist role", min_values=1, max_values=1, options=options)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            return
        role_name = self.values[0]
        heist = await self.parent.bot.heist_service.join_role(interaction.user, role_name)  # type: ignore[arg-type, union-attr]
        embed = self.parent.bot.embed_factory.success(
            "Crew Locked In",
            f"{interaction.user.mention} claimed the **{role_name}** role for heist #{heist['id']}.",
        )
        await send_interaction_message(interaction, embed=embed, view=QuickActionsView(self.parent.bot, interaction.user.id))


class HeistRoleSelectView(OwnerLockedView):
    def __init__(self, bot: "ViceCityBot") -> None:
        super().__init__(bot, owner_id=None, timeout=600)
        self.add_item(HeistRoleSelect(self))
