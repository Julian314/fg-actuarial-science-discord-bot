"""The rules of one game between a Discord user and the bot.

This module knows nothing about Discord: it only manipulates a ``chess.Board``. That keeps
the game logic easy to read and to unit-test (see ``tests/test_chess_session.py``). The cog
translates ``ChessError`` into a message for the user.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import chess


class ChessError(ValueError):
    """A problem the player can fix (illegal move, not your turn, …). Safe to show."""


TERMINATION_TEXT = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient material",
    chess.Termination.SEVENTYFIVE_MOVES: "the 75-move rule",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold repetition",
    chess.Termination.FIFTY_MOVES: "the 50-move rule",
    chess.Termination.THREEFOLD_REPETITION: "threefold repetition",
}


@dataclass
class ChessSession:
    """A running game: who plays, with which colour, and the board.

    Attributes:
        player_id: Discord user ID of the human player (IDs never change, names do).
        player_color: ``chess.WHITE`` or ``chess.BLACK``.
        board: Current position including the move history.
        lock: Serialises commands for this game, so two quick ``/chess move`` calls cannot
            interleave while the bot is thinking.
    """

    player_id: int
    player_color: chess.Color
    board: chess.Board = field(default_factory=chess.Board)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    # ------------------------------------------------------------------ creation
    @classmethod
    def create(cls, player_id: int, player_color: chess.Color, fen: str | None = None):
        """Start a game, optionally from a custom position given as FEN.

        Raises:
            ChessError: The FEN is malformed, describes an impossible position, or the game
                in it is already over.
        """
        board = chess.Board()
        if fen:
            try:
                board = chess.Board(fen.strip())
            except ValueError as error:
                raise ChessError(f"That is not a valid FEN: {error}") from error
            if not board.is_valid():
                raise ChessError("That FEN describes an impossible position.")
            if board.is_game_over():
                raise ChessError("The game in that position is already over.")
        return cls(player_id=player_id, player_color=player_color, board=board)

    # -------------------------------------------------------------------- state
    @property
    def bot_color(self) -> chess.Color:
        return not self.player_color

    @property
    def is_player_turn(self) -> bool:
        return self.board.turn == self.player_color

    @property
    def last_move(self) -> chess.Move | None:
        return self.board.peek() if self.board.move_stack else None

    def outcome(self) -> chess.Outcome | None:
        """How the game ended, or None while it is still running."""
        return self.board.outcome()

    def describe_outcome(self, outcome: chess.Outcome) -> str:
        """A sentence such as "You win by checkmate! 🎉" from the player's point of view."""
        reason = TERMINATION_TEXT.get(outcome.termination, outcome.termination.name.lower())
        if outcome.winner is None:
            return f"Draw by {reason}."
        if outcome.winner == self.player_color:
            return f"You win by {reason}! 🎉"
        return f"ShessGPT wins by {reason}."

    # -------------------------------------------------------------------- moves
    def parse_move(self, text: str) -> chess.Move:
        """Read a move in SAN (``Nf3``, ``O-O``, ``exd5``) or UCI (``g1f3``) notation.

        Raises:
            ChessError: The text is not a legal move in the current position.
        """
        text = text.strip()
        try:
            return self.board.parse_san(text)
        except ValueError:
            pass
        try:
            move = chess.Move.from_uci(text.lower())
        except ValueError:
            move = None
        if move is None or move not in self.board.legal_moves:
            raise ChessError(f"`{text}` is not a legal move here.")
        return move

    def push_player_move(self, move: chess.Move) -> str:
        """Play the human's move and return it in SAN.

        Raises:
            ChessError: It is not the player's turn or the move is illegal.
        """
        if not self.is_player_turn:
            raise ChessError("It is not your turn.")
        return self._push(move)

    def push_bot_move(self, move: chess.Move) -> str:
        """Play the bot's move and return it in SAN."""
        return self._push(move)

    def _push(self, move: chess.Move) -> str:
        if move not in self.board.legal_moves:
            raise ChessError(f"`{move.uci()}` is not a legal move here.")
        san = self.board.san(move)
        self.board.push(move)
        return san

    def undo(self) -> None:
        """Take back the bot's last move and the player's move before it.

        Raises:
            ChessError: There is no full move of the player to take back.
        """
        if not self.is_player_turn or len(self.board.move_stack) < 2:
            raise ChessError("There is no move of yours to take back.")
        self.board.pop()  # the bot's reply
        self.board.pop()  # the player's move

    def override_bot_move(self, move_text: str) -> str:
        """Replace the bot's last move with a move chosen by the player.

        Handy to explore "what if the bot had played …". The board is left unchanged when
        the new move is illegal.

        Returns:
            The new move in SAN.

        Raises:
            ChessError: The bot has not moved yet, or the move is illegal.
        """
        if not self.is_player_turn or not self.board.move_stack:
            raise ChessError("The bot has not made a move that could be replaced.")
        original = self.board.pop()
        try:
            return self.push_bot_move(self.parse_move(move_text))
        except ChessError:
            self.board.push(original)  # restore the position
            raise

    def legal_moves_san(self) -> list[str]:
        """All legal moves in SAN, sorted (used for autocomplete)."""
        return sorted(self.board.san(move) for move in self.board.legal_moves)
