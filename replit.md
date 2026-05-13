# Phosphorus

A full-stack Discord leveling bot written in Python. Members earn XP by chatting and talking in voice, level up, unlock role rewards, compete on leaderboards, and maintain daily streaks. Server admins configure everything through slash commands.

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
├── main.py          # Entry point – bot subclass, cog loader
├── constants.py     # ★ Single source of truth for all tuneable values
├── database.py      # All SQLite queries + XP/level math helpers
├── phosphorus.db    # SQLite database (created at runtime, git-ignored)
└── cogs/
    ├── leveling.py      # on_message XP grant, cooldown, blacklist, multipliers, streak bonus
    ├── voice.py         # Voice XP – tracks sessions, heartbeat tick every 60 s
    ├── leaderboard.py   # /leaderboard with 6 types and paginated buttons
    ├── admin.py         # Full admin suite (XP, config, blacklist, multipliers, drops)
    ├── profile.py       # /rank – full profile card with weekly stats, streak, voice
    ├── drops.py         # XP drops / trivia system with auto-scheduling
    ├── weekly.py        # Auto weekly report every Monday
    └── streaks.py       # /streak command
```

## Architecture decisions

- **Constants-first**: every magic number, colour, string, and command name lives in `constants.py`.
- **WAL mode SQLite**: concurrent reads without blocking.
- **Upsert pattern**: `INSERT … ON CONFLICT DO UPDATE` avoids race conditions.
- **Asyncio lock on XP writes**: prevents double-XP from near-simultaneous messages.
- **Cog-based architecture**: each concern is an isolated `commands.Cog`.
- **Safe migration**: `_migrate()` uses `ALTER TABLE … ADD COLUMN` with exception swallowing so old databases are upgraded automatically.

## Product — Full Command List

### Anyone
| Command | Description |
|---|---|
| `/rank [member]` | Full profile: level, rank, XP, messages, voice minutes, streak, weekly stats, progress bar |
| `/leaderboard [type]` | 6 types: All-Time XP, Messages, Voice · Weekly XP, Messages, Voice. Paginated. |
| `/streak [member]` | Current streak, longest streak, and active XP bonus |

### Admin (Manage Server / Administrator)
| Command | Description |
|---|---|
| `/resetxp <member>` | Reset XP, messages, voice to zero |
| `/setlevel <member> <level>` | Jump a member to a specific level |
| `/givexp <member> <amount>` | Give XP to a member |
| `/takexp <member> <amount>` | Remove XP from a member |
| `/setchannel [channel]` | Set level-up announcement channel |
| `/setweekchannel [channel]` | Set weekly report channel |
| `/setdropschannel [channel]` | Set XP drops channel |
| `/setmultiplier <mult>` | Server-wide XP multiplier (e.g. 2.0) |
| `/multiplier set <type> <id> <mult>` | Per-role / per-channel / per-user multiplier |
| `/multiplier remove <type> <id>` | Remove an entity multiplier |
| `/multiplier list` | List all entity multipliers |
| `/blacklist add <type> <id>` | Block user / role / channel from earning XP |
| `/blacklist remove <type> <id>` | Unblock |
| `/blacklist list` | Show all blacklisted entities |
| `/addrolereward <level> <role>` | Grant a role automatically at a level |
| `/removerolereward <level>` | Remove a role reward |
| `/listroles` | List all role rewards |
| `/voicexp <enabled>` | Enable / disable voice XP for the server |
| `/booster set role\|channel <id> [mult]` | Set a booster role/channel (up to 3 each, default 1.5x) |
| `/booster remove role\|channel <id>` | Remove a booster |
| `/booster list` | List all active XP boosters |
| `/dropcreate <question> <answer> [xp]` | Create a queued XP drop |
| `/droptrigger` | Post the next queued drop immediately |
| `/dropsenable <enabled>` | Enable / disable auto-drop posting |
| `/config` | View all current settings |

## XP Features

- **Message XP** — 15–25 XP per eligible message, 60-second cooldown, min 2 chars
- **Voice XP** — 5 XP/min in VC, skips AFK channel and users alone in VC
- **Streak bonus** — +5% per day above 3-day threshold, capped at +50%
- **Blacklist** — block users, roles, or channels from gaining XP
- **Per-entity multipliers** — override XP rate per role, channel, or user (stacks with server multiplier)
- **Server multiplier** — flat multiplier applied to all XP events
- **Weekly tracking** — separate XP, message, and voice counters per ISO week
- **Weekly report** — auto-posts to designated channel every Monday

## User preferences

- Use constants wherever possible for easy tuning.
- Best practices for resource efficiency (WAL, async, upsert).

## Gotchas

- Bot needs **Message Content Intent** and **Server Members Intent** in the Discord Developer Portal.
- Bot role must be **above** any role it needs to assign in the role hierarchy.
- Slash commands sync globally on startup — can take up to 1 hour to propagate (instant in test guild).
- PyNaCl warning in logs is expected — voice audio is not used.

## Leveling formula

`XP needed for level N = floor(100 × N ^ 1.65)`

| Level | XP needed |
|-------|-----------|
| 1     | 100       |
| 5     | 697       |
| 10    | 1 979     |
| 25    | 8 769     |
| 50    | 27 145    |
