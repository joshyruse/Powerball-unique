#!/usr/bin/env python3
from __future__ import annotations
import random
import argparse
# allow running directly without editable install
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]  # project root
sys.path.insert(0, str(ROOT / "src"))
from lotto.rules import PowerballRules
from lotto.history import load_history_csv
from lotto.generate import generate_unique, total_space

def _latest_date_in_history(path: str) -> str | None:
    import csv
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return None
    last_date = None
    with p.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r, None)  # header
        for row in r:
            if row and row[0]:
                last_date = row[0]
    return last_date

def main():
    ap = argparse.ArgumentParser(description="Generate Powerball draws never seen in history.")
    ap.add_argument("--file", required=True, help="CSV file with past Powerball results")
    ap.add_argument("--count", type=int, default=5, help="How many new draws to produce")
    ap.add_argument("--seed", type=int, default=None, help="Optional RNG seed for reproducibility")
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    rules = PowerballRules()
    history = load_history_csv(args.file, rules)
    latest = _latest_date_in_history(args.file)
    if latest:
        print(f"Latest draw in file: {latest}")
    universe = total_space(rules)
    print(f"Loaded {len(history)} historical draws. Total space: {universe:,}. "
          f"Coverage: {len(history)/universe:.6%}")

    new_picks = generate_unique(history, rules, count=args.count, seed=args.seed)
    print("\nNew unique draws (whites | PB):")
    for whites, red in new_picks:
        print(f"{' '.join(f'{w:02d}' for w in whites)} | {red:02d}")

if __name__ == "__main__":
    main()