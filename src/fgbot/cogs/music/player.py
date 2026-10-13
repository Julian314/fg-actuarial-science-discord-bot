"""``GuildPlayer``: plays the queue of one server, one track after another.

Every server with an active voice connection has exactly one ``GuildPlayer``. It runs a
background task (``_play_loop``) that

1. waits for the next track in the queue (or leaves after ``idle_timeout`` seconds),
2. resolves it with yt-dlp if needed,
3. plays it and posts a "Now playing" message,
4. waits until discord.py reports that the track has finished, and repeats.

discord.py calls the ``after`` callback of ``VoiceClient.play`` from its audio *thread*, so
the callback only schedules ``Event.set`` on the event loop (``call_soon_threadsafe``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import discord

from fgbot.cogs.music import sources
from fgbot.cogs.music.track import Track, TrackQueue, format_duration
from fgbot.utils import embeds

log = logging.getLogger(__name__)


class GuildPlayer:
    """Queue and playback state of one server.

    Args:
        guild: The server.
        text_channel: Where "Now playing" messages are posted (the channel of the last /play).
        volume: Initial volume between 0 and 1.
        idle_timeout: Seconds without anything playing before the bot leaves voice.
        on_destroy: Called once the player has shut down (the cog forgets it then).
    """

    def __init__(
        self,
        guild: discord.Guild,
        text_channel: discord.abc.Messageable,
        *,
        volume: float,
        idle_timeout: float,
        on_destroy: Callable[[int], None],
    ) -> None:
        self.guild = guild
        self.text_channel = text_channel
        self.queue = TrackQueue()
        self.current: Track | None = None
        self.loop = False  # repeat the current track
        self._volume = volume
        self._idle_timeout = idle_timeout
        self._on_destroy = on_destroy
        self._track_finished = asyncio.Event()
        self._skip_requested = False
        self._last_played: Track | None = None
        self._destroyed = False
        self._task = asyncio.create_task(self._play_loop(), name=f"music-player-{guild.id}")

    # ----------------------------------------------------------------- properties
    @property
    def voice(self) -> discord.VoiceClient | None:
        client = self.guild.voice_client
        return client if isinstance(client, discord.VoiceClient) else None

    @property
    def is_playing(self) -> bool:
        return self.voice is not None and (self.voice.is_playing() or self.voice.is_paused())

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        """Change the volume, including for the track that is playing right now."""
        self._volume = value
        if self.voice and isinstance(self.voice.source, discord.PCMVolumeTransformer):
            self.voice.source.volume = value

    # -------------------------------------------------------------------- controls
    def skip(self) -> None:
        """Stop the current track; the next one in the queue starts (even when looping)."""
        if self.voice and self.is_playing:
            self._skip_requested = True
            self.voice.stop()

    def stop(self) -> None:
        """Clear the queue and stop playback, but stay in the voice channel."""
        self.queue.clear()
        self.loop = False
        self.skip()

    async def destroy(self) -> None:
        """Stop everything, leave the voice channel and unregister the player."""
        if self._destroyed:
            return
        self._destroyed = True
        self.queue.clear()
        if self.voice:
            await self.voice.disconnect(force=True)
        if self._task is not asyncio.current_task():
            self._task.cancel()
        self._on_destroy(self.guild.id)

    # ------------------------------------------------------------------- the loop
    async def _play_loop(self) -> None:
        try:
            while not self._destroyed:
                track = await self._next_track()
                if track is None:  # idle for too long
                    await self.text_channel.send(
                        embed=embeds.info("Nothing to play, so I left the voice channel. 👋")
                    )
                    await self.destroy()
                    return
                await self._play(track)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Music player of guild %s crashed", self.guild.id)
            await self.destroy()

    async def _next_track(self) -> Track | None:
        """The track to play next: the current one again when looping, else the queue's next."""
        if self.loop and self.current is not None and not self._skip_requested:
            return self.current
        self._skip_requested = False
        self.current = None
        try:
            async with asyncio.timeout(self._idle_timeout):
                self.current = await self.queue.get()
        except TimeoutError:
            return None
        return self.current

    async def _play(self, track: Track) -> None:
        """Play one track and return once it has finished (or was skipped)."""
        repeating = track is self._last_played  # /loop is replaying it
        try:
            if track.needs_resolving:
                await sources.resolve(track)
        except sources.SourceError as error:
            await self.text_channel.send(embed=embeds.error(f"{error} Skipping it."))
            self.current = None
            return

        voice = self.voice
        if voice is None:  # we were disconnected in the meantime
            await self.destroy()
            return

        self._track_finished.clear()
        loop = asyncio.get_running_loop()

        def after(error: Exception | None) -> None:  # runs in discord.py's audio thread
            if error:
                log.error("Playback error in guild %s: %s", self.guild.id, error)
            loop.call_soon_threadsafe(self._track_finished.set)

        voice.play(sources.create_audio_source(track, self._volume), after=after)
        self._last_played = track
        if not repeating:  # don't spam "Now playing" for every repetition
            await self.text_channel.send(embed=now_playing_embed(track, self))
        await self._track_finished.wait()


def now_playing_embed(track: Track, player: GuildPlayer) -> discord.Embed:
    """The "Now playing" card shown by the player and by ``/now``."""
    embed = embeds.info(f"**{track.link}**", title="Now playing")
    embed.add_field(name="Duration", value=format_duration(track.duration))
    embed.add_field(name="Requested by", value=f"<@{track.requester_id}>")
    if track.uploader:
        uploader = (
            f"[{track.uploader}]({track.uploader_url})" if track.uploader_url else track.uploader
        )
        embed.add_field(name="Uploader", value=uploader)
    if player.loop:
        embed.add_field(name="Loop", value="🔁 on")
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    return embed
