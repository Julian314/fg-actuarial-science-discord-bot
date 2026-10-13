"""How ShessGPT picks a move: a 2-ply minimax search over the network's evaluation.

For every legal move of the side to move ("our" move) we look at every reply of the
opponent and assume the opponent picks the reply that is worst for us. We then play the
move whose worst case is best. Scores are always from White's point of view, so White
maximises and Black minimises.

Compared with the original bot this version

* scores finished games exactly (checkmate = ±MATE_SCORE, draw = 0) instead of asking the
  network, so it finds mate in one and no longer crashes when a move leaves the opponent
  without legal replies;
* evaluates all positions of the search tree in one batched forward pass (≈ 10× faster
  than one network call per position, while choosing the same moves);
* runs under ``torch.inference_mode()`` (no gradient bookkeeping).

These functions are CPU-heavy and synchronous: call them via ``asyncio.to_thread`` from the
bot so the event loop stays responsive.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess
import numpy as np
import torch

from fgbot.shessgpt.encoding import encode_batch, encode_features
from fgbot.shessgpt.model import ShessGPTNet

# Larger than anything the network outputs, so a forced mate always beats a good position.
MATE_SCORE = 1000.0


@dataclass(frozen=True)
class ScoredMove:
    """A move and the score (White's point of view) the search expects after it."""

    move: chess.Move
    score: float


@dataclass
class _Candidate:
    """One of our moves, waiting for its opponent replies to be evaluated."""

    move: chess.Move
    exact_score: float | None = None  # set if the move ends the game
    reply_rows: list[int] = field(default_factory=list)  # rows in the evaluation batch


def terminal_score(board: chess.Board) -> float | None:
    """The exact score of a finished game, or None while the game is still running."""
    outcome = board.outcome()
    if outcome is None:
        return None
    if outcome.winner is None:
        return 0.0  # stalemate, insufficient material, 75-move rule, fivefold repetition
    return MATE_SCORE if outcome.winner == chess.WHITE else -MATE_SCORE


def _evaluate_rows(net: ShessGPTNet, rows: list[np.ndarray]) -> list[float]:
    """Run the network once over all encoded positions."""
    if not rows:
        return []
    with torch.inference_mode():
        return net(encode_batch(rows)).squeeze(1).tolist()


def evaluate(net: ShessGPTNet, board: chess.Board) -> float:
    """ShessGPT's score of the current position (positive = good for White)."""
    exact = terminal_score(board)
    if exact is not None:
        return exact
    return _evaluate_rows(net, [encode_features(board)])[0]


def choose_move(net: ShessGPTNet, board: chess.Board) -> ScoredMove:
    """The best move for the side to move, according to a 2-ply search.

    Raises:
        ValueError: The game is already over (there is no move to choose).
    """
    if board.is_game_over():
        raise ValueError("the game is over, there is no move to choose")

    we_are_white = board.turn == chess.WHITE
    candidates: list[_Candidate] = []
    rows: list[np.ndarray] = []  # encoded leaf positions, evaluated in one batch
    exact_leaf_scores: dict[int, float] = {}  # row -> exact score for finished games

    # Work on a copy so the caller's board is never modified. The move stack is kept
    # because repetition draws depend on it.
    board = board.copy()
    for move in list(board.legal_moves):
        candidate = _Candidate(move)
        board.push(move)
        candidate.exact_score = terminal_score(board)
        if candidate.exact_score is None:
            for reply in list(board.legal_moves):
                board.push(reply)
                row = len(rows)
                rows.append(encode_features(board))
                exact = terminal_score(board)
                if exact is not None:
                    exact_leaf_scores[row] = exact
                candidate.reply_rows.append(row)
                board.pop()
        board.pop()
        candidates.append(candidate)

    leaf_scores = _evaluate_rows(net, rows)
    for row, exact in exact_leaf_scores.items():
        leaf_scores[row] = exact

    def worst_case(candidate: _Candidate) -> float:
        """The score after the opponent's best reply to this candidate move."""
        if candidate.exact_score is not None:
            return candidate.exact_score
        replies = [leaf_scores[row] for row in candidate.reply_rows]
        return min(replies) if we_are_white else max(replies)

    scored = [ScoredMove(c.move, worst_case(c)) for c in candidates]
    # max()/min() return the first of several equally good moves, like the original bot.
    pick = max if we_are_white else min
    return pick(scored, key=lambda s: s.score)
