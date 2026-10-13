# Glossary

Short definitions of the terms used in the code and in these docs, with a pointer to where
each one matters. The terms are grouped by topic and sorted alphabetically within each group.

## Discord

| Term | Meaning | Where it matters |
|---|---|---|
| **Application / bot user** | The entry in the Discord Developer Portal that owns the bot. Its *bot user* is the account that appears in the server. | [setup-discord-app.md](setup-discord-app.md) |
| **Application command sync** | Uploading the list of slash commands to Discord. Syncing to one **guild** is instant; syncing **globally** can take up to an hour. | `FGBot.setup_hook` in `src/fgbot/bot.py`, `GUILD_ID` |
| **Channel ID / Guild ID / User ID** | The permanent numbers Discord uses to identify things. Names can change; IDs never do. | `.env`, `ChessSession.player_id` |
| **DAVE** | Discord's end-to-end encryption for voice. discord.py handles it, but needs to be kept up to date. | [music.md](music.md#requirements) |
| **Defer / followup** | `interaction.response.defer()` tells Discord "I'm working on it" (shown as "Bot is thinking…"). The real answer then comes via `interaction.followup.send()`. Needed when a reply takes more than 3 seconds. | `/play`, `/chess move` |
| **Embed** | A formatted message card with title, text, colour, fields and image. Size limits: 4096 characters of text, 10 embeds and 6000 characters per message. | `src/fgbot/utils/embeds.py`, `cogs/jobs/formatting.py` |
| **Ephemeral** | A reply only the user who ran the command can see. | errors, `/help`, `/chess hint`, `/jobs …` |
| **Gateway** | The permanent connection between the bot and Discord through which events arrive. It reconnects now and then, and `on_ready` runs again each time. | `FGBot.on_ready` |
| **Guild** | Discord's internal word for a *server*. | `GUILD_ID`, `MusicCog.players` (one player per guild) |
| **Intent** | Which kinds of events the bot subscribes to. *Privileged* intents (message content, members, presence) need extra approval. This bot needs none. | `FGBot.__init__` |
| **Interaction** | One use of a slash command, a button or an autocomplete. The bot must answer within 3 seconds and can send followups for 15 minutes. | the `interaction` argument of every command |
| **Slash command** | A command typed as `/name` with typed arguments that Discord validates. | every `@app_commands.command` |
| **Voice client** | The bot's connection to one voice channel. | `GuildPlayer.voice` in `cogs/music/player.py` |

## discord.py

| Term | Meaning | Where it matters |
|---|---|---|
| **`app_commands`** | The part of discord.py for slash commands. | imports in every cog |
| **Autocomplete** | A function that suggests argument values while the user types. | `ChessCog.move_autocomplete` |
| **Cog** | A class that groups commands, event listeners and state for one feature. | `src/fgbot/cogs/*/cog.py` |
| **`cog_load` / `cog_unload`** | Methods discord.py calls when a cog is added or removed. Used to open and close resources. | Stockfish, the job service, the daily task |
| **CommandTree** | The registry of all slash commands (`bot.tree`). It dispatches each interaction to the right method. | `FGBot.setup_hook`, `/help` |
| **Extension** | A module with `async def setup(bot)` that adds a cog. Loaded with `bot.load_extension("fgbot.cogs.music")`. | `src/fgbot/cogs/*/__init__.py` |
| **GroupCog** | A cog whose commands become one group: `/chess start`, `/chess move`, … | `ChessCog`, `JobsCog` |
| **`setup_hook`** | Runs once before the bot connects. The right place to load extensions. | `FGBot.setup_hook` |
| **`tasks.loop`** | Runs a coroutine on a schedule, e.g. every day at 07:00. | `JobsCog.daily_report` |

## Python and asyncio

