from __future__ import annotations
import csv
import re
from pathlib import Path
from typing import List, Set
from .rules import PowerballRules, WhiteCombo, PowerballDraw

# --- helpers (add these near the top) ---
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _ints_in(s: str) -> List[int]:
    return [int(x) for x in re.findall(r"\d+", s)]

def _looks_like_iso_date(s: str) -> bool:
    return bool(DATE_RE.match(s.strip()))

def _normalize_whites(nums: List[int]) -> WhiteCombo:
    arr = sorted(set(nums))
    if len(arr) != 5:
        raise ValueError("Need exactly 5 distinct white numbers")
    return tuple(arr)

# --- replace your load_history_csv with this ---
def load_history_csv(path: str | Path, rules: PowerballRules) -> Set[PowerballDraw]:
    """
    Reads past draws from CSV/TXT.

    Priority 1: If the row looks like our scraper format:
        date,w1,w2,w3,w4,w5,powerball,[power_play],[source_url]
    read those columns directly.

    Fallback: collect integers across the row (skipping ISO date tokens) and
    take the first 6 as (5 whites + 1 red).
    """
    draws: Set[PowerballDraw] = set()
    p = Path(path)

    with p.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        for row in r:
            if not row:
                continue

            # Prefer exact-column parsing when row[0] is ISO date
            if _looks_like_iso_date(row[0]):
                try:
                    whites = _normalize_whites([int(row[i]) for i in range(1, 6)])
                    red = int(row[6])
                    rules.validate(whites, red)
                    draws.add((whites, red))
                    continue
                except (ValueError, IndexError):
                    # fall back to generic parsing if row is malformed
                    pass

            # Generic parsing: pull ints from all cells, but ignore any ISO-date
            ints: List[int] = []
            for cell in row:
                if _looks_like_iso_date(cell):
                    continue
                ints.extend(_ints_in(cell))

            if len(ints) < 6:
                continue

            try:
                whites = _normalize_whites(ints[:5])
                red = ints[5]
                rules.validate(whites, red)
                draws.add((whites, red))
            except ValueError:
                # Skip rows that don't match Powerball ranges/format
                continue

    return draws