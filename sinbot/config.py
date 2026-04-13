from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(slots=True)
class AppConfig:
    discord_token: str
    guild_id: int
    mayor_role_name: str
    database_path: Path
    timezone: str
    log_level: str
    groq_api_key: str | None
    groq_model: str
    disable_cooldowns: bool

    @classmethod
    def load(cls) -> "AppConfig":
        load_dotenv(override=True)
        token = os.getenv("DISCORD_TOKEN", "").strip()
        guild_id = os.getenv("GUILD_ID", "").strip()
        mayor_role_name = os.getenv("MAYOR_ROLE_NAME", "Mayor").strip() or "Mayor"
        database_path = os.getenv("DATABASE_PATH", "sinbot.db").strip() or "sinbot.db"
        timezone = os.getenv("TIMEZONE", "America/Los_Angeles").strip() or "America/Los_Angeles"
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip() or None
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"
        disable_cooldowns = os.getenv("DISABLE_COOLDOWNS", "false").strip().lower() in {"1", "true", "yes", "on"}

        if not token:
            raise ValueError("DISCORD_TOKEN is required.")
        if not guild_id:
            raise ValueError("GUILD_ID is required.")
        if not guild_id.isdigit():
            raise ValueError("GUILD_ID must be a numeric Discord guild ID.")

        return cls(
            discord_token=token,
            guild_id=int(guild_id),
            mayor_role_name=mayor_role_name,
            database_path=Path(database_path).expanduser().resolve(),
            timezone=timezone,
            log_level=log_level,
            groq_api_key=groq_api_key,
            groq_model=groq_model,
            disable_cooldowns=disable_cooldowns,
        )
