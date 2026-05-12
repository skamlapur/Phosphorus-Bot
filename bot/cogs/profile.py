"""
Phosphorus – Profile / Rank cog (v2)
/rank [member] — shows level, rank, XP, voice, messages, streak, progress bar.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    BOT_COLOR,
    BOT_ERROR_COLOR,
    CMD_RANK,
    EMBED_FOOTER,
    NO_XP_YET,
    PROGRESS_BAR_LENGTH,
    PROGRESS_EMPTY,
    PROGRESS_FILLED,
    RANK_TITLE,
    STREAK_BONUS_MAX,
    STREAK_BONUS_MULTIPLIER,
    STREAK_BONUS_THRESHOLD,
)
from database import Database, current_week, xp_for_level, xp_progress

log = logging.getLogger(__name__)


def _build_bar(xp_into: int, xp_needed: int) -> str:
    if xp_needed <= 0:
        filled = PROGRESS_BAR_LENGTH
    else:
        ratio = min(xp_into / xp_needed, 1.0)
        filled = round(ratio * PROGRESS_BAR_LENGTH)
    return PROGRESS_FILLED * filled + PROGRESS_EMPTY * (PROGRESS_BAR_LENGTH - filled)


class Profile(commands.Cog, name="Profile"):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    @app_commands.command(
        name=CMD_RANK,
        description="View your full XP profile (or another member's).",
    )
    @app_commands.describe(member="The member to look up (default: you).")
    @app_commands.guild_only()
    async def rank(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)
        assert interaction.guild

        target = member or interaction.user
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target

        row = await self.db.get_user(interaction.guild.id, target.id)
        if not row:
            await interaction.followup.send(
                embed=discord.Embed(description=NO_XP_YET, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return

        total_xp = row["xp"]
        msg_count = row["msg_count"]
        voice_minutes = row["voice_minutes"]
        level, xp_into, xp_needed = xp_progress(total_xp)
        rank_pos = await self.db.get_rank(interaction.guild.id, target.id)
        total_members = await self.db.get_guild_member_count(interaction.guild.id)

        # Weekly stats
        week = current_week()
        weekly_rows = await self.db.get_weekly_leaderboard(
            interaction.guild.id, week, "xp", 9999
        )
        weekly_xp = 0
        weekly_msgs = 0
        weekly_voice = 0
        for wr in weekly_rows:
            if wr["user_id"] == target.id:
                weekly_xp = wr["xp"]
                weekly_msgs = wr["messages"]
                weekly_voice = wr["voice_minutes"]
                break

        # Streak
        streak_row = await self.db.get_streak(interaction.guild.id, target.id)
        streak = streak_row["current_streak"] if streak_row else 0
        longest_streak = streak_row["longest_streak"] if streak_row else 0

        if streak >= STREAK_BONUS_THRESHOLD:
            bonus = min((streak - STREAK_BONUS_THRESHOLD) * STREAK_BONUS_MULTIPLIER, STREAK_BONUS_MAX)
            streak_str = f"🔥 **{streak}** days (+{round(bonus*100)}% XP)"
        else:
            streak_str = f"✨ **{streak}** days"

        # Multiplier
        role_ids = [r.id for r in target.roles] if isinstance(target, discord.Member) else []
        multiplier = await self.db.compute_multiplier(
            interaction.guild.id, target.id, 0, role_ids
        )

        bar = _build_bar(xp_into, xp_needed)

        embed = discord.Embed(
            title=RANK_TITLE.format(user=target.display_name),
            color=BOT_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Core stats
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Server Rank", value=f"**#{rank_pos}** / {total_members}", inline=True)
        embed.add_field(name="Total XP", value=f"**{total_xp:,}**", inline=True)

        # Progress bar
        embed.add_field(
            name=f"Progress → Level {level + 1}",
            value=f"`{bar}` {xp_into:,} / {xp_needed:,} XP",
            inline=False,
        )

        # Activity stats
        embed.add_field(name="💬 Messages", value=f"{msg_count:,}", inline=True)
        embed.add_field(name="🎙️ Voice", value=f"{voice_minutes:,} min", inline=True)
        embed.add_field(name="🔥 Streak", value=streak_str, inline=True)

        # Weekly stats
        embed.add_field(
            name=f"📅 This Week (Wk {week})",
            value=(
                f"XP: **{weekly_xp:,}** · "
                f"Msgs: **{weekly_msgs:,}** · "
                f"Voice: **{weekly_voice:,}** min"
            ),
            inline=False,
        )

        if multiplier != 1.0:
            embed.add_field(name="⚡ XP Multiplier", value=f"**{multiplier}x**", inline=True)
        if longest_streak > streak:
            embed.add_field(name="🏅 Best Streak", value=f"**{longest_streak}** days", inline=True)

        embed.set_footer(text=EMBED_FOOTER)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
