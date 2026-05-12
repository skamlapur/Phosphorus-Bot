"""
Phosphorus – XP Drops cog
Admin commands for drops live in admin.py.
This cog handles: listening for correct answers, the expiry loop,
and the auto-post loop.  It also exposes trigger_drop() for admin.py.
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands, tasks

from constants import (
    BOT_GOLD_COLOR,
    DROP_CLAIMED,
    DROP_EXPIRED,
    DROPS_ANSWER_TIMEOUT,
    DROPS_AUTO_INTERVAL_MIN,
    EMBED_FOOTER,
    ERR_DROP_ACTIVE,
    ERR_NO_DROP,
)
from database import Database, current_week

log = logging.getLogger(__name__)


class Drops(commands.Cog, name="Drops"):
    """XP drop / trivia system (event handling and background loops)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        # {guild_id: drop_id} — active (posted) drops
        self._active: dict[int, int] = {}
        self._drop_expiry: dict[int, float] = {}
        self.drop_expiry_loop.start()
        self.auto_drop_loop.start()

    def cog_unload(self) -> None:
        self.drop_expiry_loop.cancel()
        self.auto_drop_loop.cancel()

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _post_drop(self, guild_id: int, drop_row) -> bool:
        """Post a drop embed to the drops channel. Returns True on success."""
        cfg = await self.db.get_config(guild_id)
        if not cfg or not cfg["drops_channel"]:
            return False

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False

        channel = guild.get_channel(cfg["drops_channel"])
        if not isinstance(channel, discord.TextChannel):
            return False

        embed = discord.Embed(
            title="🎁 XP Drop!",
            description=(
                f"**{drop_row['question']}**\n\n"
                f"Prize: **{drop_row['xp_amount']} XP** • "
                f"Type your answer in this channel!"
            ),
            color=BOT_GOLD_COLOR,
        )
        embed.set_footer(text=f"{EMBED_FOOTER} • Expires in {DROPS_ANSWER_TIMEOUT}s")

        try:
            msg = await channel.send(embed=embed)
        except discord.Forbidden:
            return False

        await self.db.set_drop_message_id(drop_row["id"], msg.id)
        self._active[guild_id] = drop_row["id"]
        self._drop_expiry[guild_id] = time.time() + DROPS_ANSWER_TIMEOUT
        return True

    async def trigger_drop(self, guild_id: int) -> str:
        """Called by admin.py /droptrigger. Returns a status string."""
        if guild_id in self._active:
            return ERR_DROP_ACTIVE

        drop = await self.db.get_unposted_drop(guild_id)
        if not drop:
            return ERR_NO_DROP + " Create one with `/dropcreate`."

        ok = await self._post_drop(guild_id, drop)
        return "✅ Drop posted!" if ok else "❌ Failed to post — is the drops channel set correctly?"

    # ── message listener ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        gid = message.guild.id
        if gid not in self._active:
            return

        drop_id = self._active[gid]
        drop = await self.db.get_pending_drop(gid)
        if not drop or drop["id"] != drop_id:
            self._active.pop(gid, None)
            self._drop_expiry.pop(gid, None)
            return

        if message.channel.id != drop["channel_id"]:
            return

        if message.content.strip().lower() != drop["answer"]:
            return

        # Winner!
        await self.db.claim_drop(drop_id, message.author.id, time.time())
        self._active.pop(gid, None)
        self._drop_expiry.pop(gid, None)

        now = time.time()
        await self.db.add_xp(gid, message.author.id, drop["xp_amount"], now, is_message=False)
        week = current_week()
        await self.db.add_weekly_xp(gid, message.author.id, week, drop["xp_amount"])

        try:
            await message.channel.send(
                DROP_CLAIMED.format(user=message.author.mention, xp=drop["xp_amount"])
            )
        except discord.Forbidden:
            pass

    # ── expiry loop ───────────────────────────────────────────────────────────

    @tasks.loop(seconds=10)
    async def drop_expiry_loop(self) -> None:
        now = time.time()
        expired = [gid for gid, exp in self._drop_expiry.items() if now >= exp]
        for gid in expired:
            drop_id = self._active.pop(gid, None)
            self._drop_expiry.pop(gid, None)
            if drop_id is None:
                continue

            drop = await self.db.get_pending_drop(gid)
            if not drop:
                continue

            guild = self.bot.get_guild(gid)
            if not guild:
                continue

            channel = guild.get_channel(drop["channel_id"])
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(DROP_EXPIRED)
                except discord.Forbidden:
                    pass

    @drop_expiry_loop.before_loop
    async def before_expiry(self) -> None:
        await self.bot.wait_until_ready()

    # ── auto-drop loop ────────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def auto_drop_loop(self) -> None:
        """Check every minute if it's time to auto-post a queued drop."""
        for guild in self.bot.guilds:
            gid = guild.id
            if gid in self._active:
                continue

            cfg = await self.db.get_config(gid)
            if not cfg or not cfg["drops_enabled"] or not cfg["drops_channel"]:
                continue

            interval = cfg["drops_interval"] or DROPS_AUTO_INTERVAL_MIN
            if interval <= 0:
                continue

            meta_key = f"last_auto_drop_{gid}"
            last_str = await self.db.get_meta(meta_key)
            last_ts = float(last_str) if last_str else 0.0
            if time.time() - last_ts < interval * 60:
                continue

            drop = await self.db.get_unposted_drop(gid)
            if not drop:
                continue

            ok = await self._post_drop(gid, drop)
            if ok:
                await self.db.set_meta(meta_key, str(time.time()))

    @auto_drop_loop.before_loop
    async def before_auto_drop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Drops(bot))
