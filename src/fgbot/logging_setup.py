"""Logging: readable console output plus a daily-rotated log file.

Call ``setup_logging`` once, at startup, before anything else logs.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """Send log records to stderr and to ``log_dir/fgbot.log`` (rotated at midnight, 14 kept).

    Under systemd, stderr ends up in the journal (``journalctl -u fgbot``); the file is handy
    when running the bot by hand.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logfile = logging.handlers.TimedRotatingFileHandler(
        log_dir / "fgbot.log", when="midnight", backupCount=14, encoding="utf-8"
    )
    logfile.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers[:] = [console, logfile]

    # Third-party libraries that are very chatty at INFO level.
    for noisy in ("discord.gateway", "discord.voice_state", "httpx", "httpcore", "spotipy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