| Term | Meaning | Where it matters |
|---|---|---|
| **`asyncio.Lock`** | Lets only one task at a time into a block of code (`async with lock:`). | chess sessions, Stockfish, job reports |
| **`asyncio.to_thread`** | Runs a blocking function in a worker thread so the event loop stays free. | yt-dlp, SQLite, ShessGPT, rendering |
| **Coroutine** | A function defined with `async def`. It can pause at `await`. | everywhere |
| **Event loop** | The scheduler that runs all coroutines on one thread, switching between them whenever one waits. | [architecture.md](architecture.md#concurrency-async-code-and-threads) |
| **pydantic-settings** | A library that reads environment variables into a typed, validated class. | `src/fgbot/config.py` |
| **`SecretStr`** | A pydantic type that hides its value in logs and error messages. | `DISCORD_TOKEN`, `SPOTIFY_CLIENT_SECRET` |

## Chess

| Term | Meaning | Where it matters |
|---|---|---|
| **Bitboard** | 64 bits, one per square, marking where pieces of one kind stand. | `src/fgbot/shessgpt/encoding.py` |
| **Centipawn** | 1/100 of a pawn. Stockfish's unit of evaluation; the bot shows pawns. | `format_stockfish_score` |
| **FEN** | A one-line text description of a position, e.g. `rnbqkbnr/pppppppp/8/… w KQkq - 0 1`. | `/chess fen`, `/chess start fen:…` |
| **Minimax** | Search that assumes both sides play their best move: maximise for White, minimise for Black. | `src/fgbot/shessgpt/search.py` |
| **Outcome** | python-chess's description of how a game ended (winner and reason). | `ChessSession.outcome` |
| **Ply** | One half-move (a move of one side). ShessGPT searches 2 ply. | [chess-engine.md](chess-engine.md#the-search-searchpy) |
| **SAN** | Standard Algebraic Notation, the human notation: `e4`, `Nf3`, `O-O`, `exd5`, `e8=Q`. | `ChessSession.parse_move` |
| **ShessGPT** | The bot's own small neural network that plays against users (about 600 Elo). | `src/fgbot/shessgpt/` |
| **Stockfish** | The strongest open-source chess engine, used as the advisor. A separate program. | `cogs/chess/engines.py` |
| **UCI** | (1) Move notation with from/to squares: `g1f3`. (2) The text protocol used to talk to engines like Stockfish. | `parse_move`, `StockfishEngine` |

## Music

| Term | Meaning | Where it matters |
|---|---|---|
| **deno** | A JavaScript runtime. yt-dlp needs it to solve YouTube's player challenges. | [music.md](music.md#requirements) |
| **FFmpeg** | The program that streams and decodes audio for Discord. | `cogs/music/sources.py` |
| **Lazy resolving** | Looking a song up only when it is its turn, not when it is queued. | `Track.needs_resolving` |
| **Stream URL** | The direct audio URL yt-dlp extracts. It expires after a few hours. | `STREAM_URL_MAX_AGE_S` in `cogs/music/track.py` |
| **yt-dlp** | The library that finds videos and their audio streams. Must be updated often. | [music.md](music.md#keeping-yt-dlp-up-to-date-important) |

## Infrastructure and tooling

| Term | Meaning | Where it matters |
|---|---|---|
| **`.env`** | The local file with settings and secrets. Git-ignored, never committed. | [configuration.md](configuration.md) |
| **Editable path dependency** | A dependency installed from a local folder; changes there take effect without reinstalling. The scraper is one. | `[tool.uv.sources]` in `pyproject.toml` |
| **Exit code 2** | How the bot signals "configuration error". systemd does not restart it then. | `__main__.py`, `RestartPreventExitStatus=2` |
| **journalctl** | Shows the logs systemd collected. `journalctl --user -u fgbot -f` follows them live. | [deployment.md](deployment.md) |
| **Linger** | `loginctl enable-linger`: keeps a user's systemd services running when that user is logged out. | [deployment.md](deployment.md#option-a-this-machine-systemd-user-service) |
| **Lock file (scraper)** | `data/jobs.lock`. Prevents two scrapes from running at the same time. | [job-reports.md](job-reports.md#running-at-the-same-time-as-other-scrapes) |
| **ruff** | The linter and formatter. `uv run ruff check .` and `uv run ruff format .` | `[tool.ruff]` in `pyproject.toml` |
| **SQLite / WAL** | The scraper's single-file database. *WAL mode* lets readers work while a scrape writes. | `jobs.db`, [job-reports.md](job-reports.md#inspecting-things-by-hand) |
| **systemd unit / service** | A config file that tells Linux how to start, stop and restart a program. A *user* service runs as you; a *system* service runs as a dedicated user. | `deploy/systemd/` |
| **uv** | The Python package and project manager. Installs Python and all dependencies into `.venv/`. | `uv sync`, `uv run …` |
| **`uv.lock`** | The exact versions of every dependency. Commit it together with `pyproject.toml`. | [development.md](development.md#dependencies) |
