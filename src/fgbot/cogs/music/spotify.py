"""Turn Spotify links into search queries that yt-dlp can find on YouTube.

Spotify does not let bots stream its audio, so for every Spotify track we only read the
artist and title ("Daft Punk - One More Time") and play the matching YouTube video.

Supported links: tracks, albums and playlists, e.g.
``https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M`` or ``spotify:track:4uLU6h…``.
Requires a (free) Spotify developer app; see docs/music.md.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# open.spotify.com/(intl-de/)track/<id>  or  spotify:track:<id>
SPOTIFY_LINK = re.compile(
    r"(?:open\.spotify\.com/(?:intl-[\w-]+/)?|spotify:)(?P<kind>track|album|playlist)[/:]"
    r"(?P<id>[A-Za-z0-9]+)"
)

# Protects the queue (and the Spotify rate limit) from 10 000-song playlists.
MAX_TRACKS_PER_LINK = 200


def parse_spotify_link(text: str) -> tuple[str, str] | None:
    """``("playlist", "<id>")`` for a Spotify link, or None if ``text`` is not one."""
    match = SPOTIFY_LINK.search(text)
    return (match["kind"], match["id"]) if match else None


def _query(track: dict[str, Any]) -> str:
    """'Artist 1, Artist 2 - Title' for a Spotify track object."""
    artists = ", ".join(artist["name"] for artist in track.get("artists", []))
    return f"{artists} - {track['name']}" if artists else track["name"]


class SpotifyResolver:
    """Reads track lists from the Spotify Web API (client-credentials login, no user data)."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self._client = spotipy.Spotify(auth_manager=auth, requests_timeout=10, retries=3)

    async def queries_for(self, kind: str, spotify_id: str) -> list[str]:
        """Search queries for every track behind a link (at most ``MAX_TRACKS_PER_LINK``).

        spotipy is blocking, so the API calls run in a worker thread.
        """
        return await asyncio.to_thread(self._queries_for, kind, spotify_id)

    def _queries_for(self, kind: str, spotify_id: str) -> list[str]:
        if kind == "track":
            return [_query(self._client.track(spotify_id))]
        if kind == "album":
            page = self._client.album_tracks(spotify_id, limit=50)
            items = self._collect(page, lambda item: item)
        else:  # playlist
            page = self._client.playlist_items(spotify_id, limit=100, additional_types=("track",))
            items = self._collect(page, lambda item: item.get("track"))
        return [_query(track) for track in items]

    def _collect(self, page: dict[str, Any] | None, get_track) -> list[dict[str, Any]]:
        """Follow Spotify's pagination and collect real tracks (no podcasts or local files)."""
        tracks: list[dict[str, Any]] = []
        while page and len(tracks) < MAX_TRACKS_PER_LINK:
            for item in page["items"]:
                track = get_track(item)
                if track and track.get("type", "track") == "track" and not track.get("is_local"):
                    tracks.append(track)
            page = self._client.next(page) if page.get("next") else None
        return tracks[:MAX_TRACKS_PER_LINK]
