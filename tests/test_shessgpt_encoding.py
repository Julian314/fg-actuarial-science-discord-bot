"""The new input encoding must be identical to the one the network was trained on."""

from __future__ import annotations

import random

import chess
import old_encoding
import pytest
import torch

from fgbot.shessgpt.encoding import NUM_FEATURES, encode_position, material_balance

FENS = [
    chess.STARTING_FEN,
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",  # en passant square
    "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1",  # castling rights, Black to move
    "8/8/8/4k3/8/8/4K3/7Q w - - 50 120",  # big move counters
    "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
    "7k/P7/8/8/8/8/8/K7 w - - 0 1",  # pawn about to promote
]


def _random_positions(count: int, seed: int = 42) -> list[chess.Board]:
    """Positions reached by random play, for broader coverage."""
    rng = random.Random(seed)
    boards = []
    for _ in range(count):
        board = chess.Board()
        for _ in range(rng.randint(0, 80)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        boards.append(board)
    return boards


@pytest.mark.parametrize("board", [chess.Board(f) for f in FENS] + _random_positions(25))
def test_matches_original_encoding(board: chess.Board) -> None:
    expected = old_encoding.encode_model_input(board)
    actual = encode_position(board)
    assert actual.shape == (NUM_FEATURES,)
    assert torch.equal(actual, expected.to(actual.dtype))


def test_material_balance() -> None:
    assert material_balance(chess.Board()) == 0
    # White has an extra queen.
    assert material_balance(chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")) == 9
    # Black has an extra rook and knight.
    assert material_balance(chess.Board("rn2k3/8/8/8/8/8/8/4K3 w - - 0 1")) == -8
