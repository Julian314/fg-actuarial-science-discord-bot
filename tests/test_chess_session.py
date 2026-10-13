"""Game rules of ``ChessSession`` (no Discord involved)."""

from __future__ import annotations

import chess
import pytest

from fgbot.cogs.chess.rendering import render_board_png
from fgbot.cogs.chess.session import ChessError, ChessSession

PLAYER = 1234


def new_game(color: chess.Color = chess.WHITE, fen: str | None = None) -> ChessSession:
    return ChessSession.create(PLAYER, color, fen)


def test_parse_move_accepts_san_and_uci() -> None:
    session = new_game()
    assert session.parse_move("Nf3") == chess.Move.from_uci("g1f3")
    assert session.parse_move("g1f3") == chess.Move.from_uci("g1f3")
    assert session.parse_move(" e4 ") == chess.Move.from_uci("e2e4")


@pytest.mark.parametrize("text", ["e5", "Ke2", "hello", "e2e5", "--"])
def test_parse_move_rejects_illegal_input(text: str) -> None:
    with pytest.raises(ChessError):
        new_game().push_player_move(new_game().parse_move(text))


def test_cannot_move_out_of_turn() -> None:
    session = new_game(chess.BLACK)
    with pytest.raises(ChessError, match="not your turn"):
        session.push_player_move(chess.Move.from_uci("e2e4"))


def test_undo_takes_back_a_full_move() -> None:
    session = new_game()
    session.push_player_move(session.parse_move("e4"))
    session.push_bot_move(session.parse_move("e5"))
    session.undo()
    assert session.board.fen() == chess.STARTING_FEN


def test_undo_without_history_fails() -> None:
    session = new_game()
    with pytest.raises(ChessError):
        session.undo()
    # Player is Black and the bot has only made its first move: nothing of the player's to undo.
    black = new_game(chess.BLACK)
    black.push_bot_move(black.parse_move("e4"))
    with pytest.raises(ChessError):
        black.undo()


def test_override_replaces_bot_move_and_restores_on_error() -> None:
    session = new_game()
    session.push_player_move(session.parse_move("e4"))
    session.push_bot_move(session.parse_move("e5"))
    assert session.override_bot_move("c5") == "c5"
    assert session.last_move == chess.Move.from_uci("c7c5")

    with pytest.raises(ChessError):
        session.override_bot_move("Qh4")  # illegal for Black here
    assert session.last_move == chess.Move.from_uci("c7c5")  # unchanged


def test_create_from_fen() -> None:
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    assert new_game(fen=fen).board.fen() == fen
    with pytest.raises(ChessError, match="not a valid FEN"):
        new_game(fen="not a fen")
    with pytest.raises(ChessError, match="impossible"):
        new_game(fen="8/8/8/8/8/8/8/8 w - - 0 1")  # no kings


def test_outcome_texts() -> None:
    session = new_game(fen="6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1")
    session.push_player_move(session.parse_move("Rd8#"))
    assert session.describe_outcome(session.outcome()) == "You win by checkmate! 🎉"

    # The 75-move rule crashed the old bot; now it is a normal draw.
    session = new_game(fen="8/8/4k3/8/8/4K3/8/7R w - - 149 120")
    session.push_player_move(session.parse_move("Rh2"))
    assert session.describe_outcome(session.outcome()) == "Draw by the 75-move rule."


def test_legal_moves_san_for_autocomplete() -> None:
    moves = new_game().legal_moves_san()
    assert len(moves) == 20
    assert "Nf3" in moves and "e4" in moves


def test_render_board_png() -> None:
    png = render_board_png(chess.Board(), orientation=chess.BLACK)
    assert png.startswith(b"\x89PNG")
