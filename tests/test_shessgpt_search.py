"""ShessGPT network loading and the 2-ply search."""

from __future__ import annotations

import chess
import pytest

from fgbot.shessgpt import MATE_SCORE, choose_move, evaluate


def test_weights_load_and_produce_a_number(shessgpt_net) -> None:
    score = evaluate(shessgpt_net, chess.Board())
    assert isinstance(score, float)
    assert abs(score) < MATE_SCORE


@pytest.mark.parametrize(
    ("fen", "mating_move"),
    [
        # White: back-rank mate Rd8#.
        ("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", "d1d8"),
        # Black: back-rank mate Rd1#. (The old bot crashed in exactly this situation.)
        ("3r2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1", "d8d1"),
    ],
)
def test_finds_mate_in_one(shessgpt_net, fen: str, mating_move: str) -> None:
    best = choose_move(shessgpt_net, chess.Board(fen))
    assert best.move == chess.Move.from_uci(mating_move)
    assert abs(best.score) == MATE_SCORE


def test_avoids_stalemate_when_winning(shessgpt_net) -> None:
    # White is a queen up; Qb6?? would stalemate the black king on a8. Any other move is fine.
    board = chess.Board("k7/8/2Q5/8/8/8/8/K7 w - - 0 1")
    best = choose_move(shessgpt_net, board)
    board.push(best.move)
    assert not board.is_stalemate()


def test_returns_a_legal_move_and_does_not_touch_the_board(shessgpt_net) -> None:
    board = chess.Board()
    board.push_san("e4")
    fen_before = board.fen()
    best = choose_move(shessgpt_net, board)
    assert best.move in board.legal_moves
    assert board.fen() == fen_before


def test_game_over_raises(shessgpt_net) -> None:
    mated = chess.Board("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1")
    mated.push_uci("d1d8")
    with pytest.raises(ValueError):
        choose_move(shessgpt_net, mated)
    assert evaluate(shessgpt_net, mated) == MATE_SCORE
