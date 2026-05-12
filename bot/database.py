"""
Phosphorus – async SQLite database layer.
Single connection pool via aiosqlite; WAL mode for concurrent reads.
"""
from __future__ import annotations

import aiosqlite
import asyncio
import math
from typing import Optional

from constants import (
    DB_PATH,
    DB_PRAGMAS,
    XP_BASE,
    XP_EXPONENT,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """Total XP needed to *reach* `level` from 0."""
    if level <= 0:
        return 0
    return math.floor(XP_BASE * (level ** XP_EXPONENT))


def level_from_xp(total_xp: int) -> int:
    """Current level derived from cumulative XP."""
    level = 0
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


def xp_progress(total_xp: int) -> tuple[int, int, int]:
    """
    Returns (current_level, xp_into_level, xp_needed_for_next_level).
    Useful for displaying a progress bar.
    """
    level = level_from_xp(total_xp)
    xp_start = xp_for_level(level)
    xp_end = xp_for_level(level + 1)
    return level, total_xp - xp_start, xp_end - xp_start


# ── database class ────────────────────────────────────────────────────────────

class Database:
    """Manages the SQLite connection and all queries."""

    def __init__(self, path: str = DB_PATH) -> None:
        self._path = path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        for pragma, value in DB_PRAGMAS.items():
            await self._conn.execute(f"PRAGMA {pragma} = {value}")
        await self._conn.commit()
        await self._create_tables()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # ── schema ───────────────────────────────────────────────────────────────

    async def _create_tables(self) -> None:
        assert self._conn
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                guild_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                xp         INTEGER NOT NULL DEFAULT 0,
                last_xp_at REAL    NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id          INTEGER PRIMARY KEY,
                levelup_channel   INTEGER,
                xp_multiplier     REAL NOT NULL DEFAULT 1.0,
                announce_levelup  INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS role_rewards (
                guild_id INTEGER NOT NULL,
                level    INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, level)
            );

            CREATE INDEX IF NOT EXISTS idx_users_guild_xp
                ON users (guild_id, xp DESC);
        """)
        await self._conn.commit()

    # ── user XP ──────────────────────────────────────────────────────────────

    async def get_user(self, guild_id: int, user_id: int) -> Optional[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            return await cur.fetchone()

    async def add_xp(
        self, guild_id: int, user_id: int, xp: int, now: float
    ) -> tuple[int, int, bool]:
        """
        Upsert XP, return (new_total_xp, new_level, leveled_up).
        Thread-safe via asyncio lock.
        """
        assert self._conn
        async with self._lock:
            row = await self.get_user(guild_id, user_id)
            old_xp = row["xp"] if row else 0
            old_level = level_from_xp(old_xp)
            new_xp = old_xp + xp
            new_level = level_from_xp(new_xp)

            await self._conn.execute(
                """
                INSERT INTO users (guild_id, user_id, xp, last_xp_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    xp         = excluded.xp,
                    last_xp_at = excluded.last_xp_at
                """,
                (guild_id, user_id, new_xp, now),
            )
            await self._conn.commit()
        return new_xp, new_level, new_level > old_level

    async def set_xp(self, guild_id: int, user_id: int, xp: int) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO users (guild_id, user_id, xp, last_xp_at)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp
            """,
            (guild_id, user_id, xp),
        )
        await self._conn.commit()

    async def reset_user(self, guild_id: int, user_id: int) -> None:
        assert self._conn
        await self._conn.execute(
            "UPDATE users SET xp = 0, last_xp_at = 0 WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await self._conn.commit()

    async def get_last_xp_at(self, guild_id: int, user_id: int) -> float:
        assert self._conn
        async with self._conn.execute(
            "SELECT last_xp_at FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            return row["last_xp_at"] if row else 0.0

    # ── leaderboard ──────────────────────────────────────────────────────────

    async def get_leaderboard(
        self, guild_id: int, limit: int, offset: int = 0
    ) -> list[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT user_id, xp FROM users WHERE guild_id = ? ORDER BY xp DESC LIMIT ? OFFSET ?",
            (guild_id, limit, offset),
        ) as cur:
            return await cur.fetchall()

    async def get_rank(self, guild_id: int, user_id: int) -> int:
        """1-indexed rank of the user in the guild."""
        assert self._conn
        row = await self.get_user(guild_id, user_id)
        if not row:
            return 0
        async with self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE guild_id = ? AND xp > ?",
            (guild_id, row["xp"]),
        ) as cur:
            result = await cur.fetchone()
            return (result["cnt"] if result else 0) + 1

    async def get_guild_member_count(self, guild_id: int) -> int:
        assert self._conn
        async with self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    # ── guild config ─────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> Optional[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return await cur.fetchone()

    async def set_levelup_channel(
        self, guild_id: int, channel_id: Optional[int]
    ) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO guild_config (guild_id, levelup_channel)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET levelup_channel = excluded.levelup_channel
            """,
            (guild_id, channel_id),
        )
        await self._conn.commit()

    async def set_multiplier(self, guild_id: int, multiplier: float) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO guild_config (guild_id, xp_multiplier)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET xp_multiplier = excluded.xp_multiplier
            """,
            (guild_id, multiplier),
        )
        await self._conn.commit()

    async def get_multiplier(self, guild_id: int) -> float:
        cfg = await self.get_config(guild_id)
        return cfg["xp_multiplier"] if cfg else 1.0

    # ── role rewards ─────────────────────────────────────────────────────────

    async def add_role_reward(
        self, guild_id: int, level: int, role_id: int
    ) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO role_rewards (guild_id, level, role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id
            """,
            (guild_id, level, role_id),
        )
        await self._conn.commit()

    async def remove_role_reward(self, guild_id: int, level: int) -> bool:
        assert self._conn
        cur = await self._conn.execute(
            "DELETE FROM role_rewards WHERE guild_id = ? AND level = ?",
            (guild_id, level),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def get_role_rewards(self, guild_id: int) -> list[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT level, role_id FROM role_rewards WHERE guild_id = ? ORDER BY level",
            (guild_id,),
        ) as cur:
            return await cur.fetchall()

    async def get_role_reward_for_level(
        self, guild_id: int, level: int
    ) -> Optional[int]:
        assert self._conn
        async with self._conn.execute(
            "SELECT role_id FROM role_rewards WHERE guild_id = ? AND level = ?",
            (guild_id, level),
        ) as cur:
            row = await cur.fetchone()
            return row["role_id"] if row else None
