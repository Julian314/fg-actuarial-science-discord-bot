"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make ``tests/fixtures`` importable as plain modules (e.g. ``import old_encoding``).
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))


@pytest.fixture(scope="session")
def shessgpt_net():
    """The real ShessGPT network with the bundled weights (loaded once per test session)."""
    from fgbot.config import BUNDLED_WEIGHTS
    from fgbot.shessgpt import load_net

    return load_net(BUNDLED_WEIGHTS)
