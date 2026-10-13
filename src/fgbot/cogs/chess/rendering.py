"""Draw the board as a PNG image (in memory, never written to disk)."""

from __future__ import annotations

import cairosvg
import chess
import chess.svg

BOARD_SIZE_PX = 480


def render_board_png(
    board: chess.Board,
    *,
    orientation: chess.Color = chess.WHITE,
    highlight: chess.Move | None = None,
) -> bytes:
    """PNG bytes of ``board`` seen from ``orientation``'s side.

    Args:
        board: The position to draw.
        orientation: ``chess.BLACK`` puts Black at the bottom (for a player with Black).
        highlight: A move whose from/to squares are coloured (usually the last move).
    """
    king_in_check = board.king(board.turn) if board.is_check() else None
    svg = chess.svg.board(
        board,
        orientation=orientation,
        lastmove=highlight,
        check=king_in_check,
        size=BOARD_SIZE_PX,
    )
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"))
