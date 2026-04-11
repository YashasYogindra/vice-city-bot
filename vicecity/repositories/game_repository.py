from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from vicecity.constants import DEFAULT_TAX_RATE, TURF_HOURLY_INCOME
from vicecity.exceptions import InsufficientFundsError
from vicecity.models.events import CityEvent, CityEventEffect
from vicecity.repositories.database import Database
from vicecity.utils.time import isoformat, parse_datetime, utcnow


class GameRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def initialize(self) -> None:
        await self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                mayor_role_id INTEGER,
                news_channel_id INTEGER,
                city_hall_channel_id INTEGER,
                black_market_channel_id INTEGER,
                turf_war_channel_id INTEGER,
                wanted_channel_id INTEGER,
                vault_channel_id INTEGER,
                tax_rate INTEGER NOT NULL DEFAULT 10,
                treasury_balance INTEGER NOT NULL DEFAULT 0,
                crackdown_until TEXT,
                wanted_message_id INTEGER,
                vault_message_id INTEGER,
                city_synced_at TEXT
            );

            CREATE TABLE IF NOT EXISTS gangs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                role_id INTEGER,
                channel_id INTEGER,
                bank_balance INTEGER NOT NULL DEFAULT 0,
                boss_user_id INTEGER,
                last_boss_active_at TEXT,
                UNIQUE (guild_id, name)
            );

            CREATE TABLE IF NOT EXISTS turfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                owner_gang_id INTEGER NOT NULL,
                hourly_income INTEGER NOT NULL DEFAULT 400,
                UNIQUE (guild_id, name),
                FOREIGN KEY (owner_gang_id) REFERENCES gangs(id)
            );

            CREATE TABLE IF NOT EXISTS players (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                gang_id INTEGER,
                rank TEXT NOT NULL DEFAULT 'Street Rat',
                wallet INTEGER NOT NULL DEFAULT 0,
                heat INTEGER NOT NULL DEFAULT 0,
                xp INTEGER NOT NULL DEFAULT 0,
                trust_score INTEGER NOT NULL DEFAULT 0,
                is_joined INTEGER NOT NULL DEFAULT 0,
                lawyer_cooldown_until TEXT,
                last_operation_at TEXT,
                last_daily_claim_at TEXT,
                daily_streak INTEGER NOT NULL DEFAULT 0,
                last_heat_change_at TEXT,
                last_active_at TEXT,
                jailed_until TEXT,
                pending_income_penalties INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id),
                FOREIGN KEY (gang_id) REFERENCES gangs(id)
            );

            CREATE TABLE IF NOT EXISTS player_inventory (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, item_name)
            );

            CREATE TABLE IF NOT EXISTS news_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                color_kind TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jail_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                release_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                attacker_gang_id INTEGER NOT NULL,
                defender_gang_id INTEGER NOT NULL,
                turf_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolve_at TEXT NOT NULL,
                winner_gang_id INTEGER,
                attack_message_id INTEGER,
                defend_message_id INTEGER,
                FOREIGN KEY (attacker_gang_id) REFERENCES gangs(id),
                FOREIGN KEY (defender_gang_id) REFERENCES gangs(id),
                FOREIGN KEY (turf_id) REFERENCES turfs(id)
            );

            CREATE TABLE IF NOT EXISTS war_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                war_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                gang_id INTEGER NOT NULL,
                side TEXT NOT NULL,
                weapons_used INTEGER NOT NULL DEFAULT 0,
                base_power REAL NOT NULL DEFAULT 1,
                total_power REAL NOT NULL DEFAULT 1,
                committed_at TEXT NOT NULL,
                UNIQUE (war_id, user_id),
                FOREIGN KEY (war_id) REFERENCES wars(id)
            );

            CREATE TABLE IF NOT EXISTS heists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                gang_id INTEGER NOT NULL,
                boss_user_id INTEGER NOT NULL,
                planning_channel_id INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                launch_deadline TEXT NOT NULL,
                execution_deadline TEXT,
                hacker_id INTEGER,
                driver_id INTEGER,
                inside_id INTEGER,
                hacker_prompt TEXT,
                hacker_answer TEXT,
                hacker_response TEXT,
                hacker_success INTEGER NOT NULL DEFAULT 0,
                driver_prompt TEXT,
                driver_answer TEXT,
                driver_response TEXT,
                driver_success INTEGER NOT NULL DEFAULT 0,
                inside_prompt TEXT,
                inside_window_start TEXT,
                inside_window_end TEXT,
                inside_response TEXT,
                inside_success INTEGER NOT NULL DEFAULT 0,
                treasury_snapshot INTEGER NOT NULL DEFAULT 0,
                resolved_at TEXT,
                cancel_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                target_user_id INTEGER NOT NULL,
                gang_id INTEGER NOT NULL,
                initiator_user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS vote_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vote_id INTEGER NOT NULL,
                voter_user_id INTEGER NOT NULL,
                vote TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (vote_id, voter_user_id),
                FOREIGN KEY (vote_id) REFERENCES votes(id)
            );

            CREATE TABLE IF NOT EXISTS bribes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                briber_user_id INTEGER NOT NULL,
                mayor_user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                request_text TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS city_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                event_key TEXT NOT NULL,
                headline TEXT NOT NULL,
                description TEXT NOT NULL,
                effect_json TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        await self._ensure_players_columns()

    async def _fetchone(self, query: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        row = await self.db.execute_fetchone(query, params)
        return dict(row) if row else None

    async def _fetchall(self, query: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        rows = await self.db.execute_fetchall(query, params)
        return [dict(row) for row in rows]

    async def _insert(self, query: str, params: Sequence[Any] = ()) -> int:
        return await self.db.execute_insert(query, params)

    async def ensure_guild_settings(self, guild_id: int) -> dict[str, Any]:
        existing = await self.get_guild_settings(guild_id)
        if existing:
            return existing
        now = isoformat(utcnow())
        await self.db.execute(
            """
            INSERT INTO guild_settings (guild_id, tax_rate, treasury_balance, city_synced_at)
            VALUES (?, ?, 0, ?)
            """,
            (guild_id, DEFAULT_TAX_RATE, now),
        )
        return await self.get_guild_settings(guild_id)  # type: ignore[return-value]

    async def get_guild_settings(self, guild_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))

    async def update_guild_settings(self, guild_id: int, **fields: Any) -> dict[str, Any]:
        await self.ensure_guild_settings(guild_id)
        if fields:
            await self._update_by_pk("guild_settings", "guild_id", guild_id, fields)
        return await self.get_guild_settings(guild_id)  # type: ignore[return-value]

    async def upsert_gang(self, guild_id: int, name: str, **fields: Any) -> dict[str, Any]:
        existing = await self.get_gang_by_name(guild_id, name)
        now = isoformat(utcnow())
        if existing is None:
            await self.db.execute(
                """
                INSERT INTO gangs (guild_id, name, last_boss_active_at)
                VALUES (?, ?, ?)
                """,
                (guild_id, name, now),
            )
        if fields:
            gang = await self.get_gang_by_name(guild_id, name)
            await self._update_by_pk("gangs", "id", gang["id"], fields)  # type: ignore[index]
        return await self.get_gang_by_name(guild_id, name)  # type: ignore[return-value]

    async def list_gangs(self, guild_id: int) -> list[dict[str, Any]]:
        return await self._fetchall("SELECT * FROM gangs WHERE guild_id = ? ORDER BY id", (guild_id,))

    async def get_gang(self, gang_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM gangs WHERE id = ?", (gang_id,))

    async def get_gang_by_name(self, guild_id: int, name: str) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM gangs WHERE guild_id = ? AND lower(name) = lower(?)", (guild_id, name))

    async def get_gang_by_role_id(self, guild_id: int, role_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM gangs WHERE guild_id = ? AND role_id = ?", (guild_id, role_id))

    async def get_gang_for_user(self, guild_id: int, user_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT g.* FROM gangs g
            INNER JOIN players p ON p.gang_id = g.id
            WHERE p.guild_id = ? AND p.user_id = ?
            """,
            (guild_id, user_id),
        )

    async def ensure_player(self, guild_id: int, user_id: int, **defaults: Any) -> dict[str, Any]:
        player = await self.get_player(guild_id, user_id)
        if player:
            return player
        now = isoformat(utcnow())
        fields = {
            "guild_id": guild_id,
            "user_id": user_id,
            "gang_id": defaults.get("gang_id"),
            "rank": defaults.get("rank", "Street Rat"),
            "wallet": defaults.get("wallet", 0),
            "heat": defaults.get("heat", 0),
            "xp": defaults.get("xp", 0),
            "trust_score": defaults.get("trust_score", 0),
            "is_joined": 1 if defaults.get("is_joined", 0) else 0,
            "lawyer_cooldown_until": defaults.get("lawyer_cooldown_until"),
            "last_operation_at": defaults.get("last_operation_at"),
            "last_daily_claim_at": defaults.get("last_daily_claim_at"),
            "daily_streak": defaults.get("daily_streak", 0),
            "last_heat_change_at": defaults.get("last_heat_change_at"),
            "last_active_at": defaults.get("last_active_at", now),
            "jailed_until": defaults.get("jailed_until"),
            "pending_income_penalties": defaults.get("pending_income_penalties", 0),
            "created_at": now,
            "updated_at": now,
        }
        columns = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        await self.db.execute(
            f"INSERT INTO players ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        return await self.get_player(guild_id, user_id)  # type: ignore[return-value]

    async def get_player(self, guild_id: int, user_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM players WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

    async def update_player(self, guild_id: int, user_id: int, **fields: Any) -> dict[str, Any]:
        fields["updated_at"] = isoformat(utcnow())
        await self._update_compound_pk("players", ("guild_id", guild_id), ("user_id", user_id), fields)
        return await self.get_player(guild_id, user_id)  # type: ignore[return-value]

    async def list_joined_players(self, guild_id: int, gang_id: int | None = None) -> list[dict[str, Any]]:
        if gang_id is None:
            return await self._fetchall(
                "SELECT * FROM players WHERE guild_id = ? AND is_joined = 1 ORDER BY xp DESC, wallet DESC",
                (guild_id,),
            )
        return await self._fetchall(
            """
            SELECT * FROM players
            WHERE guild_id = ? AND gang_id = ? AND is_joined = 1
            ORDER BY xp DESC, wallet DESC
            """,
            (guild_id, gang_id),
        )

    async def count_joined_players_by_gang(self, guild_id: int) -> dict[int, int]:
        rows = await self._fetchall(
            """
            SELECT gang_id, COUNT(*) AS total
            FROM players
            WHERE guild_id = ? AND is_joined = 1 AND gang_id IS NOT NULL
            GROUP BY gang_id
            """,
            (guild_id,),
        )
        return {row["gang_id"]: row["total"] for row in rows}

    async def list_wanted_players(self, guild_id: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT p.*, g.name AS gang_name
            FROM players p
            LEFT JOIN gangs g ON g.id = p.gang_id
            WHERE p.guild_id = ? AND p.is_joined = 1 AND p.heat >= 2
            ORDER BY p.heat DESC, p.wallet DESC
            """,
            (guild_id,),
        )

    async def get_richest_players(self, guild_id: int, limit: int = 10) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT p.*, g.name AS gang_name
            FROM players p
            LEFT JOIN gangs g ON g.id = p.gang_id
            WHERE p.guild_id = ? AND p.is_joined = 1
            ORDER BY p.wallet DESC, p.xp DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )

    async def get_powerful_gangs(self, guild_id: int, limit: int = 10) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT g.*, COUNT(t.id) AS turf_count
            FROM gangs g
            LEFT JOIN turfs t ON t.owner_gang_id = g.id
            WHERE g.guild_id = ?
            GROUP BY g.id
            ORDER BY turf_count DESC, g.bank_balance DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )

    async def add_news_event(self, guild_id: int, title: str, description: str, color_kind: str) -> int:
        return await self._insert(
            """
            INSERT INTO news_events (guild_id, title, description, color_kind, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, title, description, color_kind, isoformat(utcnow())),
        )

    async def list_news_events(self, guild_id: int, limit: int = 10) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT * FROM news_events
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )

    async def get_inventory_item(self, guild_id: int, user_id: int, item_name: str) -> int:
        row = await self._fetchone(
            """
            SELECT quantity FROM player_inventory
            WHERE guild_id = ? AND user_id = ? AND item_name = ?
            """,
            (guild_id, user_id, item_name),
        )
        return int(row["quantity"]) if row else 0

    async def list_inventory(self, guild_id: int, user_id: int) -> dict[str, int]:
        rows = await self._fetchall(
            "SELECT item_name, quantity FROM player_inventory WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return {row["item_name"]: row["quantity"] for row in rows}

    async def adjust_inventory(self, guild_id: int, user_id: int, item_name: str, delta: int) -> int:
        async with self.db.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT quantity FROM player_inventory
                WHERE guild_id = ? AND user_id = ? AND item_name = ?
                """,
                (guild_id, user_id, item_name),
            )
            row = await cursor.fetchone()
            await cursor.close()
            current = int(row["quantity"]) if row else 0
            new_value = max(0, current + delta)
            if row:
                await connection.execute(
                    """
                    UPDATE player_inventory
                    SET quantity = ?
                    WHERE guild_id = ? AND user_id = ? AND item_name = ?
                    """,
                    (new_value, guild_id, user_id, item_name),
                )
            else:
                await connection.execute(
                    """
                    INSERT INTO player_inventory (guild_id, user_id, item_name, quantity)
                    VALUES (?, ?, ?, ?)
                    """,
                    (guild_id, user_id, item_name, new_value),
                )
        return new_value

    async def credit_wallet(self, guild_id: int, user_id: int, amount: int) -> int:
        async with self.db.transaction() as connection:
            cursor = await connection.execute(
                "SELECT wallet FROM players WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise ValueError(f"Player {user_id} not found.")
            new_balance = int(row["wallet"]) + amount
            await connection.execute(
                "UPDATE players SET wallet = ?, updated_at = ? WHERE guild_id = ? AND user_id = ?",
                (new_balance, isoformat(utcnow()), guild_id, user_id),
            )
        return new_balance

    async def debit_wallet(self, guild_id: int, user_id: int, amount: int) -> int:
        async with self.db.transaction() as connection:
            cursor = await connection.execute(
                "SELECT wallet FROM players WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise ValueError(f"Player {user_id} not found.")
            current = int(row["wallet"])
            if current < amount:
                raise InsufficientFundsError("wallet", current, amount)
            new_balance = current - amount
            await connection.execute(
                "UPDATE players SET wallet = ?, updated_at = ? WHERE guild_id = ? AND user_id = ?",
                (new_balance, isoformat(utcnow()), guild_id, user_id),
            )
        return new_balance

    async def transfer_wallet(self, guild_id: int, from_user_id: int, to_user_id: int, amount: int) -> tuple[int, int]:
        async with self.db.transaction() as connection:
            source_cursor = await connection.execute(
                "SELECT wallet FROM players WHERE guild_id = ? AND user_id = ?",
                (guild_id, from_user_id),
            )
            source = await source_cursor.fetchone()
            await source_cursor.close()
            target_cursor = await connection.execute(
                "SELECT wallet FROM players WHERE guild_id = ? AND user_id = ?",
                (guild_id, to_user_id),
            )
            target = await target_cursor.fetchone()
            await target_cursor.close()
            if source is None or target is None:
                raise ValueError("Wallet transfer participants must both exist.")
            current = int(source["wallet"])
            if current < amount:
                raise InsufficientFundsError("wallet", current, amount)
            source_new = current - amount
            target_new = int(target["wallet"]) + amount
            now = isoformat(utcnow())
            await connection.execute(
                "UPDATE players SET wallet = ?, updated_at = ? WHERE guild_id = ? AND user_id = ?",
                (source_new, now, guild_id, from_user_id),
            )
            await connection.execute(
                "UPDATE players SET wallet = ?, updated_at = ? WHERE guild_id = ? AND user_id = ?",
                (target_new, now, guild_id, to_user_id),
            )
        return source_new, target_new

    async def claim_daily_reward(
        self,
        guild_id: int,
        user_id: int,
        *,
        amount: int,
        claimed_at: str,
        streak: int,
    ) -> dict[str, Any]:
        async with self.db.transaction() as connection:
            cursor = await connection.execute(
                "SELECT * FROM players WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise ValueError(f"Player {user_id} not found.")
            new_balance = int(row["wallet"]) + amount
            updated_at = isoformat(utcnow())
            await connection.execute(
                """
                UPDATE players
                SET wallet = ?, last_daily_claim_at = ?, daily_streak = ?, updated_at = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (new_balance, claimed_at, streak, updated_at, guild_id, user_id),
            )
            refreshed_cursor = await connection.execute(
                "SELECT * FROM players WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            refreshed = await refreshed_cursor.fetchone()
            await refreshed_cursor.close()
        if refreshed is None:
            raise ValueError(f"Player {user_id} not found after daily claim.")
        return dict(refreshed)

    async def credit_gang_bank(self, gang_id: int, amount: int) -> int:
        async with self.db.transaction() as connection:
            cursor = await connection.execute("SELECT bank_balance FROM gangs WHERE id = ?", (gang_id,))
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise ValueError(f"Gang {gang_id} not found.")
            new_balance = int(row["bank_balance"]) + amount
            await connection.execute("UPDATE gangs SET bank_balance = ? WHERE id = ?", (new_balance, gang_id))
        return new_balance

    async def debit_gang_bank(self, gang_id: int, amount: int) -> int:
        async with self.db.transaction() as connection:
            cursor = await connection.execute("SELECT bank_balance FROM gangs WHERE id = ?", (gang_id,))
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise ValueError(f"Gang {gang_id} not found.")
            current = int(row["bank_balance"])
            if current < amount:
                raise InsufficientFundsError("gang bank", current, amount)
            new_balance = current - amount
            await connection.execute("UPDATE gangs SET bank_balance = ? WHERE id = ?", (new_balance, gang_id))
        return new_balance

    async def credit_treasury(self, guild_id: int, amount: int) -> int:
        async with self.db.transaction() as connection:
            cursor = await connection.execute(
                "SELECT treasury_balance FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
            current = int(row["treasury_balance"]) if row else 0
            new_balance = current + amount
            await connection.execute(
                "UPDATE guild_settings SET treasury_balance = ? WHERE guild_id = ?",
                (new_balance, guild_id),
            )
        return new_balance

    async def debit_treasury(self, guild_id: int, amount: int, *, allow_partial: bool = False) -> tuple[int, int]:
        async with self.db.transaction() as connection:
            cursor = await connection.execute(
                "SELECT treasury_balance FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
            current = int(row["treasury_balance"]) if row else 0
            payout = amount
            if current < amount:
                if not allow_partial:
                    raise InsufficientFundsError("treasury", current, amount)
                payout = current
            new_balance = max(0, current - payout)
            await connection.execute(
                "UPDATE guild_settings SET treasury_balance = ? WHERE guild_id = ?",
                (new_balance, guild_id),
            )
        return payout, new_balance

    async def create_turf(self, guild_id: int, name: str, owner_gang_id: int, hourly_income: int = TURF_HOURLY_INCOME) -> int:
        return await self._insert(
            """
            INSERT INTO turfs (guild_id, name, owner_gang_id, hourly_income)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, name, owner_gang_id, hourly_income),
        )

    async def list_turfs(self, guild_id: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT t.*, g.name AS owner_name
            FROM turfs t
            INNER JOIN gangs g ON g.id = t.owner_gang_id
            WHERE t.guild_id = ?
            ORDER BY t.name
            """,
            (guild_id,),
        )

    async def get_turf(self, turf_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT t.*, g.name AS owner_name
            FROM turfs t
            INNER JOIN gangs g ON g.id = t.owner_gang_id
            WHERE t.id = ?
            """,
            (turf_id,),
        )

    async def get_turf_by_name(self, guild_id: int, name: str) -> dict[str, Any] | None:
        normalized = name.strip().lstrip("#")
        return await self._fetchone(
            """
            SELECT t.*, g.name AS owner_name
            FROM turfs t
            INNER JOIN gangs g ON g.id = t.owner_gang_id
            WHERE t.guild_id = ? AND lower(t.name) = lower(?)
            """,
            (guild_id, normalized),
        )

    async def update_turf_owner(self, turf_id: int, owner_gang_id: int) -> dict[str, Any]:
        await self._update_by_pk("turfs", "id", turf_id, {"owner_gang_id": owner_gang_id})
        return await self.get_turf(turf_id)  # type: ignore[return-value]

    async def create_jail_record(self, guild_id: int, user_id: int, reason: str, release_at: str) -> int:
        return await self._insert(
            """
            INSERT INTO jail_records (guild_id, user_id, reason, release_at, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (guild_id, user_id, reason, release_at, isoformat(utcnow())),
        )

    async def list_active_jails(self, guild_id: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            "SELECT * FROM jail_records WHERE guild_id = ? AND active = 1 ORDER BY release_at",
            (guild_id,),
        )

    async def get_active_jail_for_user(self, guild_id: int, user_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT * FROM jail_records
            WHERE guild_id = ? AND user_id = ? AND active = 1
            ORDER BY id DESC LIMIT 1
            """,
            (guild_id, user_id),
        )

    async def release_jail_record(self, jail_id: int) -> None:
        await self._update_by_pk("jail_records", "id", jail_id, {"active": 0})

    async def create_war(
        self,
        guild_id: int,
        attacker_gang_id: int,
        defender_gang_id: int,
        turf_id: int,
        resolve_at: str,
    ) -> int:
        return await self._insert(
            """
            INSERT INTO wars (guild_id, attacker_gang_id, defender_gang_id, turf_id, status, created_at, resolve_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
            """,
            (guild_id, attacker_gang_id, defender_gang_id, turf_id, isoformat(utcnow()), resolve_at),
        )

    async def get_war(self, war_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM wars WHERE id = ?", (war_id,))

    async def list_active_wars(self, guild_id: int) -> list[dict[str, Any]]:
        return await self._fetchall("SELECT * FROM wars WHERE guild_id = ? AND status = 'active'", (guild_id,))

    async def get_active_war_for_gang(self, guild_id: int, gang_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT * FROM wars
            WHERE guild_id = ? AND status = 'active'
              AND (attacker_gang_id = ? OR defender_gang_id = ?)
            ORDER BY id DESC LIMIT 1
            """,
            (guild_id, gang_id, gang_id),
        )

    async def add_war_participant(
        self,
        war_id: int,
        user_id: int,
        gang_id: int,
        side: str,
        weapons_used: int,
        base_power: float,
        total_power: float,
    ) -> int:
        return await self._insert(
            """
            INSERT INTO war_participants
            (war_id, user_id, gang_id, side, weapons_used, base_power, total_power, committed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (war_id, user_id, gang_id, side, weapons_used, base_power, total_power, isoformat(utcnow())),
        )

    async def get_war_participant(self, war_id: int, user_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            "SELECT * FROM war_participants WHERE war_id = ? AND user_id = ?",
            (war_id, user_id),
        )

    async def list_war_participants(self, war_id: int) -> list[dict[str, Any]]:
        return await self._fetchall("SELECT * FROM war_participants WHERE war_id = ?", (war_id,))

    async def update_war(self, war_id: int, **fields: Any) -> dict[str, Any]:
        await self._update_by_pk("wars", "id", war_id, fields)
        return await self.get_war(war_id)  # type: ignore[return-value]

    async def create_heist(
        self,
        guild_id: int,
        gang_id: int,
        boss_user_id: int,
        planning_channel_id: int,
        launch_deadline: str,
    ) -> int:
        return await self._insert(
            """
            INSERT INTO heists
            (guild_id, gang_id, boss_user_id, planning_channel_id, status, created_at, launch_deadline)
            VALUES (?, ?, ?, ?, 'planning', ?, ?)
            """,
            (guild_id, gang_id, boss_user_id, planning_channel_id, isoformat(utcnow()), launch_deadline),
        )

    async def get_heist(self, heist_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM heists WHERE id = ?", (heist_id,))

    async def get_active_heist_for_gang(self, guild_id: int, gang_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT * FROM heists
            WHERE guild_id = ? AND gang_id = ? AND status IN ('planning', 'ready', 'executing')
            ORDER BY id DESC LIMIT 1
            """,
            (guild_id, gang_id),
        )

    async def list_active_heists(self, guild_id: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT * FROM heists
            WHERE guild_id = ? AND status IN ('planning', 'ready', 'executing')
            ORDER BY id DESC
            """,
            (guild_id,),
        )

    async def find_active_heist_for_member(self, user_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT * FROM heists
            WHERE status = 'executing'
              AND (? IN (hacker_id, driver_id, inside_id))
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        )

    async def update_heist(self, heist_id: int, **fields: Any) -> dict[str, Any]:
        await self._update_by_pk("heists", "id", heist_id, fields)
        return await self.get_heist(heist_id)  # type: ignore[return-value]

    async def create_vote(
        self,
        guild_id: int,
        vote_type: str,
        target_user_id: int,
        gang_id: int,
        initiator_user_id: int,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        return await self._insert(
            """
            INSERT INTO votes
            (guild_id, vote_type, target_user_id, gang_id, initiator_user_id, status, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                guild_id,
                vote_type,
                target_user_id,
                gang_id,
                initiator_user_id,
                isoformat(utcnow()),
                json.dumps(metadata or {}),
            ),
        )

    async def get_active_vote(self, guild_id: int, vote_type: str, gang_id: int, target_user_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT * FROM votes
            WHERE guild_id = ? AND vote_type = ? AND gang_id = ? AND target_user_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
            """,
            (guild_id, vote_type, gang_id, target_user_id),
        )

    async def get_vote(self, vote_id: int) -> dict[str, Any] | None:
        vote = await self._fetchone("SELECT * FROM votes WHERE id = ?", (vote_id,))
        if vote and vote["metadata_json"]:
            vote["metadata"] = json.loads(vote["metadata_json"])
        elif vote:
            vote["metadata"] = {}
        return vote

    async def cast_vote(self, vote_id: int, voter_user_id: int, vote: str) -> None:
        await self.db.execute(
            """
            INSERT INTO vote_entries (vote_id, voter_user_id, vote, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (vote_id, voter_user_id) DO NOTHING
            """,
            (vote_id, voter_user_id, vote, isoformat(utcnow())),
        )

    async def list_vote_entries(self, vote_id: int) -> list[dict[str, Any]]:
        return await self._fetchall("SELECT * FROM vote_entries WHERE vote_id = ?", (vote_id,))

    async def update_vote(self, vote_id: int, **fields: Any) -> dict[str, Any]:
        if "metadata" in fields:
            fields["metadata_json"] = json.dumps(fields.pop("metadata"))
        await self._update_by_pk("votes", "id", vote_id, fields)
        return await self.get_vote(vote_id)  # type: ignore[return-value]

    async def create_bribe(self, guild_id: int, briber_user_id: int, mayor_user_id: int, amount: int, request_text: str | None = None) -> int:
        return await self._insert(
            """
            INSERT INTO bribes (guild_id, briber_user_id, mayor_user_id, amount, status, request_text, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (guild_id, briber_user_id, mayor_user_id, amount, request_text, isoformat(utcnow())),
        )

    async def get_bribe(self, bribe_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM bribes WHERE id = ?", (bribe_id,))

    async def update_bribe(self, bribe_id: int, **fields: Any) -> dict[str, Any]:
        await self._update_by_pk("bribes", "id", bribe_id, fields)
        return await self.get_bribe(bribe_id)  # type: ignore[return-value]

    # ── City Events ──────────────────────────────────────────────

    async def get_active_city_event(self, guild_id: int) -> CityEvent | None:
        now = isoformat(utcnow()) or ""
        row = await self._fetchone(
            """
            SELECT * FROM city_events
            WHERE guild_id = ? AND ends_at > ?
            ORDER BY id DESC LIMIT 1
            """,
            (guild_id, now),
        )
        if row is None:
            return None
        return self._row_to_city_event(row)

    async def replace_active_city_event(
        self,
        guild_id: int,
        *,
        event_key: str,
        headline: str,
        description: str,
        effect: CityEventEffect,
        starts_at: str,
        ends_at: str,
    ) -> CityEvent:
        now = isoformat(utcnow()) or ""
        async with self.db.transaction() as connection:
            await connection.execute(
                "DELETE FROM city_events WHERE guild_id = ?",
                (guild_id,),
            )
            await connection.execute(
                """
                INSERT INTO city_events
                (guild_id, event_key, headline, description, effect_json, starts_at, ends_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    event_key,
                    headline,
                    description,
                    json.dumps(effect.to_payload()),
                    starts_at,
                    ends_at,
                    now,
                ),
            )
            cursor = await connection.execute(
                "SELECT * FROM city_events WHERE guild_id = ? ORDER BY id DESC LIMIT 1",
                (guild_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if row is None:
            raise RuntimeError("Failed to insert city event.")
        return self._row_to_city_event(dict(row))

    def _row_to_city_event(self, row: dict[str, Any]) -> CityEvent:
        effect_data = json.loads(row["effect_json"]) if isinstance(row["effect_json"], str) else row["effect_json"]
        return CityEvent(
            guild_id=int(row["guild_id"]),
            event_key=str(row["event_key"]),
            headline=str(row["headline"]),
            description=str(row["description"]),
            effect=CityEventEffect.from_payload(effect_data),
            starts_at=parse_datetime(row["starts_at"]) or utcnow(),
            ends_at=parse_datetime(row["ends_at"]) or utcnow(),
            created_at=parse_datetime(row["created_at"]) or utcnow(),
        )

    async def _update_by_pk(self, table: str, pk_column: str, pk_value: Any, fields: dict[str, Any]) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{column} = ?" for column in fields)
        params = list(fields.values()) + [pk_value]
        await self.db.execute(f"UPDATE {table} SET {assignments} WHERE {pk_column} = ?", params)

    async def _update_compound_pk(
        self,
        table: str,
        pk_a: tuple[str, Any],
        pk_b: tuple[str, Any],
        fields: dict[str, Any],
    ) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{column} = ?" for column in fields)
        params = list(fields.values()) + [pk_a[1], pk_b[1]]
        await self.db.execute(
            f"UPDATE {table} SET {assignments} WHERE {pk_a[0]} = ? AND {pk_b[0]} = ?",
            params,
        )

    async def _ensure_players_columns(self) -> None:
        rows = await self.db.execute_fetchall("PRAGMA table_info(players)")
        existing = {str(row["name"]) for row in rows}
        if "last_daily_claim_at" not in existing:
            await self.db.execute("ALTER TABLE players ADD COLUMN last_daily_claim_at TEXT")
        if "daily_streak" not in existing:
            await self.db.execute("ALTER TABLE players ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0")
