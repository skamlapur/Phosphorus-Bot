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
    VARIABLES,
    COLOUR_ZERO,
    COLOUR_ONE,
    COLOUR_TWO,
    COLOUR_THREE,
    COLOUR_FOUR,
    COLOUR_FIVE,
    COLOUR_SIX,
    COLOUR_SEVEN,
    COLOUR_EIGHT
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

# Modular categorization of administrative subcommands to reduce embed clutter
_ADMIN_LEVELING = [
    ("/givexp @member amount", "Give XP to a member."),
    ("/takexp @member amount", "Remove XP from a member."),
    ("/resetxp @member", "Reset a member's XP and stats to zero."),
    ("/setlevel @member level", "Jump a member to a specific level."),
    ("/addrolereward level @role", "Grant a role automatically at a level."),
    ("/removerolereward level", "Remove a role reward."),
    ("/listroles", "List all role rewards."),
]

_ADMIN_MULTIPLIERS = [
    ("/setmultiplier value", "Global server-wide XP multiplier (applies to everything)."),
    ("/multiplier set type @entity value", "Per-role / per-channel / per-user XP multiplier (overrides global)."),
    ("/multiplier remove type @entity", "Remove a per-entity multiplier."),
    ("/multiplier list", "List all per-entity multipliers."),
]

_ADMIN_BLACKLIST = [
    ("/blacklist add type @entity", "Block a user/role/channel from earning XP."),
    ("/blacklist remove type @entity", "Unblock."),
    ("/blacklist list", "Show all blacklisted entities."),
]

_ADMIN_DROPS = [
    ("/dropcreate question answer [xp]", "Create a queued XP drop/trivia."),
    ("/droptrigger", "Post the next queued drop immediately."),
    ("/dropsenable true/false", "Enable or disable auto-drops."),
]

_ADMIN_CONFIG_PERMITS = [
    ("/setchannel [#channel]", "Set the level-up announcement channel."),
    ("/setweekchannel [#channel]", "Set the weekly report channel."),
    ("/setdropschannel [#channel]", "Set the XP drops channel."),
    ("/voicexp true/false", "Enable or disable voice XP."),
    ("/config", "View all current server settings."),
    ("/permit set command type @user/@role", "Grant a role/user access to a specific admin command."),
    ("/permit remove command type @user/@role", "Remove a command permit."),
    ("/permit list [command]", "List all active permits."),
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
        
    elif category == "Leveling Commands":
        lines = "\n".join(f"`{name}` — {desc}" for name, desc in _ADMIN_LEVELING)
        embed.add_field(name="Admin Leveling System", value=lines, inline=False)

    elif category == "Multiplier Commands":
        lines = "\n".join(f"`{name}` — {desc}" for name, desc in _ADMIN_MULTIPLIERS)
        embed.add_field(name="XP Multipliers Configuration", value=lines, inline=False)

    elif category == "Blacklist Commands":
        lines = "\n".join(f"`{name}` — {desc}" for name, desc in _ADMIN_BLACKLIST)
        embed.add_field(name="System Restrictions & Blacklists", value=lines, inline=False)

    elif category == "XP Drops Commands":
        lines = "\n".join(f"`{name}` — {desc}" for name, desc in _ADMIN_DROPS)
        embed.add_field(name="Random XP Drops & Trivia", value=lines, inline=False)

    elif category == "Configuration & Permits":
        lines = "\n".join(f"`{name}` — {desc}" for name, desc in _ADMIN_CONFIG_PERMITS)
        embed.add_field(name="Server Settings & Permissions", value=lines, inline=False)
            
    elif category == "Booster Overview":
        embed.add_field(
            name="Booster Roles & Channels",
            value=(
                "Up to **3 booster roles** and **3 booster channels** can be configured per server. "
                "Members who have a booster role or send messages in a booster channel earn extra XP.\n"
                "Use `/booster set role|channel <id> [multiplier]` to add one, "
                "`/booster remove` to delete, and `/booster list` to display active configurations."
            ),
            inline=False,
        )

    elif category == "Variables":
        # Format the global text custom components directly from variables dictionary
        var_lines = "\n".join(f"**{var}** — {desc}" for var, desc in VARIABLES.items())
        embed.add_field(
            name="🔑 Level-Up Announcement Placeholders", 
            value=f"Use these text codes within your customizable level-up message configurations:\n\n{var_lines}", 
            inline=False
        )

    embed.set_footer(text=EMBED_FOOTER)
    return embed


class HelpDropdown(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Main Menu", description="Return to the main help screen.", emoji=COLOUR_ZERO),
            discord.SelectOption(label="User Commands", description="Show general member commands.", emoji=COLOUR_ONE),
            discord.SelectOption(label="Booster Overview", description="View details on XP Boosters.", emoji=COLOUR_TWO),
            discord.SelectOption(label="Leveling Commands", description="Manage user levels and experience.", emoji=COLOUR_THREE),
            discord.SelectOption(label="Multiplier Commands", description="Configure experience point scales.", emoji=COLOUR_FOUR),
            discord.SelectOption(label="Blacklist Commands", description="Restrict specific users or rooms.", emoji=COLOUR_FIVE),
            discord.SelectOption(label="XP Drops Commands", description="Control dynamic interaction events.", emoji=COLOUR_SIX),
            discord.SelectOption(label="Configuration & Permits", description="System core configurations.", emoji=COLOUR_SEVEN),
            discord.SelectOption(label="Variables", description="Placeholders for announcement customization.", emoji=COLOUR_EIGHT),
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
