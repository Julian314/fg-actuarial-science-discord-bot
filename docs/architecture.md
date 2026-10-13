# Architecture

This page explains how the code is organised and why. Read it before changing anything
substantial.

## Overview

```
                         ┌──────────────────────────────────────────────┐
  uv run fgbot  ───────▶ │ __main__.py   load Settings → logging → run  │
                         └──────────────────────┬───────────────────────┘
                                                │
                         ┌──────────────────────▼───────────────────────┐
                         │ bot.py  FGBot(commands.Bot)                  │
                         │   setup_hook: load extensions, sync commands │
                         │   on_app_command_error: one error handler    │
                         └───┬──────────┬───────────┬───────────┬───────┘
                             │          │           │           │
                  ┌──────────▼┐  ┌──────▼─────┐ ┌───▼──────┐ ┌──▼─────────────┐
                  │ general   │  │ music      │ │ chess    │ │ jobs           │
                  │ /help …   │  │ /play …    │ │ /chess … │ │ /jobs …, daily │
                  └───────────┘  └──┬─────────┘ └──┬───────┘ └──┬─────────────┘
                                    │              │            │
                             yt-dlp, FFmpeg,   shessgpt/     actjobs.service.JobService
                             Spotify API       (PyTorch),    (swiss-actuarial-job-scraper,
                                               Stockfish      SQLite)
```

## Building blocks

### Extensions and cogs

Each feature is a **cog**, a class that groups commands, event listeners and state. Each cog
lives in its own package, `fgbot.cogs.<feature>`. The package's `__init__.py` is a discord.py
**extension**: a module with `async def setup(bot)` that adds the cog.

- `FGBot.setup_hook` loads one extension per enabled feature (`MUSIC_ENABLED`, …). This runs
  **once**, before the bot connects. The old bot added its cogs in `on_ready`, which runs again
  after every reconnect.
- Resources are opened in `cog_load` and closed in `cog_unload`: the Stockfish process, the
  ShessGPT network, the job service and the daily task.
- `/chess …` and `/jobs …` use `commands.GroupCog`, which turns the cog into one slash-command
  group. Music and general commands are top-level.

### Separation of logic and Discord

The rule: **code that decides things does not import Discord.** It takes plain values and
returns plain values, so it can be tested without a Discord connection.

| Discord layer (thin) | Logic layer (tested) |
|---|---|
| `cogs/chess/cog.py` | `cogs/chess/session.py`, `shessgpt/*` |
| `cogs/music/cog.py`, `player.py` | `cogs/music/track.py`, `spotify.py`, `sources.py` |
| `cogs/jobs/cog.py` | `cogs/jobs/reporter.py`, `formatting.py` |

`formatting.py` creates `discord.Embed` objects, but these are plain data containers and need no
connection.

### Configuration

`config.Settings` (pydantic-settings) is the single source of truth for every setting. It is
created once in `__main__` and passed to the bot (`bot.settings`). Nothing else reads
environment variables. Validation happens at startup. See [configuration.md](configuration.md).

### Error handling

- Code raises `fgbot.errors.UserFacingError("message")` for problems the user can fix: not in a
  voice channel, illegal move, empty queue. The global handler `FGBot.on_app_command_error`
  shows the message privately.
- Permission and check failures get standard texts.
- **Every other exception is a bug.** It is logged with a full traceback, and the user sees
  "Something went wrong". Internal error texts never reach the chat. The old bot showed raw
  exceptions, or nothing at all.
- Background work (the daily report, the music loop) catches and logs its own exceptions, so one
  failure never stops future runs.

## Life of a slash command

What happens between a user pressing Enter on `/chess move e4` and the board appearing. The
same flow applies to every command; only the cog method differs.

