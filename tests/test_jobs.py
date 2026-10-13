"""Daily job report: embed formatting and the reporter logic (with a fake scraper service)."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import discord
import pytest
from actjobs.config import OutputSettings
from actjobs.models import JobRecord
from actjobs.report import Digest
from actjobs.service import RunInProgressError

from fgbot.cogs.jobs import formatting
from fgbot.cogs.jobs.reporter import JobReporter


def make_job(job_id: int, category: str = "actuarial", **overrides) -> JobRecord:
    fields = dict(
        id=job_id,
        title=f"Actuarial Analyst {job_id}",
        company="Swiss Re",
        sector="reinsurance",
        city="Zürich",
        canton="ZH",
        url=f"https://example.com/jobs/{job_id}",
        category=category,
        seniority="junior",
        relevance_score=1.0,
        is_relevant=True,
        workload_min=80,
        workload_max=100,
        employment_type=None,
        languages_required=["de", "en"],
        posted_at=None,
        first_seen_at="2026-10-12T05:00:00+00:00",
        last_seen_at="2026-10-12T05:00:00+00:00",
        status="active",
        sources=["jobs.ch"],
    )
    fields.update(overrides)
    return JobRecord(**fields)


# ----------------------------------------------------------------------- formatting
def test_job_line() -> None:
    line = formatting.job_line(make_job(1))
    assert line == (
        "• **[Actuarial Analyst 1](https://example.com/jobs/1)** — Swiss Re · "
        "Zürich (ZH) · 80–100% · Junior · DE/EN"
    )


def test_job_line_without_url_and_with_brackets() -> None:
    job = make_job(1, url=None, title="Aktuar [m/w/d]", seniority="unspecified", workload_min=None)
    assert formatting.job_line(job) == "• **Aktuar (m/w/d)** — Swiss Re · Zürich (ZH) · DE/EN"


def test_category_embeds_follow_scraper_order() -> None:
    jobs = [make_job(1, "risk_management"), make_job(2, "actuarial"), make_job(3, "actuarial")]
    titles = [embed.title for embed in formatting.category_embeds(jobs)]
    assert titles == ["Actuarial (2)", "Risk management (1)"]


def test_long_category_is_split_within_limits() -> None:
    jobs = [make_job(i, title="Senior Pricing Actuary " * 6) for i in range(200)]
    result = formatting.category_embeds(jobs)
    assert len(result) > 1
    assert result[1].title == "Actuarial (continued)"
    assert all(len(e.description) <= formatting.DESCRIPTION_LIMIT for e in result)
    # Every job appears exactly once.
    assert sum(e.description.count("• ") for e in result) == 200


def test_batches_respect_message_limits() -> None:
    many = [discord.Embed(title="x", description="y" * 1000) for _ in range(23)]
    batches = formatting.batch_embeds(many)
    assert sum(len(b) for b in batches) == 23
    for batch in batches:
        assert len(batch) <= formatting.EMBEDS_PER_MESSAGE
        assert sum(len(e) for e in batch) <= formatting.CHARS_PER_MESSAGE


def test_summary_embed() -> None:
    run = SimpleNamespace(
        run_id=7, status="ok", closed=2, sources=[SimpleNamespace(requests=3)] * 2
    )
    embed = formatting.summary_embed(
        new_count=1,
        open_count=82,
        generated_at=dt.datetime(2026, 10, 13, 5, 0, tzinfo=dt.UTC),
        timezone="Europe/Zurich",
        notes=["jobup.ch returned 0 postings"],
        run=run,
    )
    assert embed.title.endswith("Tuesday 13.10.2026")
    assert embed.description.startswith("**1 new posting** for you · 82")
    assert "jobup.ch" in embed.fields[0].value
    assert embed.footer.text.startswith("Scrape #7 · ok · 2 sources · 6 requests")


def test_status_embed_without_runs() -> None:
    embed = formatting.status_embed(None, None, "Europe/Zurich")
    assert embed.description == "The scraper has never run."


# ------------------------------------------------------------------------- reporter
class FakeService:
    """Implements the part of ``actjobs.service.JobService`` that the reporter uses."""

    def __init__(self, jobs: list[JobRecord], *, scrape_error: Exception | None = None) -> None:
        self.cfg = SimpleNamespace(settings=SimpleNamespace(output=OutputSettings()))
        self.jobs = jobs
        self.posted: dict[str, set[int]] = {}
        self.scrape_error = scrape_error
        self.last_filter = None

    def run_scrape(self, *, trigger, notifiers):
        if self.scrape_error:
            raise self.scrape_error
        run = SimpleNamespace(run_id=1, status="ok", closed=0, sources=[])
        digest = Digest(
            generated_at=dt.datetime.now(dt.UTC),
            run=run,
            jobs=self.jobs,
            hidden_new=0,
            stats={"active_relevant": 42},
            warnings=["a source is unhealthy"],
        )
        return run, digest

    def default_notifiers(self):
        return [SimpleNamespace(channel="console"), SimpleNamespace(channel="markdown")]

    def unnotified(self, channel, job_filter):
        self.last_filter = job_filter
        done = self.posted.get(channel, set())
        return [job for job in self.jobs if job.id not in done]

    def mark_notified(self, ids, channel):
        self.posted.setdefault(channel, set()).update(ids)

    def stats(self):
        return {"active_relevant": 42}


def make_reporter(service, **kwargs) -> JobReporter:
    return JobReporter(service, channel_id=99, max_age_days=7, timezone="Europe/Zurich", **kwargs)


async def test_report_lists_jobs_attaches_markdown_and_dedupes() -> None:
    service = FakeService([make_job(1), make_job(2, "underwriting")])
    reporter = make_reporter(service)

    digest, notes = await reporter.scrape()
    assert notes == ["a source is unhealthy"]
    report = await reporter.build_report(digest, notes)
    assert sorted(report.job_ids) == [1, 2]
    embeds = [e for m in report.messages for e in m.embeds]
    assert [e.title for e in embeds][1:] == ["Actuarial (1)", "Underwriting (1)"]
    assert report.messages[-1].file[0].startswith("jobs-")
    # Only jobs first seen within the last 7 days are considered.
    assert report.messages and service.last_filter.first_seen_after is not None

    await reporter.mark_posted(report.job_ids)
    again = await reporter.build_report(None, [])
    assert again.job_ids == []
    assert "No new postings today." in again.messages[0].embeds[0].description


async def test_scrape_uses_channel_specific_key_and_skips_console_notifier() -> None:
    reporter = make_reporter(FakeService([]))
    assert reporter.channel_key == "discord:99"
    assert [n.channel for n in reporter._scraper_notifiers()] == ["markdown"]


async def test_quiet_when_nothing_new_and_post_when_empty_is_off() -> None:
    reporter = make_reporter(FakeService([]), post_when_empty=False)
    report = await reporter.build_report(None, [])
    assert report.messages == []


@pytest.mark.parametrize(
    ("error", "note"),
    [(RunInProgressError("locked"), "already running"), (RuntimeError("boom"), "failed")],
)
async def test_scrape_problems_become_notes(error, note) -> None:
    reporter = make_reporter(FakeService([make_job(1)], scrape_error=error))
    digest, notes = await reporter.scrape()
    assert digest is None
    assert note in notes[0]
    report = await reporter.build_report(digest, notes)
    assert report.job_ids == [1]  # jobs from earlier scrapes are still posted
    assert report.messages[-1].file is None  # no digest -> no Markdown attachment
