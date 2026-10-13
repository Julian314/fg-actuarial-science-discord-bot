# New maintainer? Start here

This page is for the student who takes over the bot. It tells you what to learn first, in which
order to read the other pages, and walks you through the code along four real paths. Plan
about one afternoon for the reading and the code tour, and a few evenings for the exercises.

You don't need to be a software engineer. If you can write a Python function and a class, you
can maintain this bot. Everything else is explained here or in the [glossary](glossary.md).

## 1. What you need to know

| Topic | Why it matters here | Learn it from |
|---|---|---|
| **Python basics**: functions, classes, `dataclass`, type hints, modules and packages | All of the code | [The Python tutorial](https://docs.python.org/3/tutorial/) |
| **asyncio**: `async def`, `await`, tasks, locks | The whole bot runs on one asyncio event loop | The primer below, then [asyncio docs](https://docs.python.org/3/library/asyncio.html) |
| **discord.py**: bot, cog, extension, slash command, interaction | Every file in `src/fgbot/cogs/` | The primer below, then [discord.py docs](https://discordpy.readthedocs.io/en/stable/) |
| **git** and **uv** | Getting, changing and running the code | [git book, ch. 1–3](https://git-scm.com/book/en/v2), [uv docs](https://docs.astral.sh/uv/) |
| **systemd** (only if you host the bot) | Keeping the bot running 24/7 | [deployment.md](deployment.md) |

You do **not** need to know PyTorch, chess engines or web scraping to maintain the bot. Those
parts are self-contained and rarely change.

### asyncio in five minutes

A normal Python program does one thing at a time. A Discord bot has to wait for many things at
once: messages from Discord, YouTube lookups, a 5-minute scrape. asyncio handles this with one
**event loop** that switches between tasks whenever one of them is *waiting*.

```python
async def play(interaction):  # "async def" = a coroutine, can pause at "await"
    await interaction.response.defer()  # pause here; the loop serves other commands meanwhile
    track = await sources.resolve(...)  # pause again while yt-dlp works
```

Three rules follow from this. The code follows them everywhere, and so should you:

1. **Never block the loop.** A function that takes long *without* `await` (a slow library
   call, heavy computation) freezes the whole bot. Run it in a worker thread with
   `await asyncio.to_thread(slow_function, arg)`. Examples: yt-dlp, SQLite, the ShessGPT
   search.
2. **Answer Discord within 3 seconds.** If a command needs longer, call
   `await interaction.response.defer()` first ("Bot is thinking…") and send the real answer
   with `interaction.followup.send(...)` later.
3. **Use a lock when two commands could interfere.** `async with session.lock:` makes the
   second `/chess move` wait until the first one has finished.

### discord.py in five minutes

| Term | Meaning | In this code |
|---|---|---|
| **Bot** | The program that logs in to Discord as the bot user | `FGBot` in `src/fgbot/bot.py` |
| **Cog** | A class that groups related commands and their state | `MusicCog`, `ChessCog`, `JobsCog`, `GeneralCog` |
| **Extension** | A module with `async def setup(bot)` that adds a cog | each `src/fgbot/cogs/<feature>/__init__.py` |
| **Slash command** | A method decorated with `@app_commands.command(...)` | e.g. `ping` in `cogs/general/cog.py` |
| **Interaction** | One use of a slash command; you reply through it | the `interaction` argument of every command |
| **Embed** | A formatted message card (title, text, colour, fields) | helpers in `src/fgbot/utils/embeds.py` |

## 2. Reading order

Read the pages in this order. Each one assumes you have read the ones before it.

1. [README](../README.md): what the bot does, quick start, project layout.
2. [Setting up the Discord app](setup-discord-app.md): create your own **test bot**. Do this
   now, before reading the code.
3. [Architecture](architecture.md): how the code is organised and why. The most important page.
4. [Development](development.md): tests, conventions, how to add a command.
5. [CONTRIBUTING](../CONTRIBUTING.md): the workflow for a change, from branch to deployment.
6. The feature pages, when you work on that feature: [music](music.md),
   [chess engine](chess-engine.md), [job reports](job-reports.md).
7. [Handover](handover.md): accounts, secrets, the maintenance calendar and known limitations.
8. Keep [troubleshooting](troubleshooting.md), [configuration](configuration.md),
   [commands](commands.md) and the [glossary](glossary.md) as references.

## 3. Code tour

Open the files side by side and follow along. Line numbers are correct as of version 1.0.0;
if they have drifted, search for the function name instead.

### Path 1: the bot starts

1. `uv run fgbot` runs `main()` in `src/fgbot/__main__.py:19`. The command name comes from
   `[project.scripts]` in `pyproject.toml`.
2. `Settings()` (`__main__.py:21`) reads `.env` and validates every value
   (`src/fgbot/config.py`). A wrong value stops the bot here with exit code 2.
3. `setup_logging(...)` (`__main__.py:27`) sends logs to the console and to `logs/fgbot.log`.
4. `bot.run(...)` (`__main__.py:31`) hands control to discord.py. From now on, discord.py
   calls *our* methods.
5. discord.py calls `FGBot.setup_hook` (`src/fgbot/bot.py:60`) exactly once. It loads one
   extension per enabled feature (`enabled_extensions`, `bot.py:49`) and then **syncs** the
   slash commands to Discord.
6. Loading an extension calls its `setup(bot)`, which adds the cog. discord.py then calls the
   cog's `cog_load`. For example, `ChessCog.cog_load` (`cogs/chess/cog.py:50`) loads the neural
   network and starts Stockfish.
7. When the connection is up, `FGBot.on_ready` (`bot.py:76`) logs "Logged in as …".

### Path 2: a simple command, `/ping`

`GeneralCog.ping` in `src/fgbot/cogs/general/cog.py:42`:

```python
@app_commands.command(name="ping", description="Check that the bot is alive.")
async def ping(self, interaction: discord.Interaction) -> None:
    latency_ms = self.bot.latency * 1000
    await interaction.response.send_message(f"Pong! 🏓 ({latency_ms:.0f} ms)", ephemeral=True)
```

- The decorator registers the method as `/ping`; the description is shown in Discord's command
  picker and in `/help`.
- `ephemeral=True` means only the user who typed the command sees the answer.
- It answers immediately, so no `defer()` is needed.

### Path 3: a complex command, `/chess move`

`ChessCog.move` in `src/fgbot/cogs/chess/cog.py:135`. Follow these steps:

1. `_session_for(..., player_only=True)` finds the game of this channel. It raises
   `UserFacingError` if there is none or if someone else typed the command. The global error
   handler (`FGBot.on_app_command_error`, `bot.py:87`) turns that into a private red message.
2. `async with session.lock:` (`cog.py:138`): a second `/chess move` waits here.
3. `session.parse_move(move)` and `session.push_player_move(...)`
   (`cogs/chess/session.py:96` and `:115`) contain the game rules. That module has no Discord
   code at all, so `tests/test_chess_session.py` can test it directly.
4. `interaction.response.defer(thinking=True)`: ShessGPT and rendering can take longer than
   3 seconds.
5. `_bot_turn` (`cog.py:84`) → `ShessGPTEngine.choose_move` (`cogs/chess/engines.py:40`) →
   `asyncio.to_thread(choose_move, ...)`: the neural-network search
   (`src/fgbot/shessgpt/search.py:79`) runs in a worker thread.
6. `_board_message` (`cog.py:69`) renders the board PNG, also in a thread
   (`cogs/chess/rendering.py`), and `interaction.followup.send(...)` posts it.

This one command shows almost every pattern in the codebase: the Discord layer is thin, the logic
lives in a separate module, blocking work goes to a thread, slow replies are deferred, a lock
protects shared state, and errors become `UserFacingError`.

### Path 4: a background job, the daily report

Code in `src/fgbot/cogs/jobs/`. Read [job-reports.md](job-reports.md) alongside.

1. `JobsCog.__init__` creates the daily loop with `tasks.loop(time=...)` (`cog.py:56`).
2. `JobsCog.cog_load` (`cog.py:59`) opens the scraper's `JobService`, creates the
   `JobReporter` and starts the loop.
3. Before the first iteration, `_before_daily_report` (`cog.py:80`) waits for the connection
   and catches up if no scrape ran in the last 20 hours.
4. Every day at `JOBS_TIME`, `_scheduled_report` (`cog.py:89`) calls `run_report`
   (`cog.py:95`). It catches every exception: one failed day must never stop the loop.
5. `run_report` does the following:
   - calls `reporter.scrape()` (`reporter.py:92`), which runs the scraper in a thread
   - calls `reporter.build_report()` (`reporter.py:136`), which builds the message objects
   - sends the messages
   - only after all of them were sent, calls `reporter.mark_posted()` (`reporter.py:130`)

## 4. First-week exercises

Do these on your **own test server with your own test bot**, never on the real server. Each
exercise has a clear "done" signal.

1. **Run the tests.** `uv sync && uv run pytest` is done when you see `96 passed` (or more).
2. **Run your test bot.** Set `DISCORD_TOKEN` and `GUILD_ID` in `.env` and run `uv run fgbot`.
   Done when `/ping` answers in your test server. Set `JOBS_ENABLED=false` if you don't have
   the scraper checked out.
3. **Add a command.** Add `/clear` as shown in
   [development.md](development.md#adding-a-command-to-an-existing-cog). Done when it appears
   in `/help` and empties the queue.
4. **Break a test on purpose.** In `src/fgbot/cogs/jobs/formatting.py`, change the
   `"No new postings today."` text. Run `uv run pytest tests/test_jobs.py`, read the failure,
   then change the text back. You now know how tests protect behaviour.
5. **Read a log.** Start the bot with `LOG_LEVEL=DEBUG`, use a few commands and find them in
   `logs/fgbot.log`.
6. **Follow the checklist.** Go through the manual test checklist in
   [development.md](development.md#manual-test-checklist-before-a-release) once. Done when you
   have ticked every box on your test server.

## 5. Getting help

- The outgoing maintainer's notes, the account inventory and the maintenance calendar are in
  [handover.md](handover.md). Fill in the "Contacts" section there when you take over.
- Most problems are already in [troubleshooting.md](troubleshooting.md).
- The [discord.py Discord server](https://discord.gg/dpy) and the
  [discord.py docs](https://discordpy.readthedocs.io/en/stable/) answer most discord.py
  questions.
- When you change something, update the documentation in the same commit. The next
  maintainer will thank you.