```
 User          Discord              discord.py (in our process)         our code
  │               │                          │                              │
  │ /chess move e4│                          │                              │
  ├──────────────▶│  INTERACTION_CREATE      │                              │
  │               ├─────(gateway)───────────▶│ CommandTree finds            │
  │               │                          │ "chess move"                 │
  │               │                          ├─ interaction_check() ───────▶│ cog-wide checks
  │               │                          │  (music: server only)        │ (if any)
  │               │                          ├─ ChessCog.move(...) ────────▶│
  │               │    ┌─ 3-second deadline ─┼──────────────────────────────┤ _session_for()
  │               │    │                     │                              │ async with lock
  │               │    │                     │                              │ parse + push move
  │               │◀───┴── defer(thinking) ──┼──────────────────────────────┤
  │ "thinking…"   │                          │                              │ ShessGPT (thread)
  │◀──────────────┤                          │                              │ render PNG (thread)
  │               │◀──── followup.send() ────┼──────────────────────────────┤
  │ board image   │      (up to 15 minutes)  │                              │
  │◀──────────────┤                          │                              │
  │               │                          │                              │
  │      ── if the method raises ──          │                              │
  │               │                          │◀──── exception ──────────────┤
  │               │                          ├─ FGBot.on_app_command_error  │
  │               │◀──── ephemeral red embed ┤   UserFacingError → its text │
  │◀──────────────┤                          │   anything else → logged,    │
  │               │                          │   "Something went wrong"     │
```

Key points:

- Discord waits **3 seconds** for the first response: `send_message` or `defer`. After a
  `defer`, the interaction stays valid for **15 minutes** for `followup.send`.
- A command answers **exactly once** through `interaction.response`; everything after that
  goes through `interaction.followup`. The error handler checks `interaction.response.is_done()`
  to pick the right one.
- Autocomplete (`ChessCog.move_autocomplete`) is a separate, smaller interaction. It runs on
  every keystroke and must return quickly, so it only reads the in-memory session.

## Startup and shutdown order

```
uv run fgbot
 └─ __main__.main()
     ├─ Settings()                 read + validate .env          ✗ → print errors, exit 2
     ├─ setup_logging()            console + logs/fgbot.log
     ├─ FGBot(settings)
     └─ bot.run(token)             discord.py takes over         ✗ bad token → exit 2
         ├─ login
         ├─ setup_hook()           runs ONCE
         │   ├─ load_extension("fgbot.cogs.general")  → setup(bot) → add_cog → cog_load()
         │   ├─ load_extension("fgbot.cogs.music")    (if MUSIC_ENABLED)
         │   ├─ load_extension("fgbot.cogs.chess")    (if CHESS_ENABLED)  → load ShessGPT, start Stockfish
         │   ├─ load_extension("fgbot.cogs.jobs")     (if JOBS_ENABLED)   → open JobService, start daily loop
         │   └─ tree.sync()        upload the slash commands (guild or global)
         ├─ connect to the gateway
         ├─ on_ready()             runs after EVERY (re)connect; only logs
         └─ daily loop: before_loop waits for ready, catches up if the last scrape is > 20 h old
```

Shutdown depends on how the bot is stopped:

- **Ctrl+C** in a terminal: discord.py closes the bot cleanly. Every extension is unloaded, so
  every `cog_unload` runs:
  - `ChessCog` quits Stockfish
  - `MusicCog` destroys all players and leaves voice
  - `JobsCog` cancels the daily loop and any `/jobs run-now` task
