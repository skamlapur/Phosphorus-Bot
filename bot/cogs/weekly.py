from __future__ import annotations

import logging
from datetime import date, timedelta

import discord
from discord.ext import commands, tasks

from constants import (
    BOT_GOLD_COLOR,
    EMBED_FOOTER,
    WEEKLY_REPORT_DAY,
    WEEKLY_REPORT_HOUR,
)
from database import Database

log = logging.getLogger(__name__)


def _last_week_str() -> str:
    """ISO week string for the week that just ended."""
    last_week = date.today() - timedelta(days=7)
    iso = last_week.isocalendar()
    return f"{iso[0]:04d}-{iso[1]:02d}"


class Weekly(commands.Cog, name="Weekly"):
    """Auto weekly leaderboard report."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.weekly_report_loop.start()

    def cog_unload(self) -> None:
        self.weekly_report_loop.cancel()

    @tasks.loop(hours=1)
    async def weekly_report_loop(self) -> None:
        now = date.today()
        if now.weekday() != WEEKLY_REPORT_DAY:
            return
        # Only fire once per Monday by checking against stored key
        week_key = _last_week_str()
        meta_key = f"weekly_report_sent_{week_key}"
        already_sent = await self.db.get_meta(meta_key)
        if already_sent:
            return

        for guild in self.bot.guilds:
            await self._send_report(guild, week_key)

        await self.db.set_meta(meta_key, "1")
        log.info("Weekly reports sent for week %s", week_key)

    @weekly_report_loop.before_loop
    async def before_weekly(self) -> None:
        await self.bot.wait_until_ready()

    async def _send_report(self, guild: discord.Guild, week: str) -> None:
        cfg = await self.db.get_config(guild.id)
        if not cfg or not cfg["weekly_channel"]:
            return

        channel = guild.get_channel(cfg["weekly_channel"])
        if not isinstance(channel, discord.TextChannel):
            return

        # Top 10 by XP this week
        xp_rows = await self.db.get_weekly_leaderboard(guild.id, week, "xp", 10)
        msg_rows = await self.db.get_weekly_leaderboard(guild.id, week, "messages", 10)
        vc_rows = await self.db.get_weekly_leaderboard(guild.id, week, "voice_minutes", 10)

        if not xp_rows and not msg_rows and not vc_rows:
            return

        embed = discord.Embed(
            title=f"📅 Weekly Activity Report — Week {week}",
            color=BOT_GOLD_COLOR,
        )

        def _fmt(rows, col: str, unit: str) -> str:
            if not rows:
                return "_No activity this week._"
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, row in enumerate(rows):
                member = guild.get_member(row["user_id"])
                name = member.display_name if member else f"User {row['user_id']}"
                medal = medals[i] if i < 3 else f"`#{i+1}`"
                lines.append(f"{medal} **{name}** — {row[col]:,} {unit}")
            return "\n".join(lines)

        embed.add_field(
            name="🏆 Top XP Earners",
            value=_fmt(xp_rows, "xp", "XP"),
            inline=False,
        )
        embed.add_field(
            name="💬 Top Message Senders",
            value=_fmt(msg_rows, "messages", "messages"),
            inline=False,
        )
        embed.add_field(
            name="🎙️ Top Voice Participants",
            value=_fmt(vc_rows, "voice_minutes", "min"),
            inline=False,
        )
        embed.set_footer(text=f"{EMBED_FOOTER} • Keep grinding — new week starting now!")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning("Cannot send weekly report to %s in %s", channel.name, guild.name)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Weekly(bot))
