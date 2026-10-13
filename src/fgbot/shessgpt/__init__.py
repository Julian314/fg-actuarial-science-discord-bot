"""ShessGPT: the neural-network chess engine from the original bot.

Typical use::

    net = load_net(Path("weights/ShessGPT_2_57.pth"))
    best = choose_move(net, board)       # ScoredMove(move=..., score=...)
    score = evaluate(net, board)         # > 0: White is better

The package has no Discord dependencies, so it can be used and tested on its own. See
``docs/chess-engine.md`` for how the input encoding and the search work.
"""

from fgbot.shessgpt.encoding import encode_position
from fgbot.shessgpt.model import ShessGPTNet, load_net
from fgbot.shessgpt.search import MATE_SCORE, ScoredMove, choose_move, evaluate

__all__ = [
    "MATE_SCORE",
    "ScoredMove",
    "ShessGPTNet",
    "choose_move",
    "encode_position",
    "evaluate",
    "load_net",
]
