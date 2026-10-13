"""Exceptions shared by all cogs.

Commands raise ``UserFacingError`` for problems the user caused or can fix ("you are not in a
voice channel", "illegal move"). The global error handler in ``bot.py`` shows its message as
is. Any *other* exception is a bug: it is logged with a full traceback and the user only sees
a generic "something went wrong", so internals never leak into the chat.
"""

from __future__ import annotations

from discord import app_commands


class UserFacingError(app_commands.AppCommandError):
    """An error whose message is safe and helpful to show to the user."""
