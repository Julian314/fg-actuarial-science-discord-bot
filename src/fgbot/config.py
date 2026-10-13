"""Bot configuration, loaded from environment variables and an optional ``.env`` file.

Every setting is declared once here, with its type, default and meaning. pydantic validates
the values at startup, so a typo such as ``JOBS_TIME=7am`` stops the bot immediately with a
clear message instead of failing hours later inside a cog.

Variable names are the field names in upper case, e.g. ``discord_token`` -> ``DISCORD_TOKEN``.
See ``.env.example`` and ``docs/configuration.md`` for a commented list.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (…/fg-actuarial-science-discord-bot). Relative paths in the config are
# resolved against it, so the bot behaves the same no matter which directory it starts from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The ShessGPT weights ship inside the package.
BUNDLED_WEIGHTS = Path(__file__).resolve().parent / "shessgpt" / "weights" / "ShessGPT_2_57.pth"


class Settings(BaseSettings):
    """All bot settings. Instantiate with ``Settings()`` to read the environment."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # "GUILD_ID=" (empty) means "use the default"
        extra="ignore",  # other tools may share the .env file
    )

    # ------------------------------------------------------------------------ core
    discord_token: SecretStr = Field(description="Bot token from the Discord developer portal.")
    guild_id: int | None = Field(
        default=None,
        description="If set, slash commands are synced to this server only (instant). "
        "Leave empty to sync globally (can take up to an hour the first time).",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_dir: Path = Path("logs")

    # ------------------------------------------------------------- feature toggles
    music_enabled: bool = True
    chess_enabled: bool = True
    jobs_enabled: bool = True

    # ----------------------------------------------------------------------- music
    spotify_client_id: str = ""
    spotify_client_secret: SecretStr = SecretStr("")
    music_idle_timeout: int = Field(
        default=300, ge=10, description="Seconds of silence before the bot leaves voice."
    )
    music_default_volume: int = Field(default=50, ge=0, le=100)

    # ----------------------------------------------------------------------- chess
    stockfish_path: str = Field(
        default="stockfish", description="Path to the Stockfish binary or a name on $PATH."
    )
    stockfish_think_time: float = Field(default=0.5, gt=0, le=10)
    shessgpt_weights: Path = BUNDLED_WEIGHTS

    # ------------------------------------------------------------------------ jobs
    jobs_channel_id: int | None = Field(
        default=None, description="Text channel that receives the daily job report."
    )
    actjobs_config: Path = Field(
        default=Path("../swiss-actuarial-job-scraper/config/settings.toml"),
        description="settings.toml of the swiss-actuarial-job-scraper project.",
    )
    jobs_time: dt.time = Field(
        default=dt.time(7, 0), description="Local time (HH:MM) of the daily scrape + report."
    )
    jobs_timezone: str = "Europe/Zurich"
    jobs_max_age_days: int = Field(
        default=7,
        ge=1,
        description="Only jobs first seen within this many days are posted "
        "(prevents a new channel from being flooded with the whole backlog).",
    )
    jobs_post_when_empty: bool = True
    jobs_attach_report: bool = True

    # ------------------------------------------------------------------ validators
    @field_validator("log_dir", "actjobs_config", "shessgpt_weights")
    @classmethod
    def _resolve_path(cls, value: Path) -> Path:
        """Make relative paths relative to the project root, not the working directory."""
        value = value.expanduser()
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @field_validator("jobs_timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown time zone {value!r} (e.g. 'Europe/Zurich')") from error
        return value

    @model_validator(mode="after")
    def _check_jobs_settings(self) -> Settings:
        """The jobs feature needs a channel and the scraper's config file."""
        if not self.jobs_enabled:
            return self
        if self.jobs_channel_id is None:
            raise ValueError("JOBS_CHANNEL_ID is required when JOBS_ENABLED=true")
        if not self.actjobs_config.is_file():
            raise ValueError(
                f"ACTJOBS_CONFIG points to {self.actjobs_config}, which does not exist. "
                "Clone swiss-actuarial-job-scraper next to this repository or fix the path."
            )
        return self

    # --------------------------------------------------------------------- helpers
    @property
    def jobs_schedule_time(self) -> dt.time:
        """``jobs_time`` with the configured time zone attached (what ``tasks.loop`` needs)."""
        return self.jobs_time.replace(tzinfo=ZoneInfo(self.jobs_timezone))

    @property
    def spotify_enabled(self) -> bool:
        """Spotify links work only when both credentials are configured."""
        return bool(self.spotify_client_id and self.spotify_client_secret.get_secret_value())
