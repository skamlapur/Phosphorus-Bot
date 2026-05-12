"""
Phosphorus – XP Drops cog
Admins create trivia drops; first correct answer wins XP.
"""
from __future__ import annotations

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from constants import (
    BOT_COLOR,
    BOT_ERROR_COLOR,
    BOT_GOLD_COLOR,
    BOT_SUCCESS_COLOR,
    BOT_WARN_COLOR,
    CMD_DROP_CREATE,
    CMD_DROP_TRIGGER,
    DROP_ANNOUNCED,
    DROP_CLAIMED,
    DROP_CREATED,
    DROP_EXPIRED,
    DROPS_ANSWER_TIMEOUT,
    DROPS_AUTO_INTERVAL_MIN,
    DROPS_DEFAULT_XP,
    EMBED_FOOTER,
    ERR_DROP_ACTIVE,
    ERR_NO_DROP,
    ERR_NO_PERMISSION,
)
from database import Database, current_week

log = logging.getLogger(__name__)


def _is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or member.guild_permissions.manage_guild


class Drops(commands.Cog, name="Drops"):
    """XP drop / trivia system."""

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
            description=f"**{drop_row['question']}**\n\n"
                        f"Prize: **{drop_row['xp_amount']} XP** • "
                        f"Type your answer in this channel!",
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

    # ── slash commands ────────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_DROP_CREATE,
        description="[Admin] Create a new XP drop that users can answer for XP.",
    )
    @app_commands.describe(
        question="The question users must answer.",
        answer="The correct answer (case-insensitive).",
        xp="XP reward for the winner.",
    )
    @app_commands.guild_only()
    async def dropcreate(
        self,
        interaction: discord.Interaction,
        question: str,
        answer: str,
        xp: int = DROPS_DEFAULT_XP,
    ) -> None:
        if not isinstance(interaction.user, discord.Member) or not _is_admin(interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_NO_PERMISSION, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild

        cfg = await self.db.get_config(interaction.guild.id)
        channel_id = cfg["drops_channel"] if cfg else None
        if not channel_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No drops channel set. Use `/setdropschannel` first.",
                    color=BOT_ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return

        await self.db.create_drop(
            guild_id=interaction.guild.id,
            channel_id=channel_id,
            question=question,
            answer=answer.strip().lower(),
            xp_amount=max(1, xp),
            created_at=time.time(),
        )
        await interaction.response.send_message(
            embed=discord.Embed(description=DROP_CREATED, color=BOT_SUCCESS_COLOR),
            ephemeral=True,
        )

    @app_commands.command(
        name=CMD_DROP_TRIGGER,
        description="[Admin] Post the next queued XP drop now.",
    )
    @app_commands.guild_only()
    async def droptrigger(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member) or not _is_admin(interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_NO_PERMISSION, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        gid = interaction.guild.id

        if gid in self._active:
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_DROP_ACTIVE, color=BOT_WARN_COLOR),
                ephemeral=True,
            )
            return

        drop = await self.db.get_unposted_drop(gid)
        if not drop:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=ERR_NO_DROP + " Create one with `/dropcreate`.",
                    color=BOT_WARN_COLOR,
                ),
                ephemeral=True,
            )
            return

        ok = await self._post_drop(gid, drop)
        if ok:
            await interaction.response.send_message(
                embed=discord.Embed(description="✅ Drop posted!", color=BOT_SUCCESS_COLOR),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ Failed to post drop. Is the drops channel set correctly?",
                    color=BOT_ERROR_COLOR,
                ),
                ephemeral=True,
            )

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

        # Check if the channel matches
        if message.channel.id != drop["channel_id"]:
            return

        # Check answer (case-insensitive, stripped)
        if message.content.strip().lower() != drop["answer"]:
            return

        # Winner!
        await self.db.claim_drop(drop_id, message.author.id, time.time())
        self._active.pop(gid, None)
        self._drop_expiry.pop(gid, None)

        # Award XP
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

            # Use bot_meta to track last auto-drop time per guild
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
