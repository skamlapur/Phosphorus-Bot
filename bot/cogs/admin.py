"""
Phosphorus – Admin cog
Slash commands for server administrators to configure the bot and manage XP.
All commands require Manage Server or Administrator permission.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    BOT_COLOR,
    BOT_ERROR_COLOR,
    BOT_SUCCESS_COLOR,
    BOT_WARN_COLOR,
    CHANNEL_SET_SUCCESS,
    CMD_CONFIG_VIEW,
    CMD_ROLE_REWARD_ADD,
    CMD_ROLE_REWARD_LIST,
    CMD_ROLE_REWARD_REMOVE,
    CMD_SET_CHANNEL,
    CMD_SET_MULTIPLIER,
    CMD_LEVEL_RESET,
    CMD_LEVEL_SET,
    EMBED_FOOTER,
    ERR_INVALID_LEVEL,
    ERR_INVALID_MULT,
    ERR_NO_PERMISSION,
    ERR_USER_NOT_FOUND,
    MULTIPLIER_SET_SUCCESS,
    RESET_SUCCESS,
    ROLE_ADDED_SUCCESS,
    ROLE_REMOVED_SUCCESS,
    SET_LEVEL_SUCCESS,
)
from database import Database, xp_for_level

log = logging.getLogger(__name__)


def _is_admin(member: discord.Member) -> bool:
    return (
        member.guild_permissions.administrator
        or member.guild_permissions.manage_guild
    )


class Admin(commands.Cog, name="Admin"):
    """Admin-only commands for configuring Phosphorus."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    # ── guard ─────────────────────────────────────────────────────────────────

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member) or not _is_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_NO_PERMISSION, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return False
        return True

    # ── /resetxp ─────────────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_LEVEL_RESET,
        description="[Admin] Reset a member's XP and level to zero.",
    )
    @app_commands.describe(member="The member whose XP you want to reset.")
    @app_commands.guild_only()
    async def resetxp(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        await self.db.reset_user(interaction.guild.id, member.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=RESET_SUCCESS.format(user=member.display_name),
                color=BOT_SUCCESS_COLOR,
            )
        )

    # ── /setlevel ────────────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_LEVEL_SET,
        description="[Admin] Set a member's level directly.",
    )
    @app_commands.describe(
        member="Target member.",
        level="The level to set (must be a positive integer).",
    )
    @app_commands.guild_only()
    async def setlevel(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        level: int,
    ) -> None:
        if not await self._guard(interaction):
            return
        if level < 0:
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_INVALID_LEVEL, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        target_xp = xp_for_level(level)
        await self.db.set_xp(interaction.guild.id, member.id, target_xp)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=SET_LEVEL_SUCCESS.format(
                    user=member.display_name, level=level
                ),
                color=BOT_SUCCESS_COLOR,
            )
        )

    # ── /setchannel ──────────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_SET_CHANNEL,
        description="[Admin] Set the channel for level-up announcements.",
    )
    @app_commands.describe(
        channel="The text channel for announcements (leave blank to use the message's channel)."
    )
    @app_commands.guild_only()
    async def setchannel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        ch_id = channel.id if channel else None
        await self.db.set_levelup_channel(interaction.guild.id, ch_id)
        desc = (
            CHANNEL_SET_SUCCESS.format(channel=channel.mention)
            if channel
            else "✅ Level-up announcements will now appear in the same channel as the message."
        )
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=BOT_SUCCESS_COLOR)
        )

    # ── /setmultiplier ───────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_SET_MULTIPLIER,
        description="[Admin] Set a server-wide XP multiplier (e.g. 2.0 for double XP).",
    )
    @app_commands.describe(multiplier="A positive number. 1.0 = default, 2.0 = double XP.")
    @app_commands.guild_only()
    async def setmultiplier(
        self, interaction: discord.Interaction, multiplier: float
    ) -> None:
        if not await self._guard(interaction):
            return
        if multiplier <= 0:
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_INVALID_MULT, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        mult_rounded = round(multiplier, 2)
        await self.db.set_multiplier(interaction.guild.id, mult_rounded)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=MULTIPLIER_SET_SUCCESS.format(mult=mult_rounded),
                color=BOT_SUCCESS_COLOR,
            )
        )

    # ── /addrolereward ───────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_ROLE_REWARD_ADD,
        description="[Admin] Assign a role reward when a member reaches a given level.",
    )
    @app_commands.describe(
        level="The level that triggers the role reward.",
        role="The role to grant.",
    )
    @app_commands.guild_only()
    async def addrolereward(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role,
    ) -> None:
        if not await self._guard(interaction):
            return
        if level <= 0:
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_INVALID_LEVEL, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        await self.db.add_role_reward(interaction.guild.id, level, role.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=ROLE_ADDED_SUCCESS.format(role=role.name, level=level),
                color=BOT_SUCCESS_COLOR,
            )
        )

    # ── /removerolereward ────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_ROLE_REWARD_REMOVE,
        description="[Admin] Remove the role reward for a specific level.",
    )
    @app_commands.describe(level="The level whose reward you want to remove.")
    @app_commands.guild_only()
    async def removerolereward(
        self, interaction: discord.Interaction, level: int
    ) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        removed = await self.db.remove_role_reward(interaction.guild.id, level)
        color = BOT_SUCCESS_COLOR if removed else BOT_WARN_COLOR
        desc = (
            ROLE_REMOVED_SUCCESS.format(level=level)
            if removed
            else f"⚠️ No role reward was set for level **{level}**."
        )
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=color)
        )

    # ── /listroles ───────────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_ROLE_REWARD_LIST,
        description="[Admin] List all configured role rewards.",
    )
    @app_commands.guild_only()
    async def listroles(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        rows = await self.db.get_role_rewards(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="No role rewards configured yet. Use `/addrolereward` to add one.",
                    color=BOT_WARN_COLOR,
                ),
                ephemeral=True,
            )
            return
        lines = []
        for row in rows:
            role = interaction.guild.get_role(row["role_id"])
            role_name = role.mention if role else f"Deleted role ({row['role_id']})"
            lines.append(f"**Level {row['level']}** → {role_name}")
        embed = discord.Embed(
            title="🎖️ Role Rewards",
            description="\n".join(lines),
            color=BOT_COLOR,
        )
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── /config ──────────────────────────────────────────────────────────────

    @app_commands.command(
        name=CMD_CONFIG_VIEW,
        description="[Admin] View the current Phosphorus configuration for this server.",
    )
    @app_commands.guild_only()
    async def config(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        cfg = await self.db.get_config(interaction.guild.id)
        multiplier = cfg["xp_multiplier"] if cfg else 1.0

        ch_id = cfg["levelup_channel"] if cfg else None
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            channel_str = ch.mention if ch else f"Deleted ({ch_id})"
        else:
            channel_str = "Same channel as the triggering message"

        embed = discord.Embed(
            title=f"⚙️ Phosphorus Config — {interaction.guild.name}",
            color=BOT_COLOR,
        )
        embed.add_field(name="Level-Up Channel", value=channel_str, inline=False)
        embed.add_field(name="XP Multiplier", value=f"**{multiplier}x**", inline=True)
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
