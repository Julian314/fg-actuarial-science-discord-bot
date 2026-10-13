# Deployment

The bot is a single long-running process (`fgbot`). Options A and B use **systemd**, which
starts the bot at boot, restarts it after a crash, and collects its logs. Option C runs it as a
Docker container on a TrueNAS NAS.

> **Run only one instance per bot token.** If the bot runs on your laptop *and* on the server,
> both answer every command and both post the job report. Stop the old one when you move.

## Requirements (options A and B)

| What | Why |
|---|---|
| [uv](https://docs.astral.sh/uv/) | Installs Python 3.13 and all dependencies into `.venv/` |
| `git` | Getting and updating the code |
| `ffmpeg` | Music playback |
| `deno` | yt-dlp needs it for YouTube |
| `stockfish` (optional) | `/chess eval` and `/chess hint` |
| cairo library | Drawing the chess board (pre-installed on most desktops) |
| both repositories, **side by side** | The bot imports the job scraper from `../swiss-actuarial-job-scraper` |
| ~1.5 GB disk, ~300 MB RAM | PyTorch is the big one; without chess about 90 MB RAM |

## Option A: this machine (systemd user service)

The bot runs as your own user from `~/Projects/fg-actuarial-science-discord-bot`.

```bash
# 1. System packages (Arch / Omarchy)
sudo pacman -S --needed ffmpeg deno stockfish cairo

# 2. Dependencies and configuration
cd ~/Projects/fg-actuarial-science-discord-bot
uv sync --frozen
cp .env.example .env && $EDITOR .env      # token, JOBS_CHANNEL_ID, GUILD_ID …
uv run fgbot                               # try it once in the foreground, Ctrl+C to stop

# 3. Install the service
mkdir -p ~/.config/systemd/user
cp deploy/systemd/fgbot.user.service ~/.config/systemd/user/fgbot.service
systemctl --user daemon-reload
systemctl --user enable --now fgbot

# 4. Keep it running while you are logged out (and start it at boot)
loginctl enable-linger "$USER"
```

Everyday commands:

```bash
systemctl --user status fgbot          # is it running?
journalctl --user -u fgbot -f          # live log (Ctrl+C to quit)
systemctl --user restart fgbot         # after changing .env or updating
systemctl --user stop fgbot
```

If your repository is not in `~/Projects`, edit `WorkingDirectory` and `ExecStart` in
`~/.config/systemd/user/fgbot.service`.

**Sleep/suspend:** a laptop that sleeps at 07:00 misses the scheduled report. The bot catches up
automatically after waking: when no successful scrape happened in the last 20 hours, it makes the
report as soon as it reconnects.

## Option B: a server (systemd system service, Debian/Ubuntu)

The bot runs as a dedicated, unprivileged `fgbot` user, with both repositories in `/opt/fgbot`.

### 1. Packages and tools

```bash
sudo apt update
sudo apt install -y git ffmpeg stockfish libcairo2 curl unzip

# uv for all users
curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh

# deno for all users (yt-dlp needs it for YouTube)
curl -fsSL https://deno.land/install.sh | sudo DENO_INSTALL=/usr/local sh
deno --version     # must work; the binary must be in /usr/local/bin
```

### 2. User and code

```bash
sudo useradd --system --create-home --home-dir /opt/fgbot --shell /usr/sbin/nologin fgbot
sudo -u fgbot git clone https://github.com/Julian314/fg-actuarial-science-discord-bot.git /opt/fgbot/fg-actuarial-science-discord-bot
sudo -u fgbot git clone https://github.com/Julian314/swiss-actuarial-job-scraper.git /opt/fgbot/swiss-actuarial-job-scraper

cd /opt/fgbot/fg-actuarial-science-discord-bot
sudo -u fgbot uv sync --frozen        # downloads Python 3.13 and all dependencies
```

(Adjust the clone URLs to wherever the repositories are hosted. Private repositories need a
deploy key or token.)

### 3. Configuration and data

```bash
sudo -u fgbot cp .env.example .env
sudo -u fgbot nano .env
sudo chmod 600 .env                   # only the fgbot user can read the token
```

To keep the job history, including which jobs were already posted, copy the database from
your machine **while no scrape is running**, and stop the local bot first:

```bash
# on your machine
systemctl --user stop fgbot
scp ~/Projects/swiss-actuarial-job-scraper/data/jobs.db server:/tmp/jobs.db
# on the server
sudo -u fgbot mkdir -p /opt/fgbot/swiss-actuarial-job-scraper/data
sudo install -o fgbot -g fgbot -m 640 /tmp/jobs.db /opt/fgbot/swiss-actuarial-job-scraper/data/jobs.db
```

### 4. Service

```bash
sudo cp deploy/systemd/fgbot.system.service /etc/systemd/system/fgbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now fgbot
journalctl -u fgbot -f
```

The unit uses systemd's sandboxing: the bot can only write inside `/opt/fgbot`.

## Option C: TrueNAS (Docker Custom App)

TrueNAS Community Edition (24.10 and newer) runs apps as Docker containers. GitHub Actions
builds the bot's image on every push to `main` ([`.github/workflows/docker.yml`](../.github/workflows/docker.yml))
and publishes it as a private package to `ghcr.io/julian314/fg-actuarial-science-discord-bot`.
TrueNAS pulls it from there. Nothing needs to be installed on the NAS or on your own machine,
and SSH can stay off.

The image ([`deploy/docker/Dockerfile`](../deploy/docker/Dockerfile)) contains both
repositories, ffmpeg, deno and Stockfish. The bot runs as TrueNAS's `apps` user (uid 568). All
state lives on one dataset, which is mounted at `/state` in the container:

| On the dataset | What |
|---|---|
| `logs/` | the bot's log files |
| `actjobs/data/jobs.db` | the job database (see [Backups](#backups)) |
| `actjobs/reports/`, `actjobs/logs/` | the scraper's daily Markdown reports and log files |

Settings are environment variables in the app's YAML, with the same names as in `.env.example`.

### 1. GitHub (once)

1. **Token for the build.** The scraper repository is private, so the workflow needs a token
   to read it. On GitHub: **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**. Repository access: only
   `swiss-actuarial-job-scraper`. Permissions: **Contents: Read-only**. Then store it in the
   bot repository:
   ```bash
   gh secret set SCRAPER_REPO_TOKEN --repo Julian314/fg-actuarial-science-discord-bot
   ```
2. **Token for TrueNAS.** The registry doesn't accept fine-grained tokens. Create a
   **classic** token instead (**Tokens (classic) → Generate new token**) with only the
   **`read:packages`** scope.
3. Push to `main`, or start the workflow by hand: **Actions → Docker image → Run workflow**.
   Wait for the green check. The package then appears on your GitHub profile under **Packages**.

Write both tokens' expiry dates into the maintenance calendar ([handover.md](handover.md)).
When one expires, the build or the update fails.

### 2. TrueNAS web UI (once)

1. **Apps:** on first use, TrueNAS asks for a pool for apps (**Apps → Configuration →
   Choose Pool**).
2. **Datasets:** select your pool, then **Add Dataset**. Name: `fgbot`, Dataset Preset:
   **Apps**. Save it, then **Permissions → Edit**: set owner user and group to `apps`, tick
   *Apply recursively*, and save.
3. **Registry login:** **Apps → Configuration → Manage Container Image Registries → Add**.
   URI `https://ghcr.io`, username: your GitHub user name, password: the `read:packages` token.
4. **App:** **Apps → Discover Apps → Custom App → Install via YAML** (the ⋮ menu or the button
   next to *Custom App*, depending on the version). Name: `fgbot`. Paste
   [`deploy/truenas/fgbot.yaml`](../deploy/truenas/fgbot.yaml), replace `<POOL>`, fill in
   `DISCORD_TOKEN`, `GUILD_ID`, `JOBS_CHANNEL_ID` and so on, and save.
5. **Check:** **Apps → Installed → fgbot**. The app should show *Running*. Under
   **Workloads**, the container's logs icon shows the bot's output; look for the login and the
   command sync. Then try `/ping`, `/about` and `/jobs status` in Discord.
6. **Backups:** **Data Protection → Periodic Snapshot Tasks → Add**. Dataset `fgbot`, daily,
   keep for 4 weeks.

Stop any other running copy of the bot first (one instance per token).

### Everyday tasks

| Task | How |
|---|---|
| Read the log | Apps → Installed → fgbot → Workloads → logs icon. Older logs: `logs/` on the dataset. |
| Change a setting | Apps → Installed → fgbot → **Edit**, change the variable, **Save**. The app restarts. |
| Restart | Apps → Installed → fgbot → **Stop**, then **Start**. |
| Deploy an update | Wait for the green build on GitHub, then **Edit → Save** (or Stop/Start). `pull_policy: always` makes the app pull the newest image every time it starts. |

If the app keeps restarting, the log usually starts with `Invalid configuration`, which means
a variable in the YAML is wrong.

## Updating

```bash
cd <bot repository>
git pull
(cd ../swiss-actuarial-job-scraper && git pull)
uv sync --frozen
systemctl --user restart fgbot          # server: sudo systemctl restart fgbot
```

**TrueNAS (option C):** push to `main` and let GitHub build the image. Then
**Apps → Installed → fgbot → Edit → Save** in TrueNAS. After a change that is only in the scraper
repository, start the build by hand (**Actions → Docker image → Run workflow**).

If `/play` starts failing, update yt-dlp (see [music.md](music.md#keeping-yt-dlp-up-to-date-important)):

```bash
uv lock --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs && uv sync
```

Commit the updated `uv.lock` so the server gets the same versions. On TrueNAS, the next image
build picks them up.

## Backups

The only state worth backing up is the scraper's SQLite database. It holds all job history and
the "already posted" records. Chess games and music queues live in memory only.

```bash
# consistent copy even while the bot runs (SQLite online backup)
sqlite3 /opt/fgbot/swiss-actuarial-job-scraper/data/jobs.db ".backup '/var/backups/jobs-$(date +%F).db'"
```

Put this in a daily cron job or systemd timer if you like. On TrueNAS, the daily snapshot of
the `fgbot` dataset ([option C](#2-truenas-web-ui-once)) is the backup. To restore, roll the
dataset back under **Datasets → fgbot → Snapshots**, with the app stopped. `.env` should also be kept somewhere
safe, such as a password manager, rather than in git.
