# Deployment

The bot is a single long-running process (`fgbot`). Both setups below use **systemd**, which
starts the bot at boot, restarts it after a crash, and collects its logs.

> **Run only one instance per bot token.** If the bot runs on your laptop *and* on the server,
> both answer every command and both post the job report. Stop the old one when you move.

## Requirements (both setups)

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

## Updating

```bash
cd <bot repository>
git pull
(cd ../swiss-actuarial-job-scraper && git pull)
uv sync --frozen
systemctl --user restart fgbot          # server: sudo systemctl restart fgbot
```

If `/play` starts failing, update yt-dlp (see [music.md](music.md#keeping-yt-dlp-up-to-date-important)):

```bash
uv lock --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs && uv sync
```

Commit the updated `uv.lock` so the server gets the same versions.

## Backups

The only state worth backing up is the scraper's SQLite database. It holds all job history and
the "already posted" records. Chess games and music queues live in memory only.

```bash
# consistent copy even while the bot runs (SQLite online backup)
sqlite3 /opt/fgbot/swiss-actuarial-job-scraper/data/jobs.db ".backup '/var/backups/jobs-$(date +%F).db'"
```

Put this in a daily cron job or systemd timer if you like. `.env` should also be kept somewhere
safe, such as a password manager, rather than in git.
