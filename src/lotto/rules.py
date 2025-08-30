from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

WhiteCombo = Tuple[int, ...]            # a sorted 5-tuple of white numbers
PowerballDraw = Tuple[WhiteCombo, int]  # (whites, red)

@dataclass(frozen=True)
class PowerballRules:
    white_count: int = 5
    white_pool: int = 69
    red_pool: int = 26

    def validate(self, whites: WhiteCombo, red: int) -> None:
        """Check that whites and red match Powerball rules."""
        if len(whites) != self.white_count:
            raise ValueError("Must pick exactly 5 white balls")
        if len(set(whites)) != len(whites):
            raise ValueError("Duplicate numbers in white balls")
        if not all(1 <= w <= self.white_pool for w in whites):
            raise ValueError("White ball out of range (1-69)")
        if not (1 <= red <= self.red_pool):
            raise ValueError("Powerball out of range (1-26)")