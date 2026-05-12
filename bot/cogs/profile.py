"""
Phosphorus – Profile / Rank cog
Slash command: /rank [user]
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
    ERR_NO_PERMISSION,
    ERR_USER_NOT_FOUND,
    NO_XP_YET,
    PROGRESS_BAR_LENGTH,
    PROGRESS_EMPTY,
    PROGRESS_FILLED,
    RANK_TITLE,
)
from database import Database, xp_for_level, xp_progress

log = logging.getLogger(__name__)


def _build_progress_bar(xp_into: int, xp_needed: int) -> str:
    if xp_needed <= 0:
        filled = PROGRESS_BAR_LENGTH
    else:
        ratio = min(xp_into / xp_needed, 1.0)
        filled = round(ratio * PROGRESS_BAR_LENGTH)
    return PROGRESS_FILLED * filled + PROGRESS_EMPTY * (PROGRESS_BAR_LENGTH - filled)


class Profile(commands.Cog, name="Profile"):
    """User rank and profile display."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    @app_commands.command(name=CMD_RANK, description="View your XP rank (or another member's).")
    @app_commands.describe(member="The member whose rank you want to check (default: you).")
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
            embed = discord.Embed(
                description=NO_XP_YET if target == interaction.user
                else ERR_USER_NOT_FOUND,
                color=BOT_ERROR_COLOR,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        total_xp = row["xp"]
        level, xp_into, xp_needed = xp_progress(total_xp)
        rank_pos = await self.db.get_rank(interaction.guild.id, target.id)
        total_members = await self.db.get_guild_member_count(interaction.guild.id)

        bar = _build_progress_bar(xp_into, xp_needed)
        multiplier = await self.db.get_multiplier(interaction.guild.id)

        embed = discord.Embed(
            title=RANK_TITLE.format(user=target.display_name),
            color=BOT_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Rank", value=f"**#{rank_pos}** / {total_members}", inline=True)
        embed.add_field(name="Total XP", value=f"**{total_xp:,}**", inline=True)
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"`{bar}` {xp_into:,} / {xp_needed:,} XP",
            inline=False,
        )
        if multiplier != 1.0:
            embed.add_field(name="Server XP Multiplier", value=f"**{multiplier}x**", inline=True)
        embed.set_footer(text=EMBED_FOOTER)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
