"""
Phosphorus – Leaderboard cog
Slash command: /leaderboard [page]
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from constants import (
    BOT_COLOR,
    BOT_ERROR_COLOR,
    CMD_LEADERBOARD,
    EMBED_FOOTER,
    LEADERBOARD_MAX_PAGES,
    LEADERBOARD_PAGE_SIZE,
    LB_TITLE,
)
from database import Database, level_from_xp

log = logging.getLogger(__name__)

# Medals for top 3 spots
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class LeaderboardView(discord.ui.View):
    """Paginated leaderboard using Discord buttons."""

    def __init__(
        self,
        bot: commands.Bot,
        guild: discord.Guild,
        total: int,
        requester_id: int,
    ) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.guild = guild
        self.total = total
        self.requester_id = requester_id
        self.page = 1
        self.max_pages = min(
            LEADERBOARD_MAX_PAGES,
            max(1, -(-total // LEADERBOARD_PAGE_SIZE)),  # ceiling div
        )
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.max_pages

    async def build_embed(self) -> discord.Embed:
        offset = (self.page - 1) * LEADERBOARD_PAGE_SIZE
        rows = await self.db.get_leaderboard(
            self.guild.id, LEADERBOARD_PAGE_SIZE, offset
        )

        embed = discord.Embed(
            title=LB_TITLE.format(guild=self.guild.name),
            color=BOT_COLOR,
        )
        embed.set_thumbnail(url=self.guild.icon.url if self.guild.icon else discord.Embed.Empty)

        if not rows:
            embed.description = "No one has earned XP yet. Start chatting!"
            embed.set_footer(text=EMBED_FOOTER)
            return embed

        lines: list[str] = []
        for i, row in enumerate(rows):
            global_rank = offset + i + 1
            medal = MEDALS.get(global_rank, f"`#{global_rank}`")
            member = self.guild.get_member(row["user_id"])
            name = member.display_name if member else f"Unknown ({row['user_id']})"
            level = level_from_xp(row["xp"])
            lines.append(
                f"{medal} **{name}** — Level **{level}** · {row['xp']:,} XP"
            )

        embed.description = "\n".join(lines)
        embed.set_footer(
            text=f"{EMBED_FOOTER} · Page {self.page}/{self.max_pages}"
        )
        return embed

    async def _check_requester(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the person who ran this command can change pages.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check_requester(interaction):
            return
        self.page -= 1
        self._update_buttons()
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._check_requester(interaction):
            return
        self.page += 1
        self._update_buttons()
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class Leaderboard(commands.Cog, name="Leaderboard"):
    """Guild XP leaderboard."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    @app_commands.command(
        name=CMD_LEADERBOARD,
        description="Show the XP leaderboard for this server.",
    )
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        assert interaction.guild

        total = await self.db.get_guild_member_count(interaction.guild.id)
        if total == 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="No one has earned XP in this server yet.",
                    color=BOT_ERROR_COLOR,
                )
            )
            return

        view = LeaderboardView(
            self.bot, interaction.guild, total, interaction.user.id
        )
        embed = await view.build_embed()
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
