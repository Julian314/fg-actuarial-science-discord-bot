# Music

## How a song gets from `/play` to your ears

```
/play daft punk one more time
   │
   ├─ Spotify link?  ── yes ─→ spotify.py: read "Artist - Title" of each track from the
   │                           Spotify API → queue them as search texts (resolved later)
   │
   └─ no ─→ sources.resolve(): yt-dlp finds the video and its audio stream URL
              │
              ▼
        TrackQueue (one per server)
              │
              ▼
        GuildPlayer._play_loop()  ── takes the next track, resolves it if needed,
              │                      creates a fresh FFmpeg audio source,
              ▼                      posts "Now playing", waits until it ends
        FFmpeg streams + decodes the audio → discord.py sends it to the voice channel
```

| File | Responsibility |
|---|---|
| `cogs/music/cog.py` | The slash commands and who may use them |
| `cogs/music/player.py` | `GuildPlayer`: the playback loop of one server |
| `cogs/music/track.py` | `Track` (one song) and `TrackQueue` |
| `cogs/music/sources.py` | yt-dlp lookup and FFmpeg audio source |
| `cogs/music/spotify.py` | Spotify link parsing and track lists |

Design decisions worth knowing:

- **Lazy resolving.** A Spotify playlist with 100 songs is queued instantly, as 100 search texts.
  Each song is looked up on YouTube only when it is its turn. The old bot searched all 100
  up front, which took minutes.
- **Fresh audio source for every playback.** YouTube stream URLs expire after a few hours, so a
  track is re-resolved if its URL is older than 30 minutes. An FFmpeg source can only be played
  once, which is why `/loop` was broken in the old bot.
- **Threads.** yt-dlp and spotipy block, so they run via `asyncio.to_thread` and the bot stays
  responsive while a song is being looked up.

## Requirements

| Requirement | Why | Install (Arch / Debian) |
|---|---|---|
| `ffmpeg` | Streams and decodes the audio | `pacman -S ffmpeg` / `apt install ffmpeg` |
| `deno` | yt-dlp needs a JavaScript runtime to solve YouTube's player challenges | `pacman -S deno` / see [deno.com](https://docs.deno.com/runtime/getting_started/installation/) |
| `yt-dlp` | Finds videos and stream URLs | installed by `uv sync` (with its `yt-dlp-ejs` add-on) |
| `PyNaCl`, `davey` | Voice encryption, including Discord's end-to-end encrypted voice (DAVE) | installed by `uv sync` (`discord.py[voice]`) |

## Keeping yt-dlp up to date (important)

YouTube changes regularly, and old yt-dlp versions stop working. The typical symptom is that
every `/play` fails with "Couldn't load …". Update yt-dlp first whenever music breaks:

```bash
uv lock --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs
uv sync
systemctl --user restart fgbot      # or restart the bot however you run it
```

Doing this once a month is a good habit.

## Spotify links

Spotify doesn't let bots stream its audio. The bot reads the artist and title of each track
through the Spotify Web API and plays the matching YouTube video. For this the bot needs free
API credentials:

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. **Create app**: any name and description; redirect URI `http://127.0.0.1:8888/callback`
   (it is not used); tick **Web API**.
3. Open the app's **Settings** and copy the **Client ID** and **Client secret** into `.env`:

   ```dotenv
   SPOTIFY_CLIENT_ID=...
   SPOTIFY_CLIENT_SECRET=...
   ```

4. Restart the bot.

Supported: track, album and playlist links (`open.spotify.com/...`, including `intl-xx/` links,
and `spotify:track:...` URIs). Limits:

- At most 200 tracks are queued per link.
- Podcasts and local files are skipped.
- **Playlists made by Spotify itself** ("Today's Top Hits", "Discover Weekly", …) can't be read
  by apps. This is a Spotify restriction. Playlists made by users work.

Without credentials, everything except Spotify links still works, and the bot explains this when
someone posts a Spotify link.
