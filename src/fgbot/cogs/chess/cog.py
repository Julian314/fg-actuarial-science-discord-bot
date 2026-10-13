"""Slash commands for playing chess against ShessGPT: ``/chess …``.

There is one game per text channel, so several people can play at the same time in
different channels. Only the player who started a game can move in it.
"""

from __future__ import annotations

import asyncio
import io
import logging
import random
from typing import TYPE_CHECKING, Literal

import chess
import discord
from discord import app_commands
from discord.ext import commands

from fgbot.cogs.chess.engines import (
    ShessGPTEngine,
    StockfishEngine,
    format_shessgpt_score,
    format_stockfish_score,
)
from fgbot.cogs.chess.rendering import render_board_png
from fgbot.cogs.chess.session import ChessError, ChessSession
from fgbot.errors import UserFacingError
from fgbot.utils import embeds

if TYPE_CHECKING:
    from fgbot.bot import FGBot

log = logging.getLogger(__name__)

COLOR_NAMES = {chess.WHITE: "White", chess.BLACK: "Black"}


class ChessCog(commands.GroupCog, group_name="chess", group_description="Play chess vs ShessGPT"):
    """Play chess against ShessGPT, with Stockfish as an advisor."""

    def __init__(self, bot: FGBot) -> None:
        self.bot = bot
        self.sessions: dict[int, ChessSession] = {}  # channel id -> running game
        self.shessgpt: ShessGPTEngine | None = None
        self.stockfish = StockfishEngine(
            bot.settings.stockfish_path, bot.settings.stockfish_think_time
        )

    async def cog_load(self) -> None:
        self.shessgpt = await ShessGPTEngine.load(self.bot.settings.shessgpt_weights)
        await self.stockfish.start()

    async def cog_unload(self) -> None:
        await self.stockfish.close()

    # --------------------------------------------------------------------- helpers
    def _session_for(self, interaction: discord.Interaction, *, player_only: bool) -> ChessSession:
        """The game in this channel; with ``player_only`` the caller must be its player."""
        session = self.sessions.get(interaction.channel_id or 0)
        if session is None:
            raise UserFacingError(
                "No game is running in this channel. Start one with `/chess start`."
            )
        if player_only and interaction.user.id != session.player_id:
            raise UserFacingError(f"Only <@{session.player_id}> can do that in this game.")
        return session

    async def _board_message(
        self, session: ChessSession, text: str, *, title: str | None = None
    ) -> dict:
        """Keyword arguments for ``send``: an embed with the rendered board attached."""
        png = await asyncio.to_thread(
            render_board_png,
            session.board,
            orientation=session.player_color,
            highlight=session.last_move,
        )
        embed = embeds.info(text, title=title)
        embed.set_image(url="attachment://board.png")
        embed.set_footer(text=f"You play {COLOR_NAMES[session.player_color]} · /chess move")
        return {"embed": embed, "file": discord.File(io.BytesIO(png), filename="board.png")}

    async def _bot_turn(self, session: ChessSession) -> str:
        """Let ShessGPT move; returns a line describing the move."""
        assert self.shessgpt is not None
        best = await self.shessgpt.choose_move(session.board)
        san = session.push_bot_move(best.move)
        return f"ShessGPT played **{san}**."

    def _finish_if_over(self, channel_id: int, session: ChessSession) -> str | None:
        """End the game if it is over; returns the result sentence, else None."""
        outcome = session.outcome()
        if outcome is None:
            return None
        del self.sessions[channel_id]
        return session.describe_outcome(outcome)

    # -------------------------------------------------------------------- commands
    @app_commands.command(name="start", description="Start a game against ShessGPT.")
    @app_commands.describe(
        color="The colour you want to play",
        fen="Optional: start from this position (FEN string)",
    )
    @app_commands.guild_only()
    async def start(
        self,
        interaction: discord.Interaction,
        color: Literal["white", "black", "random"] = "white",
        fen: str | None = None,
    ) -> None:
        channel_id = interaction.channel_id or 0
        if channel_id in self.sessions:
            raise UserFacingError(
                "A game is already running in this channel. End it with `/chess resign`."
            )
        if color == "random":
            color = random.choice(["white", "black"])
        player_color = chess.WHITE if color == "white" else chess.BLACK
        try:
            session = ChessSession.create(interaction.user.id, player_color, fen)
        except ChessError as error:
            raise UserFacingError(str(error)) from error

        self.sessions[channel_id] = session
        await interaction.response.defer(thinking=True)
        lines = [f"{interaction.user.mention} plays **{color}** against ShessGPT. Good luck!"]
        async with session.lock:
            if not session.is_player_turn:
                lines.append(await self._bot_turn(session))
        await interaction.followup.send(**await self._board_message(session, "\n".join(lines)))

    @app_commands.command(name="move", description="Make a move, e.g. e4, Nf3, O-O or e2e4.")
    @app_commands.describe(move="Your move in SAN (Nf3) or UCI (g1f3) notation")
    async def move(self, interaction: discord.Interaction, move: str) -> None:
        session = self._session_for(interaction, player_only=True)
        channel_id = interaction.channel_id or 0
        async with session.lock:
            try:
                player_san = session.push_player_move(session.parse_move(move))
            except ChessError as error:
                raise UserFacingError(str(error)) from error

            await interaction.response.defer(thinking=True)
            lines = [f"You played **{player_san}**."]
            result = self._finish_if_over(channel_id, session)
            if result is None:
                lines.append(await self._bot_turn(session))
                result = self._finish_if_over(channel_id, session)
            if result:
                lines.append(f"\n**Game over:** {result}")
            elif session.board.is_check():
                lines.append("Check!")
        await interaction.followup.send(**await self._board_message(session, "\n".join(lines)))

    @move.autocomplete("move")
    async def move_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest the legal moves that start with what the user typed so far."""
        session = self.sessions.get(interaction.channel_id or 0)
        if session is None or not session.is_player_turn:
            return []
        typed = current.strip().lower()
        moves = [san for san in session.legal_moves_san() if san.lower().startswith(typed)]
        return [app_commands.Choice(name=san, value=san) for san in moves[:25]]

    @app_commands.command(
        name="undo", description="Take back your last move (and the bot's reply)."
    )
    async def undo(self, interaction: discord.Interaction) -> None:
        session = self._session_for(interaction, player_only=True)
        async with session.lock:
            try:
                session.undo()
            except ChessError as error:
                raise UserFacingError(str(error)) from error
        await interaction.response.send_message(
            **await self._board_message(session, "Took back the last full move.")
        )

    @app_commands.command(
        name="override", description="Replace ShessGPT's last move with one you choose."
    )
    @app_commands.describe(move="The move ShessGPT should have played")
    async def override(self, interaction: discord.Interaction, move: str) -> None:
        session = self._session_for(interaction, player_only=True)
        channel_id = interaction.channel_id or 0
        async with session.lock:
            try:
                san = session.override_bot_move(move)
            except ChessError as error:
                raise UserFacingError(str(error)) from error
            text = f"ShessGPT's move was replaced by **{san}**."
            result = self._finish_if_over(channel_id, session)
            if result:
                text += f"\n\n**Game over:** {result}"
        await interaction.response.send_message(**await self._board_message(session, text))

    @app_commands.command(name="resign", description="End the game in this channel.")
    async def resign(self, interaction: discord.Interaction) -> None:
        session = self._session_for(interaction, player_only=False)
        is_moderator = interaction.permissions.manage_messages
        if interaction.user.id != session.player_id and not is_moderator:
            raise UserFacingError("Only the player or a moderator can end this game.")
        del self.sessions[interaction.channel_id or 0]
        await interaction.response.send_message(
            f"{interaction.user.mention} ended the game. Final position: `{session.board.fen()}`"
        )

    @app_commands.command(
        name="eval", description="How good is the position? (Stockfish & ShessGPT)"
    )
    async def evaluate(self, interaction: discord.Interaction) -> None:
        session = self._session_for(interaction, player_only=False)
        assert self.shessgpt is not None
        await interaction.response.defer(thinking=True)
        lines = [
            f"**ShessGPT:** {format_shessgpt_score(await self.shessgpt.evaluate(session.board))}"
        ]
        if self.stockfish.available:
            analysis = await self.stockfish.analyse(session.board)
            lines.insert(0, f"**Stockfish:** {format_stockfish_score(analysis.score)}")
        else:
            lines.append("_Stockfish is not available on this host._")
        lines.append("Positive numbers mean White is better (in pawns).")
        await interaction.followup.send(embed=embeds.info("\n".join(lines), title="Evaluation"))

    @app_commands.command(name="hint", description="Ask Stockfish and ShessGPT for the best move.")
    async def hint(self, interaction: discord.Interaction) -> None:
        session = self._session_for(interaction, player_only=False)
        if session.outcome() is not None:
            raise UserFacingError("The game is over.")
        assert self.shessgpt is not None
        await interaction.response.defer(thinking=True, ephemeral=True)
        board = session.board
        shessgpt_move = (await self.shessgpt.choose_move(board)).move
        lines = [f"**ShessGPT** suggests **{board.san(shessgpt_move)}**"]
        if self.stockfish.available:
            analysis = await self.stockfish.analyse(board)
            if analysis.best_move is not None:
                lines.insert(0, f"**Stockfish** suggests **{board.san(analysis.best_move)}**")
        else:
            lines.append("_Stockfish is not available on this host._")
        side = COLOR_NAMES[board.turn]
        await interaction.followup.send(
            embed=embeds.info("\n".join(lines), title=f"Hint for {side}"), ephemeral=True
        )

    @app_commands.command(name="fen", description="Show the current position as a FEN string.")
    async def fen(self, interaction: discord.Interaction) -> None:
        session = self._session_for(interaction, player_only=False)
        await interaction.response.send_message(f"`{session.board.fen()}`")

    @app_commands.command(name="board", description="Show the current board again.")
    async def board(self, interaction: discord.Interaction) -> None:
        session = self._session_for(interaction, player_only=False)
        turn = "your" if session.is_player_turn else "ShessGPT's"
        await interaction.response.send_message(
            **await self._board_message(session, f"It is {turn} turn.")
        )
