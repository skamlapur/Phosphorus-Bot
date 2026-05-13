"""
Phosphorus – Help cog (v2.1)
/help  and  p!help — shows all available commands, grouped by category.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    BOT_COLOR,
    BOT_NAME,
    BOT_VERSION,
    CMD_HELP,
    CMD_PREFIX,
    EMBED_FOOTER,
)

log = logging.getLogger(__name__)

_USER_COMMANDS = [
    (f"`{CMD_PREFIX}rank [@member]`  or  `/rank`",
     "Your full profile: level, XP, messages, voice, streak, weekly stats."),
    (f"`{CMD_PREFIX}leaderboard [type]`  or  `/leaderboard`",
     "Server leaderboard — types: `xp`, `messages`, `voice`, `weekly_xp`, `weekly_messages`, `weekly_voice`."),
    (f"`{CMD_PREFIX}streak [@member]`  or  `/streak`",
     "Current streak, longest streak, and active XP bonus."),
    (f"`{CMD_PREFIX}help`  or  `/help`",
     "Show this help message."),
]

_ADMIN_COMMANDS = [
    ("/givexp @member amount", "Give XP to a member."),
    ("/takexp @member amount", "Remove XP from a member."),
    ("/resetxp @member", "Reset a member's XP and stats to zero."),
    ("/setlevel @member level", "Jump a member to a specific level."),
    ("/setchannel [#channel]", "Set the level-up announcement channel."),
    ("/setweekchannel [#channel]", "Set the weekly report channel."),
    ("/setdropschannel [#channel]", "Set the XP drops channel."),
    ("/setmultiplier value", "Server-wide XP multiplier (e.g. `2.0`)."),
    ("/multiplier set type id value", "Per-role/channel/user XP multiplier."),
    ("/multiplier remove type id", "Remove a per-entity multiplier."),
    ("/multiplier list", "List all per-entity multipliers."),
    ("/blacklist add type id", "Block a user/role/channel from earning XP."),
    ("/blacklist remove type id", "Unblock."),
    ("/blacklist list", "Show all blacklisted entities."),
    ("/addrolereward level @role", "Grant a role automatically at a level."),
    ("/removerolereward level", "Remove a role reward."),
    ("/listroles", "List all role rewards."),
    ("/voicexp true/false", "Enable or disable voice XP."),
    ("/dropcreate question answer [xp]", "Create a queued XP drop/trivia."),
    ("/droptrigger", "Post the next queued drop immediately."),
    ("/dropsenable true/false", "Enable or disable auto-drops."),
    ("/config", "View all current server settings."),
    ("/permit set command type id", "Grant a role/user access to a specific admin command."),
    ("/permit remove command type id", "Remove a command permit."),
    ("/permit list [command]", "List all active permits."),
    ("/booster set role|channel id [mult]", "Set a booster role/channel (up to 3 each). Default 1.5x."),
    ("/booster remove role|channel id", "Remove a booster role or channel."),
    ("/booster list", "Show all active XP boosters."),
]


def _build_embed() -> discord.Embed:
    embed = discord.Embed(
        title=f"📖 {BOT_NAME} Help",
        description=(
            f"**{BOT_NAME}** is a full-featured XP leveling bot.\n"
            f"Prefix: `{CMD_PREFIX}` · Slash commands: `/`"
        ),
        color=BOT_COLOR,
    )

    user_lines = "\n".join(
        f"**{name}**\n{desc}" for name, desc in _USER_COMMANDS
    )
    embed.add_field(name="👤 User Commands", value=user_lines, inline=False)

    admin_lines = "\n".join(
        f"`{name}` — {desc}" for name, desc in _ADMIN_COMMANDS
    )
    embed.add_field(
        name="🛡️ Admin Commands  *(Manage Server / Administrator / Permit)*",
        value=admin_lines,
        inline=False,
    )

    embed.add_field(
        name="🔑 Permit System",
        value=(
            "Permits let server owners grant specific users or roles access "
            "to individual admin commands without giving them full Manage Server.\n"
            "Use `/permit set <command> role|user <id>` to grant, "
            "`/permit remove` to revoke, `/permit list` to inspect."
        ),
        inline=False,
    )
    embed.add_field(
        name="🚀 Booster Roles & Channels",
        value=(
            "Up to **3 booster roles** and **3 booster channels** can be configured per server. "
            "Members who have a booster role or send messages in a booster channel earn extra XP "
            "(the highest applicable booster multiplier is used, stacking on top of other multipliers).\n"
            "Use `/booster set role|channel <id> [multiplier]` to add one."
        ),
        inline=False,
    )

    embed.set_footer(text=f"{EMBED_FOOTER} · v{BOT_VERSION}")
    return embed


class Help(commands.Cog, name="Help"):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── slash command ─────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_HELP, description="Show all Phosphorus commands.")
    async def help_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=_build_embed(), ephemeral=True)

    # ── prefix command ────────────────────────────────────────────────────────

    @commands.command(name=CMD_HELP, aliases=["h", "commands"])
    async def help_prefix(self, ctx: commands.Context) -> None:
        await ctx.send(embed=_build_embed())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
