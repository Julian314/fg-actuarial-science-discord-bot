# Development

## Setup

```bash
uv sync                  # installs the bot, the scraper (editable) and dev tools
cp .env.example .env     # use a test server: set GUILD_ID so commands appear instantly
uv run fgbot
```

**Use a separate test bot** (a second application in the Developer Portal) and a private test
server while developing, so you don't disturb the real server.

## Everyday commands

```bash
uv run pytest                    # all tests (≈ 3 s, offline, no Discord needed)
uv run pytest tests/test_jobs.py -k summary -v     # a subset, verbose
uv run ruff check .              # lint
uv run ruff check . --fix        # lint and fix what can be fixed automatically
uv run ruff format .             # format
```

Run all three before committing. The full workflow, from branch to release, and the definition
of done are in [CONTRIBUTING.md](../CONTRIBUTING.md).

## What the tests cover

| File | Covers |
|---|---|
| `test_config.py` | Defaults, validation errors, `.env.example` stays valid |
| `test_bot.py` | All extensions load into a real (unconnected) bot and register their commands; missing Stockfish is not fatal |
| `test_shessgpt_encoding.py` | The input encoding equals the original training encoding (regression oracle) |
| `test_shessgpt_search.py` | Weights load, mate in one is found, no crash in finished games |
| `test_chess_session.py` | Move parsing, turns, undo, override, game endings, board rendering |
| `test_music.py` | Queue, durations, Spotify link parsing and pagination, yt-dlp result handling (faked) |
| `test_jobs.py` | Embed formatting and Discord limits, the report flow with a fake scraper service |

Nothing touches the network. yt-dlp, Spotify and the scraper are replaced by small fakes. The
real network paths (playing a song, a real scrape) are checked by hand; see the checklist below.

## Writing tests

Tests are plain functions in `tests/test_<topic>.py` whose names start with `test_`. pytest
finds and runs them. A few patterns are already in use; copy them.

**Test the logic module, not the cog.** `ChessSession`, `TrackQueue`, `formatting` and
`JobReporter` take plain values and return plain values, so a test just calls them:

```python
def test_undo_takes_back_a_full_move() -> None:
    session = ChessSession.create(player_id=1, player_color=chess.WHITE)
    session.push_player_move(session.parse_move("e4"))
    session.push_bot_move(session.parse_move("e5"))
    session.undo()
    assert session.board.fen() == chess.STARTING_FEN
```

**Async tests need no decorator.** `asyncio_mode = "auto"` in `pyproject.toml` means an
`async def test_…` runs in an event loop automatically.

**Replace slow or external things with a fake.** `tests/test_jobs.py` defines `FakeService`, a
small class with just the `JobService` methods that `JobReporter` calls (`run_scrape`,
`unnotified`, `mark_notified`, …). It keeps "posted" jobs in a dict instead of SQLite. For
objects where only a few attributes matter, `types.SimpleNamespace(run_id=1, status="ok")`
is enough. `tests/test_music.py` fakes yt-dlp's result dicts the same way.

**Expensive fixtures are loaded once.** The real ShessGPT network is provided by the
`shessgpt_net` fixture in `tests/conftest.py` (`scope="session"`). Ask for it by naming it as
a parameter: `def test_mate_in_one(shessgpt_net): …`.

**Regression oracle.** `tests/fixtures/old_encoding.py` is a verbatim copy of the original
training code's input encoding. `tests/test_shessgpt_encoding.py` checks that the new encoding
produces exactly the same numbers. Don't "clean up" that fixture: its whole point is to stay
identical to the old code. It is excluded from ruff for that reason.

**Tests that need the scraper skip themselves** if `../swiss-actuarial-job-scraper` is missing
(see `tests/test_bot.py`), so the rest of the suite still runs.

## Conventions

- **Formatting and lint:** ruff, line length 100. Configured in `pyproject.toml`.
- **Type hints** on all functions; `from __future__ import annotations` at the top of every
  module.
- **Docstrings:** every module starts with one explaining *what it is for*. Public classes and
  functions have one too. Comments explain *why*, not *what*.
- **Logic without Discord** where possible (see [architecture.md](architecture.md#separation-of-logic-and-discord)).
- **Blocking work goes into `asyncio.to_thread`.** If a command can take more than about 2 s,
  `defer()` first.
- **User-facing errors** raise `UserFacingError("Clear sentence with a fix.")`.
- **Logging:** `log = logging.getLogger(__name__)` per module. Never `print`. Never log tokens or
  secrets.
- **Messages in English**, short and friendly.

## Adding a command to an existing cog

```python
# src/fgbot/cogs/music/cog.py, inside class MusicCog
@app_commands.command(name="clear", description="Remove all songs from the queue.")
async def clear(self, interaction: discord.Interaction) -> None:
    player = self._require_player(interaction)  # raises UserFacingError if not allowed
    player.queue.clear()
    await interaction.response.send_message("🧹 Cleared the queue.")
```

Restart the bot. With `GUILD_ID` set, the command appears immediately; `/help` picks it up
automatically. Add the command to [commands.md](commands.md).

## Adding a new feature (cog)

1. Create the package `src/fgbot/cogs/quiz/` with:

   ```python
   # cog.py
   """Actuarial exam quiz: /quiz …"""

   from __future__ import annotations
   from typing import TYPE_CHECKING
   import discord
   from discord import app_commands
   from discord.ext import commands

   if TYPE_CHECKING:
       from fgbot.bot import FGBot


   class QuizCog(commands.GroupCog, group_name="quiz", group_description="Exam practice"):
       def __init__(self, bot: FGBot) -> None:
           self.bot = bot

       @app_commands.command(name="question", description="Get a practice question.")
       async def question(self, interaction: discord.Interaction) -> None:
           await interaction.response.send_message("What is the expected value of …?")
   ```

   ```python
   # __init__.py
   """Extension entry point for the quiz feature."""

   from fgbot.cogs.quiz.cog import QuizCog


   async def setup(bot) -> None:
       await bot.add_cog(QuizCog(bot))
   ```

2. Add a toggle `quiz_enabled: bool = True` to `Settings` in `config.py`, plus `.env.example` and
   [configuration.md](configuration.md).
3. Register the extension in `FGBot.enabled_extensions()` in `bot.py`.
4. Put the logic in a Discord-free module and test it in `tests/test_quiz.py`. Add the new
   commands to the expected set in `tests/test_bot.py`.
5. Document it in [commands.md](commands.md) and the README's feature table.

## Dependencies

```bash
uv add some-package                 # runtime dependency
uv add --group dev some-tool        # development-only
uv lock --upgrade                   # upgrade everything within the constraints
```

Always commit `pyproject.toml` and `uv.lock` together.

## Manual test checklist (before a release)

Run against a test server with `GUILD_ID` set.

- [ ] `/ping`, `/about`, `/help`
- [ ] `/play` with search text, a YouTube URL, a Spotify track and a Spotify playlist
- [ ] `/queue`, `/skip`, `/loop` (song repeats, only one "Now playing"), `/volume 20` (changes immediately), `/pause`, `/resume`, `/remove 2`, `/shuffle`, `/stop`
- [ ] Everyone leaves the voice channel → bot leaves; idle timeout → bot leaves
- [ ] `/chess start color:black` (bot moves first, board flipped), several `/chess move` with autocomplete, `/chess hint`, `/chess eval`, `/chess undo`, `/chess override`, play until mate, `/chess resign`
- [ ] `/jobs status`, `/jobs list category:Actuarial`, `/jobs search Swiss`
- [ ] `/jobs run-now` → report appears; run it again → "No new postings today"
