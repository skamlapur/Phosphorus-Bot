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
    RED_CROSS,
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
    ("/setmultiplier value", "Global server-wide XP multiplier (applies to everything)."),
    ("/multiplier set type @entity value", "Per-role / per-channel / per-user XP multiplier (overrides global)."),
    ("/multiplier remove type @entity", "Remove a per-entity multiplier."),
    ("/multiplier list", "List all per-entity multipliers."),
    ("/blacklist add type @entity", "Block a user/role/channel from earning XP."),
    ("/blacklist remove type @entity", "Unblock."),
    ("/blacklist list", "Show all blacklisted entities."),
    ("/addrolereward level @role", "Grant a role automatically at a level."),
    ("/removerolereward level", "Remove a role reward."),
    ("/listroles", "List all role rewards."),
    ("/voicexp true/false", "Enable or disable voice XP."),
    ("/dropcreate question answer [xp]", "Create a queued XP drop/trivia."),
    ("/droptrigger", "Post the next queued drop immediately."),
    ("/dropsenable true/false", "Enable or disable auto-drops."),
    ("/config", "View all current server settings."),
    ("/permit set command type @user/@role", "Grant a role/user access to a specific admin command."),
    ("/permit remove command type @user/@role", "Remove a command permit."),
    ("/permit list [command]", "List all active permits."),
    ("/booster set role|channel @role/#channel [mult]", "Set a booster role/channel (up to 3 each). Default 1.5x."),
    ("/booster remove role|channel @role/#channel", "Remove a booster role or channel."),
    ("/booster list", "Show all active XP boosters."),
]


def _build_main_embed() -> discord.Embed:
    """Builds the initial landing page help embed."""
    embed = discord.Embed(
        title=f"{BOT_NAME} Help",
        description=(
            f"**{BOT_NAME}** is a full-featured Discord leveling bot.\n\n"
            "Select the category you want to see commands of:"
        ),
        color=BOT_COLOR,
    )
    embed.set_footer(text=EMBED_FOOTER)
    return embed


def _build_category_embed(category: str) -> discord.Embed:
    """Builds the specific category views when picked from the dropdown."""
    embed = discord.Embed(
        title=f"{BOT_NAME} Help — {category}",
        color=BOT_COLOR,
    )
    
    if category == "User Commands":
        user_lines = "\n".join(f"**{name}**\n{desc}" for name, desc in _USER_COMMANDS)
        embed.add_field(name="General Commands", value=user_lines, inline=False)
        
    elif category == "Admin Commands":
        admin_fields: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for name, desc in _ADMIN_COMMANDS:
            line = f"`{name}` — {desc}\n"
            if current_length + len(line) > 1000:
                admin_fields.append("".join(current_chunk))
                current_chunk = [line]
                current_length = len(line)
            else:
                current_chunk.append(line)
                current_length += len(line)

        if current_chunk:
            admin_fields.append("".join(current_chunk))

        for i, field_content in enumerate(admin_fields):
            field_name = "Admin Actions" if i == 0 else "Admin Actions (Continued)"
            embed.add_field(name=field_name, value=field_content, inline=False)
            
    elif category == "System Overview":
        embed.add_field(
            name="Permit System",
            value=(
                "Permits let server owners grant specific users or roles access "
                "to individual admin commands without giving them full Manage Server.\n"
                "Use `/permit set <command> role|user <id>` to grant, "
                "`/permit remove` to revoke, `/permit list` to inspect."
            ),
            inline=False,
        )
        embed.add_field(
            name="Booster Roles & Channels",
            value=(
                "Up to **3 booster roles** and **3 booster channels** can be configured per server. "
                "Members who have a booster role or send messages in a booster channel earn extra XP.\n"
                "Use `/booster set role|channel <id> [multiplier]` to add one."
            ),
            inline=False,
        )

    embed.set_footer(text=EMBED_FOOTER)
    return embed


class HelpDropdown(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Main Menu", description="Return to the main help screen."),
            discord.SelectOption(label="User Commands", description="Show general member commands."),
            discord.SelectOption(label="Admin Commands", description="Show server management commands."),
            discord.SelectOption(label="System Overview", description="View details on Permits and Boosters."),
        ]
        super().__init__(placeholder="Choose a help category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_category = self.values[0]
        
        if selected_category == "Main Menu":
            new_embed = _build_main_embed()
        else:
            new_embed = _build_category_embed(selected_category)
            
        await interaction.response.edit_message(embed=new_embed, view=self.view)


class HelpDropdownView(discord.ui.View):
    def __init__(self, timeout: float = 120.0) -> None:
        super().__init__(timeout=timeout)
        self.add_item(HelpDropdown())


class Help(commands.Cog, name="Help"):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── slash command ─────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_HELP, description="Show all Phosphorus commands.")
    async def help_slash(self, interaction: discord.Interaction) -> None:
        try:
            embed = _build_main_embed()
            view = HelpDropdownView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as exc:
            log.error("help_slash failed: %s", exc, exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=discord.Embed(description=f"{RED_CROSS} Failed to show help. Please try again.", color=0xED4245),
                    ephemeral=True,
                )

    # ── prefix command ────────────────────────────────────────────────────────

    @commands.command(name=CMD_HELP, aliases=["h", "commands"])
    async def help_prefix(self, ctx: commands.Context) -> None:
        embed = _build_main_embed()
        view = HelpDropdownView()
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
