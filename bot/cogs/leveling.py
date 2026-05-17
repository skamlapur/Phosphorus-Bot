from __future__ import annotations

import random
import time
import logging

import discord
from discord.ext import commands

from constants import (
    BOT_COLOR,
    EMBED_FOOTER,
    LEVELUP_DESC,
    LEVELUP_TITLE,
    GREEN_TICK,
    RED_CROSS,
    ROLE_REWARD_GRANTED,
    STREAK_BONUS_MAX,
    STREAK_BONUS_MULTIPLIER,
    STREAK_BONUS_THRESHOLD,
    XP_COOLDOWN_SECONDS,
    XP_PER_MESSAGE_MAX,
    XP_PER_MESSAGE_MIN,
    MIN_MESSAGE_LENGTH,
    STREAK_LEVELUP_BONUS,
)
from database import Database, current_week, xp_progress

log = logging.getLogger(__name__)


class Leveling(commands.Cog, name="Leveling"):
    """Core XP and leveling logic for messages."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _is_eligible(self, message: discord.Message) -> bool:
        if message.author.bot:
            return False
        if not message.guild:
            return False
        if not message.content or len(message.content.strip()) < MIN_MESSAGE_LENGTH:
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

    def _streak_multiplier(self, streak: int) -> float:
        if streak < STREAK_BONUS_THRESHOLD:
            return 1.0
        bonus = min((streak - STREAK_BONUS_THRESHOLD) * STREAK_BONUS_MULTIPLIER, STREAK_BONUS_MAX)
        return round(1.0 + bonus, 4)

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
        if not role or role in member.roles:
            return
        try:
            await member.add_roles(role, reason=f"Phosphorus: reached level {level}")
            if announce_channel:
                await announce_channel.send(
                    ROLE_REWARD_GRANTED.format(
                        user=member.mention, role=role.name, level=level
                    )
                )
        except discord.Forbidden:
            log.warning("Missing permission to assign role %s in %s", role.name, member.guild.name)

    # ── events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._is_eligible(message):
            return

        guild_id = message.guild.id  # type: ignore[union-attr]
        user_id = message.author.id
        now = time.time()

        # Cooldown check
        last_xp_at = await self.db.get_last_xp_at(guild_id, user_id)
        if now - last_xp_at < XP_COOLDOWN_SECONDS:
            return

        # Blacklist check
        member = message.author
        role_ids: list[int] = []
        if isinstance(member, discord.Member):
            role_ids = [r.id for r in member.roles]
        if await self.db.is_blacklisted(guild_id, user_id, message.channel.id, role_ids):
            return

        # Compute multipliers
        server_and_entity_mult = await self.db.compute_multiplier(
            guild_id, user_id, message.channel.id, role_ids
        )

        # Booster role / channel bonus (takes highest applicable booster)
        booster_mult = await self.db.get_booster_multiplier(
            guild_id, message.channel.id, role_ids
        )

        # Streak bonus
        streak, is_new_day = await self.db.update_streak(guild_id, user_id)
        streak_mult = self._streak_multiplier(streak)

        raw_xp = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
        xp_gain = max(1, round(raw_xp * server_and_entity_mult * booster_mult * streak_mult))

        new_xp, new_level, leveled_up = await self.db.add_xp(
            guild_id, user_id, xp_gain, now, is_message=True
        )

        # Weekly stats
        week = current_week()
        await self.db.add_weekly_xp(guild_id, user_id, week, xp_gain, messages=1)

        if not leveled_up:
            return

        announce_ch = await self._get_levelup_channel(message.guild)  # type: ignore[arg-type]
        target = announce_ch or (
            message.channel if isinstance(message.channel, discord.TextChannel) else None
        )

        if target:
            embed = discord.Embed(
                title=LEVELUP_TITLE,
                description=LEVELUP_DESC.format(
                    user=message.author.mention, level=new_level
                ),
                color=BOT_COLOR,
            )
            # Streak bonus shoutout
            if streak >= STREAK_BONUS_THRESHOLD:
                pct = round((streak_mult - 1.0) * 100)
                embed.description += STREAK_LEVELUP_BONUS.format(days=streak, pct=pct)

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
