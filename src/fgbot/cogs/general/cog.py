"""General commands: /help, /ping and /about."""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from fgbot import __version__
from fgbot.utils import embeds

if TYPE_CHECKING:
    from fgbot.bot import FGBot


class GeneralCog(commands.Cog, name="General"):
    """Commands that are always available, regardless of the enabled features."""

    def __init__(self, bot: FGBot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="List all commands of this bot.")
    async def help(self, interaction: discord.Interaction) -> None:
        # Built from the registered commands, so it is never out of date.
        embed = embeds.info("", title="Commands")
        for cog_name, cog in self.bot.cogs.items():
            lines = []
            for command in cog.walk_app_commands():
                if isinstance(command, app_commands.Command):
                    lines.append(f"`/{command.qualified_name}` – {command.description}")
            if lines:
                embed.add_field(
                    name=cog_name, value=embeds.truncate("\n".join(lines), 1024), inline=False
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Check that the bot is alive.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! 🏓 ({latency_ms:.0f} ms)", ephemeral=True)

    @app_commands.command(name="about", description="Version, uptime and enabled features.")
    async def about(self, interaction: discord.Interaction) -> None:
        uptime = dt.timedelta(seconds=int(time.monotonic() - self.bot.started_at))
        settings = self.bot.settings
        features = {
            "Music": settings.music_enabled,
            "Chess": settings.chess_enabled,
            "Job reports": settings.jobs_enabled,
        }
        embed = embeds.info(
            "Bot of the FG Actuarial Science Discord server.", title="About this bot"
        )
        embed.add_field(name="Version", value=__version__)
        embed.add_field(name="Uptime", value=str(uptime))
        embed.add_field(
            name="Features",
            value="\n".join(f"{'✅' if on else '❌'} {name}" for name, on in features.items()),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
