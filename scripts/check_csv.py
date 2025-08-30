#!/usr/bin/env python3
import csv, sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/powerball_history_full.csv")

def peek(path: Path, n_head=5, n_tail=5):
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    print("Header:", header)
    print("Total rows:", len(data))
    print("\nFirst rows:")
    for r in data[:n_head]:
        print(r)
    print("\nLast rows:")
    for r in data[-n_tail:]:
        print(r)

if __name__ == "__main__":
    if not path.exists():
        print("File not found:", path)
    else:
        peek(path)