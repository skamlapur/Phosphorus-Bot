"""
Phosphorus – Streaks cog (v2.1)
/streak [member]  and  p!streak [member]
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

    # ── shared embed builder ──────────────────────────────────────────────────

    async def _make_embed(
        self,
        target: discord.Member | discord.User,
        requester: discord.Member | discord.User,
        guild_id: int,
    ) -> discord.Embed:
        row = await self.db.get_streak(guild_id, target.id)

        if not row or row["current_streak"] == 0:
            is_self = target.id == requester.id
            desc = (
                "You haven't started a streak yet. Chat every day to build one!"
                if is_self
                else f"**{target.display_name}** doesn't have an active streak yet."
            )
            return discord.Embed(description=desc, color=BOT_ERROR_COLOR)

        current = row["current_streak"]
        longest = row["longest_streak"]
        last = row["last_active_date"]

        if current >= STREAK_BONUS_THRESHOLD:
            bonus = min((current - STREAK_BONUS_THRESHOLD) * STREAK_BONUS_MULTIPLIER, STREAK_BONUS_MAX)
            bonus_str = f"+{round(bonus * 100)}% XP bonus active 🔥"
        else:
            days_left = STREAK_BONUS_THRESHOLD - current
            bonus_str = f"{days_left} more day(s) until streak bonus kicks in"

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
        return embed

    # ── slash command ─────────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_STREAK,
        description="Check your daily XP streak (or another member's).",
    )
    @app_commands.describe(member="The member to check (default: you).")
    @app_commands.guild_only()
    async def streak_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)
        assert interaction.guild

        target = member or interaction.user
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target

        embed = await self._make_embed(target, interaction.user, interaction.guild.id)
        ephemeral = embed.color == BOT_ERROR_COLOR
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # ── prefix command ────────────────────────────────────────────────────────

    @commands.command(name=CMD_STREAK, aliases=["str", "daily"])
    @commands.guild_only()
    async def streak_prefix(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ) -> None:
        async with ctx.typing():
            target = member or ctx.author
            assert ctx.guild
            embed = await self._make_embed(target, ctx.author, ctx.guild.id)
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Streaks(bot))
