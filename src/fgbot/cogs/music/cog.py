"""Slash commands for music: ``/play``, ``/skip``, ``/queue``, …

The cog itself is thin: it checks who may do what, then delegates to the server's
``GuildPlayer`` (playback) and to ``sources`` / ``spotify`` (finding songs).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from fgbot.cogs.music import sources
from fgbot.cogs.music.player import GuildPlayer, now_playing_embed
from fgbot.cogs.music.spotify import SpotifyResolver, parse_spotify_link
from fgbot.cogs.music.track import Track
from fgbot.errors import UserFacingError
from fgbot.utils import embeds

if TYPE_CHECKING:
    from fgbot.bot import FGBot

log = logging.getLogger(__name__)


class MusicCog(commands.Cog, name="Music"):
    """Play music from YouTube (and Spotify links) in voice channels."""

    def __init__(self, bot: FGBot) -> None:
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}  # guild id -> player
        settings = bot.settings
        self.spotify = (
            SpotifyResolver(
                settings.spotify_client_id, settings.spotify_client_secret.get_secret_value()
            )
            if settings.spotify_enabled
            else None
        )

    async def cog_unload(self) -> None:
        for player in list(self.players.values()):
            await player.destroy()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Every music command needs a server (voice channels don't exist in DMs)."""
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        return True

    # --------------------------------------------------------------------- helpers
    def _player(self, interaction: discord.Interaction) -> GuildPlayer | None:
        return self.players.get(interaction.guild_id or 0)

    def _require_player(self, interaction: discord.Interaction) -> GuildPlayer:
        """The server's player; the user must be in the same voice channel as the bot."""
        player = self._player(interaction)
        if player is None or player.voice is None:
            raise UserFacingError("I'm not in a voice channel. Use `/join` or `/play` first.")
        self._require_same_channel(interaction, player.voice.channel)
        return player

    @staticmethod
    def _user_voice_channel(interaction: discord.Interaction) -> discord.abc.Connectable | None:
        user = interaction.user
        if isinstance(user, discord.Member) and user.voice and user.voice.channel:
            return user.voice.channel
        return None

    def _require_same_channel(self, interaction: discord.Interaction, channel) -> None:
        if self._user_voice_channel(interaction) != channel:
            raise UserFacingError(f"You need to be in {channel.mention} to control the music.")

    async def _connect(
        self, interaction: discord.Interaction, channel: discord.VoiceChannel | discord.StageChannel
    ) -> GuildPlayer:
        """Join (or move to) ``channel`` and return the server's player."""
        guild = interaction.guild
        assert guild is not None
        voice = guild.voice_client
        if isinstance(voice, discord.VoiceClient):
            if voice.channel != channel:
                await voice.move_to(channel)
        else:
            await channel.connect(self_deaf=True)

        player = self.players.get(guild.id)
        if player is None:
            player = GuildPlayer(
                guild,
                interaction.channel,  # type: ignore[arg-type]
                volume=self.bot.settings.music_default_volume / 100,
                idle_timeout=self.bot.settings.music_idle_timeout,
                on_destroy=lambda guild_id: self.players.pop(guild_id, None),
            )
            self.players[guild.id] = player
        else:
            player.text_channel = interaction.channel  # type: ignore[assignment]
        return player

    async def _connect_to_user(self, interaction: discord.Interaction) -> GuildPlayer:
        """Join the user's voice channel, unless the bot is busy in another one."""
        channel = self._user_voice_channel(interaction)
        if channel is None:
            raise UserFacingError("Join a voice channel first.")
        player = self._player(interaction)
        if player and player.voice and player.voice.channel != channel and player.is_playing:
            raise UserFacingError(
                f"I'm already playing music in {player.voice.channel.mention}. Join me there!"
            )
        return await self._connect(interaction, channel)  # type: ignore[arg-type]

    # ------------------------------------------------------------- joining/leaving
    @app_commands.command(name="join", description="Join your voice channel.")
    async def join(self, interaction: discord.Interaction) -> None:
        # Connecting to voice can take a few seconds, longer than Discord waits for a reply.
        await interaction.response.defer()
        player = await self._connect_to_user(interaction)
        assert player.voice is not None
        await interaction.followup.send(f"Joined {player.voice.channel.mention}. 🎶")

    @app_commands.command(name="summon", description="Move the bot to a voice channel.")
    @app_commands.describe(channel="Voice channel to join (default: yours)")
    @app_commands.default_permissions(manage_guild=True)
    async def summon(
        self, interaction: discord.Interaction, channel: discord.VoiceChannel | None = None
    ) -> None:
        target = channel or self._user_voice_channel(interaction)
        if target is None:
            raise UserFacingError("Pick a channel or join a voice channel first.")
        await interaction.response.defer()
        await self._connect(interaction, target)  # type: ignore[arg-type]
        await interaction.followup.send(f"Joined {target.mention}. 🎶")

    @app_commands.command(name="leave", description="Clear the queue and leave the voice channel.")
    @app_commands.default_permissions(manage_guild=True)
    async def leave(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if player is None:
            raise UserFacingError("I'm not in a voice channel.")
        await player.destroy()
        await interaction.response.send_message("Bye! 👋")

    # --------------------------------------------------------------------- playing
    @app_commands.command(
        name="play", description="Play a song: search text, a URL or a Spotify link."
    )
    @app_commands.describe(
        query="Song name, YouTube (or other) URL, or Spotify track/album/playlist"
    )
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        # Joining voice and finding a song can take a few seconds; "thinking…" avoids
        # Discord's 3-second reply deadline.
        await interaction.response.defer(thinking=True)
        player = await self._connect_to_user(interaction)

        spotify_link = parse_spotify_link(query)
        if spotify_link:
            await self._enqueue_spotify(interaction, player, *spotify_link)
            return

        try:
            track = await sources.resolve(Track(query=query, requester_id=interaction.user.id))
        except sources.SourceError as error:
            raise UserFacingError(str(error)) from error
        position = player.queue.add(track)
        if player.current is None and position == 1:
            message = f"Starting **{track.link}**"
        else:
            message = f"Queued **{track.link}** at position {position}"
        if track.uploader:
            message += f" by **{track.uploader}**"
        await interaction.followup.send(embed=embeds.success(message))

    async def _enqueue_spotify(
        self, interaction: discord.Interaction, player: GuildPlayer, kind: str, spotify_id: str
    ) -> None:
        if self.spotify is None:
            raise UserFacingError(
                "Spotify links are not set up on this bot (missing SPOTIFY_CLIENT_ID/SECRET)."
            )
        try:
            queries = await self.spotify.queries_for(kind, spotify_id)
        except Exception as error:  # spotipy raises various exception types
            log.warning("Spotify lookup of %s %s failed: %s", kind, spotify_id, error)
            raise UserFacingError(
                f"Couldn't read that Spotify {kind}. Is it public? "
                "(Playlists made by Spotify itself can't be read by bots.)"
            ) from error
        if not queries:
            raise UserFacingError(f"That Spotify {kind} has no playable tracks.")
        # Tracks are only looked up on YouTube when it's their turn (see Track).
        for query in queries:
            player.queue.add(Track(query=query, requester_id=interaction.user.id))
        what = f"**{queries[0]}**" if len(queries) == 1 else f"**{len(queries)} tracks**"
        await interaction.followup.send(embed=embeds.success(f"Queued {what} from Spotify."))

    @app_commands.command(name="pause", description="Pause the music.")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self._require_player(interaction)
        if not (player.voice and player.voice.is_playing()):
            raise UserFacingError("Nothing is playing.")
        player.voice.pause()
        await interaction.response.send_message("⏸️ Paused.")

    @app_commands.command(name="resume", description="Resume paused music.")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self._require_player(interaction)
        if not (player.voice and player.voice.is_paused()):
            raise UserFacingError("The music isn't paused.")
        player.voice.resume()
        await interaction.response.send_message("▶️ Resumed.")

    @app_commands.command(name="stop", description="Stop the music and clear the queue.")
    @app_commands.default_permissions(manage_guild=True)
    async def stop(self, interaction: discord.Interaction) -> None:
        player = self._require_player(interaction)
        player.stop()
        await interaction.response.send_message("⏹️ Stopped and cleared the queue.")

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = self._require_player(interaction)
        if not player.is_playing or player.current is None:
            raise UserFacingError("Nothing is playing.")
        skipped = player.current
        player.skip()
        await interaction.response.send_message(f"⏭️ Skipped **{skipped.title}**.")

    @app_commands.command(name="now", description="Show the song that is playing.")
    async def now(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if player is None or player.current is None or not player.is_playing:
            raise UserFacingError("Nothing is playing.")
        await interaction.response.send_message(embed=now_playing_embed(player.current, player))

    # ----------------------------------------------------------------------- queue
    @app_commands.command(name="queue", description="Show the queue.")
    @app_commands.describe(page="Page number (10 songs per page)")
    async def queue(
        self, interaction: discord.Interaction, page: app_commands.Range[int, 1] = 1
    ) -> None:
        player = self._player(interaction)
        if player is None or len(player.queue) == 0:
            raise UserFacingError("The queue is empty.")
        items, pages = player.queue.page(page)
        lines = [f"`{position}.` {track.link}" for position, track in items]
        embed = embeds.info(
            embeds.truncate("\n".join(lines), 4096), title=f"Queue ({len(player.queue)} songs)"
        )
        page_shown = min(page, pages)
        embed.set_footer(text=f"Page {page_shown}/{pages}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        player = self._require_player(interaction)
        if len(player.queue) < 2:
            raise UserFacingError("There is nothing to shuffle.")
        player.queue.shuffle()
        await interaction.response.send_message("🔀 Shuffled the queue.")

    @app_commands.command(name="remove", description="Remove a song from the queue.")
    @app_commands.describe(position="Position in /queue")
    async def remove(
        self, interaction: discord.Interaction, position: app_commands.Range[int, 1]
    ) -> None:
        player = self._require_player(interaction)
        try:
            track = player.queue.remove(position)
        except IndexError:
            raise UserFacingError(f"There is no song at position {position}.") from None
        await interaction.response.send_message(f"🗑️ Removed **{track.title}**.")

    @app_commands.command(name="loop", description="Repeat the current song (toggle).")
    async def loop(self, interaction: discord.Interaction) -> None:
        player = self._require_player(interaction)
        player.loop = not player.loop
        state = "on 🔁" if player.loop else "off"
        await interaction.response.send_message(f"Loop is now {state}.")

    @app_commands.command(name="volume", description="Set the volume (0–100).")
    @app_commands.describe(volume="New volume in percent")
    async def volume(
        self, interaction: discord.Interaction, volume: app_commands.Range[int, 0, 100]
    ) -> None:
        player = self._require_player(interaction)
        player.volume = volume / 100
        await interaction.response.send_message(f"🔊 Volume set to {volume}%.")

    # ---------------------------------------------------------------------- events
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Leave when everybody else has left, and clean up if the bot was disconnected."""
        player = self.players.get(member.guild.id)
        if player is None:
            return
        assert self.bot.user is not None
        if member.id == self.bot.user.id and after.channel is None:
            await player.destroy()  # kicked or disconnected by someone
            return
        voice = player.voice
        # Only react when someone *left* the bot's channel (not when the bot itself arrives
        # in an empty channel via /summon; the idle timeout handles that case).
        if voice is None or before.channel != voice.channel or after.channel == voice.channel:
            return
        listeners = [m for m in voice.channel.members if not m.bot]
        if not listeners:
            await player.text_channel.send(
                embed=embeds.info("Everyone left the voice channel, so I left too. 👋")
            )
            await player.destroy()
