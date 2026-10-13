# Changelog

All notable changes to this bot are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version numbers follow
[semantic versioning](https://semver.org/) (see [CONTRIBUTING.md](CONTRIBUTING.md#releasing)).

## [Unreleased]

### Added
- Maintainer documentation: [onboarding guide](docs/onboarding.md), [glossary](docs/glossary.md),
  [handover runbook](docs/handover.md), this changelog and [CONTRIBUTING.md](CONTRIBUTING.md).
- [Architecture](docs/architecture.md): a slash command traced end to end, the startup and
  shutdown order, where state lives, and the import rules.
- [Job reports](docs/job-reports.md): the scraper API contract.
- **TrueNAS deployment** ([deployment.md](docs/deployment.md), option C): a container image
  that GitHub Actions builds and publishes to the GitHub Container Registry, and a TrueNAS
  Custom App template.

## [1.0.0] – 2026-10-13

A complete rewrite of the 2024
[Discord-Music-Chess-Bot](https://github.com/Julian314/Discord-Music-Chess-Bot). See
[docs/migration-from-old-bot.md](docs/migration-from-old-bot.md) for the command mapping and
every bug fixed.

### Added
- **Daily job report:** every morning, the bot scrapes Swiss insurers and job boards through
  `swiss-actuarial-job-scraper` and posts new junior actuarial jobs. Also adds `/jobs list`,
  `/jobs search`, `/jobs status` and `/jobs run-now`.
- **General commands:** `/help`, `/ping`, `/about`.
- **Chess:**
  - `/chess board` shows the board again.
  - Legal moves are suggested while you type a move.
  - Games can start from any FEN position.
- **Music:** Spotify album links are supported.
- **Configuration:** settings are validated at startup, and each feature can be turned on or
  off.
- **Deployment:** systemd units for a laptop (user service) and a server (system service).
- **Tests:** a test suite that runs offline, in about 3 seconds.

### Changed
- All commands are slash commands; the `.` prefix is gone.
- No privileged intents are needed.
- **Chess:**
  - There is one game per channel instead of one global game.
  - Players are identified by user ID instead of display name.
  - ShessGPT's search runs as one batched pass in a worker thread, about 10× faster.
  - One long-running Stockfish process replaces a new process per command.
- **Music:** songs are looked up lazily, and a fresh audio source is created for every playback.
- Messages are in English.

### Removed
- The "NÄ ÄÄÄÄ" joke block, which depended on hard-coded names and channel IDs.
- Automatic shuffling of Spotify playlists. Use `/shuffle` instead.

### Fixed
- Many crashes and bugs of the old bot, among them `/loop`, `/volume`, ShessGPT not finding mate
  in one, and the 75-move rule. Full list:
  [migration-from-old-bot.md](docs/migration-from-old-bot.md#bugs-fixed).

### Security
- Secrets are read only from the git-ignored `.env`. The credentials leaked in the old
  repository's history must be rotated; see the migration guide.

[Unreleased]: https://github.com/Julian314/fg-actuarial-science-discord-bot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Julian314/fg-actuarial-science-discord-bot/releases/tag/v1.0.0
