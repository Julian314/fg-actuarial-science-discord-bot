# The chess engines

The bot uses two engines with different jobs:

| Engine | Role | Strength |
|---|---|---|
| **ShessGPT** | The bot's own neural network. It **plays against you**. | roughly 600 Elo; beatable, which is the point |
| **Stockfish** | The world-class open-source engine. It **advises** in `/chess eval` and `/chess hint`. | far above any human |

The ShessGPT code is in `src/fgbot/shessgpt/`. It has no Discord dependencies, so you can use it
from a Python shell:

```python
import chess
from fgbot.config import BUNDLED_WEIGHTS
from fgbot.shessgpt import load_net, choose_move, evaluate

net = load_net(BUNDLED_WEIGHTS)
board = chess.Board()
print(evaluate(net, board))  # > 0: White is better
print(choose_move(net, board))  # ScoredMove(move=Move.from_uci('…'), score=…)
```

## ShessGPT

### The network (`model.py`)

ShessGPT is a plain multi-layer perceptron. It maps a position (770 numbers) to one number,
the evaluation:

```
770 → 512 → 256 → 128 → 64 → 32 → 16 → 1      ReLU between layers, none after the last
```

- It was trained (in a separate project) to imitate Stockfish's evaluation, measured in pawns
  and clipped to about ±20. Forced mates were mapped to larger values.
- **Positive means White is better.**
- The weights are in `shessgpt/weights/ShessGPT_2_57.pth` (2.2 MB). They load with
  `strict=True`, so a mismatch between code and weights fails loudly instead of silently giving
  nonsense.

### The input (`encoding.py`)

The network sees a position as 770 numbers:

| Index | Content |
|---|---|
| 0–767 | 12 bitboards × 64 squares: White pawn, rook, knight, bishop, queen, king, then Black in the same order. A 1 means "a piece of this kind stands here". Inside each bitboard the first entry is h8 and the last is a1. |
| 768 | Side to move: 1 = White, 0 = Black |
| 769 | Material balance, White minus Black (pawn 1, knight 3, bishop 3, rook 5, queen 9) |

The original training code also computed castling rights, en passant and move counters, but
truncated them away before they reached the network. ShessGPT therefore can't "see" castling
rights; that information is simply not part of its input. The new encoding reproduces exactly
what the network was trained on. `tests/test_shessgpt_encoding.py` compares it with the
original code (kept in `tests/fixtures/old_encoding.py`) on 32 positions.

> If you ever retrain ShessGPT with a different input, change `encoding.py` and the oracle test
> together, and ship the new weights.

### The search (`search.py`)

ShessGPT looks **two half-moves** ahead (2-ply minimax):

```
for each of my moves M:
    for each opponent reply R:
        score(M, R) = network(position after M and R)
    worst(M) = the score of the reply that is best for the opponent
play the M with the best worst(M)
```

Scores are always from White's point of view, so White picks the maximum and Black the minimum.

Improvements over the original implementation, verified to pick the **same moves** in ordinary
positions:

- **Finished games are scored exactly** instead of asking the network: checkmate is ±1000, any
  draw is 0. ShessGPT therefore takes a mate in one, avoids stalemating when it is winning, and
  no longer crashes when a move leaves the opponent without legal replies. The old bot crashed
  in exactly that situation.
- **One batched forward pass.** All roughly 900 leaf positions go through the network as one
  matrix instead of 900 separate calls, about 10× faster (around 30 ms per move).
- **`torch.inference_mode()`** turns off gradient tracking.
- The search runs in a **worker thread** (`asyncio.to_thread`), so the bot keeps answering other
  commands while ShessGPT thinks.

## Stockfish (`cogs/chess/engines.py`)

- One Stockfish process starts when the bot starts and is reused. python-chess talks to it
  asynchronously via the UCI protocol. The old bot started a new process for every command and
  never stopped them.
- It thinks for `STOCKFISH_THINK_TIME` seconds (default 0.5) per request.
- If the process dies, it is restarted on the next request.
- If Stockfish is not installed, the bot logs a warning at startup, and `/chess eval` and
  `/chess hint` show ShessGPT's opinion only.

Install: `sudo pacman -S stockfish` (Arch) or `sudo apt install stockfish` (Debian/Ubuntu; the
binary lands in `/usr/games/stockfish`, which the server systemd unit includes in `PATH`).

## Game rules (`cogs/chess/session.py`)

`ChessSession` holds one game. It is pure Python (no Discord) and is tested in
`tests/test_chess_session.py`:

- **One game per text channel**, and only its player may move, undo or override. Players are
  identified by their Discord **user ID**; display names can be changed or faked.
- **Moves in SAN or UCI.** `parse_move` accepts `Nf3`, `O-O`, `e8=Q` as well as `g1f3`.
- **All game endings are detected** via python-chess's `board.outcome()`: checkmate, stalemate,
  insufficient material, the 75-move rule and fivefold repetition. The 75-move rule crashed the
  old bot.
- **`undo`** removes your last move and the reply. It refuses when there is nothing to undo.
- **`override`** replaces ShessGPT's last move. The position is restored if the new move is
  illegal.
- A per-game `asyncio.Lock` makes sure two quick `/chess move` commands can't interleave while
  ShessGPT is thinking.
