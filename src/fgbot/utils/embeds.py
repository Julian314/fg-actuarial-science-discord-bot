"""Small helpers so every cog's messages look the same."""

from __future__ import annotations

import discord

# One colour per kind of message.
INFO = discord.Colour.blurple()
SUCCESS = discord.Colour.green()
ERROR = discord.Colour.red()
WARNING = discord.Colour.orange()


def info(description: str, *, title: str | None = None) -> discord.Embed:
    """A neutral embed (blurple)."""
    return discord.Embed(title=title, description=description, colour=INFO)


def success(description: str, *, title: str | None = None) -> discord.Embed:
    """A confirmation embed (green)."""
    return discord.Embed(title=title, description=description, colour=SUCCESS)


def error(description: str, *, title: str | None = None) -> discord.Embed:
    """An error embed (red)."""
    return discord.Embed(title=title, description=description, colour=ERROR)


def truncate(text: str, limit: int) -> str:
    """Cut ``text`` to at most ``limit`` characters, ending with "…" if it was shortened."""
    return text if len(text) <= limit else text[: limit - 1] + "…"
