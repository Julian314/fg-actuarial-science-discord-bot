# Daily job reports

Every morning the bot posts the new junior actuarial job postings in Switzerland to a Discord
channel. The data comes from the sibling project
[`swiss-actuarial-job-scraper`](../../swiss-actuarial-job-scraper), which the bot uses as a
Python library (package name `actjobs`).

## What a report looks like

```
📊 Actuarial & risk jobs in Switzerland — Tuesday 13.10.2026
5 new postings for you · 82 relevant jobs currently open
⚠️ Notes
• jobup.ch returned 70% fewer postings than usual
Scrape #12 · ok · 8 sources · 41 requests · 1 postings closed

Actuarial (2)
• Actuarial Analyst — Swiss Re · Zürich (ZH) · 100% · Junior · DE/EN
• Graduate Programme Actuarial — AXA · Winterthur (ZH) · Trainee / Graduate programme
Risk management (3)
• …
📎 jobs-2026-10-13.md
```

- One summary card, then one card per category, in the scraper's order. Titles link to the job
  ad, preferably on the employer's own site.
- The attached Markdown file is the scraper's full report of that run (`JOBS_ATTACH_REPORT`).
- A long report is split automatically to stay within Discord's limits: 10 cards and 6000
  characters per message, 4096 characters per card.
- With nothing new, the bot posts a one-line "No new postings today." Set
  `JOBS_POST_WHEN_EMPTY=false` to stay silent instead.

## The daily flow

```
07:00 (JOBS_TIME, JOBS_TIMEZONE)
  │
  ├─ 1. Scrape          JobService.run_scrape()              ~ 2–8 minutes, in a worker thread
  │                     → stores jobs in data/jobs.db, writes reports/YYYY-MM-DD.md
  │
  ├─ 2. Select jobs     JobService.unnotified("discord:<channel id>", filter)
  │                     = matching jobs, first seen ≤ JOBS_MAX_AGE_DAYS ago,
  │                       never posted to this channel
  │
  ├─ 3. Post            summary card + category cards (+ Markdown file)
  │
  └─ 4. Remember        JobService.mark_notified(ids, "discord:<channel id>")
                        (only after Discord accepted every message)
```

The code lives in `src/fgbot/cogs/jobs/`:

| File | Responsibility |
|---|---|
| `cog.py` | Schedule (`discord.ext.tasks.loop`), the `/jobs` commands, sending messages |
| `reporter.py` | `JobReporter`: scraping, choosing the jobs, building the messages, marking them as posted |
| `formatting.py` | Pure functions that turn job records into Discord embeds within the size limits |

### Why jobs are never posted twice

The scraper's database has a `notifications` table with one row per *(job, channel)*. The bot
uses the channel key `discord:<JOBS_CHANNEL_ID>` and records jobs **after** a successful post.
This gives three guarantees:

- A job appears in the channel **once**, even when the bot restarts or a report is made manually.
- If posting fails (Discord down, missing permission), the jobs are **not** marked and come again
  in the next report.
- If you change `JOBS_CHANNEL_ID`, the new channel starts with an empty history. It receives
  at most the last `JOBS_MAX_AGE_DAYS` days of jobs, not the whole backlog.

### Missed reports (computer was off)

When the bot starts, it asks the scraper whether a successful scrape happened in the last
20 hours (`JobService.needs_catch_up()`). If not, it makes the report right away. A laptop that was
asleep at 07:00 therefore posts the report when it wakes up and the bot reconnects.

### Running at the same time as other scrapes

The scraper allows only one scrape at a time, using a lock file `data/jobs.lock`. If another
scrape is running, for example `actjobs run` in a terminal, the bot skips its own scrape. It still
posts whatever is new in the database and adds a note to the report. Inside the bot, an
`asyncio.Lock` prevents `/jobs run-now` from overlapping the scheduled report.

> **Disable the scraper's own scheduling.** The bot now owns the daily run. Don't also enable the
> scraper's `actjobs.timer`, `actjobs schedule` or its Discord webhook (`[discord].webhook_url`),
> or you get two scrapes and two posts. The lock prevents corruption, but it's wasted work.

## The scraper API contract

The bot and the scraper are separate repositories, but the bot imports the scraper as a
library. The table below lists **every** scraper symbol the bot uses. It is the contract
between the two projects:

- In the **scraper**, don't rename, remove or change the meaning of anything in this table
  without changing the bot at the same time.
- In the **bot**, don't import anything from `actjobs` that is not listed here. If you need
  something new, add it to this table.

