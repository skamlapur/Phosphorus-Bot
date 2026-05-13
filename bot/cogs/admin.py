"""
Phosphorus – Admin cog (v2.1)
Full suite of admin commands: XP management, config, blacklist,
per-entity multipliers, role rewards, drops, voice toggle, permit system.
"""
from __future__ import annotations

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    ADMIN_COMMANDS,
    BLACKLIST_ADD,
    BLACKLIST_REMOVE,
    BOT_COLOR,
    BOT_ERROR_COLOR,
    BOT_SUCCESS_COLOR,
    BOT_WARN_COLOR,
    BOOSTER_DEFAULT_MULTIPLIER,
    BOOSTER_LIMIT,
    BOOSTER_MAX_CHANNELS,
    BOOSTER_MAX_ROLES,
    BOOSTER_NOT_FOUND,
    BOOSTER_REMOVED,
    BOOSTER_SET,
    CHANNEL_SET_SUCCESS,
    CMD_BLACKLIST,
    CMD_BOOSTER,
    CMD_CONFIG_VIEW,
    CMD_DROP_CREATE,
    CMD_ENTITY_MULT,
    CMD_GIVE_XP,
    CMD_LEVEL_RESET,
    CMD_LEVEL_SET,
    CMD_PERMIT,
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
    PERMIT_NOT_FOUND,
    PERMIT_REMOVED,
    PERMIT_SET,
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
        """Return True if the invoker may run this admin command.

        Passes if the member has Manage Server / Administrator,
        OR has a permit explicitly granted for this command.
        """
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=discord.Embed(description=ERR_NO_PERMISSION, color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return False

        member = interaction.user

        if _is_admin(member):
            return True

        assert interaction.guild
        cmd_name = interaction.command.qualified_name if interaction.command else ""
        role_ids = [r.id for r in member.roles]
        if await self.db.has_permit(interaction.guild.id, cmd_name, member.id, role_ids):
            return True

        await interaction.response.send_message(
            embed=discord.Embed(description=ERR_NO_PERMISSION, color=BOT_ERROR_COLOR),
            ephemeral=True,
        )
        return False

    async def _admin_only_guard(self, interaction: discord.Interaction) -> bool:
        """Strict guard — only Manage Server / Administrator (no permits)."""
        if not isinstance(interaction.user, discord.Member) or not _is_admin(interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Only server administrators can manage permits.", color=BOT_ERROR_COLOR),
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

    # ── drops ─────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_DROP_CREATE, description="[Admin] Create a queued XP drop/trivia question.")
    @app_commands.describe(
        question="The question to ask.",
        answer="The correct answer (case-insensitive).",
        xp="XP reward (default from config).",
    )
    @app_commands.guild_only()
    async def dropcreate(
        self,
        interaction: discord.Interaction,
        question: str,
        answer: str,
        xp: int = 300,
    ) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        cfg = await self.db.get_config(interaction.guild.id)
        if not cfg or not cfg["drops_channel"]:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ Set a drops channel first with `/setdropschannel`.",
                    color=BOT_ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return
        import time
        await self.db.create_drop(
            interaction.guild.id, cfg["drops_channel"], question, answer.strip().lower(), max(1, xp), time.time()
        )
        await interaction.response.send_message(
            embed=discord.Embed(
                description="✅ Drop created. Use `/droptrigger` to post it, or it will auto-post if drops are enabled.",
                color=BOT_SUCCESS_COLOR,
            )
        )

    @app_commands.command(name="droptrigger", description="[Admin] Post the next queued XP drop immediately.")
    @app_commands.guild_only()
    async def droptrigger(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        drops_cog = self.bot.get_cog("Drops")
        if not drops_cog:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Drops system unavailable.", color=BOT_ERROR_COLOR),
                ephemeral=True,
            )
            return
        result = await drops_cog.trigger_drop(interaction.guild.id)  # type: ignore[attr-defined]
        color = BOT_SUCCESS_COLOR if result.startswith("✅") else BOT_WARN_COLOR
        await interaction.response.send_message(
            embed=discord.Embed(description=result, color=color),
            ephemeral=True,
        )

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

    # ── permit system ─────────────────────────────────────────────────────────

    permit_group = app_commands.Group(
        name=CMD_PERMIT,
        description="Grant specific users or roles access to individual admin commands.",
        guild_only=True,
    )

    @permit_group.command(name="set", description="[Admin] Grant a role or user access to a specific command.")
    @app_commands.describe(
        command="The admin command name to permit.",
        entity_type="Whether to grant to a role or user.",
        entity_id="The ID of the role or user.",
    )
    @app_commands.choices(
        command=[app_commands.Choice(name=c, value=c) for c in ADMIN_COMMANDS],
        entity_type=[
            app_commands.Choice(name="Role", value="role"),
            app_commands.Choice(name="User", value="user"),
        ],
    )
    async def permit_set(
        self,
        interaction: discord.Interaction,
        command: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        if not await self._admin_only_guard(interaction):
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
        await self.db.add_permit(interaction.guild.id, command, entity_type, eid)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=PERMIT_SET.format(cmd=command, type=entity_type, id=entity_id),
                color=BOT_SUCCESS_COLOR,
            )
        )

    @permit_group.command(name="remove", description="[Admin] Remove a command permit from a role or user.")
    @app_commands.describe(
        command="The command whose permit to remove.",
        entity_type="Role or user.",
        entity_id="The ID of the role or user.",
    )
    @app_commands.choices(
        command=[app_commands.Choice(name=c, value=c) for c in ADMIN_COMMANDS],
        entity_type=[
            app_commands.Choice(name="Role", value="role"),
            app_commands.Choice(name="User", value="user"),
        ],
    )
    async def permit_remove(
        self,
        interaction: discord.Interaction,
        command: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        if not await self._admin_only_guard(interaction):
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
        removed = await self.db.remove_permit(interaction.guild.id, command, entity_type, eid)
        color = BOT_SUCCESS_COLOR if removed else BOT_WARN_COLOR
        desc = (
            PERMIT_REMOVED.format(cmd=command, type=entity_type, id=entity_id)
            if removed else PERMIT_NOT_FOUND
        )
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=color)
        )

    @permit_group.command(name="list", description="[Admin] List all active command permits.")
    @app_commands.describe(command="Filter by command (optional).")
    @app_commands.choices(
        command=[app_commands.Choice(name=c, value=c) for c in ADMIN_COMMANDS],
    )
    async def permit_list(
        self,
        interaction: discord.Interaction,
        command: str | None = None,
    ) -> None:
        if not await self._admin_only_guard(interaction):
            return
        assert interaction.guild
        rows = await self.db.get_permits(interaction.guild.id, command)
        if not rows:
            desc = "No permits configured" + (f" for `{command}`" if command else "") + "."
            await interaction.response.send_message(
                embed=discord.Embed(description=desc, color=BOT_WARN_COLOR),
                ephemeral=True,
            )
            return
        lines = [
            f"`{r['command_name']}` → **{r['entity_type']}** `{r['entity_id']}`"
            for r in rows
        ]
        title = f"🔑 Permits" + (f" — {command}" if command else "")
        embed = discord.Embed(title=title, description="\n".join(lines), color=BOT_COLOR)
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)


    # ── booster system ────────────────────────────────────────────────────────

    booster_group = app_commands.Group(
        name=CMD_BOOSTER,
        description="Set up to 3 booster roles and 3 booster channels that earn bonus XP.",
        guild_only=True,
    )

    @booster_group.command(name="set", description="[Admin] Set an XP booster role or channel.")
    @app_commands.describe(
        entity_type="Whether to boost a role or a channel.",
        entity_id="The ID of the role or channel.",
        multiplier=f"XP multiplier (default {BOOSTER_DEFAULT_MULTIPLIER}). Must be > 1.",
    )
    @app_commands.choices(entity_type=[
        app_commands.Choice(name="Role", value="role"),
        app_commands.Choice(name="Channel", value="channel"),
    ])
    async def booster_set(
        self,
        interaction: discord.Interaction,
        entity_type: str,
        entity_id: str,
        multiplier: float = BOOSTER_DEFAULT_MULTIPLIER,
    ) -> None:
        if not await self._guard(interaction):
            return
        if multiplier <= 1.0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ Booster multiplier must be greater than **1.0**.",
                    color=BOT_ERROR_COLOR,
                ),
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
        ok = await self.db.add_booster(
            interaction.guild.id, entity_type, eid, multiplier,
            BOOSTER_MAX_ROLES, BOOSTER_MAX_CHANNELS,
        )
        if not ok:
            max_val = BOOSTER_MAX_ROLES if entity_type == "role" else BOOSTER_MAX_CHANNELS
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=BOOSTER_LIMIT.format(max=max_val, type=entity_type),
                    color=BOT_ERROR_COLOR,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=discord.Embed(
                description=BOOSTER_SET.format(mult=round(multiplier, 2), type=entity_type, id=entity_id),
                color=BOT_SUCCESS_COLOR,
            )
        )

    @booster_group.command(name="remove", description="[Admin] Remove an XP booster role or channel.")
    @app_commands.describe(
        entity_type="Role or channel.",
        entity_id="The ID to remove.",
    )
    @app_commands.choices(entity_type=[
        app_commands.Choice(name="Role", value="role"),
        app_commands.Choice(name="Channel", value="channel"),
    ])
    async def booster_remove(
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
        removed = await self.db.remove_booster(interaction.guild.id, entity_type, eid)
        color = BOT_SUCCESS_COLOR if removed else BOT_WARN_COLOR
        desc = (
            BOOSTER_REMOVED.format(type=entity_type, id=entity_id)
            if removed
            else BOOSTER_NOT_FOUND.format(type=entity_type)
        )
        await interaction.response.send_message(
            embed=discord.Embed(description=desc, color=color)
        )

    @booster_group.command(name="list", description="[Admin] List all active XP boosters.")
    async def booster_list(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        assert interaction.guild
        rows = await self.db.get_boosters(interaction.guild.id)
        if not rows:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="No boosters configured. Use `/booster set` to add one.",
                    color=BOT_WARN_COLOR,
                ),
                ephemeral=True,
            )
            return
        lines: list[str] = []
        for r in rows:
            if r["entity_type"] == "role":
                obj = interaction.guild.get_role(r["entity_id"])
                label = obj.mention if obj else f"Deleted role ({r['entity_id']})"
            else:
                obj = interaction.guild.get_channel(r["entity_id"])
                label = obj.mention if obj else f"Deleted channel ({r['entity_id']})"
            lines.append(f"**{r['entity_type'].title()}** {label} → **{r['multiplier']}x**")
        roles_used = sum(1 for r in rows if r["entity_type"] == "role")
        channels_used = sum(1 for r in rows if r["entity_type"] == "channel")
        embed = discord.Embed(
            title="🚀 XP Boosters",
            description="\n".join(lines),
            color=BOT_COLOR,
        )
        embed.set_footer(
            text=f"{EMBED_FOOTER} · "
                 f"Roles {roles_used}/{BOOSTER_MAX_ROLES} · "
                 f"Channels {channels_used}/{BOOSTER_MAX_CHANNELS}"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
