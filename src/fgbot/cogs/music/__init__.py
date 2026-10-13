"""Extension entry point for the music feature (``/play``, ``/queue``, …)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fgbot.cogs.music.cog import MusicCog

if TYPE_CHECKING:
    from fgbot.bot import FGBot


async def setup(bot: FGBot) -> None:
    await bot.add_cog(MusicCog(bot))
