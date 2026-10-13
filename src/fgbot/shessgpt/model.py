"""The ShessGPT neural network: a plain multi-layer perceptron that scores a chess position.

The network maps the 770 input features of ``encoding.encode_position`` to a single number:
positive means White is better, negative means Black is better.

Architecture (identical to ``NeuralNetwork_corrected`` of the original bot, so the trained
weights load unchanged)::

    770 → 512 → 256 → 128 → 64 → 32 → 16 → 1     (ReLU between layers, none after the last)
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import torch
from torch import nn

LAYER_SIZES = (770, 512, 256, 128, 64, 32, 16, 1)


class ShessGPTNet(nn.Module):
    """Fully connected network with ReLU activations.

    The layers live in ``self.seq`` because the saved weights use the key names
    ``seq.0.weight``, ``seq.2.weight``, … (the odd indices are the ReLUs).
    """

    def __init__(self, layer_sizes: tuple[int, ...] = LAYER_SIZES) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        for size_in, size_out in pairwise(layer_sizes):
            layers += [nn.Linear(size_in, size_out), nn.ReLU()]
        layers.pop()  # no activation after the output layer: the score may be negative
        self.seq = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.seq(x)


def load_net(weights_path: Path) -> ShessGPTNet:
    """Create the network, load the trained weights and switch it to inference mode."""
    net = ShessGPTNet()
    state = torch.load(weights_path, map_location="cpu", weights_only=True)
    net.load_state_dict(state, strict=True)
    net.eval()
    return net
