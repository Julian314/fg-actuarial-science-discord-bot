# Contributing

This page describes how a change gets from an idea onto the running bot. Coding conventions,
the test suite and step-by-step guides for adding a command or a feature are in
[docs/development.md](docs/development.md). If you are new to the project, start with
[docs/onboarding.md](docs/onboarding.md).

## Workflow

1. **Start from an up-to-date `main`.**

   ```bash
   git switch main && git pull
   ```

2. **Create a branch** named after the change:

   ```bash
   git switch -c add-clear-command        # or fix-loop-after-skip, docs-handover, …
   ```

3. **Make the change** with your own test bot on a test server (`GUILD_ID` set), never against
   the real server. See [docs/development.md](docs/development.md#setup).

4. **Check the definition of done** (below).

5. **Commit** with a message that says *what* changed and, if not obvious, *why*:

   ```
   Add /clear to empty the music queue

   Several members asked for a way to clear the queue without stopping the
   current song.
   ```

   Use the imperative mood ("Add", "Fix", "Update"), keep the first line under about 70
   characters, and make one logical change per commit.

6. **Open a pull request** against `main` on GitHub. Describe what you changed and how you
   tested it. If another member knows the code, ask them to review; otherwise review your own
   diff once more on GitHub before merging. A fresh look finds mistakes.

7. **Merge, then deploy** following [Releasing](#releasing) below.

Small documentation fixes can go straight to `main`.

## Definition of done

A change is finished when **all** of these are true:

- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check .` reports no problems, and `uv run ruff format .` changes nothing.
- [ ] New logic has tests, ideally in a Discord-free module
      ([why](docs/architecture.md#separation-of-logic-and-discord)).
- [ ] **New or renamed slash command:**
  - [ ] it is listed in [docs/commands.md](docs/commands.md)
  - [ ] it is in the expected set in `tests/test_bot.py`
- [ ] **New setting:**
  - [ ] the field is added to `Settings` in `src/fgbot/config.py`
  - [ ] it is documented in [`.env.example`](.env.example) and
        [docs/configuration.md](docs/configuration.md)
- [ ] **Changed behaviour:** the relevant page in `docs/` is updated, and
      [CHANGELOG.md](CHANGELOG.md) has a line under *Unreleased*.
- [ ] **New dependency:** `pyproject.toml` and `uv.lock` are committed together.
- [ ] You tried the change on your test server.
- [ ] No secrets in the diff: no tokens, no `.env`, no IDs of private channels in code.

## Releasing

The version follows [semantic versioning](https://semver.org/):

- **MAJOR** for changes that need action from users or the host. Examples: a removed command,
  a renamed setting.
- **MINOR** for new features.
- **PATCH** for bug fixes.

1. **Bump the version in both places.** They must match; see
   [handover.md](docs/handover.md#known-limitations-and-technical-debt).
   - `version = "…"` in `pyproject.toml`
   - `__version__ = "…"` in `src/fgbot/__init__.py`
2. **Run `uv lock`** so `uv.lock` records the new version.
3. **Update the changelog.** In [CHANGELOG.md](CHANGELOG.md), rename *Unreleased* to the new
   version and today's date, and add a new empty *Unreleased* section.
4. **Commit and tag:**

   ```bash
   git commit -am "Release 1.1.0"
   git tag v1.1.0
   git push && git push --tags
   ```

5. **Deploy** on the host as described in [docs/deployment.md](docs/deployment.md#updating).
   `/about` then shows the new version.

## Questions and bugs

Open a GitHub issue with:

- what you did
- what you expected
- what happened instead
- the relevant log lines, from `journalctl --user -u fgbot` or `logs/fgbot.log`

Remove tokens from the log lines before posting.
