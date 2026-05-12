"""
Phosphorus – Streaks cog
Slash command: /streak [member]
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    BOT_COLOR,
    BOT_ERROR_COLOR,
    CMD_STREAK,
    EMBED_FOOTER,
    STREAK_BONUS_MAX,
    STREAK_BONUS_MULTIPLIER,
    STREAK_BONUS_THRESHOLD,
)
from database import Database

log = logging.getLogger(__name__)


class Streaks(commands.Cog, name="Streaks"):
    """Daily activity streak tracking and display."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    @app_commands.command(
        name=CMD_STREAK,
        description="Check your daily XP streak (or another member's).",
    )
    @app_commands.describe(member="The member to check (default: you).")
    @app_commands.guild_only()
    async def streak(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)
        assert interaction.guild

        target = member or interaction.user
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target

        row = await self.db.get_streak(interaction.guild.id, target.id)

        if not row or row["current_streak"] == 0:
            embed = discord.Embed(
                description=(
                    "You haven't started a streak yet. Chat every day to build one!"
                    if target == interaction.user
                    else f"**{target.display_name}** doesn't have an active streak yet."
                ),
                color=BOT_ERROR_COLOR,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        current = row["current_streak"]
        longest = row["longest_streak"]
        last = row["last_active_date"]

        # Compute streak bonus
        if current >= STREAK_BONUS_THRESHOLD:
            bonus = min((current - STREAK_BONUS_THRESHOLD) * STREAK_BONUS_MULTIPLIER, STREAK_BONUS_MAX)
            bonus_str = f"+{round(bonus * 100)}% XP bonus active 🔥"
        else:
            days_left = STREAK_BONUS_THRESHOLD - current
            bonus_str = f"{days_left} more day(s) until streak bonus kicks in"

        # Flame emoji scale
        if current >= 30:
            flame = "🔥🔥🔥"
        elif current >= 14:
            flame = "🔥🔥"
        elif current >= 3:
            flame = "🔥"
        else:
            flame = "✨"

        embed = discord.Embed(
            title=f"{flame} {target.display_name}'s Streak",
            color=BOT_COLOR,
        )
        embed.add_field(name="Current Streak", value=f"**{current}** day(s)", inline=True)
        embed.add_field(name="Longest Streak", value=f"**{longest}** day(s)", inline=True)
        embed.add_field(name="Last Active", value=last or "Unknown", inline=True)
        embed.add_field(name="Streak Bonus", value=bonus_str, inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=EMBED_FOOTER)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Streaks(bot))
