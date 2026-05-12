"""
Phosphorus – Discord Leveling Bot  v2
Entry point: loads cogs, connects to DB, starts the bot.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

from constants import BOT_NAME, BOT_VERSION, CMD_PREFIX, COGS
from database import Database

load_dotenv()

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(BOT_NAME)

# ── intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True


# ── bot subclass ──────────────────────────────────────────────────────────────
class Phosphorus(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=CMD_PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.db = Database()

    async def setup_hook(self) -> None:
        await self.db.connect()
        log.info("Database connected.")
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("Loaded cog: %s", cog)
            except Exception as exc:
                log.error("Failed to load cog %s: %s", cog, exc, exc_info=True)
        await self.tree.sync()
        log.info("Slash commands synced globally.")

    async def on_ready(self) -> None:
        assert self.user
        log.info(
            "%s v%s online as %s (ID %d) — %d guild(s)",
            BOT_NAME, BOT_VERSION, self.user, self.user.id, len(self.guilds),
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="your XP climb 📈",
            )
        )

    async def close(self) -> None:
        await self.db.close()
        await super().close()


# ── entry point ───────────────────────────────────────────────────────────────
async def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        log.critical(
            "DISCORD_BOT_TOKEN is not set. "
            "Add it to Replit Secrets and restart."
        )
        sys.exit(1)

    async with Phosphorus() as bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
