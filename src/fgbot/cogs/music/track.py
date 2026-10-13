"""A song in the queue (``Track``) and the queue itself (``TrackQueue``).

Neither class talks to Discord or YouTube, so both are easy to test.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass, field

# Stream URLs from YouTube expire after a few hours; re-resolve well before that.
STREAM_URL_MAX_AGE_S = 30 * 60


@dataclass
class Track:
    """A song requested by a user.

    A track starts with only a ``query`` (search text or URL). The remaining fields are filled
    in by ``sources.resolve`` – right away for ``/play <song>``, or just before playback for
    tracks that came from a Spotify playlist (resolving 100 songs up front would take minutes).

    Attributes:
        query: What to look up on YouTube (a URL or search text such as "Artist - Title").
        requester_id: Discord ID of the user who added the track.
        title: Display title; the query until the track is resolved.
    """

    query: str
    requester_id: int
    title: str = ""
    stream_url: str | None = None
    webpage_url: str | None = None
    uploader: str | None = None
    uploader_url: str | None = None
    thumbnail: str | None = None
    duration: int | None = None  # seconds; None for live streams or unknown
    http_headers: dict[str, str] = field(default_factory=dict)
    resolved_at: float | None = None  # time.monotonic() of the last resolve

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.query

    @property
    def needs_resolving(self) -> bool:
        """True if there is no stream URL yet or it may have expired."""
        if self.stream_url is None or self.resolved_at is None:
            return True
        return time.monotonic() - self.resolved_at > STREAM_URL_MAX_AGE_S

    @property
    def link(self) -> str:
        """Markdown link to the track's page (or just the title)."""
        return f"[{self.title}]({self.webpage_url})" if self.webpage_url else self.title


def format_duration(seconds: int | None) -> str:
    """``3:07``, ``1:02:03`` or ``live``."""
    if seconds is None:
        return "live"
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"


class TrackQueue:
    """First-in-first-out list of tracks that the player can ``await`` on.

    Positions in the public methods are 1-based, as shown to users in ``/queue``.
    """

    def __init__(self) -> None:
        self._tracks: list[Track] = []
        self._added = asyncio.Event()

    def __len__(self) -> int:
        return len(self._tracks)

    def __iter__(self):
        return iter(self._tracks)

    def add(self, track: Track) -> int:
        """Append a track; returns its position."""
        self._tracks.append(track)
        self._added.set()
        return len(self._tracks)

    async def get(self) -> Track:
        """Remove and return the first track, waiting until one is available."""
        while not self._tracks:
            self._added.clear()
            await self._added.wait()
        return self._tracks.pop(0)

    def remove(self, position: int) -> Track:
        """Remove the track at ``position`` (1-based).

        Raises:
            IndexError: No track at that position.
        """
        if not 1 <= position <= len(self._tracks):
            raise IndexError(position)
        return self._tracks.pop(position - 1)

    def shuffle(self) -> None:
        random.shuffle(self._tracks)

    def clear(self) -> None:
        self._tracks.clear()

    def page(self, number: int, per_page: int = 10) -> tuple[list[tuple[int, Track]], int]:
        """One page of the queue as ``(position, track)`` pairs, plus the number of pages.

        ``number`` is clamped to the valid range, so asking for page 99 shows the last page.
        """
        pages = max(1, math.ceil(len(self._tracks) / per_page))
        number = min(max(number, 1), pages)
        start = (number - 1) * per_page
        items = list(enumerate(self._tracks[start : start + per_page], start=start + 1))
        return items, pages
