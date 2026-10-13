# FG Actuarial Science Discord Bot

A Discord bot for the FG Actuarial Science server. It does three things:

| Feature | What it does | Commands |
|---|---|---|
| 🎵 **Music** | Plays songs from YouTube (search text or URL) and Spotify links in voice channels | `/play`, `/skip`, `/queue`, `/loop`, … |
| ♟️ **Chess** | Play against **ShessGPT**, a small neural-network engine, with Stockfish as an advisor | `/chess start`, `/chess move`, `/chess hint`, … |
| 💼 **Job reports** | Every morning, scrapes Swiss insurers and job boards for junior actuarial jobs and posts the new ones to a channel | `/jobs list`, `/jobs search`, `/jobs status`, `/jobs run-now` |

This is a rewrite of the older [Discord-Music-Chess-Bot](https://github.com/Julian314/Discord-Music-Chess-Bot)
with modern slash commands, many bug fixes and the new job report. The job data comes from the
sibling project [`swiss-actuarial-job-scraper`](../swiss-actuarial-job-scraper).

> **Taking over the bot?** Start with [docs/onboarding.md](docs/onboarding.md), then
> [docs/handover.md](docs/handover.md).

## Quick start (about 5 minutes)

You need: Linux, [uv](https://docs.astral.sh/uv/), `ffmpeg`, `deno` and (optional) `stockfish`.
Both repositories must be in the same parent folder:

```
~/Projects/
├── fg-actuarial-science-discord-bot/     ← this repository
└── swiss-actuarial-job-scraper/          ← the job scraper (imported as a library)
```

```bash
# 1. System packages (Arch; Debian/Ubuntu names in docs/deployment.md)
sudo pacman -S ffmpeg deno stockfish

# 2. Python dependencies (creates .venv/, downloads Python 3.13 if needed)
cd ~/Projects/fg-actuarial-science-discord-bot
uv sync

# 3. Configuration
cp .env.example .env
$EDITOR .env          # at least DISCORD_TOKEN and JOBS_CHANNEL_ID (GUILD_ID recommended)

# 4. Run
uv run fgbot
```

You don't have a bot token yet? [docs/setup-discord-app.md](docs/setup-discord-app.md) walks you
through creating the Discord application and inviting the bot to your server.

To keep the bot running in the background, and to start it automatically, use the systemd service
described in [docs/deployment.md](docs/deployment.md).

## Documentation

| Document | Read it when you want to… |
|---|---|
| [Onboarding](docs/onboarding.md) | **take over the project**: what to learn, reading order, code tour, exercises |
| [Handover](docs/handover.md) | transfer accounts and secrets, see the maintenance calendar and known limitations |
| [Glossary](docs/glossary.md) | look up a term (guild, defer, cog, FEN, WAL, …) |
| [Setting up the Discord app](docs/setup-discord-app.md) | create the bot account, get the token, invite the bot |
| [Configuration](docs/configuration.md) | understand every setting in `.env` |
| [Commands](docs/commands.md) | know what every slash command does (user guide) |
| [Job reports](docs/job-reports.md) | understand or change the daily job report |
| [Music](docs/music.md) | set up Spotify, understand yt-dlp and keep it working |
| [Chess engine](docs/chess-engine.md) | understand how ShessGPT thinks |
| [Deployment](docs/deployment.md) | run the bot 24/7 on this machine or on a server |
| [Architecture](docs/architecture.md) | understand how the code is organised and why |
| [Development](docs/development.md) | run tests, add a command or a new feature |
| [Troubleshooting](docs/troubleshooting.md) | fix a problem |
| [Migrating from the old bot](docs/migration-from-old-bot.md) | see what changed compared to the 2024 bot ⚠️ security note inside |
| [CONTRIBUTING](CONTRIBUTING.md) | make a change: workflow, definition of done, releasing |
| [CHANGELOG](CHANGELOG.md) | see what changed between versions |

## Project layout

```
src/fgbot/
├── __main__.py        entry point (`uv run fgbot`)
├── bot.py             the bot: loads cogs, syncs slash commands, handles errors
├── config.py          all settings, validated at startup
├── cogs/              one folder per feature
│   ├── general/       /help, /ping, /about
│   ├── music/         /play & co.
│   ├── chess/         /chess …
│   └── jobs/          daily job report, /jobs …
└── shessgpt/          the neural-network chess engine (no Discord code)
tests/                 pytest suite (runs offline, no Discord connection needed)
docs/                  documentation
deploy/systemd/        service files for running the bot permanently
deploy/docker/         container image (built by .github/workflows/docker.yml)
deploy/truenas/        TrueNAS Custom App template
```

## Development in one minute

```bash
uv run pytest          # run the tests
uv run ruff check .    # lint
uv run ruff format .   # format
```

See [docs/development.md](docs/development.md) for conventions and how to add a feature, and
[CONTRIBUTING.md](CONTRIBUTING.md) for the workflow from branch to release.

## Credits

- The music player design was originally inspired by the
  [discord.py music bot gist](https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d)
  by Valentin B. (MIT).
- ShessGPT was trained by Julian in a separate project; this repository only contains the
  trained weights and the code to run them.
- Licensed under the MIT License, see [LICENSE](LICENSE).
