"""Music building blocks: queue, track, Spotify link parsing and yt-dlp result handling."""

from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest

from fgbot.cogs.music import sources
from fgbot.cogs.music.spotify import MAX_TRACKS_PER_LINK, SpotifyResolver, parse_spotify_link
from fgbot.cogs.music.track import Track, TrackQueue, format_duration


def make_tracks(n: int) -> list[Track]:
    return [Track(query=f"song {i}", requester_id=1) for i in range(1, n + 1)]


# --------------------------------------------------------------------------- queue
async def test_queue_get_waits_for_a_track() -> None:
    queue = TrackQueue()
    getter = asyncio.create_task(queue.get())
    await asyncio.sleep(0)
    assert not getter.done()
    track = make_tracks(1)[0]
    queue.add(track)
    assert await asyncio.wait_for(getter, 1) is track


def test_queue_remove_is_one_based_and_bounds_checked() -> None:
    queue = TrackQueue()
    for track in make_tracks(3):
        queue.add(track)
    assert queue.remove(2).query == "song 2"
    assert [t.query for t in queue] == ["song 1", "song 3"]
    for bad in (0, 3, -1):
        with pytest.raises(IndexError):
            queue.remove(bad)


def test_queue_pages_are_clamped() -> None:
    queue = TrackQueue()
    for track in make_tracks(25):
        queue.add(track)
    items, pages = queue.page(1)
    assert pages == 3
    assert [pos for pos, _ in items] == list(range(1, 11))
    items, _ = queue.page(99)  # too large -> last page
    assert [pos for pos, _ in items] == [21, 22, 23, 24, 25]
    assert TrackQueue().page(1) == ([], 1)


def test_queue_shuffle_and_clear_keep_tracks_consistent() -> None:
    queue = TrackQueue()
    tracks = make_tracks(10)
    for track in tracks:
        queue.add(track)
    queue.shuffle()
    assert sorted(t.query for t in queue) == sorted(t.query for t in tracks)
    queue.clear()
    assert len(queue) == 0


# --------------------------------------------------------------------------- track
@pytest.mark.parametrize(
    ("seconds", "text"), [(None, "live"), (0, "0:00"), (187, "3:07"), (3723, "1:02:03")]
)
def test_format_duration(seconds, text) -> None:
    assert format_duration(seconds) == text


def test_track_needs_resolving() -> None:
    track = Track(query="never gonna give you up", requester_id=1)
    assert track.title == "never gonna give you up"
    assert track.needs_resolving
    track.stream_url, track.resolved_at = "https://stream", 0.0  # resolved long ago
    assert track.needs_resolving


# ------------------------------------------------------------------------- spotify
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC?si=abc",
            ("track", "4uLU6hMCjMI75M1A2tKUQC"),
        ),
        (
            "https://open.spotify.com/intl-de/album/1ATL5GLyefJaxhQzSPVrLX",
            ("album", "1ATL5GLyefJaxhQzSPVrLX"),
        ),
        (
            "open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
            ("playlist", "37i9dQZF1DXcBWIGoYBM5M"),
        ),
        ("spotify:track:4uLU6hMCjMI75M1A2tKUQC", ("track", "4uLU6hMCjMI75M1A2tKUQC")),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", None),
        ("daft punk one more time", None),
    ],
)
def test_parse_spotify_link(text, expected) -> None:
    assert parse_spotify_link(text) == expected


class FakeSpotify:
    """Mimics the few spotipy calls we use: two playlist pages, then the end."""

    def __init__(self) -> None:
        def item(name, **extra):
            return {"track": {"name": name, "artists": [{"name": "Artist"}], **extra}}

        self.pages = [
            {"items": [item("One"), {"track": None}, item("Local", is_local=True)], "next": "p2"},
            {"items": [item("Two"), item("Podcast", type="episode")], "next": None},
        ]

    def playlist_items(self, *_args, **_kwargs):
        return self.pages[0]

    def next(self, _page):
        return self.pages[1]


def test_spotify_playlist_pagination_and_filtering() -> None:
    resolver = SpotifyResolver.__new__(SpotifyResolver)  # skip the real login
    resolver._client = FakeSpotify()
    assert resolver._queries_for("playlist", "x") == ["Artist - One", "Artist - Two"]
    assert MAX_TRACKS_PER_LINK >= 100


# -------------------------------------------------------------------------- yt-dlp
class FakeYoutubeDL:
    result: ClassVar[dict] = {}

    def __init__(self, _options) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def extract_info(self, _query, download):
        assert download is False
        return self.result


async def test_resolve_takes_first_search_result(monkeypatch) -> None:
    FakeYoutubeDL.result = {
        "entries": [
            None,
            {
                "title": "Song",
                "url": "https://stream",
                "webpage_url": "https://youtube.com/watch?v=x",
                "uploader": "Band",
                "duration": 200.0,
                "http_headers": {"User-Agent": "yt"},
            },
        ]
    }
    monkeypatch.setattr(sources.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    track = await sources.resolve(Track(query="song", requester_id=1))
    assert (track.title, track.stream_url, track.duration) == ("Song", "https://stream", 200)
    assert track.query == "https://youtube.com/watch?v=x"  # later lookups use the page URL
    assert not track.needs_resolving


async def test_resolve_live_stream_has_no_duration(monkeypatch) -> None:
    FakeYoutubeDL.result = {"title": "Live", "url": "https://stream", "is_live": True}
    monkeypatch.setattr(sources.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    track = await sources.resolve(Track(query="live", requester_id=1))
    assert track.duration is None


async def test_resolve_nothing_found(monkeypatch) -> None:
    FakeYoutubeDL.result = {"entries": []}
    monkeypatch.setattr(sources.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    with pytest.raises(sources.SourceError):
        await sources.resolve(Track(query="asdfghjkl", requester_id=1))
