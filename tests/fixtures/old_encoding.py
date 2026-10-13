"""The ORIGINAL ShessGPT input encoding from the old bot (helpers.py), kept as a test oracle.

Only the formatting was changed (the original file no longer imported). The logic is
unchanged on purpose: ``test_shessgpt_encoding.py`` checks that the new, readable
``fgbot.shessgpt.encoding`` produces exactly the same tensor, because the network weights
were trained on this encoding. Do not "clean up" this file.
"""
# ruff: noqa

import chess
import torch


def int_to_binary_64(num):
    binary_string = bin(num)[2:]
    binary_string = binary_string.zfill(64)
    return binary_string


def int_to_binary_6(num):
    binary_string = bin(num)[2:]
    binary_string = binary_string.zfill(6)
    return binary_string


def int_to_binary_10(num):
    binary_string = bin(num)[2:]
    binary_string = binary_string.zfill(10)
    return binary_string


def en_passant(board):
    if board.ep_square == None:
        return int_to_binary_10(65)
    return int_to_binary_10(int(board.ep_square))


def rook(strng):
    zaehler = 0
    for i in range(64):
        if strng[i] == "1":
            zaehler += 1
    return zaehler * 5


def bishop_knight(strng):
    zaehler = 0
    for i in range(128):
        if strng[i] == "1":
            zaehler += 1
    return 3 * zaehler


def queen(strng):
    zaehler = 0
    for i in range(64):
        if strng[i] == "1":
            zaehler += 1
    return 9 * zaehler


def pawn(strng):
    zaehler = 0
    for i in range(64):
        if strng[i] == "1":
            zaehler += 1
    return zaehler


def encode_model_input(board):
    bin_string = (
        int_to_binary_64(int(board.pieces(chess.PAWN, chess.WHITE)))
        + int_to_binary_64(int(board.pieces(chess.ROOK, chess.WHITE)))
        + int_to_binary_64(int(board.pieces(chess.KNIGHT, chess.WHITE)))
        + int_to_binary_64(int(board.pieces(chess.BISHOP, chess.WHITE)))
        + int_to_binary_64(int(board.pieces(chess.QUEEN, chess.WHITE)))
        + int_to_binary_64(int(board.pieces(chess.KING, chess.WHITE)))
        + int_to_binary_64(int(board.pieces(chess.PAWN, chess.BLACK)))
        + int_to_binary_64(int(board.pieces(chess.ROOK, chess.BLACK)))
        + int_to_binary_64(int(board.pieces(chess.KNIGHT, chess.BLACK)))
        + int_to_binary_64(int(board.pieces(chess.BISHOP, chess.BLACK)))
        + int_to_binary_64(int(board.pieces(chess.QUEEN, chess.BLACK)))
        + int_to_binary_64(int(board.pieces(chess.KING, chess.BLACK)))
        + str(int(board.turn))
        + str(int(board.has_kingside_castling_rights(chess.WHITE)))
        + str(int(board.has_queenside_castling_rights(chess.WHITE)))
        + str(int(board.has_kingside_castling_rights(chess.BLACK)))
        + str(int(board.has_queenside_castling_rights(chess.BLACK)))
        + en_passant(board)
        + int_to_binary_6(board.halfmove_clock)
        + int_to_binary_10(board.fullmove_number)
    )
    binary = bytes(int(bin_string[i : i + 8], 2) for i in range(0, len(bin_string), 8))
    bin_string = "".join(format(byte, "08b") for byte in binary)
    bins = bin_string[:769]
    points_white = (
        pawn(bin_string[:64])
        + rook(bin_string[64:128])
        + bishop_knight(bin_string[128:256])
        + queen(bin_string[256:320])
    )
    points_black = (
        pawn(bin_string[384:448])
        + rook(bin_string[448:512])
        + bishop_knight(bin_string[512:640])
        + queen(bin_string[640:704])
    )
    points = torch.tensor([points_white - points_black])
    bins_ = torch.tensor([float(digit) for digit in bins])
    bins_tensor = torch.cat((bins_, points))
    return bins_tensor
