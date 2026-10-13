# Troubleshooting

Look at the log first. Most problems explain themselves there:

```bash
journalctl --user -u fgbot -n 100      # systemd user service (server: journalctl -u fgbot)
tail -n 100 logs/fgbot.log             # file log, also when started by hand
```

For more detail, set `LOG_LEVEL=DEBUG` in `.env` and restart.

## Startup

| Symptom | Cause and fix |
|---|---|
| `Invalid configuration (check your .env file)` | A setting is missing or wrong; the message names it. See [configuration.md](configuration.md). The bot exits with code 2 and systemd doesn't restart it. |
| `Discord rejected the bot token` | Wrong or reset token. Copy a fresh one from the Developer Portal → Bot → Reset Token. |
| `JOBS_CHANNEL_ID is required when JOBS_ENABLED=true` | Set the channel ID, or `JOBS_ENABLED=false`. |
| `ACTJOBS_CONFIG points to …, which does not exist` | Clone `swiss-actuarial-job-scraper` next to this repository, or set the full path. |
| `uv sync` fails building the scraper | The scraper isn't at `../swiss-actuarial-job-scraper` (see `[tool.uv.sources]` in `pyproject.toml`). |
| `Stockfish could not be started` (warning) | Not installed or not on `PATH` (Debian: `/usr/games/stockfish`). Install it or set `STOCKFISH_PATH`. The bot works without it. |
| `OSError: no library called "cairo"` | Install cairo: `pacman -S cairo` / `apt install libcairo2`. |

## Slash commands

| Symptom | Cause and fix |
|---|---|
| Commands don't show up | Without `GUILD_ID`, global commands can take up to an hour to appear. Set `GUILD_ID` for instant registration. Restart Discord with Ctrl+R. Check that the bot was invited with the `applications.commands` scope. |
| Old commands from a previous version still appear | They were registered globally earlier. Start the bot once with `GUILD_ID` empty, so the global list is replaced by the current one. |
| "The application did not respond" | The bot is offline or was blocked for more than 3 s. Check the log for errors. |
| A command is missing for some users | Permissions: **Server Settings → Integrations → bot** may restrict it, and `/stop`, `/summon`, `/leave`, `/jobs run-now` need *Manage Server* by default. |

## Music

| Symptom | Cause and fix |
|---|---|
| Every `/play` says "Couldn't load …" | Usually an outdated yt-dlp. Update it: `uv lock --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs && uv sync`, then restart. Also check that `deno --version` works for the bot's user. |
| Log mentions "Sign in to confirm you're not a bot" | YouTube blocks the server's IP address, which is common for data-centre IPs. Try again later, or run the bot from a home connection. |
| The bot joins but there is no sound | `ffmpeg` missing from the service's `PATH` (check `which ffmpeg`), or the bot lacks the *Speak* permission in that channel. |
| Joining voice fails or times out | Check the *Connect* permission. Make sure discord.py is current (`uv lock --upgrade-package discord-py && uv sync`), because Discord's voice protocol (DAVE encryption) changes occasionally. |
| "Spotify links are not set up" | Add `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` ([how](music.md#spotify-links)). |
| "Couldn't read that Spotify playlist" | The playlist is private or made by Spotify itself. Neither can be read by apps. |

## Chess

| Symptom | Cause and fix |
|---|---|
| "A game is already running in this channel" | Finish it or `/chess resign`; moderators can also resign other people's games. Or play in another channel. |
| No move suggestions while typing | Autocomplete only works for the player whose turn it is, in a channel with a running game. |
| Games vanished | Games live in memory, so a restart ends them. Save the position with `/chess fen` and continue later with `/chess start fen:…`. |

## Job reports

| Symptom | Cause and fix |
|---|---|
| No report in the morning | Check `/jobs status` and the log around `JOBS_TIME`. Was the bot running? It catches up after the next start. Can the bot post in the channel (*Send Messages*, *Embed Links*, *Attach Files*)? |
| "Another scrape was already running" | The scraper's own timer or a manual `actjobs run` was running at the same moment. Disable the scraper's scheduling ([job-reports.md](job-reports.md#running-at-the-same-time-as-other-scrapes)). |
| "Today's scrape failed" | The traceback is in the log. Test the sources: `cd ../swiss-actuarial-job-scraper && uv run actjobs sources check`. |
| Report every day is "No new postings" | Possibly correct. Otherwise compare with `uv run actjobs list --new` in the scraper and check the `[output]` filter in its `settings.toml`. |
| The same jobs are posted twice | Two bot instances with the same token, or the scraper's own Discord webhook is enabled as well. |
| Want to re-post everything | Delete this channel's rows: `sqlite3 data/jobs.db "DELETE FROM notifications WHERE channel='discord:<id>'"` in the scraper folder, then `/jobs run-now scrape:False`. |
