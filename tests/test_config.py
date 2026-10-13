"""Configuration parsing and validation."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from fgbot.config import PROJECT_ROOT, Settings


def make_settings(**overrides) -> Settings:
    """Settings that ignore the real .env file; jobs are off unless a test enables them."""
    values = {"discord_token": "test-token", "jobs_enabled": False, **overrides}
    return Settings(_env_file=None, **values)


def test_defaults() -> None:
    settings = make_settings()
    assert settings.music_default_volume == 50
    assert settings.jobs_time == dt.time(7, 0)
    assert settings.log_dir == PROJECT_ROOT / "logs"  # relative paths -> project root
    assert not settings.spotify_enabled
    assert "test-token" not in repr(settings)  # the token is never printed


def test_values_from_strings_like_in_env_files() -> None:
    settings = make_settings(jobs_time="08:30", music_default_volume="80", guild_id="123")
    assert settings.jobs_time == dt.time(8, 30)
    assert settings.music_default_volume == 80
    assert settings.guild_id == 123
    assert settings.jobs_schedule_time.tzinfo is not None


def test_spotify_needs_both_credentials() -> None:
    assert not make_settings(spotify_client_id="id").spotify_enabled
    assert make_settings(spotify_client_id="id", spotify_client_secret="secret").spotify_enabled


@pytest.mark.parametrize(
    "overrides",
    [
        {"music_default_volume": 150},
        {"jobs_time": "7am"},
        {"jobs_timezone": "Mars/Olympus"},
        {"log_level": "LOUD"},
    ],
)
def test_invalid_values_are_rejected(overrides) -> None:
    with pytest.raises(ValidationError):
        make_settings(**overrides)


def test_jobs_need_channel_and_scraper_config(tmp_path) -> None:
    with pytest.raises(ValidationError, match="JOBS_CHANNEL_ID"):
        make_settings(jobs_enabled=True)
    with pytest.raises(ValidationError, match="does not exist"):
        make_settings(jobs_enabled=True, jobs_channel_id=1, actjobs_config=tmp_path / "x.toml")
    config = tmp_path / "settings.toml"
    config.write_text("")
    assert make_settings(jobs_enabled=True, jobs_channel_id=1, actjobs_config=config).jobs_enabled


def test_missing_token_is_an_error(monkeypatch) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(ValidationError, match="discord_token"):
        Settings(_env_file=None, jobs_enabled=False)


def test_env_example_is_valid_once_the_required_values_are_filled_in(tmp_path) -> None:
    """``.env.example`` with only token and channel filled in must load without errors."""
    example = (PROJECT_ROOT / ".env.example").read_text()
    example = example.replace("DISCORD_TOKEN=\n", "DISCORD_TOKEN=abc\n")
    example = example.replace("JOBS_CHANNEL_ID=\n", "JOBS_CHANNEL_ID=42\n")
    scraper_config = tmp_path / "settings.toml"
    scraper_config.write_text("")
    example = example.replace(
        "ACTJOBS_CONFIG=../swiss-actuarial-job-scraper/config/settings.toml",
        f"ACTJOBS_CONFIG={scraper_config}",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(example)

    settings = Settings(_env_file=env_file)
    assert settings.guild_id is None
    assert settings.jobs_channel_id == 42
    assert not settings.spotify_enabled
