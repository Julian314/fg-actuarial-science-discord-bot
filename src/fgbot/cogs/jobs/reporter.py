"""The daily job report: run the scraper, collect unposted jobs, build the messages.

``JobReporter`` contains the *logic* of the report and talks to the scraper through its
public ``JobService`` API. It does not send anything itself: ``build_report`` returns the
messages and the cog sends them. Only after Discord has accepted every message does the cog
call ``mark_posted``, so a failed post is retried the next day instead of being lost.

How "already posted" works: the scraper's database has a ``notifications`` table with one row
per (job, channel). The channel key is ``discord:<channel id>``, so every Discord channel has
its own history and switching ``JOBS_CHANNEL_ID`` starts a fresh one (limited to the last
``JOBS_MAX_AGE_DAYS`` days so the new channel isn't flooded).

All ``JobService`` calls block (SQLite, HTTP), so they run in worker threads.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import logging
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

import discord
from actjobs.models import JobRecord
from actjobs.report import Digest, render_markdown
from actjobs.service import JobService, RunInProgressError, output_filter

from fgbot.cogs.jobs import formatting

log = logging.getLogger(__name__)


@dataclass
class ReportMessage:
    """One Discord message of the report (keyword arguments for ``Messageable.send``)."""

    content: str | None = None
    embeds: list[discord.Embed] = field(default_factory=list)
    file: tuple[str, bytes] | None = None  # (filename, data)

    def send_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"embeds": self.embeds}
        if self.content:
            kwargs["content"] = self.content
        if self.file:
            name, data = self.file
            kwargs["file"] = discord.File(io.BytesIO(data), filename=name)
        return kwargs


@dataclass
class Report:
    """Everything the cog needs to post a report and record it afterwards."""

    messages: list[ReportMessage]
    job_ids: list[int]


class JobReporter:
    """Builds the daily report for one channel.

    Args:
        service: The scraper's API object.
        channel_id: Discord channel that receives the report.
        max_age_days: Ignore jobs first seen longer ago than this.
        timezone: Used for dates in the report.
        post_when_empty: Post a short "no new postings" report instead of staying silent.
        attach_report: Attach the scraper's full Markdown report as a file.
    """

    def __init__(
        self,
        service: JobService,
        *,
        channel_id: int,
        max_age_days: int,
        timezone: str,
        post_when_empty: bool = True,
        attach_report: bool = True,
    ) -> None:
        self.service = service
        self.channel_key = f"discord:{channel_id}"
        self.max_age_days = max_age_days
        self.timezone = timezone
        self.post_when_empty = post_when_empty
        self.attach_report = attach_report

    # --------------------------------------------------------------------- scraping
    async def scrape(self) -> tuple[Digest | None, list[str]]:
        """Run the scraper (takes a few minutes).

        Returns:
            The digest of the run (None if no run happened) and notes for the report, e.g.
            source-health warnings or why the scrape did not run.
        """
        try:
            _result, digest = await asyncio.to_thread(
                self.service.run_scrape,
                trigger="discord",
                notifiers=self._scraper_notifiers(),
            )
        except RunInProgressError:
            log.warning("A scrape is already running elsewhere; reporting from the database")
            return None, ["Another scrape was already running; showing what's in the database."]
        except Exception:
            log.exception("The job scrape failed")
            return None, ["Today's scrape failed (see the bot's log); showing earlier results."]
        return digest, list(digest.warnings)

    def _scraper_notifiers(self) -> list:
        """The scraper's own notifiers, minus the console table (it would clutter our log).

        The Markdown notifier keeps writing ``reports/YYYY-MM-DD.md`` in the scraper project.
        """
        return [n for n in self.service.default_notifiers() if n.channel != "console"]

    # ---------------------------------------------------------------------- queries
    async def unposted_jobs(self) -> list[JobRecord]:
        """Jobs matching the scraper's ``[output]`` filter that this channel hasn't seen yet."""
        since = dt.datetime.now(dt.UTC) - dt.timedelta(days=self.max_age_days)
        job_filter = output_filter(
            self.service.cfg.settings.output,
            first_seen_after=since.isoformat(timespec="seconds"),
        )
        return await asyncio.to_thread(self.service.unnotified, self.channel_key, job_filter)

    async def mark_posted(self, job_ids: list[int]) -> None:
        """Record that these jobs were posted, so they are never posted again."""
        if job_ids:
            await asyncio.to_thread(self.service.mark_notified, job_ids, self.channel_key)

    # ---------------------------------------------------------------------- report
    async def build_report(self, digest: Digest | None, notes: list[str]) -> Report:
        """The messages to post. ``messages`` is empty if there is nothing worth posting."""
        jobs = await self.unposted_jobs()
        if not jobs and not notes and not self.post_when_empty:
            return Report(messages=[], job_ids=[])

        stats = digest.stats if digest else await asyncio.to_thread(self.service.stats)
        summary = formatting.summary_embed(
            new_count=len(jobs),
            open_count=stats.get("active_relevant", 0),
            generated_at=dt.datetime.now(dt.UTC),
            timezone=self.timezone,
            notes=notes,
            run=digest.run if digest else None,
        )

        batches = formatting.batch_embeds([summary, *formatting.category_embeds(jobs)])
        messages = [ReportMessage(embeds=batch) for batch in batches]
        if digest is not None and self.attach_report and digest.jobs:
            markdown = render_markdown(digest, self.timezone)
            day = dt.datetime.now(ZoneInfo(self.timezone))
            messages[-1].file = (f"jobs-{day:%Y-%m-%d}.md", markdown.encode("utf-8"))
        return Report(messages=messages, job_ids=[job.id for job in jobs])
