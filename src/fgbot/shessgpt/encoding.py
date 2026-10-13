"""Turn a chess position into the 770 numbers the ShessGPT network was trained on.

Feature layout (index ranges are inclusive-exclusive)::

    [  0, 768)  12 bitboards of 64 bits each, in this order:
                White pawn, rook, knight, bishop, queen, king,
                Black pawn, rook, knight, bishop, queen, king.
                Within a bitboard the first bit is square h8 (63) and the last is a1 (0),
                i.e. the board's 64-bit mask written most-significant bit first.
    [768]       side to move: 1 = White, 0 = Black
    [769]       material balance, White minus Black (pawn 1, knight/bishop 3, rook 5, queen 9)

The original training code also built castling, en passant and move-counter bits, but they
were cut off before reaching the network, so they are deliberately not computed here. This
encoding must stay byte-for-byte compatible with the trained weights;
``tests/test_shessgpt_encoding.py`` checks it against the original implementation.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess
import numpy as np
import torch

NUM_FEATURES = 770

# Order of the 12 bitboards (note: rook before knight, as in the training data).
PIECE_ORDER = (chess.PAWN, chess.ROOK, chess.KNIGHT, chess.BISHOP, chess.QUEEN, chess.KING)
PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def material_balance(board: chess.Board) -> int:
    """Material of White minus material of Black, in pawns."""
    return sum(
        value * (len(board.pieces(piece, chess.WHITE)) - len(board.pieces(piece, chess.BLACK)))
        for piece, value in PIECE_VALUES.items()
    )


def encode_features(board: chess.Board) -> np.ndarray:
    """The 770 features of ``board`` as a float32 NumPy array."""
    # 12 bitboards as big-endian bytes -> unpackbits yields the bits MSB first (h8 ... a1).
    masks = (
        board.pieces_mask(piece, color)
        for color in (chess.WHITE, chess.BLACK)
        for piece in PIECE_ORDER
    )
    raw = b"".join(mask.to_bytes(8, "big") for mask in masks)
    bitboards = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))

    features = np.empty(NUM_FEATURES, dtype=np.float32)
    features[:768] = bitboards
    features[768] = 1.0 if board.turn == chess.WHITE else 0.0
    features[769] = material_balance(board)
    return features


def encode_position(board: chess.Board) -> torch.Tensor:
    """The network input for one position: a float tensor of shape ``(770,)``."""
    return torch.from_numpy(encode_features(board))


def encode_batch(rows: Sequence[np.ndarray]) -> torch.Tensor:
    """Stack already encoded positions into one ``(n, 770)`` tensor for a single forward pass."""
    return torch.from_numpy(np.stack(rows))
