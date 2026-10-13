"""Find songs with yt-dlp and turn them into audio that Discord can play.

yt-dlp does the hard work of finding a video (from a URL or search text) and extracting the
URL of its audio stream. FFmpeg then streams and decodes that audio for discord.py.

yt-dlp is blocking (network I/O), so ``resolve`` runs it in a worker thread.

Keep yt-dlp up to date (``uv lock --upgrade-package yt-dlp && uv sync``): YouTube changes
often and old versions stop working. For YouTube, yt-dlp also needs a JavaScript runtime
(``deno``) to be installed; see docs/music.md.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import time
from typing import Any

import discord
import yt_dlp

from fgbot.cogs.music.track import Track

log = logging.getLogger(__name__)

YTDL_OPTIONS: dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,  # a YouTube playlist URL plays only its video, not the whole list
    "default_search": "ytsearch",  # plain text is searched on YouTube
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",  # force IPv4; IPv6 addresses get blocked more often
}

# Reconnect if the connection drops mid-song; ignore the video track.
FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"


class SourceError(Exception):
    """Nothing playable was found for a query."""


def _extract(query: str) -> dict[str, Any]:
    """Run yt-dlp (blocking). Returns the info dict of a single video."""
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
        except yt_dlp.utils.DownloadError as error:
            raise SourceError(f"Couldn't load `{query}`.") from error
    if info is None:
        raise SourceError(f"Nothing found for `{query}`.")
    if "entries" in info:  # search results: take the first hit
        entries = [entry for entry in info["entries"] if entry]
        if not entries:
            raise SourceError(f"Nothing found for `{query}`.")
        info = entries[0]
    if not info.get("url"):
        raise SourceError(f"`{query}` has no playable audio stream.")
    return info


async def resolve(track: Track) -> Track:
    """Look the track up with yt-dlp and fill in its title, stream URL, duration, …

    Raises:
        SourceError: Nothing playable was found.
    """
    info = await asyncio.to_thread(_extract, track.query)
    track.title = info.get("title") or track.query
    track.stream_url = info["url"]
    track.webpage_url = info.get("webpage_url")
    track.uploader = info.get("uploader") or info.get("channel")
    track.uploader_url = info.get("uploader_url") or info.get("channel_url")
    track.thumbnail = info.get("thumbnail")
    track.duration = None if info.get("is_live") else _int_or_none(info.get("duration"))
    track.http_headers = dict(info.get("http_headers") or {})
    track.resolved_at = time.monotonic()
    # Later lookups (e.g. when /loop repeats the song) go straight to the video page.
    if track.webpage_url:
        track.query = track.webpage_url
    return track


def create_audio_source(track: Track, volume: float) -> discord.PCMVolumeTransformer:
    """A fresh FFmpeg audio source for a resolved track.

    A new source is needed for every playback: an FFmpeg source can only be played once
    (re-using it is what broke ``loop`` in the old bot).
    """
    if track.stream_url is None:
        raise ValueError("track is not resolved")
    before_options = FFMPEG_BEFORE_OPTIONS
    if track.http_headers:
        # Some sites only serve the stream with the same headers yt-dlp used.
        headers = "".join(f"{key}: {value}\r\n" for key, value in track.http_headers.items())
        before_options += f" -headers {shlex.quote(headers)}"
    audio = discord.FFmpegPCMAudio(
        track.stream_url, before_options=before_options, options=FFMPEG_OPTIONS
    )
    return discord.PCMVolumeTransformer(audio, volume=volume)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