| Symbol | Used in | What the bot relies on |
|---|---|---|
| `actjobs.service.JobService(config_path)` | `cog.py` (`cog_load`) | Opens the scraper with its `settings.toml`. Blocking, so it runs in a thread. |
| `JobService.cfg.settings.output` | `cog.py`, `reporter.py` | The scraper's `[output]` filter settings, passed to `output_filter`. |
| `JobService.run_scrape(trigger=, notifiers=)` | `reporter.py` (`scrape`) | Runs one scrape under the lock and returns `(RunResult, Digest)`. Raises `RunInProgressError` if another scrape holds the lock. |
| `JobService.default_notifiers()` | `reporter.py` | The scraper's notifiers. Each has a `.channel`; the bot drops the one whose channel is `"console"`. |
| `JobService.unnotified(channel, filter)` | `reporter.py` (`unposted_jobs`) | Matching jobs never recorded for `channel` (`"discord:<id>"`), newest first. |
| `JobService.mark_notified(job_ids, channel)` | `reporter.py` (`mark_posted`) | Records the jobs as posted to `channel`. |
| `JobService.stats()` | `reporter.py` | A dict with at least `"active_relevant"` (open relevant jobs). |
| `JobService.needs_catch_up()` | `cog.py` (`_before_daily_report`) | True if no successful scrape happened in the last 20 hours. |
| `JobService.last_run()` | `cog.py` (`/jobs status`) | `None`, or a dict with `id`, `started_at` (ISO), `status`, `trigger` and `sources` (dicts with `source`, `status`, `fetched`, `new`, `error`). |
| `JobService.query_jobs(filter)` | `cog.py` (`/jobs list`, `/jobs search`) | The jobs matching the filter, best match first. |
| `actjobs.service.output_filter(output, **overrides)` | `cog.py`, `reporter.py` | Builds a `JobFilter` from `[output]`. The bot uses the overrides `limit`, `categories`, `cantons`, `seniorities`, `search` and `first_seen_after`. |
| `actjobs.service.RunInProgressError` | `reporter.py` | Raised by `run_scrape` when the lock is taken. |
| `actjobs.report.Digest` | `reporter.py` | Result of a run, with the fields `run`, `jobs`, `stats` and `warnings`. |
| `actjobs.report.render_markdown(digest, tz)` | `reporter.py` | The Markdown file attached to the report. |
| `actjobs.report.CATEGORY_LABELS`, `SENIORITY_LABELS` | `cog.py`, `formatting.py` | Dicts from key to display label, in display order. They are the choices of `/jobs list`. |
| `actjobs.report.place(job)`, `workload(job)` | `formatting.py` | Short display texts such as `"Zürich (ZH)"` and `"80–100%"`. |
| `actjobs.models.JobRecord` | `formatting.py`, `reporter.py` | A job, with the fields `id`, `title`, `company`, `url`, `category`, `seniority`, `languages_required`, and the fields `place` and `workload` read. |
| `RunResult` (via `Digest.run`) | `formatting.py` (`summary_embed`) | The fields `run_id`, `status`, `closed`, and `sources`, each with `.requests`. |

The tests in `tests/test_jobs.py` use a `FakeService` that implements exactly the methods
`JobReporter` calls, together with the scraper's real `Digest`, `JobRecord` and
`OutputSettings`. After changing either side, run `uv run pytest tests/test_jobs.py
tests/test_bot.py` with both repositories checked out side by side.

## Changing which jobs are posted

The *filter* belongs to the scraper, so the CLI (`actjobs list`) and the bot always agree. Edit
the `[output]` section of `../swiss-actuarial-job-scraper/config/settings.toml`:

```toml
[output]
seniorities = ["intern", "working_student", "trainee", "graduate", "junior", "unspecified"]
categories = []                 # empty = all; e.g. ["actuarial", "underwriting"]
cantons = []                    # empty = all; e.g. ["ZH", "BS", "BE"]
languages = []                  # e.g. ["de", "en"] hides jobs that require French/Italian
min_workload = 0                # e.g. 40 hides jobs whose max workload is below 40%
include_borderline = false
```

Restart the bot afterwards (`systemctl --user restart fgbot`); it reads the file at startup.
Companies, career sites and keyword rules are also configured in the scraper; see its
`README.md` and `docs/configuration.md`.

## Where the files are

| What | Where |
|---|---|
| Job database (SQLite) | `../swiss-actuarial-job-scraper/data/jobs.db` (`[general].db_path`) |
| Markdown reports | `../swiss-actuarial-job-scraper/reports/YYYY-MM-DD.md` |
| Scraper log lines | in the bot's log (`logs/fgbot.log`, `journalctl --user -u fgbot`) |

Back up `jobs.db` if you care about the history. It also holds the "already posted" records.

## Inspecting things by hand

The scraper's CLI works next to the running bot, because the database uses WAL mode and
reading is safe during a scrape:

```bash
cd ../swiss-actuarial-job-scraper
uv run actjobs list --new           # what would be "new"
uv run actjobs db runs              # recent scrape runs and their status
uv run actjobs sources check        # test every source without storing anything
```

In Discord: `/jobs status` shows the last run and the next scheduled one, and
`/jobs run-now scrape:False` re-posts anything that wasn't delivered yet.
