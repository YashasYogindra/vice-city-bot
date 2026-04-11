"""Seed the Vice City database with demo-ready state.

Creates:
- 4 players across 2 gangs with varying wallets/XP/heat.
- One near-Heat-5 player to showcase the wanted poster.
- Gang bank differences for visible leaderboard variety.
- Several news entries for a populated feed.
- One ready city event (Harbor Shipment).

Usage:
    py -3.11 tools/seed_demo.py
    py -3.11 tools/seed_demo.py --db-path path/to/vicecity.db
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

# Add project root to path so we can import vicecity modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vicecity.constants import GANGS
from vicecity.models.events import CityEventEffect
from vicecity.repositories.database import Database
from vicecity.repositories.game_repository import GameRepository
from vicecity.utils.time import isoformat, utcnow


DEMO_TURFS = (
    ("Docks", 0, 500),
    ("Downtown", 0, 650),
    ("Harbor", 0, 550),
    ("Little Havana", 1, 450),
    ("North Beach", 1, 400),
)


async def seed(db_path: Path, guild_id: int) -> None:
    db = Database(db_path)
    await db.connect()
    repo = GameRepository(db)
    await repo.initialize()

    # Ensure guild settings exist
    await repo.ensure_guild_settings(guild_id)

    # Ensure at least two demo gangs exist even if the bot has not bootstrapped yet.
    gangs = await repo.list_gangs(guild_id)
    if len(gangs) < 2:
        for definition in GANGS[:2]:
            await repo.upsert_gang(guild_id, definition.name)
        gangs = await repo.list_gangs(guild_id)

    gang_a = gangs[0]  # First gang (e.g., Serpents)
    gang_b = gangs[1]  # Second gang (e.g., Wolves)

    # Seed player IDs (these are fake Discord user IDs for demo)
    players = [
        {
            "user_id": 100000000000000001,
            "gang_id": gang_a["id"],
            "rank": "Boss",
            "wallet": 4200,
            "heat": 2,
            "xp": 6500,
            "is_joined": 1,
        },
        {
            "user_id": 100000000000000002,
            "gang_id": gang_a["id"],
            "rank": "Lieutenant",
            "wallet": 1800,
            "heat": 4,
            "xp": 2200,
            "is_joined": 1,
        },
        {
            "user_id": 100000000000000003,
            "gang_id": gang_b["id"],
            "rank": "Capo",
            "wallet": 3100,
            "heat": 1,
            "xp": 3800,
            "is_joined": 1,
        },
        {
            "user_id": 100000000000000004,
            "gang_id": gang_b["id"],
            "rank": "Soldier",
            "wallet": 600,
            "heat": 4,  # One more bust pushes this player toward Heat 5.
            "xp": 900,
            "is_joined": 1,
        },
    ]

    for p in players:
        await repo.ensure_player(guild_id, p["user_id"], **p)
        await repo.update_player(guild_id, p["user_id"], **{k: v for k, v in p.items() if k != "user_id"})
        # Give some inventory
        if p["rank"] in ("Boss", "Capo"):
            await repo.adjust_inventory(guild_id, p["user_id"], "weapon", 2)
        await repo.adjust_inventory(guild_id, p["user_id"], "burnerphone", 1)

    # Gang bank differences
    await repo.upsert_gang(guild_id, gang_a["name"])
    current_a = await repo.get_gang_by_name(guild_id, gang_a["name"])
    if current_a and int(current_a.get("bank_balance", 0)) < 2000:
        await repo.credit_gang_bank(gang_a["id"], 2500)

    current_b = await repo.get_gang_by_name(guild_id, gang_b["name"])
    if current_b and int(current_b.get("bank_balance", 0)) < 500:
        await repo.credit_gang_bank(gang_b["id"], 800)

    # Set boss for gang A
    await repo.upsert_gang(guild_id, gang_a["name"], boss_user_id=100000000000000001)

    # Turf ownership differences
    for turf_name, gang_index, hourly_income in DEMO_TURFS:
        owner = (gang_a, gang_b)[gang_index]
        existing_turf = await repo.get_turf_by_name(guild_id, turf_name)
        if existing_turf is None:
            await repo.create_turf(guild_id, turf_name, owner["id"], hourly_income=hourly_income)
        else:
            await repo.update_turf_owner(existing_turf["id"], owner["id"])

    # Credit some treasury
    settings = await repo.get_guild_settings(guild_id)
    if settings and int(settings.get("treasury_balance", 0)) < 1000:
        await repo.credit_treasury(guild_id, 1500)

    # Seed news entries
    news_entries = [
        ("Street Operation", "An anonymous runner pulled off a high-risk drug run and walked away clean.", "success"),
        ("Arms Deal Cleared", "A Serpents crew moved product through the docks without a single badge showing up.", "success"),
        ("Bust", "A Wolves soldier got pinched on a medium drug run. Heat is climbing.", "danger"),
        ("Hourly Income Report", "Serpents collected 1200 Racks from 3 turfs. Wolves banked 800 from 2 turfs.", "reward"),
        ("New Recruit", "A fresh face joined The Wolves with 500 Racks to their name.", "success"),
    ]
    for title, desc, color in news_entries:
        await repo.add_news_event(guild_id, title, desc, color)

    # Seed a city event: Harbor Shipment boosts operation payouts.
    now = utcnow()
    effect = CityEventEffect(operation_payout_multiplier=1.4)
    await repo.replace_active_city_event(
        guild_id,
        event_key="harbor_shipment",
        headline="Harbor Shipment Incoming",
        description="Fresh cargo is flooding the docks. Every courier in the city smells fast money tonight.",
        effect=effect,
        starts_at=isoformat(now) or "",
        ends_at=isoformat(now + timedelta(hours=4)) or "",
    )

    await db.close()
    print(f"Demo state seeded successfully into {db_path}")
    print(f"  Guild ID: {guild_id}")
    print(f"  Players: {len(players)}")
    print(f"  News entries: {len(news_entries)}")
    print(f"  City event: Harbor Shipment (4h)")
    print()
    print("Next steps:")
    print("  1. Start the bot: py -3.11 main.py")
    print("  2. /city event - see the live Harbor Shipment")
    print("  3. /city event trigger police_sweep - swap to Police Sweep")
    print("  4. /status - verify bot health")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Vice City demo state")
    parser.add_argument("--db-path", type=str, default="vicecity.db", help="Path to the SQLite database")
    parser.add_argument("--guild-id", type=int, default=0, help="Discord guild ID (reads from .env if 0)")
    args = parser.parse_args()

    guild_id = args.guild_id
    if guild_id == 0:
        # Try to read from .env
        from dotenv import load_dotenv
        import os

        load_dotenv()
        guild_id = int(os.getenv("GUILD_ID", "0"))
        if guild_id == 0:
            print("ERROR: Provide --guild-id or set GUILD_ID in .env")
            sys.exit(1)

    db_path = Path(args.db_path).expanduser().resolve()
    asyncio.run(seed(db_path, guild_id))


if __name__ == "__main__":
    main()
