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
    gemini_api_key: str | None
    gemini_model: str

    @classmethod
    def load(cls) -> "AppConfig":
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN", "").strip()
        guild_id = os.getenv("GUILD_ID", "").strip()
        mayor_role_name = os.getenv("MAYOR_ROLE_NAME", "Mayor").strip() or "Mayor"
        database_path = os.getenv("DATABASE_PATH", "vicecity.db").strip() or "vicecity.db"
        timezone = os.getenv("TIMEZONE", "Asia/Calcutta").strip() or "Asia/Calcutta"
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip() or None
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"

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
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
        )
