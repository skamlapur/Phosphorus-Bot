"""
Phosphorus – Bot Info cog (v2.2)
Shows bot stats, system info, and version.
"""
from __future__ import annotations

import logging
import os
import platform
import time

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    BOT_COLOR,
    BOT_NAME,
    BOT_VERSION,
    CMD_BOTINFO,
    DB_PATH,
    EMBED_FOOTER,
)

log = logging.getLogger(__name__)


def _uptime(start: float) -> str:
    delta = int(time.time() - start)
    days, rem = divmod(delta, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


def _system_stats() -> dict[str, str]:
    stats: dict[str, str] = {}
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info().rss / (1024 * 1024)
        stats["RAM"] = f"{mem:.1f} MB"
        stats["CPU"] = f"{psutil.cpu_percent(interval=0.1):.1f}%"
    except Exception:
        stats["RAM"] = "N/A (psutil not installed)"
        stats["CPU"] = "N/A (psutil not installed)"

    try:
        db_size = os.path.getsize(DB_PATH)
        stats["DB Size"] = f"{db_size / (1024 * 1024):.2f} MB"
    except Exception:
        stats["DB Size"] = "N/A"
    return stats


class BotInfo(commands.Cog, name="BotInfo"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── slash command ─────────────────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD_BOTINFO, description="Show bot info, stats, and system status.")
    async def botinfo_slash(self, interaction: discord.Interaction) -> None:
        try:
            embed = self._build_embed()
            await interaction.response.send_message(embed=embed)
        except Exception as exc:
            log.error("botinfo_slash failed: %s", exc, exc_info=True)
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Failed to build bot info.", color=0xED4245),
                ephemeral=True,
            )

    # ── prefix command ─────────────────────────────────────────────────────────────────────────────

    @commands.command(name=CMD_BOTINFO, aliases=["bi", "about"])
    async def botinfo_prefix(self, ctx: commands.Context) -> None:
        embed = self._build_embed()
        await ctx.send(embed=embed)

    def _build_embed(self) -> discord.Embed:
        assert self.bot.user
        guild_count = len(self.bot.guilds)
        total_members = sum(g.member_count or 0 for g in self.bot.guilds)

        embed = discord.Embed(
            title=f"{BOT_NAME} v{BOT_VERSION}",
            description=f"**{BOT_NAME}** is a full-featured Discord leveling bot built with discord.py.",
            color=BOT_COLOR,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        start = getattr(self.bot, "_start_time", time.time())
        sys_stats = _system_stats()

        embed.add_field(name="Guilds", value=f"**{guild_count}**", inline=True)
        embed.add_field(name="Members", value=f"**{total_members:,}**", inline=True)
        embed.add_field(name="Uptime", value=_uptime(start), inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="RAM", value=sys_stats.get("RAM", "N/A"), inline=True)
        embed.add_field(name="CPU", value=sys_stats.get("CPU", "N/A"), inline=True)
        embed.add_field(name="DB Size", value=sys_stats.get("DB Size", "N/A"), inline=True)

        embed.set_footer(text=EMBED_FOOTER)
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotInfo(bot))
