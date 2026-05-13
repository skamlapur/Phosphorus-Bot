"""
Phosphorus – Discord Leveling Bot
All tuneable constants live here so changes only happen in one place.
"""
import os

_BOT_DIR = os.path.dirname(os.path.abspath(__file__))

# ──────────────────────────────────────────────
# Bot metadata
# ──────────────────────────────────────────────
BOT_NAME = "Phosphorus"
BOT_VERSION = "2.1.0"
BOT_COLOR = 0x7289DA
BOT_SUCCESS_COLOR = 0x57F287
BOT_ERROR_COLOR = 0xED4245
BOT_WARN_COLOR = 0xFEE75C
BOT_GOLD_COLOR = 0xF1C40F

# ──────────────────────────────────────────────
# XP system – message XP
# ──────────────────────────────────────────────
XP_PER_MESSAGE_MIN = 15
XP_PER_MESSAGE_MAX = 25
XP_COOLDOWN_SECONDS = 60
MIN_MESSAGE_LENGTH = 2          # shorter messages don't award XP

# ──────────────────────────────────────────────
# XP system – voice XP
# ──────────────────────────────────────────────
VOICE_XP_PER_MINUTE = 5        # XP per minute in a non-AFK VC
VOICE_ALONE_DENY = True        # don't award XP if user is alone in VC
VOICE_HEARTBEAT_INTERVAL = 60  # seconds between voice XP ticks

# ──────────────────────────────────────────────
# Booster roles / channels
# ──────────────────────────────────────────────
BOOSTER_MAX_ROLES    = 3      # max booster roles per guild
BOOSTER_MAX_CHANNELS = 3      # max booster channels per guild
BOOSTER_DEFAULT_MULTIPLIER = 1.5  # default XP multiplier for boosters

# ──────────────────────────────────────────────
# Streak system
# ──────────────────────────────────────────────
STREAK_BONUS_THRESHOLD = 3     # streak days needed before bonus applies
STREAK_BONUS_MULTIPLIER = 0.05 # +5 % per day above threshold, stacked up to cap
STREAK_BONUS_MAX = 0.50        # cap at +50 % bonus from streak alone

# ──────────────────────────────────────────────
# Level scaling:  floor(XP_BASE * level ^ XP_EXPONENT)
# ──────────────────────────────────────────────
XP_BASE = 100
XP_EXPONENT = 1.65

# ──────────────────────────────────────────────
# Leaderboard
# ──────────────────────────────────────────────
LEADERBOARD_PAGE_SIZE = 10
LEADERBOARD_MAX_PAGES = 10
LB_TYPES = ["xp", "messages", "voice", "weekly_xp", "weekly_messages", "weekly_voice"]

# ──────────────────────────────────────────────
# Drops system
# ──────────────────────────────────────────────
DROPS_DEFAULT_XP = 300
DROPS_ANSWER_TIMEOUT = 120     # seconds before a drop expires
DROPS_AUTO_INTERVAL_MIN = 20   # minutes between auto-drops (0 = disabled)

# ──────────────────────────────────────────────
# Weekly report
# ──────────────────────────────────────────────
WEEKLY_REPORT_DAY = 0          # 0 = Monday (Python weekday)
WEEKLY_REPORT_HOUR = 9         # 09:00 UTC

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DB_PATH = os.path.join(_BOT_DIR, "phosphorus.db")
DB_PRAGMAS = {
    "journal_mode": "WAL",
    "foreign_keys": "ON",
    "synchronous": "NORMAL",
    "cache_size": -8000,
    "temp_store": "MEMORY",
}

# ──────────────────────────────────────────────
# Cog list
# ──────────────────────────────────────────────
COGS = [
    "cogs.leveling",
    "cogs.voice",
    "cogs.leaderboard",
    "cogs.admin",
    "cogs.profile",
    "cogs.drops",
    "cogs.weekly",
    "cogs.streaks",
    "cogs.help",
]

# ──────────────────────────────────────────────
# Command names
# ──────────────────────────────────────────────
CMD_PREFIX = "p!"
CMD_RANK = "rank"
CMD_LEADERBOARD = "leaderboard"
CMD_STREAK = "streak"
CMD_HELP = "help"
CMD_LEVEL_RESET = "resetxp"
CMD_LEVEL_SET = "setlevel"
CMD_GIVE_XP = "givexp"
CMD_TAKE_XP = "takexp"
CMD_SET_CHANNEL = "setchannel"
CMD_SET_WEEKLY_CHANNEL = "setweekchannel"
CMD_SET_DROPS_CHANNEL = "setdropschannel"
CMD_SET_MULTIPLIER = "setmultiplier"
CMD_ROLE_REWARD_ADD = "addrolereward"
CMD_ROLE_REWARD_REMOVE = "removerolereward"
CMD_ROLE_REWARD_LIST = "listroles"
CMD_CONFIG_VIEW = "config"
CMD_BLACKLIST = "blacklist"
CMD_ENTITY_MULT = "multiplier"
CMD_DROP_CREATE = "dropcreate"
CMD_DROP_TRIGGER = "droptrigger"
CMD_PERMIT  = "permit"
CMD_BOOSTER = "booster"

