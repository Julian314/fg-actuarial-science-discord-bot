"""Turn job postings into Discord embeds, respecting Discord's size limits.

Everything here is a pure function (job records in, ``discord.Embed`` objects out), so it is
tested without a Discord connection in ``tests/test_jobs.py``.

Discord limits that matter here (https://discord.com/developers/docs/resources/message):
an embed description holds 4096 characters, a message holds at most 10 embeds, and all
embeds of one message together hold at most 6000 characters.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any
from zoneinfo import ZoneInfo

import discord
from actjobs.models import JobRecord
from actjobs.report import CATEGORY_LABELS, SENIORITY_LABELS, place, workload

from fgbot.utils import embeds

DESCRIPTION_LIMIT = 4096
EMBEDS_PER_MESSAGE = 10
CHARS_PER_MESSAGE = 6000
JOB_COLOUR = discord.Colour.teal()


def job_line(job: JobRecord) -> str:
    """One bullet line of the report, for example::

    • **[Actuarial Analyst](url)** — Swiss Re · Zürich (ZH) · 100% · Junior · DE/EN
    """
    details = [place(job)]
    if workload(job):
        details.append(workload(job))
    if job.seniority != "unspecified":
        details.append(SENIORITY_LABELS.get(job.seniority, job.seniority))
    if job.languages_required:
        details.append("/".join(language.upper() for language in job.languages_required))
    title = job.title.replace("[", "(").replace("]", ")")  # brackets would break the link
    linked = f"[{title}]({job.url})" if job.url else title
    return f"• **{linked}** — {job.company or '?'} · {' · '.join(details)}"


def group_by_category(jobs: Iterable[JobRecord]) -> dict[str, list[JobRecord]]:
    """Jobs grouped by category in the scraper's display order; empty groups are left out."""
    jobs = list(jobs)
    groups = {key: [job for job in jobs if job.category == key] for key in CATEGORY_LABELS}
    # Categories the scraper might add in the future still get shown, at the end.
    for job in jobs:
        if job.category not in CATEGORY_LABELS:
            groups.setdefault(job.category, []).append(job)
    return {key: group for key, group in groups.items() if group}


def category_embeds(jobs: Iterable[JobRecord]) -> list[discord.Embed]:
    """One embed per category, split into several embeds if a category is very long."""
    result: list[discord.Embed] = []
    for category, group in group_by_category(jobs).items():
        label = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
        chunks = _chunk_lines([job_line(job) for job in group], DESCRIPTION_LIMIT)
        for index, chunk in enumerate(chunks):
            title = f"{label} ({len(group)})" if index == 0 else f"{label} (continued)"
            result.append(discord.Embed(title=title, description=chunk, colour=JOB_COLOUR))
    return result


def _chunk_lines(lines: list[str], limit: int) -> list[str]:
    """Join lines with newlines into as few chunks as possible, each at most ``limit`` long."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        line = embeds.truncate(line, limit)
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            candidate = line
        current = candidate
    if current:
        chunks.append(current)
    return chunks


def batch_embeds(items: list[discord.Embed]) -> list[list[discord.Embed]]:
    """Split embeds into groups that each fit into one Discord message."""
    batches: list[list[discord.Embed]] = []
    current: list[discord.Embed] = []
    size = 0
    for embed in items:
        embed_size = len(embed)  # discord.py counts all text in the embed
        if current and (
            len(current) == EMBEDS_PER_MESSAGE or size + embed_size > CHARS_PER_MESSAGE
        ):
            batches.append(current)
            current, size = [], 0
        current.append(embed)
        size += embed_size
    if current:
        batches.append(current)
    return batches


def summary_embed(
    *,
    new_count: int,
    open_count: int,
    generated_at: dt.datetime,
    timezone: str,
    notes: list[str],
    run: Any | None = None,
) -> discord.Embed:
    """The headline of the daily report.

    Args:
        new_count: Number of jobs posted in this report.
        open_count: Relevant jobs currently open (from the scraper's statistics).
        generated_at: When the report was made (any time zone).
        timezone: Time zone for the date in the title.
        notes: Warnings such as unhealthy sources or a failed scrape.
        run: The scraper's ``RunResult`` (for the footer), if a scrape ran.
    """
    local = generated_at.astimezone(ZoneInfo(timezone))
    if new_count:
        description = f"**{new_count} new posting{'s' if new_count != 1 else ''}** for you"
    else:
        description = "No new postings today."
    description += f" · {open_count} relevant jobs currently open"
    embed = discord.Embed(
        title=f"📊 Actuarial & risk jobs in Switzerland — {local:%A %d.%m.%Y}",
        description=description,
        colour=JOB_COLOUR,
    )
    if notes:
        embed.add_field(
            name="⚠️ Notes",
            value=embeds.truncate("\n".join(f"• {note}" for note in notes), 1024),
            inline=False,
        )
    if run is not None:
        requests = sum(source.requests for source in run.sources)
        embed.set_footer(
            text=f"Scrape #{run.run_id} · {run.status} · {len(run.sources)} sources · "
            f"{requests} requests · {run.closed} postings closed"
        )
    return embed


def job_list_embed(title: str, jobs: list[JobRecord], *, empty_text: str) -> discord.Embed:
    """A single embed listing jobs (used by ``/jobs list`` and ``/jobs search``)."""
    lines = [job_line(job) for job in jobs]
    description = _chunk_lines(lines, DESCRIPTION_LIMIT)[0] if lines else empty_text
    shown = description.count("\n") + 1 if lines else 0
    embed = discord.Embed(title=title, description=description, colour=JOB_COLOUR)
    if lines and shown < len(lines):
        embed.set_footer(text=f"Showing {shown} of {len(lines)}. Narrow the filters to see more.")
    return embed


def status_embed(
    last_run: dict[str, Any] | None, next_run: dt.datetime | None, timezone: str
) -> discord.Embed:
    """``/jobs status``: the last scrape, its sources and the next scheduled run."""
    tz = ZoneInfo(timezone)
    embed = discord.Embed(title="Job scraper status", colour=JOB_COLOUR)
    if next_run is not None:
        embed.add_field(name="Next run", value=f"{next_run.astimezone(tz):%a %d.%m. %H:%M}")
    if last_run is None:
        embed.description = "The scraper has never run."
        return embed

    started = dt.datetime.fromisoformat(last_run["started_at"]).astimezone(tz)
    embed.description = (
        f"Last scrape **#{last_run['id']}** on {started:%a %d.%m.%Y %H:%M}: "
        f"**{last_run['status']}** (triggered by {last_run['trigger']})"
    )
    lines = []
    for source in last_run.get("sources", []):
        icon = "✅" if source["status"] == "ok" else "⚠️"
        line = f"{icon} `{source['source']}` – {source['fetched']} fetched, {source['new']} new"
        if source.get("error"):
            line += f" ({embeds.truncate(source['error'], 80)})"
        lines.append(line)
    if lines:
        embed.add_field(name="Sources", value=embeds.truncate("\n".join(lines), 1024), inline=False)
    return embed
