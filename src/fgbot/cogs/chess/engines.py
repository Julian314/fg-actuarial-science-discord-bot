"""Async wrappers around the two chess engines.

* ``ShessGPTEngine`` – the bot's own neural network; it plays against the user. Its search is
  CPU-bound, so it runs in a worker thread (``asyncio.to_thread``).
* ``StockfishEngine`` – the strong open-source engine, used for ``/chess eval`` and
  ``/chess hint``. One Stockfish process is started when the cog loads and reused for every
  request (python-chess talks to it asynchronously over the UCI protocol). If Stockfish is
  not installed, the cog keeps working with ShessGPT only.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine

from fgbot.shessgpt import MATE_SCORE, ScoredMove, ShessGPTNet, choose_move, evaluate, load_net

log = logging.getLogger(__name__)


class ShessGPTEngine:
    """The ShessGPT network, usable from async code."""

    def __init__(self, net: ShessGPTNet) -> None:
        self._net = net

    @classmethod
    async def load(cls, weights_path: Path) -> ShessGPTEngine:
        """Load the weights in a thread (reading the file and building torch modules blocks)."""
        net = await asyncio.to_thread(load_net, weights_path)
        log.info("ShessGPT loaded from %s", weights_path)
        return cls(net)

    async def choose_move(self, board: chess.Board) -> ScoredMove:
        """The move ShessGPT plays for the side to move."""
        return await asyncio.to_thread(choose_move, self._net, board.copy())

    async def evaluate(self, board: chess.Board) -> float:
        """ShessGPT's score of the position (White's point of view)."""
        return await asyncio.to_thread(evaluate, self._net, board.copy())


def format_shessgpt_score(score: float) -> str:
    """'+1.35', or a win/loss text for a finished game."""
    if score >= MATE_SCORE:
        return "White has won"
    if score <= -MATE_SCORE:
        return "Black has won"
    return f"{score:+.2f}"


@dataclass(frozen=True)
class StockfishAnalysis:
    """What ``/chess eval`` and ``/chess hint`` need from Stockfish."""

    score: chess.engine.PovScore
    best_move: chess.Move | None


class StockfishEngine:
    """A long-running Stockfish process.

    Call ``start()`` once (``cog_load``) and ``close()`` on shutdown (``cog_unload``).
    """

    def __init__(self, path: str, think_time: float) -> None:
        self._path = path
        self._limit = chess.engine.Limit(time=think_time)
        self._engine: chess.engine.UciProtocol | None = None
        self._lock = asyncio.Lock()  # one UCI conversation at a time

    @property
    def available(self) -> bool:
        return self._engine is not None

    async def start(self) -> None:
        """Start Stockfish. Logs a warning (instead of failing) if it cannot be started."""
        try:
            _transport, self._engine = await chess.engine.popen_uci(self._path)
        except (OSError, chess.engine.EngineError) as error:
            log.warning(
                "Stockfish could not be started (%s: %s). /chess eval and /chess hint will use "
                "ShessGPT only. Install Stockfish or set STOCKFISH_PATH.",
                type(error).__name__,
                error,
            )
            self._engine = None
            return
        log.info("Stockfish started: %s", self._engine.id.get("name", self._path))

    async def analyse(self, board: chess.Board) -> StockfishAnalysis:
        """Evaluate the position and find the best move for the side to move.

        Restarts Stockfish once if the process has died in the meantime.

        Raises:
            RuntimeError: Stockfish is not available.
        """
        async with self._lock:
            if self._engine is None:
                raise RuntimeError("Stockfish is not available")
            try:
                info = await self._engine.analyse(board, self._limit)
            except chess.engine.EngineTerminatedError:
                log.warning("Stockfish terminated unexpectedly, restarting it")
                await self.start()
                if self._engine is None:
                    raise RuntimeError("Stockfish is not available") from None
                info = await self._engine.analyse(board, self._limit)
        principal_variation = info.get("pv") or [None]
        return StockfishAnalysis(score=info["score"], best_move=principal_variation[0])

    async def close(self) -> None:
        if self._engine is not None:
            with contextlib.suppress(chess.engine.EngineTerminatedError):  # already gone
                await self._engine.quit()
            self._engine = None


def format_stockfish_score(score: chess.engine.PovScore) -> str:
    """'+0.45' (pawns, White's view) or 'White mates in 3'."""
    white = score.white()
    mate = white.mate()
    if mate is not None:
        if mate == 0:
            return "Checkmate"
        side = "White" if mate > 0 else "Black"
        return f"{side} mates in {abs(mate)}"
    centipawns = white.score()
    return f"{centipawns / 100:+.2f}" if centipawns is not None else "?"
