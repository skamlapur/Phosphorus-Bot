"""
Phosphorus – Admin cog (v2)
Full suite of admin commands: XP management, config, blacklist,
per-entity multipliers, role rewards, drops, voice toggle.
"""
from __future__ import annotations

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    BLACKLIST_ADD,
    BLACKLIST_REMOVE,
    BOT_COLOR,
    BOT_ERROR_COLOR,
    BOT_SUCCESS_COLOR,
    BOT_WARN_COLOR,
    CHANNEL_SET_SUCCESS,
    CMD_BLACKLIST,
    CMD_CONFIG_VIEW,
    CMD_DROP_CREATE,
    CMD_ENTITY_MULT,
    CMD_GIVE_XP,
    CMD_LEVEL_RESET,
    CMD_LEVEL_SET,
    CMD_ROLE_REWARD_ADD,
    CMD_ROLE_REWARD_LIST,
    CMD_ROLE_REWARD_REMOVE,
    CMD_SET_CHANNEL,
    CMD_SET_DROPS_CHANNEL,
    CMD_SET_MULTIPLIER,
    CMD_SET_WEEKLY_CHANNEL,
    CMD_TAKE_XP,
    DROPS_CHANNEL_SET,
    EMBED_FOOTER,
    ENTITY_MULT_REMOVED,
    ENTITY_MULT_SET,
    ERR_INVALID_LEVEL,
    ERR_INVALID_MULT,
    ERR_NO_PERMISSION,
    GIVE_XP_SUCCESS,
    MULTIPLIER_SET_SUCCESS,
    RESET_SUCCESS,
    ROLE_ADDED_SUCCESS,
    ROLE_REMOVED_SUCCESS,
    SET_LEVEL_SUCCESS,
    TAKE_XP_SUCCESS,
    WEEKLY_CHANNEL_SET,
)
from database import Database, xp_for_level

log = logging.getLogger(__name__)


def _is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or member.guild_permissions.manage_guild


