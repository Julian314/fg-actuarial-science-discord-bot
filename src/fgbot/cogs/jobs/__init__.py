"""Extension entry point for the daily job report (``/jobs …``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fgbot.cogs.jobs.cog import JobsCog

if TYPE_CHECKING:
    from fgbot.bot import FGBot


async def setup(bot: FGBot) -> None:
    await bot.add_cog(JobsCog(bot))
