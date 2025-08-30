#!/usr/bin/env python3
import csv
from pathlib import Path
import sys
from datetime import datetime

def sort_csv(path: Path, descending: bool = True):
    with path.open("r", encoding="utf-8", newline="") as f:
        r = list(csv.reader(f))
    header, rows = r[0], r[1:]

    # sort rows by first column (date), descending by default
    rows.sort(key=lambda row: datetime.fromisoformat(row[0]), reverse=descending)

    out_path = path.with_name(path.stem + "_sorted.csv")
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    print(f"Sorted file written to {out_path} (rows={len(rows)})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/sort_csv.py <csvfile>")
        sys.exit(1)
    sort_csv(Path(sys.argv[1]))