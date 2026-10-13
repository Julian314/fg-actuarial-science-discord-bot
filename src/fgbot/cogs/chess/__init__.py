"""Extension entry point for the chess feature (``/chess …``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fgbot.cogs.chess.cog import ChessCog

if TYPE_CHECKING:
    from fgbot.bot import FGBot


async def setup(bot: FGBot) -> None:
    await bot.add_cog(ChessCog(bot))
