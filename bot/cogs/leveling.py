"""
Phosphorus – Leveling cog
Handles XP grant on message, cooldown enforcement, level-up announcements,
and role-reward assignment.
"""
from __future__ import annotations

import random
import time
import logging

import discord
from discord.ext import commands

from constants import (
    BOT_COLOR,
    LEVELUP_DESC,
    LEVELUP_TITLE,
    ROLE_REWARD_GRANTED,
    XP_COOLDOWN_SECONDS,
    XP_PER_MESSAGE_MAX,
    XP_PER_MESSAGE_MIN,
    EMBED_FOOTER,
)
from database import Database, xp_progress

log = logging.getLogger(__name__)


class Leveling(commands.Cog, name="Leveling"):
    """Core XP and leveling logic."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _is_eligible(self, message: discord.Message) -> bool:
        """Return True if the message should award XP."""
        if message.author.bot:
            return False
        if not message.guild:
            return False
        if not message.content or len(message.content.strip()) < 2:
            return False
        return True

    async def _get_levelup_channel(
        self, guild: discord.Guild
    ) -> discord.TextChannel | None:
        cfg = await self.db.get_config(guild.id)
        if cfg and cfg["levelup_channel"]:
            ch = guild.get_channel(cfg["levelup_channel"])
            if isinstance(ch, discord.TextChannel):
                return ch
        return None

    async def _grant_role_reward(
        self,
        member: discord.Member,
        level: int,
        announce_channel: discord.TextChannel | None,
    ) -> None:
        role_id = await self.db.get_role_reward_for_level(member.guild.id, level)
        if not role_id:
            return
        role = member.guild.get_role(role_id)
        if not role:
            return
        try:
            await member.add_roles(role, reason=f"Phosphorus: reached level {level}")
            if announce_channel:
                await announce_channel.send(
                    ROLE_REWARD_GRANTED.format(user=member.mention, role=role.name, level=level)
                )
        except discord.Forbidden:
            log.warning(
                "Missing permission to assign role %s in guild %s.",
                role.name, member.guild.name,
            )

    # ── events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._is_eligible(message):
            return

        guild_id = message.guild.id  # type: ignore[union-attr]
        user_id = message.author.id
        now = time.time()

        last_xp_at = await self.db.get_last_xp_at(guild_id, user_id)
        if now - last_xp_at < XP_COOLDOWN_SECONDS:
            return

        multiplier = await self.db.get_multiplier(guild_id)
        raw_xp = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
        xp_gain = max(1, round(raw_xp * multiplier))

        new_xp, new_level, leveled_up = await self.db.add_xp(
            guild_id, user_id, xp_gain, now
        )

        if not leveled_up:
            return

        announce_ch = await self._get_levelup_channel(message.guild)  # type: ignore[arg-type]
        target = announce_ch or (
            message.channel
            if isinstance(message.channel, discord.TextChannel)
            else None
        )

        if target:
            level, xp_into, xp_needed = xp_progress(new_xp)
            embed = discord.Embed(
                title=LEVELUP_TITLE,
                description=LEVELUP_DESC.format(
                    user=message.author.mention, level=new_level
                ),
                color=BOT_COLOR,
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text=EMBED_FOOTER)
            try:
                await target.send(embed=embed)
            except discord.Forbidden:
                pass

        if isinstance(message.author, discord.Member):
            await self._grant_role_reward(message.author, new_level, target)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot))