# All admin command names used for the permit system
ADMIN_COMMANDS = [
    "resetxp", "setlevel", "givexp", "takexp",
    "setchannel", "setweekchannel", "setdropschannel",
    "setmultiplier",
    "multiplier set", "multiplier remove", "multiplier list",
    "blacklist add", "blacklist remove", "blacklist list",
    "addrolereward", "removerolereward", "listroles",
    "voicexp", "dropcreate", "droptrigger", "dropsenable",
    "config",
    "booster set", "booster remove", "booster list",
]

# ──────────────────────────────────────────────
# Progress bar
# ──────────────────────────────────────────────
PROGRESS_BAR_LENGTH = 20
PROGRESS_FILLED = "█"
PROGRESS_EMPTY = "░"

# ──────────────────────────────────────────────
# Embed strings
# ──────────────────────────────────────────────
EMBED_FOOTER = f"{BOT_NAME} v{BOT_VERSION}"
RANK_TITLE = "📊 {user}'s Profile"
LB_TITLE = "🏆 {guild} Leaderboard"
LEVELUP_TITLE = "🎉 Level Up!"
LEVELUP_DESC = "**{user}** just reached **Level {level}**! 🚀"
STREAK_LEVELUP_BONUS = "\n🔥 **{days}-day streak** is boosting your XP by **+{pct}%**!"
ROLE_REWARD_GRANTED = "🎖️ You've earned the **{role}** role for reaching level {level}!"
NO_XP_YET = "You haven't earned any XP here yet. Start chatting!"
RESET_SUCCESS = "✅ Reset XP and level for **{user}**."
SET_LEVEL_SUCCESS = "✅ Set **{user}**'s level to **{level}**."
GIVE_XP_SUCCESS = "✅ Gave **{xp} XP** to **{user}**."
TAKE_XP_SUCCESS = "✅ Removed **{xp} XP** from **{user}**."
CHANNEL_SET_SUCCESS = "✅ Level-up announcements → {channel}."
WEEKLY_CHANNEL_SET = "✅ Weekly reports → {channel}."
DROPS_CHANNEL_SET = "✅ XP drops channel → {channel}."
MULTIPLIER_SET_SUCCESS = "✅ Server XP multiplier set to **{mult}x**."
ENTITY_MULT_SET = "✅ Set **{mult}x** multiplier for {type} `{id}`."
ENTITY_MULT_REMOVED = "✅ Removed multiplier for {type} `{id}`."
ROLE_ADDED_SUCCESS = "✅ Linked **{role}** as reward for level **{level}**."
ROLE_REMOVED_SUCCESS = "✅ Removed role reward for level **{level}**."
BLACKLIST_ADD = "✅ Added {type} `{id}` to the XP blacklist."
BLACKLIST_REMOVE = "✅ Removed {type} `{id}` from the XP blacklist."
DROP_ANNOUNCED = "❓ **XP Drop!** First to answer wins **{xp} XP**!\n\n{question}"
DROP_CLAIMED = "🎉 **{user}** answered correctly and won **{xp} XP**!"
DROP_EXPIRED = "⏰ The XP drop expired — no one claimed it."
DROP_CREATED = "✅ Drop created. Use `/droptrigger` to post it, or it will auto-post if drops are enabled."
ERR_NO_PERMISSION = "❌ You need **Manage Server**, **Administrator**, or a command permit to use this."
PERMIT_SET = "✅ Granted `{cmd}` access to {type} `{id}`."
PERMIT_REMOVED = "✅ Removed `{cmd}` permit for {type} `{id}`."
PERMIT_NOT_FOUND = "⚠️ No matching permit found."
BOOSTER_SET = "✅ Set **{mult}x** XP boost for {type} `{id}`."
BOOSTER_REMOVED = "✅ Removed XP boost for {type} `{id}`."
BOOSTER_NOT_FOUND = "⚠️ No booster found for that {type}."
BOOSTER_LIMIT = "❌ Maximum {max} booster {type}(s) reached. Remove one first with `/booster remove`."
ERR_INVALID_LEVEL = "❌ Level must be a positive integer."
ERR_INVALID_MULT = "❌ Multiplier must be a positive number (e.g. `1.5`)."
ERR_USER_NOT_FOUND = "❌ That user has no XP records in this server."
ERR_ROLE_NOT_FOUND = "❌ Could not find that role."
ERR_NO_DROP = "❌ No pending drops for this server."
ERR_DROP_ACTIVE = "❌ A drop is already active. Wait for it to expire or be claimed."
