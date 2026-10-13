"""Smoke test: every extension loads into a real (unconnected) bot and registers its commands."""

from __future__ import annotations

import pytest

from fgbot.bot import FGBot
from fgbot.cogs.chess.engines import StockfishEngine
from fgbot.config import Settings

SCRAPER_CONFIG = Settings.model_fields["actjobs_config"].default


async def test_all_extensions_load_and_register_commands(tmp_path) -> None:
    from fgbot.config import PROJECT_ROOT

    scraper_config = (PROJECT_ROOT / SCRAPER_CONFIG).resolve()
    if not scraper_config.is_file():
        pytest.skip("swiss-actuarial-job-scraper is not checked out next to this repository")

    settings = Settings(
        _env_file=None,
        discord_token="test-token",
        jobs_enabled=True,
        jobs_channel_id=1,
        actjobs_config=scraper_config,
        stockfish_path="/nonexistent/stockfish",  # the bot must cope without Stockfish
        log_dir=tmp_path,
    )
    bot = FGBot(settings)
    async with bot:  # prepares the bot's internals without logging in
        for extension in bot.enabled_extensions():
            await bot.load_extension(extension)

        names = {command.qualified_name for command in bot.tree.walk_commands()}
        expected = {
            "help", "ping", "about",
            "play", "skip", "queue", "loop", "volume", "summon", "leave",
            "chess start", "chess move", "chess undo", "chess override", "chess hint",
            "chess eval", "chess resign", "chess fen", "chess board",
            "jobs list", "jobs search", "jobs status", "jobs run-now",
        }  # fmt: skip
        assert expected <= names

        for extension in list(bot.extensions):
            await bot.unload_extension(extension)


async def test_stockfish_missing_is_not_fatal() -> None:
    engine = StockfishEngine("/nonexistent/stockfish", think_time=0.1)
    await engine.start()
    assert not engine.available
    await engine.close()
