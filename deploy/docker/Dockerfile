# Container image for fgbot, used for the TrueNAS deployment (see docs/deployment.md).
#
# The bot imports the job scraper from ../swiss-actuarial-job-scraper, so the build context is
# the folder that holds BOTH repositories side by side:
#
#   cd ~/Projects      # contains fg-actuarial-science-discord-bot/ and swiss-actuarial-job-scraper/
#   docker build -f fg-actuarial-science-discord-bot/deploy/docker/Dockerfile -t fgbot .
#
# GitHub Actions builds and publishes it automatically (.github/workflows/docker.yml).
#
# All state lives in one volume mounted at /state:
#   /state/logs              the bot's log files (LOG_DIR)
#   /state/actjobs/data      the scraper's jobs.db (job history, "already posted" records)
#   /state/actjobs/reports   the scraper's daily Markdown reports
#   /state/actjobs/logs      the scraper's log files
# Configuration comes from environment variables (the same names as in .env.example).

FROM denoland/deno:bin-2.9.7 AS deno
FROM ghcr.io/astral-sh/uv:0.11.20 AS uv

FROM python:3.13-slim-trixie

# ffmpeg: music playback · stockfish: /chess eval and /chess hint · libcairo2: board images
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg stockfish libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# deno: yt-dlp needs a JavaScript runtime for YouTube
COPY --from=deno /deno /usr/local/bin/deno
COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    TZ=Europe/Zurich

WORKDIR /app/fg-actuarial-science-discord-bot

# 1. Third-party dependencies only (PyTorch & co.): this layer is reused until uv.lock changes.
COPY fg-actuarial-science-discord-bot/pyproject.toml fg-actuarial-science-discord-bot/uv.lock \
     fg-actuarial-science-discord-bot/.python-version ./
COPY swiss-actuarial-job-scraper/pyproject.toml swiss-actuarial-job-scraper/README.md \
     ../swiss-actuarial-job-scraper/
RUN uv sync --frozen --no-dev --no-install-project \
        --no-install-package swiss-actuarial-job-scraper

# 2. Both projects. They stay editable installs: fgbot resolves relative paths against its
#    repository folder (PROJECT_ROOT in src/fgbot/config.py), so the code must stay in place.
COPY swiss-actuarial-job-scraper/ ../swiss-actuarial-job-scraper/
COPY fg-actuarial-science-discord-bot/ ./
RUN uv sync --frozen --no-dev \
    && cd ../swiss-actuarial-job-scraper \
    && rm -rf data reports logs \
    && ln -s /state/actjobs/data data \
    && ln -s /state/actjobs/reports reports \
    && ln -s /state/actjobs/logs logs \
    && chmod 755 /app/fg-actuarial-science-discord-bot/deploy/docker/entrypoint.sh

# Debian installs stockfish to /usr/games. HOME and DENO_DIR point to writable places because
# the container runs as an unprivileged user (TrueNAS: apps, uid 568) without a home folder.
ENV PATH="/app/fg-actuarial-science-discord-bot/.venv/bin:/usr/games:$PATH" \
    LOG_DIR=/state/logs \
    HOME=/tmp \
    DENO_DIR=/tmp/deno

LABEL org.opencontainers.image.source="https://github.com/Julian314/fg-actuarial-science-discord-bot" \
      org.opencontainers.image.description="FG Actuarial Science Discord bot" \
      org.opencontainers.image.licenses="MIT"

VOLUME ["/state"]
ENTRYPOINT ["/app/fg-actuarial-science-discord-bot/deploy/docker/entrypoint.sh"]
