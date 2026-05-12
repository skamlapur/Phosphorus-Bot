"""
Phosphorus – Voice XP cog
Tracks voice sessions and awards XP every VOICE_HEARTBEAT_INTERVAL seconds.
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands, tasks

from constants import (
    BOT_COLOR,
    EMBED_FOOTER,
    LEVELUP_DESC,
    LEVELUP_TITLE,
    ROLE_REWARD_GRANTED,
    VOICE_ALONE_DENY,
    VOICE_HEARTBEAT_INTERVAL,
    VOICE_XP_PER_MINUTE,
)
from database import Database, current_week, level_from_xp

log = logging.getLogger(__name__)


class Voice(commands.Cog, name="Voice"):
    """Voice channel XP tracking."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.voice_heartbeat.start()

    def cog_unload(self) -> None:
        self.voice_heartbeat.cancel()

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _get_levelup_channel(
        self, guild: discord.Guild
    ) -> discord.TextChannel | None:
        cfg = await self.db.get_config(guild.id)
        if cfg and cfg["levelup_channel"]:
            ch = guild.get_channel(cfg["levelup_channel"])
            if isinstance(ch, discord.TextChannel):
                return ch
        return None

    async def _is_voice_xp_enabled(self, guild_id: int) -> bool:
        cfg = await self.db.get_config(guild_id)
        if cfg is None:
            return True
        return bool(cfg["voice_xp_enabled"])

    def _is_alone(self, member: discord.Member, channel: discord.VoiceChannel | discord.StageChannel) -> bool:
        """True if the member is the only non-bot in the channel."""
        human_members = [m for m in channel.members if not m.bot]
        return len(human_members) <= 1

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
            log.warning("Missing permission for role %s in %s", role.name, member.guild.name)

    # ── events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return

        guild_id = member.guild.id

        if not await self._is_voice_xp_enabled(guild_id):
            return

        old_ch = before.channel
        new_ch = after.channel

        # AFK channel ID
        afk_ch_id = member.guild.afk_channel.id if member.guild.afk_channel else None

        # Left VC or moved to AFK
        if not new_ch or (afk_ch_id and new_ch.id == afk_ch_id):
            await self.db.delete_voice_session(guild_id, member.id)
            return

        # Joined VC (or moved from AFK)
        if new_ch and (not old_ch or (afk_ch_id and old_ch.id == afk_ch_id)):
            await self.db.set_voice_session(guild_id, member.id, new_ch.id, time.time())
            return

        # Moved between non-AFK channels
        if new_ch and old_ch and new_ch.id != old_ch.id:
            await self.db.set_voice_session(guild_id, member.id, new_ch.id, time.time())

    # ── heartbeat ─────────────────────────────────────────────────────────────

    @tasks.loop(seconds=VOICE_HEARTBEAT_INTERVAL)
    async def voice_heartbeat(self) -> None:
        """Award voice XP to every active VC session."""
        sessions = await self.db.get_active_voice_sessions()
        if not sessions:
            return

        now = time.time()
        minutes_per_tick = VOICE_HEARTBEAT_INTERVAL / 60.0

        for session in sessions:
            guild_id = session["guild_id"]
            user_id = session["user_id"]
            channel_id = session["channel_id"]

            guild = self.bot.get_guild(guild_id)
            if not guild:
                await self.db.delete_voice_session(guild_id, user_id)
                continue

            member = guild.get_member(user_id)
            if not member:
                await self.db.delete_voice_session(guild_id, user_id)
                continue

            # Must still be in the tracked channel
            if not member.voice or not member.voice.channel or member.voice.channel.id != channel_id:
                await self.db.delete_voice_session(guild_id, user_id)
                continue

            # Alone check
            if VOICE_ALONE_DENY and isinstance(member.voice.channel, (discord.VoiceChannel, discord.StageChannel)):
                if self._is_alone(member, member.voice.channel):  # type: ignore[arg-type]
                    continue

            # Blacklist check
            role_ids = [r.id for r in member.roles]
            if await self.db.is_blacklisted(guild_id, user_id, channel_id, role_ids):
                continue

            # Compute XP
            multiplier = await self.db.compute_multiplier(guild_id, user_id, channel_id, role_ids)
            xp_gain = max(1, round(VOICE_XP_PER_MINUTE * minutes_per_tick * multiplier))
            minutes_int = max(1, round(minutes_per_tick))

            old_row = await self.db.get_user(guild_id, user_id)
            old_level = level_from_xp(old_row["xp"] if old_row else 0)

            new_xp, new_level, leveled_up = await self.db.add_voice_minutes(
                guild_id, user_id, minutes_int, xp_gain
            )

            # Weekly stats
            week = current_week()
            await self.db.add_weekly_xp(guild_id, user_id, week, xp_gain, voice_minutes=minutes_int)

            if leveled_up:
                announce_ch = await self._get_levelup_channel(guild)
                target = announce_ch or (
                    member.voice.channel
                    if isinstance(member.voice.channel, discord.TextChannel)
                    else None
                )
                if target:
                    embed = discord.Embed(
                        title=LEVELUP_TITLE,
                        description=LEVELUP_DESC.format(
                            user=member.mention, level=new_level
                        ) + "\n🎙️ *Leveled up in voice!*",
                        color=BOT_COLOR,
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text=EMBED_FOOTER)
                    try:
                        await target.send(embed=embed)
                    except discord.Forbidden:
                        pass

                await self._grant_role_reward(member, new_level, announce_ch)

    @voice_heartbeat.before_loop
    async def before_heartbeat(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Voice(bot))
