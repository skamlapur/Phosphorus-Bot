"""
Phosphorus – async SQLite database layer (v2)
"""
from __future__ import annotations

import aiosqlite
import asyncio
import math
from datetime import date, datetime, timedelta
from typing import Optional

from constants import (
    DB_PATH,
    DB_PRAGMAS,
    XP_BASE,
    XP_EXPONENT,
)


# ── XP / level math ───────────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    if level <= 0:
        return 0
    return math.floor(XP_BASE * (level ** XP_EXPONENT))


def level_from_xp(total_xp: int) -> int:
    level = 0
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


def xp_progress(total_xp: int) -> tuple[int, int, int]:
    level = level_from_xp(total_xp)
    xp_start = xp_for_level(level)
    xp_end = xp_for_level(level + 1)
    return level, total_xp - xp_start, xp_end - xp_start


def current_week() -> str:
    """ISO week string: YYYY-WW"""
    today = date.today()
    return f"{today.isocalendar()[0]:04d}-{today.isocalendar()[1]:02d}"


def today_str() -> str:
    return date.today().isoformat()


# ── Database ──────────────────────────────────────────────────────────────────

class Database:

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
        await self._migrate()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # ── schema ───────────────────────────────────────────────────────────────

    async def _create_tables(self) -> None:
        assert self._conn
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                guild_id      INTEGER NOT NULL,
                user_id       INTEGER NOT NULL,
                xp            INTEGER NOT NULL DEFAULT 0,
                msg_count     INTEGER NOT NULL DEFAULT 0,
                voice_minutes INTEGER NOT NULL DEFAULT 0,
                last_xp_at    REAL    NOT NULL DEFAULT 0,
                last_active   TEXT    NOT NULL DEFAULT '',
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id          INTEGER PRIMARY KEY,
                levelup_channel   INTEGER,
                weekly_channel    INTEGER,
                drops_channel     INTEGER,
                xp_multiplier     REAL    NOT NULL DEFAULT 1.0,
                voice_xp_enabled  INTEGER NOT NULL DEFAULT 1,
                drops_enabled     INTEGER NOT NULL DEFAULT 0,
                drops_interval    INTEGER NOT NULL DEFAULT 20
            );

            CREATE TABLE IF NOT EXISTS role_rewards (
                guild_id INTEGER NOT NULL,
                level    INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, level)
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                guild_id    INTEGER NOT NULL,
                entity_type TEXT    NOT NULL,
                entity_id   INTEGER NOT NULL,
                PRIMARY KEY (guild_id, entity_type, entity_id)
            );

            CREATE TABLE IF NOT EXISTS entity_multipliers (
                guild_id    INTEGER NOT NULL,
                entity_type TEXT    NOT NULL,
                entity_id   INTEGER NOT NULL,
                multiplier  REAL    NOT NULL,
                PRIMARY KEY (guild_id, entity_type, entity_id)
            );

            CREATE TABLE IF NOT EXISTS voice_sessions (
                guild_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                joined_at  REAL    NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS weekly_stats (
                guild_id      INTEGER NOT NULL,
                user_id       INTEGER NOT NULL,
                week          TEXT    NOT NULL,
                xp            INTEGER NOT NULL DEFAULT 0,
                messages      INTEGER NOT NULL DEFAULT 0,
                voice_minutes INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, week)
            );

            CREATE TABLE IF NOT EXISTS streaks (
                guild_id        INTEGER NOT NULL,
                user_id         INTEGER NOT NULL,
                current_streak  INTEGER NOT NULL DEFAULT 0,
                longest_streak  INTEGER NOT NULL DEFAULT 0,
                last_active_date TEXT   NOT NULL DEFAULT '',
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS drops (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                question    TEXT    NOT NULL,
                answer      TEXT    NOT NULL,
                xp_amount   INTEGER NOT NULL,
                winner_id   INTEGER,
                message_id  INTEGER,
                claimed_at  REAL,
                created_at  REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bot_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS permits (
                guild_id     INTEGER NOT NULL,
                command_name TEXT    NOT NULL,
                entity_type  TEXT    NOT NULL,
                entity_id    INTEGER NOT NULL,
                PRIMARY KEY (guild_id, command_name, entity_type, entity_id)
            );

            CREATE TABLE IF NOT EXISTS boosters (
                guild_id    INTEGER NOT NULL,
                entity_type TEXT    NOT NULL,
                entity_id   INTEGER NOT NULL,
                multiplier  REAL    NOT NULL DEFAULT 1.5,
                PRIMARY KEY (guild_id, entity_type, entity_id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_guild_xp
                ON users (guild_id, xp DESC);
            CREATE INDEX IF NOT EXISTS idx_weekly_guild_week_xp
                ON weekly_stats (guild_id, week, xp DESC);
            CREATE INDEX IF NOT EXISTS idx_weekly_guild_week_msg
                ON weekly_stats (guild_id, week, messages DESC);
            CREATE INDEX IF NOT EXISTS idx_weekly_guild_week_voice
                ON weekly_stats (guild_id, week, voice_minutes DESC);
        """)
        await self._conn.commit()

    async def _migrate(self) -> None:
        """Add columns and indexes that didn't exist in v1 of the schema."""
        assert self._conn
        cols_to_add = [
            ("users", "msg_count",     "INTEGER NOT NULL DEFAULT 0"),
            ("users", "voice_minutes", "INTEGER NOT NULL DEFAULT 0"),
            ("users", "last_active",   "TEXT NOT NULL DEFAULT ''"),
            ("guild_config", "weekly_channel",   "INTEGER"),
            ("guild_config", "drops_channel",    "INTEGER"),
            ("guild_config", "voice_xp_enabled", "INTEGER NOT NULL DEFAULT 1"),
            ("guild_config", "drops_enabled",    "INTEGER NOT NULL DEFAULT 0"),
            ("guild_config", "drops_interval",   "INTEGER NOT NULL DEFAULT 20"),
        ]
        for table, col, col_def in cols_to_add:
            try:
                await self._conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"
                )
            except Exception:
                pass  # column already exists
        await self._conn.commit()

        # Add indexes for new columns (safe to retry — IF NOT EXISTS)
        new_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_guild_msg ON users (guild_id, msg_count DESC)",
            "CREATE INDEX IF NOT EXISTS idx_users_guild_voice ON users (guild_id, voice_minutes DESC)",
        ]
        for sql in new_indexes:
            try:
                await self._conn.execute(sql)
            except Exception:
                pass
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
        self, guild_id: int, user_id: int, xp: int, now: float, is_message: bool = True
    ) -> tuple[int, int, bool]:
        """Upsert XP. Returns (new_total_xp, new_level, leveled_up)."""
        assert self._conn
        async with self._lock:
            row = await self.get_user(guild_id, user_id)
            old_xp = row["xp"] if row else 0
            old_level = level_from_xp(old_xp)
            new_xp = old_xp + xp
            new_level = level_from_xp(new_xp)
            msg_delta = 1 if is_message else 0

            await self._conn.execute(
                """
                INSERT INTO users (guild_id, user_id, xp, msg_count, last_xp_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    xp         = excluded.xp,
                    msg_count  = msg_count + ?,
                    last_xp_at = excluded.last_xp_at,
                    last_active = excluded.last_active
                """,
                (guild_id, user_id, new_xp, msg_delta, now, today_str(), msg_delta),
            )
            await self._conn.commit()
        return new_xp, new_level, new_level > old_level

    async def add_voice_minutes(self, guild_id: int, user_id: int, minutes: int, xp: int) -> tuple[int, int, bool]:
        """Award voice XP and increment voice_minutes. Returns (new_xp, new_level, leveled_up)."""
        assert self._conn
        import time as _time
        now = _time.time()
        async with self._lock:
            row = await self.get_user(guild_id, user_id)
            old_xp = row["xp"] if row else 0
            old_level = level_from_xp(old_xp)
            new_xp = old_xp + xp
            new_level = level_from_xp(new_xp)

            await self._conn.execute(
                """
                INSERT INTO users (guild_id, user_id, xp, voice_minutes, last_xp_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    xp            = excluded.xp,
                    voice_minutes = voice_minutes + ?,
                    last_xp_at    = excluded.last_xp_at,
                    last_active   = excluded.last_active
                """,
                (guild_id, user_id, new_xp, minutes, now, today_str(), minutes),
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
            (guild_id, user_id, max(0, xp)),
        )
        await self._conn.commit()

    async def reset_user(self, guild_id: int, user_id: int) -> None:
        assert self._conn
        await self._conn.execute(
            "UPDATE users SET xp = 0, msg_count = 0, voice_minutes = 0, last_xp_at = 0 "
            "WHERE guild_id = ? AND user_id = ?",
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
        self, guild_id: int, sort_col: str, limit: int, offset: int = 0
    ) -> list[aiosqlite.Row]:
        assert self._conn
        safe_cols = {"xp", "msg_count", "voice_minutes"}
        col = sort_col if sort_col in safe_cols else "xp"
        async with self._conn.execute(
            f"SELECT user_id, xp, msg_count, voice_minutes FROM users "
            f"WHERE guild_id = ? ORDER BY {col} DESC LIMIT ? OFFSET ?",
            (guild_id, limit, offset),
        ) as cur:
            return await cur.fetchall()

    async def get_weekly_leaderboard(
        self, guild_id: int, week: str, sort_col: str, limit: int, offset: int = 0
    ) -> list[aiosqlite.Row]:
        assert self._conn
        safe_cols = {"xp", "messages", "voice_minutes"}
        col = sort_col if sort_col in safe_cols else "xp"
        async with self._conn.execute(
            f"SELECT user_id, xp, messages, voice_minutes FROM weekly_stats "
            f"WHERE guild_id = ? AND week = ? ORDER BY {col} DESC LIMIT ? OFFSET ?",
            (guild_id, week, limit, offset),
        ) as cur:
            return await cur.fetchall()

    async def get_rank(self, guild_id: int, user_id: int, col: str = "xp") -> int:
        assert self._conn
        safe_cols = {"xp", "msg_count", "voice_minutes"}
        col = col if col in safe_cols else "xp"
        row = await self.get_user(guild_id, user_id)
        if not row:
            return 0
        async with self._conn.execute(
            f"SELECT COUNT(*) AS cnt FROM users WHERE guild_id = ? AND {col} > ?",
            (guild_id, row[col]),
        ) as cur:
            result = await cur.fetchone()
            return (result["cnt"] if result else 0) + 1

    async def get_guild_member_count(self, guild_id: int) -> int:
        assert self._conn
        async with self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def get_weekly_member_count(self, guild_id: int, week: str) -> int:
        assert self._conn
        async with self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM weekly_stats WHERE guild_id = ? AND week = ?",
            (guild_id, week),
        ) as cur:
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    # ── weekly stats ─────────────────────────────────────────────────────────

    async def add_weekly_xp(
        self, guild_id: int, user_id: int, week: str, xp: int,
        messages: int = 0, voice_minutes: int = 0
    ) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO weekly_stats (guild_id, user_id, week, xp, messages, voice_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, week) DO UPDATE SET
                xp            = xp + excluded.xp,
                messages      = messages + excluded.messages,
                voice_minutes = voice_minutes + excluded.voice_minutes
            """,
            (guild_id, user_id, week, xp, messages, voice_minutes),
        )
        await self._conn.commit()

    # ── guild config ─────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> Optional[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return await cur.fetchone()

    async def _upsert_config(self, guild_id: int, col: str, value) -> None:
        assert self._conn
        await self._conn.execute(
            f"""
            INSERT INTO guild_config (guild_id, {col}) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {col} = excluded.{col}
            """,
            (guild_id, value),
        )
        await self._conn.commit()

    async def set_levelup_channel(self, guild_id: int, channel_id: Optional[int]) -> None:
        await self._upsert_config(guild_id, "levelup_channel", channel_id)

    async def set_weekly_channel(self, guild_id: int, channel_id: Optional[int]) -> None:
        await self._upsert_config(guild_id, "weekly_channel", channel_id)

    async def set_drops_channel(self, guild_id: int, channel_id: Optional[int]) -> None:
        await self._upsert_config(guild_id, "drops_channel", channel_id)

    async def set_multiplier(self, guild_id: int, multiplier: float) -> None:
        await self._upsert_config(guild_id, "xp_multiplier", multiplier)

    async def set_voice_xp_enabled(self, guild_id: int, enabled: bool) -> None:
        await self._upsert_config(guild_id, "voice_xp_enabled", int(enabled))

    async def set_drops_enabled(self, guild_id: int, enabled: bool) -> None:
        await self._upsert_config(guild_id, "drops_enabled", int(enabled))

    async def get_multiplier(self, guild_id: int) -> float:
        cfg = await self.get_config(guild_id)
        return cfg["xp_multiplier"] if cfg else 1.0

    # ── role rewards ─────────────────────────────────────────────────────────

    async def add_role_reward(self, guild_id: int, level: int, role_id: int) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO role_rewards (guild_id, level, role_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id
            """,
            (guild_id, level, role_id),
        )
        await self._conn.commit()

    async def remove_role_reward(self, guild_id: int, level: int) -> bool:
        assert self._conn
        cur = await self._conn.execute(
            "DELETE FROM role_rewards WHERE guild_id = ? AND level = ?", (guild_id, level)
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

    async def get_role_reward_for_level(self, guild_id: int, level: int) -> Optional[int]:
        assert self._conn
        async with self._conn.execute(
            "SELECT role_id FROM role_rewards WHERE guild_id = ? AND level = ?",
            (guild_id, level),
        ) as cur:
            row = await cur.fetchone()
            return row["role_id"] if row else None

    # ── blacklist ─────────────────────────────────────────────────────────────

    async def add_blacklist(self, guild_id: int, entity_type: str, entity_id: int) -> None:
        assert self._conn
        await self._conn.execute(
            "INSERT OR IGNORE INTO blacklist (guild_id, entity_type, entity_id) VALUES (?,?,?)",
            (guild_id, entity_type, entity_id),
        )
        await self._conn.commit()

    async def remove_blacklist(self, guild_id: int, entity_type: str, entity_id: int) -> bool:
        assert self._conn
        cur = await self._conn.execute(
            "DELETE FROM blacklist WHERE guild_id=? AND entity_type=? AND entity_id=?",
            (guild_id, entity_type, entity_id),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def is_blacklisted(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        role_ids: list[int],
    ) -> bool:
        assert self._conn
        # Check user
        async with self._conn.execute(
            "SELECT 1 FROM blacklist WHERE guild_id=? AND entity_type='user' AND entity_id=?",
            (guild_id, user_id),
        ) as cur:
            if await cur.fetchone():
                return True
        # Check channel
        async with self._conn.execute(
            "SELECT 1 FROM blacklist WHERE guild_id=? AND entity_type='channel' AND entity_id=?",
            (guild_id, channel_id),
        ) as cur:
            if await cur.fetchone():
                return True
        # Check roles
        if role_ids:
            placeholders = ",".join("?" * len(role_ids))
            async with self._conn.execute(
                f"SELECT 1 FROM blacklist WHERE guild_id=? AND entity_type='role' "
                f"AND entity_id IN ({placeholders}) LIMIT 1",
                [guild_id] + role_ids,
            ) as cur:
                if await cur.fetchone():
                    return True
        return False

    async def get_blacklist(self, guild_id: int) -> list[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT entity_type, entity_id FROM blacklist WHERE guild_id=? ORDER BY entity_type",
            (guild_id,),
        ) as cur:
            return await cur.fetchall()

    # ── entity multipliers ───────────────────────────────────────────────────

    async def set_entity_multiplier(
        self, guild_id: int, entity_type: str, entity_id: int, multiplier: float
    ) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO entity_multipliers (guild_id, entity_type, entity_id, multiplier)
            VALUES (?,?,?,?)
            ON CONFLICT(guild_id, entity_type, entity_id) DO UPDATE SET multiplier = excluded.multiplier
            """,
            (guild_id, entity_type, entity_id, multiplier),
        )
        await self._conn.commit()

    async def remove_entity_multiplier(
        self, guild_id: int, entity_type: str, entity_id: int
    ) -> bool:
        assert self._conn
        cur = await self._conn.execute(
            "DELETE FROM entity_multipliers WHERE guild_id=? AND entity_type=? AND entity_id=?",
            (guild_id, entity_type, entity_id),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def compute_multiplier(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        role_ids: list[int],
    ) -> float:
        """Compute effective multiplier: server * max(per-entity overrides, 1.0)."""
        server_mult = await self.get_multiplier(guild_id)
        assert self._conn

        # Collect entity multipliers for user, channel, and roles
        all_ids = [user_id, channel_id] + role_ids
        all_types = (
            ["user"] + ["channel"] + ["role"] * len(role_ids)
        )
        entity_mult = 1.0
        for etype, eid in zip(all_types, all_ids):
            async with self._conn.execute(
                "SELECT multiplier FROM entity_multipliers "
                "WHERE guild_id=? AND entity_type=? AND entity_id=?",
                (guild_id, etype, eid),
            ) as cur:
                row = await cur.fetchone()
                if row:
                    entity_mult = max(entity_mult, row["multiplier"])

        return round(server_mult * entity_mult, 4)

    async def get_entity_multipliers(self, guild_id: int) -> list[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT entity_type, entity_id, multiplier FROM entity_multipliers "
            "WHERE guild_id=? ORDER BY entity_type, entity_id",
            (guild_id,),
        ) as cur:
            return await cur.fetchall()

    # ── voice sessions ────────────────────────────────────────────────────────

    async def set_voice_session(
        self, guild_id: int, user_id: int, channel_id: int, joined_at: float
    ) -> None:
        assert self._conn
        await self._conn.execute(
            """
            INSERT INTO voice_sessions (guild_id, user_id, channel_id, joined_at)
            VALUES (?,?,?,?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                joined_at  = excluded.joined_at
            """,
            (guild_id, user_id, channel_id, joined_at),
        )
        await self._conn.commit()

    async def delete_voice_session(self, guild_id: int, user_id: int) -> None:
        assert self._conn
        await self._conn.execute(
            "DELETE FROM voice_sessions WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )
        await self._conn.commit()

    async def get_active_voice_sessions(self) -> list[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT guild_id, user_id, channel_id, joined_at FROM voice_sessions"
        ) as cur:
            return await cur.fetchall()

    async def get_voice_session(self, guild_id: int, user_id: int) -> Optional[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM voice_sessions WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        ) as cur:
            return await cur.fetchone()

    # ── streaks ───────────────────────────────────────────────────────────────

    async def get_streak(self, guild_id: int, user_id: int) -> Optional[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM streaks WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        ) as cur:
            return await cur.fetchone()

    async def update_streak(self, guild_id: int, user_id: int) -> tuple[int, bool]:
        """Update streak for today. Returns (current_streak, is_new_day)."""
        assert self._conn
        today = today_str()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        row = await self.get_streak(guild_id, user_id)
        if not row:
            await self._conn.execute(
                "INSERT INTO streaks (guild_id, user_id, current_streak, longest_streak, last_active_date) "
                "VALUES (?,?,1,1,?)",
                (guild_id, user_id, today),
            )
            await self._conn.commit()
            return 1, True

        last = row["last_active_date"]
        if last == today:
            return row["current_streak"], False
        elif last == yesterday:
            new_streak = row["current_streak"] + 1
        else:
            new_streak = 1

        longest = max(row["longest_streak"], new_streak)
        await self._conn.execute(
            "UPDATE streaks SET current_streak=?, longest_streak=?, last_active_date=? "
            "WHERE guild_id=? AND user_id=?",
            (new_streak, longest, today, guild_id, user_id),
        )
        await self._conn.commit()
        return new_streak, True

    # ── drops ────────────────────────────────────────────────────────────────

    async def create_drop(
        self,
        guild_id: int,
        channel_id: int,
        question: str,
        answer: str,
        xp_amount: int,
        created_at: float,
    ) -> int:
        assert self._conn
        cur = await self._conn.execute(
            "INSERT INTO drops (guild_id, channel_id, question, answer, xp_amount, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (guild_id, channel_id, question, answer, xp_amount, created_at),
        )
        await self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    async def get_pending_drop(self, guild_id: int) -> Optional[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM drops WHERE guild_id=? AND winner_id IS NULL "
            "AND message_id IS NOT NULL ORDER BY created_at DESC LIMIT 1",
            (guild_id,),
        ) as cur:
            return await cur.fetchone()

    async def get_unposted_drop(self, guild_id: int) -> Optional[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM drops WHERE guild_id=? AND winner_id IS NULL "
            "AND message_id IS NULL ORDER BY created_at ASC LIMIT 1",
            (guild_id,),
        ) as cur:
            return await cur.fetchone()

    async def set_drop_message_id(self, drop_id: int, message_id: int) -> None:
        assert self._conn
        await self._conn.execute(
            "UPDATE drops SET message_id=? WHERE id=?", (message_id, drop_id)
        )
        await self._conn.commit()

    async def claim_drop(self, drop_id: int, winner_id: int, claimed_at: float) -> None:
        assert self._conn
        await self._conn.execute(
            "UPDATE drops SET winner_id=?, claimed_at=? WHERE id=?",
            (winner_id, claimed_at, drop_id),
        )
        await self._conn.commit()

    # ── boosters ──────────────────────────────────────────────────────────────

    async def add_booster(
        self,
        guild_id: int,
        entity_type: str,
        entity_id: int,
        multiplier: float,
        max_roles: int,
        max_channels: int,
    ) -> bool:
        """Insert or update a booster. Returns False if the limit is hit for new entries."""
        assert self._conn
        limit = max_roles if entity_type == "role" else max_channels
        async with self._conn.execute(
            "SELECT entity_id FROM boosters WHERE guild_id=? AND entity_type=?",
            (guild_id, entity_type),
        ) as cur:
            existing = [row["entity_id"] for row in await cur.fetchall()]
        if entity_id not in existing and len(existing) >= limit:
            return False
        await self._conn.execute(
            "INSERT INTO boosters (guild_id, entity_type, entity_id, multiplier) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id, entity_type, entity_id) DO UPDATE SET multiplier=excluded.multiplier",
            (guild_id, entity_type, entity_id, round(multiplier, 2)),
        )
        await self._conn.commit()
        return True

    async def remove_booster(
        self, guild_id: int, entity_type: str, entity_id: int
    ) -> bool:
        assert self._conn
        cur = await self._conn.execute(
            "DELETE FROM boosters WHERE guild_id=? AND entity_type=? AND entity_id=?",
            (guild_id, entity_type, entity_id),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def get_boosters(self, guild_id: int) -> list[aiosqlite.Row]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM boosters WHERE guild_id=? ORDER BY entity_type, entity_id",
            (guild_id,),
        ) as cur:
            return list(await cur.fetchall())

    async def get_booster_multiplier(
        self, guild_id: int, channel_id: int, role_ids: list[int]
    ) -> float:
        """Return the highest applicable booster multiplier (1.0 if none)."""
        assert self._conn
        best = 1.0
        async with self._conn.execute(
            "SELECT multiplier FROM boosters WHERE guild_id=? AND entity_type='channel' AND entity_id=?",
            (guild_id, channel_id),
        ) as cur:
            row = await cur.fetchone()
            if row:
                best = max(best, row["multiplier"])
        if role_ids:
            placeholders = ",".join("?" * len(role_ids))
            async with self._conn.execute(
                f"SELECT MAX(multiplier) AS m FROM boosters "
                f"WHERE guild_id=? AND entity_type='role' AND entity_id IN ({placeholders})",
                (guild_id, *role_ids),
            ) as cur:
                row = await cur.fetchone()
                if row and row["m"]:
                    best = max(best, row["m"])
        return best

    # ── permits ───────────────────────────────────────────────────────────────

    async def add_permit(
        self, guild_id: int, command_name: str, entity_type: str, entity_id: int
    ) -> None:
        assert self._conn
        await self._conn.execute(
            "INSERT OR IGNORE INTO permits (guild_id, command_name, entity_type, entity_id) "
            "VALUES (?,?,?,?)",
            (guild_id, command_name, entity_type, entity_id),
        )
        await self._conn.commit()

    async def remove_permit(
        self, guild_id: int, command_name: str, entity_type: str, entity_id: int
    ) -> bool:
        assert self._conn
        cur = await self._conn.execute(
            "DELETE FROM permits WHERE guild_id=? AND command_name=? "
            "AND entity_type=? AND entity_id=?",
            (guild_id, command_name, entity_type, entity_id),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def get_permits(
        self, guild_id: int, command_name: Optional[str] = None
    ) -> list[aiosqlite.Row]:
        assert self._conn
        if command_name:
            async with self._conn.execute(
                "SELECT * FROM permits WHERE guild_id=? AND command_name=? "
                "ORDER BY command_name, entity_type, entity_id",
                (guild_id, command_name),
            ) as cur:
                return list(await cur.fetchall())
        async with self._conn.execute(
            "SELECT * FROM permits WHERE guild_id=? "
            "ORDER BY command_name, entity_type, entity_id",
            (guild_id,),
        ) as cur:
            return list(await cur.fetchall())

    async def has_permit(
        self,
        guild_id: int,
        command_name: str,
        user_id: int,
        role_ids: list[int],
    ) -> bool:
        assert self._conn
        async with self._conn.execute(
            "SELECT 1 FROM permits WHERE guild_id=? AND command_name=? "
            "AND entity_type='user' AND entity_id=?",
            (guild_id, command_name, user_id),
        ) as cur:
            if await cur.fetchone():
                return True
        if role_ids:
            placeholders = ",".join("?" * len(role_ids))
            async with self._conn.execute(
                f"SELECT 1 FROM permits WHERE guild_id=? AND command_name=? "
                f"AND entity_type='role' AND entity_id IN ({placeholders})",
                (guild_id, command_name, *role_ids),
            ) as cur:
                if await cur.fetchone():
                    return True
        return False

    # ── bot meta ──────────────────────────────────────────────────────────────

    async def get_meta(self, key: str) -> Optional[str]:
        assert self._conn
        async with self._conn.execute(
            "SELECT value FROM bot_meta WHERE key=?", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row["value"] if row else None

    async def set_meta(self, key: str, value: str) -> None:
        assert self._conn
        await self._conn.execute(
            "INSERT INTO bot_meta (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await self._conn.commit()