- **`systemctl stop` / restart** (SIGTERM): Python exits immediately without running
  `cog_unload`. systemd then stops the remaining child processes of the service (Stockfish,
  FFmpeg). This is safe:
  - Nothing important is kept only in memory (see [where state lives](#where-state-lives)).
  - SQLite rolls back an interrupted write.
  - The scraper's `flock` lock is released when the process exits.
  - A job report interrupted between "sent" and "marked as posted" can post those jobs once
    more the next day. That is the deliberate trade-off: posting a job twice is better than
    losing it.
- **Exit code 2** means a configuration problem. Both systemd units set
  `RestartPreventExitStatus=2`, so systemd doesn't restart the bot in a loop.

## Concurrency: async code and threads

discord.py runs on **one asyncio event loop**. While a coroutine blocks that loop, the bot can't
answer anything, and Discord's 3-second reply deadline expires. Rules used throughout:

| Kind of work | How it is run | Examples |
|---|---|---|
| Async-native I/O | `await` directly | Discord API, Stockfish (python-chess's async UCI) |
| Blocking I/O | `await asyncio.to_thread(...)` | yt-dlp, spotipy, SQLite queries, the 5-minute scrape |
| CPU-heavy work | `await asyncio.to_thread(...)` | ShessGPT search, board rendering |
| Slow commands | `interaction.response.defer()` first | `/play`, `/chess move`, `/chess eval` |
| Very slow commands | reply at once, continue in a background task | `/jobs run-now` |

Shared state is protected with `asyncio.Lock` where two commands could interleave: one lock
per chess game, one lock for job reports, one for the Stockfish conversation.

The music player gets a callback from discord.py's audio **thread** when a song ends. The
callback only calls `loop.call_soon_threadsafe(event.set)`, because touching asyncio objects
directly from another thread is unsafe.

## Where state lives

| State | Where | Lifetime | Survives a restart? |
|---|---|---|---|
| Settings | `bot.settings` (`config.Settings`) | read once at startup | re-read from `.env` |
| Running chess games | `ChessCog.sessions`: channel ID → `ChessSession` | until the game ends or `/chess resign` | **no** |
| Music players | `MusicCog.players`: guild ID → `GuildPlayer` | while the bot is in a voice channel | **no** |
| Music queue, loop flag, volume | inside each `GuildPlayer` (`TrackQueue`) | as above | **no** |
| ShessGPT network, Stockfish process | `ChessCog.shessgpt`, `ChessCog.stockfish` | from `cog_load` to `cog_unload` | recreated |
| "A report is running" | `JobsCog._report_lock` | during a report | n/a |
| Jobs, scrape runs, "already posted" records | the scraper's SQLite DB, `../swiss-actuarial-job-scraper/data/jobs.db` | permanent | **yes** |
| Daily Markdown reports | `../swiss-actuarial-job-scraper/reports/` | permanent | **yes** |
| Logs | `logs/fgbot.log` (14 days) and the systemd journal | rotating | **yes** |

Only the scraper's database is worth backing up ([deployment.md](deployment.md#backups)).
Losing in-memory state is a deliberate simplification; see
[handover.md](handover.md#known-limitations-and-technical-debt) for how it could be persisted.

## Import rules

These rules keep the modules independent. Follow them when adding code.

```
 __main__ ──▶ bot ──▶ cogs/<feature>/__init__ ──▶ cogs/<feature>/cog.py ──▶ logic modules
                │                                        │                   (session.py, track.py,
                │                                        │                    reporter.py, …)
                ▼                                        ▼                        │
       config, errors, utils/  ◀─────────────────────────┴────────────────────────┘
                                                cogs/chess ──▶ shessgpt/ (no Discord, no fgbot.cogs)
                                                cogs/jobs  ──▶ actjobs   (the scraper, public API only)
```

- **No cog imports another cog.** Features can be switched off independently, so they must not
  depend on each other. Shared code goes into `utils/`, `errors.py` or `config.py`.
- **`shessgpt/` imports neither Discord nor anything from `fgbot.cogs`.** It is a standalone
  library that happens to live in this repository.
- **Logic modules don't talk to Discord.** The jobs modules may *build* plain discord.py data
  objects (`discord.Embed`, `discord.File`), but never send anything (see
  [above](#separation-of-logic-and-discord)).
- **Only `cogs/jobs/` imports `actjobs`**, and only the symbols listed in the
  [scraper API contract](job-reports.md#the-scraper-api-contract).
- Modules import `FGBot` only under `if TYPE_CHECKING:` (for type hints). This avoids a
  circular import, because `bot.py` loads the cogs.

## The job scraper integration

The bot imports the scraper as a library. `pyproject.toml` declares it as an editable path
dependency:

```toml
[tool.uv.sources]
swiss-actuarial-job-scraper = { path = "../swiss-actuarial-job-scraper", editable = true }
```

It uses only the scraper's public API, `actjobs.service.JobService`, plus a few helpers from
`actjobs.report`. Changes inside the scraper therefore don't break the bot as long as that API
stays the same. Details: [job-reports.md](job-reports.md).

## Design decisions

| Decision | Why |
|---|---|
| Slash commands only | Discord's recommended UI: argument hints, validation, autocomplete. No privileged *message content* intent needed. |
| No privileged intents | Simpler bot verification if the bot ever grows; less data handled. |
| One chess game per channel, players by user ID | The old single global game blocked everybody else; display names can be faked. |
| Lazy track resolution | Fast Spotify playlists; no expired stream URLs. |
| The bot runs the scrape (not a separate timer) | One service to run and monitor; the report can describe the scrape it just made. |
| The scraper decides the job filter | `actjobs list` and the Discord report always agree. |
| No database of its own | All state that matters (jobs, posted jobs) is in the scraper's DB; games and queues are short-lived. |
| PyTorch CPU wheels | ~700 MB instead of several GB; ShessGPT is tiny and fast on CPU. |
