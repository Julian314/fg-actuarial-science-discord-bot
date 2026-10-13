# Migrating from the old Discord-Music-Chess-Bot

This bot replaces [Discord-Music-Chess-Bot](https://github.com/Julian314/Discord-Music-Chess-Bot)
(January 2024). It has all of its features, the same cog structure (music, chess) and the new
job report.

## ⚠️ Security: rotate the old credentials

The old repository is public, and its **git history** (commit `b3158e6`, "Add files via upload")
contains a real **Discord bot token** (`token.txt`) and a **Spotify client ID and secret**
(`Music_Spotipy.py`). Later commits replaced them, but anyone can still read old commits.

1. Discord Developer Portal → old application → **Bot → Reset Token**. If you reuse that
   application for the new bot, put the new token in `.env`.
2. Spotify Developer Dashboard → the old app → **Settings → Rotate client secret**, or delete
   the app.
3. Optional: rewrite the old repository's history (e.g. with `git filter-repo`) or archive it.
   Resetting the credentials is what actually matters, because the old values may already have
   been copied.

The new bot reads secrets only from `.env`, which is git-ignored.

## Command mapping

The prefix `.` is gone. Everything is a slash command now.

| Old | New | Notes |
|---|---|---|
| `.join` | `/join` | |
| `.summon [channel]` | `/summon [channel]` | |
| `.leave` / `.disconnect` | `/leave` | |
| `.play <query>` | `/play <query>` | Spotify albums now work too |
| `.pause` / `.resume` | `/pause` / `/resume` | No longer need *Manage Server* |
| `.stop` | `/stop` | Needs *Manage Server* (was *Administrator*) |
| `.skip` | `/skip` | |
| `.now` / `.current` / `.playing` | `/now` | |
| `.queue [page]` | `/queue [page]` | |
| `.shuffle` | `/shuffle` | |
| `.remove <index>` | `/remove <position>` | |
| `.loop` | `/loop` | Works now |
| `.volume <n>` | `/volume <0-100>` | Applies immediately |
| `.chess white\|black` | `/chess start color:…` | Also `random` |
| `.chess_fen <fen>, <color>` | `/chess start color:… fen:…` | Either side may be to move |
| `.move e2e4` | `/chess move e4` | SAN or UCI, with autocomplete |
| `.undo` | `/chess undo` | |
| `.make_move <move>` | `/chess override <move>` | |
| `.finish` | `/chess resign` | Player or moderators only |
| `.eval` | `/chess eval` | |
| `.suggestion` | `/chess hint` | Now for the correct side, only visible to you |
| `.fen` | `/chess fen` | |
| (none) | `/chess board` | Show the board again |
| default `.help` | `/help` | |
| (none) | `/ping`, `/about` | |
| (none) | `/jobs list`, `/jobs search`, `/jobs status`, `/jobs run-now` + daily report | New feature |

## Bugs fixed

**Startup and structure**

- The bot didn't start at all: `helpers.py` had an `IndentationError`.
- Cogs were added in `on_ready`, which runs again after every reconnect. Now they are loaded once
  in `setup_hook`.
- `requirements.txt` wasn't installable. Now `pyproject.toml` + `uv.lock` pin every version.
- The bot needed three privileged intents. Now it needs none.

**Music**

- `.loop` replayed an already-finished audio source, so the bot spammed "Now playing".
- `.volume` had an impossible range check (`0 > v > 100`) and only took effect on the next song.
- `.skip` crashed when nothing was playing (wrong `ctx.send` call).
- `.now`, `.queue` and `.remove` crashed when idle or with out-of-range numbers.
- Any yt-dlp failure was silently treated as a Spotify link, through a bare `except:`.
- Spotify playlists made two extra API calls per track, used the album artist instead of the
  track artist, read only the first 100 tracks and blocked the bot while doing so.
- Live streams and videos without an upload date crashed.
- Errors raised in FFmpeg's thread were lost. Auto-leave could raise `KeyError` and left the
  player task running. There was no idle timeout.
- `self.bot.voice_clients[0]` broke as soon as the bot was in two servers.

**Chess**

- One global game for the whole bot. Now there is one game per channel.
- The player was identified by display name, which can be changed or faked. Now it's the user ID.
- ShessGPT crashed when one of its moves would mate or stalemate, so it could never give mate in
  one, and the player's move was left half-applied.
- The 75-move rule crashed the game-over check.
- `.undo` didn't check the move history, and its error message was never sent (missing `await`).
- `.chess_fen` overwrote a running game before checking whether one was running.
- `.suggestion` computed ShessGPT's suggestion for the wrong side.
- A new Stockfish process was started for every command and never closed.
- The neural-network search (about 900 forward passes) blocked the whole bot. Now it runs as one
  batched pass in a thread, about 10× faster.
- `board.png` was written to the working directory and shared between games. Images are now
  rendered in memory.
- Errors in the chess cog (bad colour, bad FEN, bad move format) produced no reply at all.

## Behaviour changes

- **Messages are in English.**
- **The "Schopp is gaming → NÄ ÄÄÄÄ" block is gone.** It depended on hardcoded display names and
  a hardcoded channel ID.
- **Spotify playlists are no longer shuffled automatically.** Use `/shuffle` if you want that.
- **YouTube playlist URLs** play only the linked video, as before.
- **Permissions** are Discord's standard slash-command permissions, which admins can change in
  Server Settings → Integrations.

## What stayed the same

- The ShessGPT network and its weights (`ShessGPT_2_57.pth`), with byte-identical input
  encoding. It plays the same moves as before, minus the crashes.
- The idea and look of the "Now playing" card and the paginated queue.
- The yt-dlp + FFmpeg playback approach and the Spotify-to-YouTube lookup.