class Admin(commands.Cog, name="Admin"):
    """Admin-only commands for configuring Phosphorus."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member) or not _is_admin(interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_NO_PERMISSION, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return False
        return True

    # ── XP management ─────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_LEVEL_RESET, description="[Admin] Reset a member's XP to zero.")
    @app_commands.describe(member="Target member.")
    @app_commands.guild_only()
    async def resetxp(self, interaction: discord.Interaction, member: discord.Member) -> None:
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

    @app_commands.command(name=CMD_LEVEL_SET, description="[Admin] Set a member's level directly.")
    @app_commands.describe(member="Target member.", level="Level to set (≥ 0).")
    @app_commands.guild_only()
    async def setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int) -> None:
        if not await self._guard(interaction):
            return
        if level < 0:
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_INVALID_LEVEL, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        await self.db.set_xp(interaction.guild.id, member.id, xp_for_level(level))
        await interaction.response.send_message(
            embed=discord.Embed(
                description=SET_LEVEL_SUCCESS.format(user=member.display_name, level=level),
                color=BOT_SUCCESS_COLOR,
            )
        )

    @app_commands.command(name=CMD_GIVE_XP, description="[Admin] Give XP to a member.")
    @app_commands.describe(member="Target member.", amount="Amount of XP to give.")
    @app_commands.guild_only()
    async def givexp(self, interaction: discord.Interaction, member: discord.Member, amount: int) -> None:
        if not await self._guard(interaction):
            return
        if amount <= 0:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Amount must be positive.", color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        import time
        assert interaction.guild
        await self.db.add_xp(interaction.guild.id, member.id, amount, time.time(), is_message=False)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=GIVE_XP_SUCCESS.format(xp=amount, user=member.display_name),
                color=BOT_SUCCESS_COLOR,
            )
        )

    @app_commands.command(name=CMD_TAKE_XP, description="[Admin] Remove XP from a member.")
    @app_commands.describe(member="Target member.", amount="Amount of XP to remove.")
    @app_commands.guild_only()
    async def takexp(self, interaction: discord.Interaction, member: discord.Member, amount: int) -> None:
        if not await self._guard(interaction):
            return
        if amount <= 0:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Amount must be positive.", color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        row = await self.db.get_user(interaction.guild.id, member.id)
        current_xp = row["xp"] if row else 0
        new_xp = max(0, current_xp - amount)
        await self.db.set_xp(interaction.guild.id, member.id, new_xp)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=TAKE_XP_SUCCESS.format(xp=amount, user=member.display_name),
                color=BOT_SUCCESS_COLOR,
            )
        )

    # ── channel config ────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_SET_CHANNEL, description="[Admin] Set the level-up announcement channel.")
    @app_commands.describe(channel="Text channel for announcements.")
    @app_commands.guild_only()
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        await self.db.set_levelup_channel(interaction.guild.id, channel.id if channel else None)
        desc = CHANNEL_SET_SUCCESS.format(channel=channel.mention) if channel else "✅ Level-up channel cleared (uses message channel)."
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=BOT_SUCCESS_COLOR)
        )

    @app_commands.command(name=CMD_SET_WEEKLY_CHANNEL, description="[Admin] Set the channel for weekly activity reports.")
    @app_commands.describe(channel="Text channel for weekly reports.")
    @app_commands.guild_only()
    async def setweekchannel(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        await self.db.set_weekly_channel(interaction.guild.id, channel.id if channel else None)
        desc = WEEKLY_CHANNEL_SET.format(channel=channel.mention) if channel else "✅ Weekly reports channel cleared."
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=BOT_SUCCESS_COLOR)
        )

    @app_commands.command(name=CMD_SET_DROPS_CHANNEL, description="[Admin] Set the channel for XP drops.")
    @app_commands.describe(channel="Text channel for XP drops.")
    @app_commands.guild_only()
    async def setdropschannel(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        await self.db.set_drops_channel(interaction.guild.id, channel.id if channel else None)
        desc = DROPS_CHANNEL_SET.format(channel=channel.mention) if channel else "✅ Drops channel cleared."
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=BOT_SUCCESS_COLOR)
        )

    # ── multipliers ───────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_SET_MULTIPLIER, description="[Admin] Set the server-wide XP multiplier.")
    @app_commands.describe(multiplier="e.g. 2.0 for double XP. Must be > 0.")
    @app_commands.guild_only()
    async def setmultiplier(self, interaction: discord.Interaction, multiplier: float) -> None:
        if not await self._guard(interaction):
            return
        if multiplier <= 0:
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_INVALID_MULT, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        m = round(multiplier, 2)
        await self.db.set_multiplier(interaction.guild.id, m)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=MULTIPLIER_SET_SUCCESS.format(mult=m), color=BOT_SUCCESS_COLOR
            )
        )

    # ── entity multipliers ────────────────────────────────────────────────────

    multiplier_group = app_commands.Group(
        name=CMD_ENTITY_MULT,
        description="Manage per-role/channel/user XP multipliers.",
        guild_only=True,
    )

    @multiplier_group.command(name="set", description="[Admin] Set an XP multiplier for a role, channel, or user.")
    @app_commands.describe(
        entity_type="What to apply the multiplier to.",
        entity_id="The ID of the role, channel, or user.",
        multiplier="Multiplier value (e.g. 1.5 = +50% XP).",
    )
    @app_commands.choices(entity_type=[
        app_commands.Choice(name="Role", value="role"),
        app_commands.Choice(name="Channel", value="channel"),
        app_commands.Choice(name="User", value="user"),
    ])
    async def multiplier_set(
        self,
        interaction: discord.Interaction,
        entity_type: str,
        entity_id: str,
        multiplier: float,
    ) -> None:
        if not await self._guard(interaction):
            return
        if multiplier <= 0:
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_INVALID_MULT, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        try:
            eid = int(entity_id)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Invalid ID — must be a number.", color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        m = round(multiplier, 2)
        await self.db.set_entity_multiplier(interaction.guild.id, entity_type, eid, m)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=ENTITY_MULT_SET.format(mult=m, type=entity_type, id=entity_id),
                color=BOT_SUCCESS_COLOR,
            )
        )

    @multiplier_group.command(name="remove", description="[Admin] Remove an XP multiplier.")
    @app_commands.describe(
        entity_type="Type of entity.",
        entity_id="The ID of the role, channel, or user.",
    )
    @app_commands.choices(entity_type=[
        app_commands.Choice(name="Role", value="role"),
        app_commands.Choice(name="Channel", value="channel"),
        app_commands.Choice(name="User", value="user"),
    ])
    async def multiplier_remove(
        self,
        interaction: discord.Interaction,
        entity_type: str,
        entity_id: str,
    ) -> None:
        if not await self._guard(interaction):
            return
        try:
            eid = int(entity_id)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Invalid ID.", color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        removed = await self.db.remove_entity_multiplier(interaction.guild.id, entity_type, eid)
        color = BOT_SUCCESS_COLOR if removed else BOT_WARN_COLOR
        desc = ENTITY_MULT_REMOVED.format(type=entity_type, id=entity_id) if removed else "⚠️ No multiplier found for that entity."
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=color)
        )

    @multiplier_group.command(name="list", description="[Admin] List all entity multipliers.")
    async def multiplier_list(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        rows = await self.db.get_entity_multipliers(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=discord.Embed(description="No per-entity multipliers configured.", color=BOT_WARN_COLOR),
                ephemeral=True,
            )
            return
        lines = [f"**{r['entity_type']}** `{r['entity_id']}` → **{r['multiplier']}x**" for r in rows]
        embed = discord.Embed(title="⚡ Entity Multipliers", description="\n".join(lines), color=BOT_COLOR)
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── blacklist ─────────────────────────────────────────────────────────────

    blacklist_group = app_commands.Group(
        name=CMD_BLACKLIST,
        description="Manage who/what is blocked from earning XP.",
        guild_only=True,
    )

    @blacklist_group.command(name="add", description="[Admin] Block a user, role, or channel from earning XP.")
    @app_commands.describe(
        entity_type="What kind of entity to blacklist.",
        entity_id="The ID of the user, role, or channel.",
    )
    @app_commands.choices(entity_type=[
        app_commands.Choice(name="User", value="user"),
        app_commands.Choice(name="Role", value="role"),
        app_commands.Choice(name="Channel", value="channel"),
    ])
    async def blacklist_add(
        self, interaction: discord.Interaction, entity_type: str, entity_id: str
    ) -> None:
        if not await self._guard(interaction):
            return
        try:
            eid = int(entity_id)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Invalid ID.", color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        await self.db.add_blacklist(interaction.guild.id, entity_type, eid)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=BLACKLIST_ADD.format(type=entity_type, id=entity_id),
                color=BOT_SUCCESS_COLOR,
            )
        )

    @blacklist_group.command(name="remove", description="[Admin] Remove a user, role, or channel from the XP blacklist.")
    @app_commands.describe(
        entity_type="Entity type.",
        entity_id="The ID to remove.",
    )
    @app_commands.choices(entity_type=[
        app_commands.Choice(name="User", value="user"),
        app_commands.Choice(name="Role", value="role"),
        app_commands.Choice(name="Channel", value="channel"),
    ])
    async def blacklist_remove(
        self, interaction: discord.Interaction, entity_type: str, entity_id: str
    ) -> None:
        if not await self._guard(interaction):
            return
        try:
            eid = int(entity_id)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Invalid ID.", color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        assert interaction.guild
        removed = await self.db.remove_blacklist(interaction.guild.id, entity_type, eid)
        color = BOT_SUCCESS_COLOR if removed else BOT_WARN_COLOR
        desc = BLACKLIST_REMOVE.format(type=entity_type, id=entity_id) if removed else "⚠️ That entity wasn't in the blacklist."
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=color)
        )

    @blacklist_group.command(name="list", description="[Admin] Show all blacklisted entities.")
    async def blacklist_list(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        rows = await self.db.get_blacklist(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=discord.Embed(description="Blacklist is empty.", color=BOT_WARN_COLOR),
                ephemeral=True,
            )
            return
        lines = [f"**{r['entity_type']}** `{r['entity_id']}`" for r in rows]
        embed = discord.Embed(title="🚫 XP Blacklist", description="\n".join(lines), color=BOT_COLOR)
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── role rewards ──────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_ROLE_REWARD_ADD, description="[Admin] Set a role reward for a level.")
    @app_commands.describe(level="Level that triggers the reward.", role="Role to grant.")
    @app_commands.guild_only()
    async def addrolereward(self, interaction: discord.Interaction, level: int, role: discord.Role) -> None:
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

    @app_commands.command(name=CMD_ROLE_REWARD_REMOVE, description="[Admin] Remove a role reward.")
    @app_commands.describe(level="Level whose reward to remove.")
    @app_commands.guild_only()
    async def removerolereward(self, interaction: discord.Interaction, level: int) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        removed = await self.db.remove_role_reward(interaction.guild.id, level)
        color = BOT_SUCCESS_COLOR if removed else BOT_WARN_COLOR
        desc = ROLE_REMOVED_SUCCESS.format(level=level) if removed else f"⚠️ No reward set for level **{level}**."
        await interaction.response.send_message(embed=discord.Embed(description=desc, color=color))

    @app_commands.command(name=CMD_ROLE_REWARD_LIST, description="[Admin] List all role rewards.")
    @app_commands.guild_only()
    async def listroles(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        rows = await self.db.get_role_rewards(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=discord.Embed(description="No role rewards set. Use `/addrolereward`.", color=BOT_WARN_COLOR),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            role = interaction.guild.get_role(r["role_id"])
            role_str = role.mention if role else f"Deleted ({r['role_id']})"
            lines.append(f"**Level {r['level']}** → {role_str}")
        embed = discord.Embed(title="🎖️ Role Rewards", description="\n".join(lines), color=BOT_COLOR)
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── voice XP toggle ───────────────────────────────────────────────────────

    @app_commands.command(name="voicexp", description="[Admin] Enable or disable voice XP for this server.")
    @app_commands.describe(enabled="True to enable, False to disable.")
    @app_commands.guild_only()
    async def voicexp(self, interaction: discord.Interaction, enabled: bool) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        await self.db.set_voice_xp_enabled(interaction.guild.id, enabled)
        state = "enabled ✅" if enabled else "disabled ❌"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"Voice XP is now **{state}**.", color=BOT_SUCCESS_COLOR)
        )

    # ── drops toggle ──────────────────────────────────────────────────────────

    @app_commands.command(name="dropsenable", description="[Admin] Enable or disable auto XP drops.")
    @app_commands.describe(enabled="True to enable auto-drops.")
    @app_commands.guild_only()
    async def dropsenable(self, interaction: discord.Interaction, enabled: bool) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        await self.db.set_drops_enabled(interaction.guild.id, enabled)
        state = "enabled ✅" if enabled else "disabled ❌"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"Auto XP drops are now **{state}**.", color=BOT_SUCCESS_COLOR)
        )

    # ── config view ───────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_CONFIG_VIEW, description="[Admin] View Phosphorus settings for this server.")
    @app_commands.guild_only()
    async def config(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        cfg = await self.db.get_config(interaction.guild.id)

        def _ch(col: str) -> str:
            if not cfg or not cfg[col]:
                return "_Not set_"
            ch = interaction.guild.get_channel(cfg[col])  # type: ignore[union-attr]
            return ch.mention if ch else f"Deleted ({cfg[col]})"

        embed = discord.Embed(
            title=f"⚙️ Phosphorus Config — {interaction.guild.name}",
            color=BOT_COLOR,
        )
        embed.add_field(name="Level-Up Channel", value=_ch("levelup_channel"), inline=True)
        embed.add_field(name="Weekly Report Channel", value=_ch("weekly_channel"), inline=True)
        embed.add_field(name="XP Drops Channel", value=_ch("drops_channel"), inline=True)
        embed.add_field(name="Server XP Multiplier", value=f"**{cfg['xp_multiplier'] if cfg else 1.0}x**", inline=True)
        embed.add_field(name="Voice XP", value="✅ Enabled" if (not cfg or cfg["voice_xp_enabled"]) else "❌ Disabled", inline=True)
        embed.add_field(name="Auto Drops", value="✅ Enabled" if (cfg and cfg["drops_enabled"]) else "❌ Disabled", inline=True)
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
