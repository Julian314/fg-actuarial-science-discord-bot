"""The bot itself: loads the feature cogs, syncs slash commands and handles command errors.

Startup sequence (all handled by discord.py once ``bot.run()`` is called):

1. ``setup_hook`` runs once, before connecting to the gateway. It loads one *extension*
   (a module with an ``async def setup(bot)`` function) per enabled feature, then registers
   the slash commands with Discord.
2. Each cog's ``cog_load`` opens its resources (Stockfish process, job service, …), and
   ``cog_unload`` closes them again when the bot shuts down.
3. ``on_ready`` fires every time the gateway (re)connects, so it only logs.
"""

from __future__ import annotations

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from fgbot import __version__
from fgbot.config import Settings
from fgbot.errors import UserFacingError
from fgbot.utils import embeds

log = logging.getLogger(__name__)


class FGBot(commands.Bot):
    """Discord bot with the configuration available as ``bot.settings``."""

    def __init__(self, settings: Settings) -> None:
        # Only non-privileged intents: slash commands do not need to read message content.
        intents = discord.Intents.default()
        super().__init__(
            # commands.Bot requires a prefix; we only use slash commands, so mentioning the
            # bot is the (unused) prefix.
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            activity=discord.Activity(type=discord.ActivityType.listening, name="/help"),
        )
        self.settings = settings
        self.started_at = time.monotonic()
        self.tree.on_error = self.on_app_command_error

    # ------------------------------------------------------------------ lifecycle
    def enabled_extensions(self) -> list[str]:
        """Module paths of the cogs to load, according to the feature toggles."""
        extensions = ["fgbot.cogs.general"]
        if self.settings.music_enabled:
            extensions.append("fgbot.cogs.music")
        if self.settings.chess_enabled:
            extensions.append("fgbot.cogs.chess")
        if self.settings.jobs_enabled:
            extensions.append("fgbot.cogs.jobs")
        return extensions

    async def setup_hook(self) -> None:
        """Load the cogs and register their slash commands with Discord."""
        for extension in self.enabled_extensions():
            await self.load_extension(extension)
            log.info("Loaded extension %s", extension)

        if self.settings.guild_id:
            # Guild commands appear instantly: ideal while developing or for a single server.
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d slash commands to guild %s", len(synced), guild.id)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d slash commands globally", len(synced))

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info(
            "Logged in as %s (id %s), fgbot %s, in %d server(s)",
            self.user,
            self.user.id,
            __version__,
            len(self.guilds),
        )

    # -------------------------------------------------------------- error handling
    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Turn any error raised by a slash command into a friendly, private reply."""
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original  # unwrap the exception raised inside the command

        if isinstance(error, UserFacingError):
            message = str(error)
        elif isinstance(error, app_commands.MissingPermissions):
            message = "You don't have permission to use this command."
        elif isinstance(error, app_commands.NoPrivateMessage):
            message = "This command only works in a server."
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = f"Slow down! Try again in {error.retry_after:.0f} s."
        elif isinstance(error, app_commands.CheckFailure):
            message = str(error) or "You can't use this command here."
        else:
            command = interaction.command.qualified_name if interaction.command else "?"
            log.error("Unhandled error in /%s", command, exc_info=error)
            message = "Something went wrong on my side. The error has been logged."

        embed = embeds.error(message)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            log.warning("Could not send the error message for an interaction", exc_info=True)
