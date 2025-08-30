from __future__ import annotations
import random
from math import comb
from typing import List, Set
from .rules import PowerballRules, WhiteCombo, PowerballDraw

def total_space(r: PowerballRules) -> int:
    """Total number of possible Powerball draws."""
    return comb(r.white_pool, r.white_count) * r.red_pool

def _random_whites(r: PowerballRules) -> WhiteCombo:
    picks = random.sample(range(1, r.white_pool + 1), k=r.white_count)
    picks.sort()
    return tuple(picks)

def _random_draw(r: PowerballRules) -> PowerballDraw:
    whites = _random_whites(r)
    red = random.randint(1, r.red_pool)
    return (whites, red)

def generate_unique(
    history: Set[PowerballDraw],
    rules: PowerballRules,
    count: int = 5,
    seed: int | None = None,
    max_tries_per_pick: int = 500_000,
) -> List[PowerballDraw]:
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()  # reseed from system time / OS entropy

    universe = total_space(rules)
    if len(history) >= universe:
        raise RuntimeError("History already covers the full sample space")

    results: List[PowerballDraw] = []
    seen = set(history)
    tries = 0

    while len(results) < count:
        if tries > max_tries_per_pick:
            raise RuntimeError("Too many tries to find a new unique draw")
        cand = _random_draw(rules)
        tries += 1
        if cand not in seen:
            results.append(cand)
            seen.add(cand)
            tries = 0
    return results