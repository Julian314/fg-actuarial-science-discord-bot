# Configuration

All settings are environment variables. The usual place for them is the `.env` file in the
repository root. Start from the commented template:

```bash
cp .env.example .env
```

How settings are read (`src/fgbot/config.py`):

- Values are read from the real environment first, then from `.env`. A variable set in the shell
  or in a systemd unit wins over the file.
- Empty values (`GUILD_ID=`) mean "use the default".
- Everything is **validated at startup**. A wrong value, e.g. `JOBS_TIME=7am`, stops the bot
  immediately with a message that names the variable, instead of failing hours later.
- Relative paths are resolved against the **repository root**, not the directory you start the
  bot from.

To add a new setting, add a field to `Settings` in `config.py`, document it in `.env.example`, and
add it to this page.

## Core

| Variable | Default | Description |
|---|---|---|
| `DISCORD_TOKEN` | **required** | The bot token ([how to get it](setup-discord-app.md#2-get-the-bot-token)). |
| `GUILD_ID` | empty | Server ID. If set, slash commands are registered for that server only and appear instantly. If empty, they are registered globally (can take up to an hour). |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |
| `LOG_DIR` | `logs` | Where `fgbot.log` is written. It rotates at midnight and keeps 14 days. |

## Feature toggles

| Variable | Default | Description |
|---|---|---|
| `MUSIC_ENABLED` | `true` | Load the music commands. |
| `CHESS_ENABLED` | `true` | Load the chess commands. This also loads PyTorch: the bot needs about 300 MB of RAM instead of about 90 MB. |
| `JOBS_ENABLED` | `true` | Load the daily job report. Requires `JOBS_CHANNEL_ID` and the scraper project. |

A disabled feature isn't loaded at all, and its commands don't appear in Discord.

## Music

| Variable | Default | Description |
|---|---|---|
| `SPOTIFY_CLIENT_ID` | empty | Spotify app credentials, only needed for Spotify links ([setup](music.md#spotify-links)). |
| `SPOTIFY_CLIENT_SECRET` | empty | See above. |
| `MUSIC_IDLE_TIMEOUT` | `300` | Seconds without music before the bot leaves the voice channel (minimum 10). |
| `MUSIC_DEFAULT_VOLUME` | `50` | Starting volume, 0–100. |

## Chess

| Variable | Default | Description |
|---|---|---|
| `STOCKFISH_PATH` | `stockfish` | The Stockfish binary: a command on `$PATH` or a full path. If it is missing, `/chess eval` and `/chess hint` only show ShessGPT's opinion. |
| `STOCKFISH_THINK_TIME` | `0.5` | Seconds Stockfish thinks per request (up to 10). |
| `SHESSGPT_WEIGHTS` | bundled file | Path to other ShessGPT weights. They must have the same network shape. |

## Daily job report

| Variable | Default | Description |
|---|---|---|
| `JOBS_CHANNEL_ID` | **required if jobs are enabled** | Text channel that receives the report. |
| `ACTJOBS_CONFIG` | `../swiss-actuarial-job-scraper/config/settings.toml` | The scraper's settings file. The scraper's database, report folder and filters are all configured there. |
| `JOBS_TIME` | `07:00` | When to scrape and post, as `HH:MM`. |
| `JOBS_TIMEZONE` | `Europe/Zurich` | Time zone for `JOBS_TIME` and for dates in the report. |
| `JOBS_MAX_AGE_DAYS` | `7` | Only post jobs first seen within this many days. This stops a new channel from receiving the whole backlog. |
| `JOBS_POST_WHEN_EMPTY` | `true` | Post "No new postings today" when nothing is new. With `false` the bot stays silent on those days. |
| `JOBS_ATTACH_REPORT` | `true` | Attach the scraper's full Markdown report (`jobs-YYYY-MM-DD.md`) to the post. |

**Which jobs count as "matching"** (seniority, categories, cantons, languages, workload) is not
set here. It is the `[output]` section of the **scraper's** `config/settings.toml`. See
[job-reports.md](job-reports.md#changing-which-jobs-are-posted).

## Example `.env`

```dotenv
DISCORD_TOKEN=MTIz...
GUILD_ID=123456789012345678
JOBS_CHANNEL_ID=234567890123456789
SPOTIFY_CLIENT_ID=0123456789abcdef
SPOTIFY_CLIENT_SECRET=fedcba9876543210
```

Everything else keeps its default.
