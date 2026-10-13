# Handover

This page is the runbook for passing the bot from one maintainer to the next. It lists every
account, secret and piece of data the bot depends on, how to transfer each one, what has to be
done regularly, and the known weak spots.

> **Keep this page current.** Update the inventory and the contacts whenever an owner, a host
> or an account changes. Fields marked _fill in_ are specific to the current setup and can't
> be read from the code.

## Contacts

| Role | Name | Reachable via | Since |
|---|---|---|---|
| Current maintainer | _fill in_ | _fill in_ | _fill in_ |
| Previous maintainer | _fill in_ | _fill in_ | _fill in_ |
| Association board contact (owns the Discord server) | _fill in_ | _fill in_ | _fill in_ |

## Asset inventory

Everything the bot needs to run, and how to hand it over. "Rotate" means: after the handover,
replace the secret so the previous maintainer's copy stops working.

| Asset | Where it lives | Owner today | How to transfer | Rotate? |
|---|---|---|---|---|
| **Bot repository** | GitHub, `Julian314/fg-actuarial-science-discord-bot` (private) | _fill in_ | Best: create a GitHub **organisation** for the association and transfer the repo there (repo **Settings → General → Danger Zone → Transfer ownership**). The next handover is then just adding a member. Otherwise transfer it to the new maintainer's account. | no |
| **Scraper repository** | GitHub, `swiss-actuarial-job-scraper` | _fill in_ | Same as the bot repository. The bot can't run the job report without it ([why](job-reports.md#the-scraper-api-contract)). | no |
| **Discord application** (the bot account and its token) | [Developer Portal](https://discord.com/developers/applications) | _fill in_ | Create a **Team** in the Developer Portal (*Teams* tab), add the new maintainer, then transfer the application to the team (the application's *General Information* page). Team members need two-factor authentication. | **yes**: Bot → Reset Token, then update `DISCORD_TOKEN` in `.env` on the host |
| **Discord server roles** | Server Settings | association board | Nothing to transfer. The new maintainer needs *Manage Server* to use `/jobs run-now`, `/stop`, `/summon` and `/leave`, and to change command permissions under **Server Settings → Integrations → bot**. | no |
| **Spotify developer app** (optional) | [Spotify dashboard](https://developer.spotify.com/dashboard) | _fill in_ | Spotify apps can't be moved between accounts. The new maintainer creates their own app ([how](music.md#spotify-links)) and replaces `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`. Then delete the old app. | **yes**: by replacing the app |
| **Host** (the machine the bot runs on) | _fill in: laptop / server name, provider_ | _fill in_ | Give the new maintainer SSH access (their own key, not a shared password) or move the bot to a host they control ([deployment.md](deployment.md)). If the host belongs to the outgoing maintainer, plan the move **before** the handover date. | remove the old SSH keys |
| **`.env`** (all settings and secrets) | On the host, next to the code | maintainer | Hand it over through a **password manager** or an encrypted channel, never by chat or email. It is git-ignored, so it is not in the repository. | rotates with the token and Spotify secrets above |
| **Job database** `jobs.db` | `../swiss-actuarial-job-scraper/data/jobs.db` on the host | — | Stays on the host. When moving hosts, copy it as described in [deployment.md](deployment.md#3-configuration-and-data). It holds the job history and the "already posted" records; without it the channel gets up to `JOBS_MAX_AGE_DAYS` days of jobs again. | no |
| **ShessGPT weights** | `src/fgbot/shessgpt/weights/ShessGPT_2_57.pth`, in the repository | — | Nothing to do; they ship with the code. | no |
| **ShessGPT training code** | _fill in: where the training project lives, or "not needed"_ | _fill in_ | Only needed to *retrain* the network ([chess-engine.md](chess-engine.md#the-input-encodingpy)). | no |
| **Old bot repository** | GitHub, `Julian314/Discord-Music-Chess-Bot` (public) | _fill in_ | Archive it. Its git history contains old credentials; make sure they were rotated ([migration-from-old-bot.md](migration-from-old-bot.md), security section). | already done? _fill in_ |

## Checklists

### Outgoing maintainer

- [ ] Fill in every _fill in_ field on this page and commit it.
- [ ] Transfer the GitHub repositories, ideally to an association organisation.
- [ ] Move the Discord application into a Developer Portal Team and add the new maintainer.
- [ ] Hand over `.env` through a password manager.
- [ ] Give the new maintainer access to the host, or help move the bot to theirs.
- [ ] Walk through [onboarding.md](onboarding.md) together, ideally while the new maintainer
      deploys a test instance.
- [ ] Write down anything unusual you know that the docs don't say (in this file or in
      [troubleshooting.md](troubleshooting.md)).
- [ ] After the new maintainer confirms that everything works: remove your own access.

### Incoming maintainer

- [ ] Work through [onboarding.md](onboarding.md), including the exercises, with your own test
      bot.
- [ ] Confirm you can: log in to the host, read the logs (`journalctl`), restart the bot, and
      `git pull` and deploy an update ([deployment.md](deployment.md#updating)).
- [ ] **Rotate the secrets** the previous maintainer knew: reset the Discord token, replace the
      Spotify app, update `.env`, restart.
- [ ] Check that `/ping`, `/about` and `/jobs status` work on the real server, and that the
      next morning's report arrives.
- [ ] Make sure **only one instance** runs with the token. Two instances answer every command
      twice and post the report twice.
- [ ] Set up a backup of `jobs.db` ([deployment.md](deployment.md#backups)) if there isn't one.
- [ ] Put the maintenance calendar below into your own calendar.
- [ ] Update the "Contacts" table.

## Maintenance calendar

The bot depends on websites and services that change without warning. These routine tasks keep
it working. Each one takes a few minutes; afterwards, run `uv run pytest` and do a quick manual
check on the test server before deploying.

| When | Task | How |
|---|---|---|
| **When music breaks**, and otherwise **monthly** | Update yt-dlp. YouTube changes often, and old versions stop working. | `uv lock --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs && uv sync`, commit `uv.lock`, deploy ([music.md](music.md#keeping-yt-dlp-up-to-date-important)) |
| **Quarterly** | Update all dependencies, including discord.py (Discord's voice protocol changes now and then). | `uv lock --upgrade && uv sync`, run the tests and the [manual checklist](development.md#manual-test-checklist-before-a-release), commit `uv.lock` |
| **Quarterly** | Check that a backup of `jobs.db` can be restored. | Copy the latest backup to a temporary folder and run `sqlite3 copy.db "SELECT count(*) FROM jobs"` |
| **Quarterly** | Glance at the logs for recurring warnings, e.g. a job source that keeps failing. | `journalctl --user -u fgbot --since "-7 days" -p warning` |
| **Yearly** | Update Python when a new version is out and the dependencies support it. | Change `.python-version` (and `requires-python` / `target-version` in `pyproject.toml` if needed), `uv sync`, run the tests |
| **Yearly** | Update the host's system packages (`ffmpeg`, `deno`, `stockfish`, cairo). | `sudo pacman -Syu` / `sudo apt update && sudo apt upgrade` |
| **At every handover** | Rotate the secrets and update this page. | See the checklists above |

## Known limitations and technical debt

These are deliberate simplifications or open weak spots, not bugs. Each has a suggested
improvement, roughly ordered from most to least useful. They make good first projects for a new
maintainer.

| Limitation | Effect | Suggested improvement |
|---|---|---|
| **No continuous integration (CI)** | Tests only run when someone remembers to run them. | A GitHub Actions workflow that runs `uv run pytest` and `uv run ruff check .` on every push. The job tests need the scraper repo checked out next to this one; `tests/test_bot.py` skips itself without it. |
| **The scraper is a sibling path dependency** | The bot can't be installed from its own repository alone; both repositories must sit side by side. | Publish the scraper as a git dependency (`uv add git+https://…`) or as a package, and pin a version. |
| **The version is defined twice** | `pyproject.toml` and `src/fgbot/__init__.py` must both be bumped for a release. | Read it at runtime with `importlib.metadata.version("fg-actuarial-science-discord-bot")`, or use hatch's dynamic versioning. |
| **Chess games and music queues live in memory** | A restart (update, crash, reboot) ends all games and empties all queues. | Save games as FEN in a small SQLite table and restore them in `cog_load`. Players can already save a game with `/chess fen` and resume it with `/chess start fen:…`. |
| **Only one job-report channel** | The report can't go to several channels or servers. | Make `JOBS_CHANNEL_ID` a list. The "already posted" tracking is already per channel (`discord:<id>`), so the scraper side needs no change. |
| **YouTube blocks data-centre IP addresses** | Music may fail on a cloud server ("Sign in to confirm you're not a bot"). | Host at home, or give yt-dlp cookies of a throwaway account (`cookiefile` in `YTDL_OPTIONS`). |
| **Playlists made by Spotify itself can't be read** | "Today's Top Hits" and similar links fail. | A Spotify API restriction; nothing to do in code. |
| **ShessGPT is weak** (about 600 Elo, 2-ply search) | Intended: it is meant to be beatable. | A deeper search (alpha-beta, 3–4 ply) would make it stronger. Keep the "same move as before" tests in mind. |
| **No health monitoring** | If the bot is down, nobody notices until someone uses it. | A free uptime monitor, or a small systemd timer that checks `systemctl is-active fgbot` and sends a message. |
