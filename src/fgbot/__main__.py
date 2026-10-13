"""Entry point: ``uv run fgbot`` or ``python -m fgbot``.

Loads and validates the configuration, sets up logging and starts the bot.
"""

from __future__ import annotations

import logging
import sys

import discord
from pydantic import ValidationError

from fgbot.bot import FGBot
from fgbot.config import Settings
from fgbot.logging_setup import setup_logging


def main() -> None:
    try:
        settings = Settings()
    except ValidationError as error:
        # Print the configuration problems without a long traceback.
        print(f"Invalid configuration (check your .env file):\n{error}", file=sys.stderr)
        sys.exit(2)

    setup_logging(settings.log_dir, settings.log_level)
    bot = FGBot(settings)
    try:
        # log_handler=None: keep the logging we just configured instead of discord.py's.
        bot.run(settings.discord_token.get_secret_value(), log_handler=None)
    except discord.LoginFailure:
        logging.getLogger("fgbot").error(
            "Discord rejected the bot token. Check DISCORD_TOKEN in your .env file "
            "(Developer Portal -> your app -> Bot -> Reset Token)."
        )
        sys.exit(2)  # a configuration problem: the systemd unit won't restart on exit code 2


if __name__ == "__main__":
    main()
