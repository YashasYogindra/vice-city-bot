from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands

from sinbot.config import AppConfig
from sinbot.exceptions import ConcurrentActionError, InsufficientFundsError, SinBotError
from sinbot.repositories.database import Database
from sinbot.repositories.game_repository import GameRepository
from sinbot.services.bootstrap import BootstrapService
from sinbot.services.casino import CasinoService
from sinbot.services.city import CityService
from sinbot.services.city_events import CityEventDirectorService
from sinbot.services.groq_service import GroqService
from sinbot.services.heist import HeistService
from sinbot.services.heat import HeatService
from sinbot.services.operations import OperationsService
from sinbot.services.social import SocialService
from sinbot.services.visuals import VisualService
from sinbot.services.war import WarService
from sinbot.utils.embeds import EmbedFactory
from sinbot.utils.locks import MemberLockManager
from sinbot.utils.logging import configure_logging
from sinbot.utils.time import format_duration, utcnow


class SinBot(commands.Bot):
    def __init__(self, config: AppConfig) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.config = config
        self.logger = configure_logging(config.log_level)
        self.db = Database(config.database_path)
        self.repo = GameRepository(self.db)
        self.embed_factory = EmbedFactory()
        self.scheduler = AsyncIOScheduler(timezone=config.timezone)
        self.member_locks = MemberLockManager()
        self.startup_lock = asyncio.Lock()
        self.runtime_ready = False
        self.start_time = utcnow()

        self.bootstrap_service: BootstrapService | None = None
        self.city_service: CityService | None = None
        self.heat_service: HeatService | None = None
        self.operations_service: OperationsService | None = None
        self.war_service: WarService | None = None
        self.social_service: SocialService | None = None
        self.heist_service: HeistService | None = None
        self.casino_service: CasinoService | None = None
        self.groq_service: GroqService | None = None
        self.visual_service: VisualService | None = None
        self.event_service: CityEventDirectorService | None = None

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.repo.initialize()
        self.scheduler.start()
        self.bootstrap_service = BootstrapService(self)
        self.city_service = CityService(self)
        self.heat_service = HeatService(self)
        self.operations_service = OperationsService(self)
        self.war_service = WarService(self)
        self.social_service = SocialService(self)
        self.heist_service = HeistService(self)
        self.casino_service = CasinoService(self)
        self.groq_service = GroqService(self)
        self.visual_service = VisualService(self)
        self.event_service = CityEventDirectorService(self)

        from sinbot.cogs.auction import AuctionCog
        from sinbot.cogs.betting import BettingCog
        from sinbot.cogs.casino import CasinoCog
        from sinbot.cogs.core import CoreCog
        from sinbot.cogs.fighting import FightingCog
        from sinbot.cogs.heist import HeistCog
        from sinbot.cogs.mayor import MayorCog
        from sinbot.cogs.operations import OperationsCog
        from sinbot.cogs.social import SocialCog
        from sinbot.cogs.status import StatusCog
        from sinbot.cogs.war import WarCog

        for cog_type in (CoreCog, OperationsCog, WarCog, MayorCog, SocialCog, HeistCog, CasinoCog, StatusCog, FightingCog, AuctionCog, BettingCog):
            await self.add_cog(await cog_type.create(self))
        self.tree.on_error = self.on_app_command_error  # type: ignore[assignment]
        guild_object = discord.Object(id=self.config.guild_id)
        self.tree.copy_global_to(guild=guild_object)
        await self.tree.sync(guild=guild_object)
        await self.start_healthcheck_server()

    async def start_healthcheck_server(self) -> None:
        from aiohttp import web
        app = web.Application()
        app.router.add_get('/health', lambda request: web.Response(text="OK", status=200))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        self.logger.info("Healthcheck server listening on port 8080")

    async def on_ready(self) -> None:
        if self.runtime_ready:
            return
        async with self.startup_lock:
            if self.runtime_ready:
                return
            await self._ensure_runtime_ready()
            self.runtime_ready = True
            self.logger.info("SinBot connected as %s", self.user)

    async def _ensure_runtime_ready(self) -> None:
        assert self.bootstrap_service is not None
        assert self.city_service is not None
        assert self.heat_service is not None
        assert self.war_service is not None
        assert self.heist_service is not None
        assert self.event_service is not None
        guild = self.get_guild(self.config.guild_id)
        if guild is None:
            raise RuntimeError(f"Guild {self.config.guild_id} is not available to the bot.")
        await self.bootstrap_service.ensure_guild_setup(guild)
        await self.city_service.schedule_hourly_cycle(guild.id)
        await self.heat_service.rehydrate_active_jails(guild.id)
        await self.war_service.rehydrate_active_wars(guild.id)
        await self.heist_service.rehydrate_active_heists(guild.id)
        await self.casino_service.rehydrate_wagers(guild.id)
        await self._catch_up_jobs(guild.id)
        await self.event_service.ensure_active_event(guild.id)
        await self.city_service.refresh_wanted_board(guild.id)
        await self.city_service.refresh_vault(guild.id)

    async def _catch_up_jobs(self, guild_id: int) -> None:
        # Catch up any scheduled events that passed while bot was offline
        # Jails
        from sinbot.utils.time import utcnow, isoformat
        now = isoformat(utcnow())
        rows = await self.db.execute_fetchall(
            "SELECT * FROM jail_records WHERE guild_id = ? AND active = 1 AND release_at <= ?",
            (guild_id, now)
        )
        for row in rows:
            jail_id, user_id = row["id"], row["user_id"]
            await self.repo.release_jail_record(jail_id)
            await self.repo.update_player(guild_id, user_id, jailed_until=None)

        # Wars
        war_rows = await self.db.execute_fetchall(
            "SELECT * FROM wars WHERE guild_id = ? AND status = 'active' AND resolve_at <= ?",
            (guild_id, now)
        )
        for row in war_rows:
            war_id = row["id"]
            # To resolve, we just trigger the end_war task logic manually, but we need
            # the war service to resolve it.
            await self.war_service.end_war(war_id)

    async def close(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await self.db.close()
        await super().close()

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        handled = await self._handle_error(ctx, error)
        if handled:
            return
        root = self._unwrap_error(error)
        self.logger.exception("Unhandled command error", exc_info=(type(root), root, root.__traceback__))
        embed = self.embed_factory.danger(
            "Command Error",
            self._format_error_for_user(root),
        )
        await self._safe_reply(ctx, embed=embed)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        handled = await self._handle_error(interaction, error)
        if handled:
            return
        root = self._unwrap_error(error)
        self.logger.exception("Unhandled app command error", exc_info=(type(root), root, root.__traceback__))
        embed = self.embed_factory.danger(
            "Command Error",
            self._format_error_for_user(root),
        )
        await self._safe_interaction_reply(interaction, embed=embed, ephemeral=True)

    async def _handle_error(self, target: commands.Context | discord.Interaction, error: Exception) -> bool:
        if isinstance(target, commands.Context) and hasattr(target.command, "on_error"):
            return True

        original = self._unwrap_error(error)
        if isinstance(original, commands.CommandNotFound):
            return True

        if isinstance(original, commands.MissingPermissions):
            embed = self.embed_factory.danger("Access Denied", "You don't have the rank for that.")
            return await self._dispatch_error(target, embed)

        if isinstance(original, commands.CommandOnCooldown):
            description = f"Try again in {format_duration(original.retry_after)}."
            embed = self.embed_factory.danger("Cooldown Active", description)
            return await self._dispatch_error(target, embed)

        if isinstance(original, app_commands.CommandOnCooldown):
            description = f"Try again in {format_duration(original.retry_after)}."
            embed = self.embed_factory.danger("Cooldown Active", description)
            return await self._dispatch_error(target, embed)

        if isinstance(original, InsufficientFundsError):
            description = f"That {original.account_type} account only has {original.current_balance} available."
            embed = self.embed_factory.danger("Insufficient Funds", description)
            return await self._dispatch_error(target, embed)

        if isinstance(original, ConcurrentActionError):
            embed = self.embed_factory.danger("Action Blocked", str(original))
            return await self._dispatch_error(target, embed)

        if isinstance(original, SinBotError):
            embed = self.embed_factory.danger("Action Blocked", str(original))
            return await self._dispatch_error(target, embed)

        if isinstance(original, app_commands.CheckFailure):
            embed = self.embed_factory.danger("Access Denied", "You don't have the rank for that.")
            return await self._dispatch_error(target, embed)

        if isinstance(original, commands.CheckFailure):
            embed = self.embed_factory.danger("Action Blocked", str(original))
            return await self._dispatch_error(target, embed)
        return False

    def _unwrap_error(self, error: Exception) -> Exception:
        current = error
        visited: set[int] = set()
        while True:
            visited.add(id(current))
            nested = getattr(current, "original", None)
            if not isinstance(nested, Exception):
                cause = getattr(current, "__cause__", None)
                nested = cause if isinstance(cause, Exception) else None
            if nested is None or id(nested) in visited:
                return current
            current = nested

    def _format_error_for_user(self, error: Exception) -> str:
        message = str(error).strip() or "No details provided."
        detail = f"{type(error).__name__}: {message}"
        if len(detail) > 800:
            detail = detail[:797] + "..."
        return detail

    async def _dispatch_error(self, target: commands.Context | discord.Interaction, embed: discord.Embed) -> bool:
        if isinstance(target, commands.Context):
            await self._safe_reply(target, embed=embed)
        else:
            await self._safe_interaction_reply(target, embed=embed, ephemeral=True)
        return True

    async def _safe_reply(self, ctx: commands.Context, **kwargs: Any) -> None:
        if getattr(ctx, "interaction", None) is not None:
            await ctx.send(**kwargs)
            return
        try:
            await ctx.reply(**kwargs, mention_author=False)
        except discord.HTTPException:
            await ctx.send(**kwargs)

    async def _safe_interaction_reply(self, interaction: discord.Interaction, **kwargs: Any) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
            return
        await interaction.response.send_message(**kwargs)


def main() -> None:
    config = AppConfig.load()
    bot = SinBot(config)
    bot.run(config.discord_token, log_handler=None)
