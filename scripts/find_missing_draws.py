#!/usr/bin/env python3
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import date, timedelta

START = date(2015, 10, 7)
MON_START = date(2021, 8, 23)  # Mondays added

def is_scheduled_draw(d: date) -> bool:
    if d < START:
        return False
    if d >= MON_START:
        return d.weekday() in (0, 2, 5)  # Mon(0), Wed(2), Sat(5)
    else:
        return d.weekday() in (2, 5)

def read_dates(csv_path: Path) -> set[str]:
    got = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if row and row[0]:
                got.add(row[0])
    return got

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/find_missing_draws.py <csv>")
        sys.exit(2)
    p = Path(sys.argv[1])
    if not p.exists():
        print("CSV not found:", p)
        sys.exit(2)

    have = read_dates(p)
    today = date.today()
    missing = []
    d = START
    while d <= today:
        if is_scheduled_draw(d) and d.isoformat() not in have:
            missing.append(d.isoformat())
        d += timedelta(days=1)

    print(f"Total scheduled draws since {START}: {len(missing) + len(have)}")
    print(f"Missing: {len(missing)}")
    for m in missing[:200]:
        print(m)
    if len(missing) > 200:
        print("... (truncated)")

if __name__ == "__main__":
    main()