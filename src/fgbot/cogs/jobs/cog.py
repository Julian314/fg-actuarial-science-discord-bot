"""Daily actuarial job report and ``/jobs …`` commands.

Every day at ``JOBS_TIME`` (default 07:00 Europe/Zurich) the bot runs the job scraper, then
posts all new matching postings to ``JOBS_CHANNEL_ID``. If the bot was offline at that time
(e.g. the computer was off), the report is made as soon as the bot starts again.

The logic lives in ``reporter.py`` and ``formatting.py``; this module only wires it to Discord.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import discord
from actjobs.report import CATEGORY_LABELS, SENIORITY_LABELS
from actjobs.service import JobService, output_filter
from discord import app_commands
from discord.ext import commands, tasks

from fgbot.cogs.jobs import formatting
from fgbot.cogs.jobs.reporter import JobReporter
from fgbot.errors import UserFacingError
from fgbot.utils import embeds

if TYPE_CHECKING:
    from fgbot.bot import FGBot

log = logging.getLogger(__name__)

CATEGORY_CHOICES = [
    app_commands.Choice(name=label, value=key) for key, label in CATEGORY_LABELS.items()
]
SENIORITY_CHOICES = [
    app_commands.Choice(name=label if key != "unspecified" else "Unspecified", value=key)
    for key, label in SENIORITY_LABELS.items()
]


class JobsCog(commands.GroupCog, group_name="jobs", group_description="Actuarial job postings"):
    """Daily report of junior actuarial jobs in Switzerland."""

    def __init__(self, bot: FGBot) -> None:
        self.bot = bot
        settings = bot.settings
        assert settings.jobs_channel_id is not None  # guaranteed by Settings validation
        self.channel_id = settings.jobs_channel_id
        self.service: JobService | None = None
        self.reporter: JobReporter | None = None
        self._report_lock = asyncio.Lock()  # never run two reports at once
        self._background: set[asyncio.Task] = set()  # keeps /jobs run-now tasks alive

        # The schedule comes from the config, so the loop is created here, not as a decorator.
        self.daily_report = tasks.loop(time=settings.jobs_schedule_time)(self._scheduled_report)
        self.daily_report.before_loop(self._before_daily_report)

    async def cog_load(self) -> None:
        settings = self.bot.settings
        # Loading the scraper config reads a few files: do it off the event loop.
        self.service = await asyncio.to_thread(JobService, settings.actjobs_config)
        self.reporter = JobReporter(
            self.service,
            channel_id=self.channel_id,
            max_age_days=settings.jobs_max_age_days,
            timezone=settings.jobs_timezone,
            post_when_empty=settings.jobs_post_when_empty,
            attach_report=settings.jobs_attach_report,
        )
        self.daily_report.start()
        log.info("Daily job report scheduled at %s %s", settings.jobs_time, settings.jobs_timezone)

    async def cog_unload(self) -> None:
        self.daily_report.cancel()
        for task in self._background:
            task.cancel()

    # ---------------------------------------------------------------- daily report
    async def _before_daily_report(self) -> None:
        """Wait for the connection, then catch up if the last successful scrape is too old."""
        await self.bot.wait_until_ready()
        assert self.service is not None
        if await asyncio.to_thread(self.service.needs_catch_up):
            log.info("No successful scrape in the last 20 hours: running the report now")
            # An exception here would stop the daily loop for good, so it is only logged.
            await self._scheduled_report()

    async def _scheduled_report(self) -> None:
        try:
            await self.run_report(scrape=True)
        except Exception:  # never let an error stop the daily loop
            log.exception("Daily job report failed")

    async def run_report(self, *, scrape: bool) -> int:
        """Scrape (optionally), then post unposted jobs to the report channel.

        Returns:
            How many jobs were posted.
        """
        assert self.reporter is not None
        async with self._report_lock:
            channel = await self._report_channel()
            digest, notes = await self.reporter.scrape() if scrape else (None, [])
            report = await self.reporter.build_report(digest, notes)
            for message in report.messages:
                await channel.send(**message.send_kwargs())
            await self.reporter.mark_posted(report.job_ids)
            log.info(
                "Job report posted: %d jobs in %d messages",
                len(report.job_ids),
                len(report.messages),
            )
            return len(report.job_ids)

    async def _report_channel(self) -> discord.abc.Messageable:
        channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(
            self.channel_id
        )
        if not isinstance(channel, discord.abc.Messageable):
            raise RuntimeError(f"JOBS_CHANNEL_ID {self.channel_id} is not a text channel")
        return channel

    # -------------------------------------------------------------------- commands
    @app_commands.command(name="list", description="Show open junior actuarial jobs.")
    @app_commands.describe(
        category="Only this field",
        canton="Two-letter canton code, e.g. ZH",
        seniority="Only this level (default: entry-level and unspecified)",
        limit="How many jobs to show (max 25)",
    )
    @app_commands.choices(category=CATEGORY_CHOICES, seniority=SENIORITY_CHOICES)
    async def list_jobs(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str] | None = None,
        canton: app_commands.Range[str, 2, 2] | None = None,
        seniority: app_commands.Choice[str] | None = None,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        assert self.service is not None
        overrides: dict = {"limit": limit}
        if category:
            overrides["categories"] = [category.value]
        if canton:
            overrides["cantons"] = [canton.upper()]
        if seniority:
            overrides["seniorities"] = [seniority.value]
        job_filter = output_filter(self.service.cfg.settings.output, **overrides)
        jobs = await asyncio.to_thread(self.service.query_jobs, job_filter)
        await interaction.response.send_message(
            embed=formatting.job_list_embed(
                "Open jobs", jobs, empty_text="No open jobs match these filters."
            ),
            ephemeral=True,
        )

    @app_commands.command(name="search", description="Search open jobs by title or company.")
    @app_commands.describe(text="Part of the job title or company name")
    async def search(
        self, interaction: discord.Interaction, text: app_commands.Range[str, 2, 100]
    ) -> None:
        assert self.service is not None
        job_filter = output_filter(self.service.cfg.settings.output, search=text, limit=25)
        jobs = await asyncio.to_thread(self.service.query_jobs, job_filter)
        await interaction.response.send_message(
            embed=formatting.job_list_embed(
                f"Jobs matching “{text}”", jobs, empty_text="No open jobs found."
            ),
            ephemeral=True,
        )

    @app_commands.command(name="status", description="When did the scraper last run?")
    async def status(self, interaction: discord.Interaction) -> None:
        assert self.service is not None
        last_run = await asyncio.to_thread(self.service.last_run)
        embed = formatting.status_embed(
            last_run, self.daily_report.next_iteration, self.bot.settings.jobs_timezone
        )
        if self._report_lock.locked():
            embed.add_field(name="Right now", value="⏳ A report is being made.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="run-now", description="Run the scraper and post the report now.")
    @app_commands.describe(scrape="Scrape first (takes a few minutes). False: only post.")
    @app_commands.default_permissions(manage_guild=True)
    async def run_now(self, interaction: discord.Interaction, scrape: bool = True) -> None:
        if self._report_lock.locked():
            raise UserFacingError("A report is already being made. Check `/jobs status`.")
        # A scrape takes minutes, so answer right away and work in the background.
        task = asyncio.create_task(self._run_now_in_background(interaction, scrape))
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        what = "Scraping and posting" if scrape else "Posting"
        await interaction.response.send_message(
            embed=embeds.info(
                f"{what} the report in <#{self.channel_id}>. This can take a few minutes."
            ),
            ephemeral=True,
        )

    async def _run_now_in_background(self, interaction: discord.Interaction, scrape: bool) -> None:
        try:
            posted = await self.run_report(scrape=scrape)
            message = embeds.success(f"Done: {posted} new job(s) posted in <#{self.channel_id}>.")
        except Exception:
            log.exception("Manual job report failed")
            message = embeds.error("The report failed. The error has been logged.")
        # Interaction tokens expire after 15 minutes; the report itself is posted anyway.
        with contextlib.suppress(discord.HTTPException):
            await interaction.followup.send(embed=message, ephemeral=True)
