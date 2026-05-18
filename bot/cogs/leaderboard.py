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
    RED_CROSS,
    LEADERBOARD_PAGE_SIZE,
    LB_TITLE,
)
from database import Database, current_week, level_from_xp

log = logging.getLogger(__name__)

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

LB_META = {
    "xp":             ("All-Time XP",             "xp",           "XP"),
    "messages":       ("All-Time Messages",        "msg_count",    "msgs"),
    "voice":          ("All-Time Voice",           "voice_minutes","min"),
    "weekly_xp":      ("Weekly XP",                "xp",           "XP"),
    "weekly_messages":("Weekly Messages",          "messages",     "msgs"),
    "weekly_voice":   ("Weekly Voice",             "voice_minutes","min"),
}


class LeaderboardDropdown(discord.ui.Select):
    """Dropdown component containing all available leaderboard categories."""
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="All-Time XP", value="xp", description="Overall server experience rankings.", emoji="✨"),
            discord.SelectOption(label="All-Time Messages", value="messages", description="Overall total message counts.", emoji="💬"),
            discord.SelectOption(label="All-Time Voice", value="voice", description="Overall time spent hanging out in VC.", emoji="🔊"),
            discord.SelectOption(label="Weekly XP", value="weekly_xp", description="XP earned over the current week cycle.", emoji="📈"),
            discord.SelectOption(label="Weekly Messages", value="weekly_messages", description="Messages posted during this week.", emoji="📝"),
            discord.SelectOption(label="Weekly Voice", value="weekly_voice", description="Voice connection active minutes this week.", emoji="🎙️"),
        ]
        super().__init__(placeholder="Switch leaderboard category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        # Cast view tracking state explicitly
        view: LeaderboardView = self.view  # type: ignore
        if not await view._check_requester(interaction):
            return

        selected_type = self.values[0]
        is_weekly = selected_type.startswith("weekly_")
        week = current_week()

        # Dynamically evaluate the total pool size for the freshly chosen metric tier
        if is_weekly:
            total = await view.db.get_weekly_member_count(view.guild.id, week)
        else:
            total = await view.db.get_guild_member_count(view.guild.id)

        # Mutate persistent UI layout state definitions 
        view.lb_type = selected_type
        view.total = total
        view.page = 1
        view.max_pages = min(
            LEADERBOARD_MAX_PAGES,
            max(1, -(-total // LEADERBOARD_PAGE_SIZE)),
        )
        
        view._update_buttons()
        await interaction.response.edit_message(embed=await view.build_embed(), view=view)


class LeaderboardView(discord.ui.View):

    def __init__(
        self,
        bot: commands.Bot,
        guild: discord.Guild,
        lb_type: str,
        total: int,
        requester_id: int,
    ) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.guild = guild
        self.lb_type = lb_type
        self.total = total
        self.requester_id = requester_id
        self.page = 1
        self.max_pages = min(
            LEADERBOARD_MAX_PAGES,
            max(1, -(-total // LEADERBOARD_PAGE_SIZE)),
        )
        
        # Inject our dynamic select element on load-up sequence execution
        self.add_item(LeaderboardDropdown())
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.max_pages

    async def build_embed(self) -> discord.Embed:
        offset = (self.page - 1) * LEADERBOARD_PAGE_SIZE
        is_weekly = self.lb_type.startswith("weekly_")

        title_label, sort_col, unit = LB_META[self.lb_type]
        week = current_week()

        if is_weekly:
            rows = await self.db.get_weekly_leaderboard(
                self.guild.id, week, sort_col, LEADERBOARD_PAGE_SIZE, offset
            )
        else:
            rows = await self.db.get_leaderboard(
                self.guild.id, sort_col, LEADERBOARD_PAGE_SIZE, offset
            )

        embed = discord.Embed(
            title=LB_TITLE.format(guild=self.guild.name) + f" — {title_label}",
            color=BOT_COLOR,
        )
        if self.guild.icon:
            embed.set_thumbnail(url=self.guild.icon.url)

        if not rows:
            embed.description = "No data yet available for this tier."
            embed.set_footer(text=EMBED_FOOTER)
            return embed

        lines: list[str] = []
        for i, row in enumerate(rows):
            global_rank = offset + i + 1
            medal = MEDALS.get(global_rank, f"`#{global_rank}`")
            member = self.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            value = row[sort_col]
            level = level_from_xp(row["xp"]) if self.lb_type in ("xp", "weekly_xp") else None
            level_str = f" · Lvl **{level}**" if level is not None else ""
            lines.append(f"{medal} **{name}**{level_str} — {value:,} {unit}")

        embed.description = "\n".join(lines)
        embed.set_footer(
            text=f"{EMBED_FOOTER} · Page {self.page}/{self.max_pages}"
            + (f" · Week {week}" if is_weekly else "")
        )
        return embed

    async def _check_requester(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the person who ran this command can use these interactive components.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_requester(interaction):
            return
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_requester(interaction):
            return
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True


class Leaderboard(commands.Cog, name="Leaderboard"):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]

    @app_commands.command(
        name=CMD_LEADERBOARD,
        description="Show the server leaderboard with interactive filtering.",
    )
    @app_commands.describe(
        type="Which leaderboard to show initially (Defaults to All-Time XP).",
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="All-Time XP",          value="xp"),
        app_commands.Choice(name="All-Time Messages",     value="messages"),
        app_commands.Choice(name="All-Time Voice",        value="voice"),
        app_commands.Choice(name="Weekly XP",             value="weekly_xp"),
        app_commands.Choice(name="Weekly Messages",       value="weekly_messages"),
        app_commands.Choice(name="Weekly Voice",          value="weekly_voice"),
    ])
    @app_commands.guild_only()
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        type: str = "xp",
    ) -> None:
        await interaction.response.defer(thinking=True)
        assert interaction.guild

        is_weekly = type.startswith("weekly_")
        week = current_week()

        if is_weekly:
            total = await self.db.get_weekly_member_count(interaction.guild.id, week)
        else:
            total = await self.db.get_guild_member_count(interaction.guild.id)

        if total == 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="No data yet for this leaderboard tier. Start chatting!",
                    color=BOT_ERROR_COLOR,
                )
            )
            return

        view = LeaderboardView(self.bot, interaction.guild, type, total, interaction.user.id)
        embed = await view.build_embed()
        await interaction.followup.send(embed=embed, view=view)


    # ── prefix command ────────────────────────────────────────────────────────

    @commands.command(name=CMD_LEADERBOARD, aliases=["lb", "top"])
    @commands.guild_only()
    async def leaderboard_prefix(
        self,
        ctx: commands.Context,
        lb_type: str = "xp",
    ) -> None:
        lb_type = lb_type.lower()
        if lb_type not in LB_META:
            valid = ", ".join(f"`{k}`" for k in LB_META)
            await ctx.send(
                embed=discord.Embed(
                    description=f"{RED_CROSS} Unknown type. Choose from: {valid}",
                    color=BOT_ERROR_COLOR,
                )
            )
            return
            
        async with ctx.typing():
            assert ctx.guild
            is_weekly = lb_type.startswith("weekly_")
            week = current_week()
            
            if is_weekly:
                total = await self.db.get_weekly_member_count(ctx.guild.id, week)
            else:
                total = await self.db.get_guild_member_count(ctx.guild.id)
                
            if total == 0:
                await ctx.send(
                    embed=discord.Embed(
                        description="No data yet available. Start chatting!",
                        color=BOT_ERROR_COLOR,
                    )
                )
                return
                
            view = LeaderboardView(self.bot, ctx.guild, lb_type, total, ctx.author.id)
            embed = await view.build_embed()
            await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
