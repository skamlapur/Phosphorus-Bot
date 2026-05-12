# Phosphorus

A full-stack Discord leveling bot written in Python. Members earn XP by chatting, level up, and unlock role rewards. Server admins can configure every aspect through slash commands.

## Run & Operate

- `cd bot && python main.py` — run the bot (managed by the **Phosphorus Bot** workflow)
- Required secret: `DISCORD_BOT_TOKEN` — set in Replit Secrets

## Stack

- Python 3.12
- discord.py 2.x (slash commands via `app_commands`)
- aiosqlite (async SQLite with WAL mode)
- python-dotenv (local `.env` support)

## Where things live

```
bot/
├── main.py          # Entry point – bot subclass, cog loader, workflow lifecycle
├── constants.py     # ★ Single source of truth for all tuneable values
├── database.py      # All SQLite queries + XP/level math helpers
├── phosphorus.db    # SQLite database (created at runtime, git-ignored)
└── cogs/
    ├── leveling.py      # on_message XP grant, cooldown, level-up announcement, role rewards
    ├── profile.py       # /rank command with progress bar
    ├── leaderboard.py   # /leaderboard with paginated button UI
    └── admin.py         # /resetxp /setlevel /setchannel /setmultiplier /addrolereward …
```

## Architecture decisions

- **Constants-first**: every magic number, colour, string, and command name lives in `constants.py` — changing one line propagates everywhere.
- **WAL mode SQLite**: enables concurrent reads without blocking, keeping latency low under load.
- **Upsert pattern**: `INSERT … ON CONFLICT DO UPDATE` avoids race conditions and redundant SELECT+INSERT pairs.
- **Asyncio lock on XP writes**: prevents double-XP from near-simultaneous messages even on a single process.
- **Cog-based architecture**: each concern (leveling, profile, leaderboard, admin) is an isolated `commands.Cog` — easy to disable or extend.

## Product

- **XP on message** — 15–25 XP per eligible message, 60-second cooldown per user per guild, configurable server multiplier.
- **Level-up announcements** — embed with avatar sent to a configurable channel (or the triggering channel).
- **Role rewards** — assign any role to trigger at any level; bot grants it automatically on level-up.
- **`/rank`** — shows level, rank position, total XP, and a visual progress bar to the next level.
- **`/leaderboard`** — paginated (10 per page) with Prev/Next buttons; live Discord member names.
- **Admin commands** — `/resetxp`, `/setlevel`, `/setchannel`, `/setmultiplier`, `/addrolereward`, `/removerolereward`, `/listroles`, `/config` — all require Manage Server or Administrator.

## User preferences

- Use constants wherever possible for easy tuning.
- Best practices for resource efficiency (WAL, async, upsert).

## Gotchas

- Bot needs **Message Content Intent** and **Server Members Intent** enabled in the Discord Developer Portal.
- Bot role must be **above** any role it needs to assign in the server's role hierarchy.
- Slash commands are synced globally on startup — new commands may take up to an hour to appear for all users (instant in the home guild during testing).
- The PyNaCl warning in logs is expected; voice is not used by this bot.

## Leveling formula

`XP needed for level N = floor(100 × N ^ 1.65)`

| Level | XP needed |
|-------|-----------|
| 1     | 100       |
| 5     | 697       |
| 10    | 1 979     |
| 25    | 8 769     |
| 50    | 27 145    |
