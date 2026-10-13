"""Extension entry point for the general commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fgbot.cogs.general.cog import GeneralCog

if TYPE_CHECKING:
    from fgbot.bot import FGBot


async def setup(bot: FGBot) -> None:
    await bot.add_cog(GeneralCog(bot))
