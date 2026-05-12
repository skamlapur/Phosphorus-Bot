"""
Phosphorus – Discord Leveling Bot
All tuneable constants live here so changes only happen in one place.
"""

# ──────────────────────────────────────────────
# Bot metadata
# ──────────────────────────────────────────────
BOT_NAME = "Phosphorus"
BOT_VERSION = "1.0.0"
BOT_COLOR = 0x7289DA          # Default embed accent color
BOT_SUCCESS_COLOR = 0x57F287  # Green  – success feedback
BOT_ERROR_COLOR = 0xED4245    # Red    – error feedback
BOT_WARN_COLOR = 0xFEE75C     # Yellow – warning feedback

# ──────────────────────────────────────────────
# XP system
# ──────────────────────────────────────────────
XP_PER_MESSAGE_MIN = 15       # Minimum XP awarded per eligible message
XP_PER_MESSAGE_MAX = 25       # Maximum XP awarded per eligible message
XP_COOLDOWN_SECONDS = 60      # Seconds between XP awards per user per guild
XP_VOICE_PER_MINUTE = 10      # XP awarded every XP_VOICE_INTERVAL_SECONDS in VC

# ──────────────────────────────────────────────
# Level scaling formula:  XP_BASE * level ^ XP_EXPONENT
# e.g. level 1 needs 100 XP, level 5 needs ~700 XP, level 10 needs ~1 979 XP
# ──────────────────────────────────────────────
XP_BASE = 100
XP_EXPONENT = 1.65

# ──────────────────────────────────────────────
# Leaderboard & display
# ──────────────────────────────────────────────
LEADERBOARD_PAGE_SIZE = 10    # Entries per leaderboard page
LEADERBOARD_MAX_PAGES = 10    # Hard cap – never show more than this many pages

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DB_PATH = "bot/phosphorus.db"
DB_PRAGMAS = {
    "journal_mode": "WAL",    # Write-Ahead Logging for concurrent reads
    "foreign_keys": "ON",
    "synchronous": "NORMAL",  # Balance safety vs. speed
    "cache_size": -8000,      # 8 MB page cache
    "temp_store": "MEMORY",
}

# ──────────────────────────────────────────────
# Cog file names  (relative to cogs/ package)
# ──────────────────────────────────────────────
COGS = [
    "cogs.leveling",
    "cogs.leaderboard",
    "cogs.admin",
    "cogs.profile",
]

# ──────────────────────────────────────────────
# Command names & groups
# ──────────────────────────────────────────────
CMD_PREFIX = "p!"             # Fallback text-command prefix (slash commands preferred)
CMD_RANK = "rank"
CMD_LEADERBOARD = "leaderboard"
CMD_LEVEL_RESET = "resetxp"
CMD_LEVEL_SET = "setlevel"
CMD_SET_CHANNEL = "setchannel"
CMD_SET_MULTIPLIER = "setmultiplier"
CMD_ROLE_REWARD_ADD = "addrolereward"
CMD_ROLE_REWARD_REMOVE = "removerolereward"
CMD_ROLE_REWARD_LIST = "listroles"
CMD_CONFIG_VIEW = "config"

# ──────────────────────────────────────────────
# Permission checks
# ──────────────────────────────────────────────
ADMIN_PERMISSIONS = ["administrator", "manage_guild"]

# ──────────────────────────────────────────────
# Embed strings  (edit here, change everywhere)
# ──────────────────────────────────────────────
EMBED_FOOTER = f"{BOT_NAME} v{BOT_VERSION}"
RANK_TITLE = "📊 {user}'s Rank"
LB_TITLE = "🏆 {guild} Leaderboard"
LEVELUP_TITLE = "🎉 Level Up!"
LEVELUP_DESC = "**{user}** just reached **Level {level}**! 🚀"
ROLE_REWARD_GRANTED = "You've been given the **{role}** role for reaching level {level}!"
NO_XP_YET = "You haven't earned any XP in this server yet. Start chatting!"
RESET_SUCCESS = "✅ Reset XP and level for **{user}**."
SET_LEVEL_SUCCESS = "✅ Set **{user}**'s level to **{level}**."
CHANNEL_SET_SUCCESS = "✅ Level-up announcements will now appear in {channel}."
MULTIPLIER_SET_SUCCESS = "✅ XP multiplier set to **{mult}x** for this server."
ROLE_ADDED_SUCCESS = "✅ Linked **{role}** as the reward for reaching level **{level}**."
ROLE_REMOVED_SUCCESS = "✅ Removed role reward for level **{level}**."
ERR_NO_PERMISSION = "❌ You need **Manage Server** (or **Administrator**) to use this command."
ERR_INVALID_LEVEL = "❌ Level must be a positive integer."
ERR_INVALID_MULT = "❌ Multiplier must be a positive number (e.g. 1.5)."
ERR_USER_NOT_FOUND = "❌ Could not find that user in this server's XP records."
ERR_ROLE_NOT_FOUND = "❌ Could not find that role."

# ──────────────────────────────────────────────
# Progress-bar rendering
# ──────────────────────────────────────────────
PROGRESS_BAR_LENGTH = 20      # characters
PROGRESS_FILLED = "█"
PROGRESS_EMPTY = "░"
