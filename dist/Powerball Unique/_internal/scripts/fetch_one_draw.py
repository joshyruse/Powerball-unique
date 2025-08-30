#!/usr/bin/env python3
from __future__ import annotations
import csv, sys, re
from pathlib import Path
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup

PREV_RESULTS_URL = "https://www.powerball.com/previous-results"

DATE_NUMS_RE = re.compile(
    r'(?P<dow>Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+'
    r'(?P<mon>[A-Za-z]{3})\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})\s+'
    r'(?P<n1>\d{1,2})\s+(?P<n2>\d{1,2})\s+(?P<n3>\d{1,2})\s+(?P<n4>\d{1,2})\s+(?P<n5>\d{1,2})\s+'
    r'(?P<pb>\d{1,2})(?:\s+Power\s+Play\s+(?P<pp>\d+)x)?'
)
MONTHS = {m: i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1
)}

def parse_prev_results(text: str):
    for m in DATE_NUMS_RE.finditer(text):
        datestr = f"{m.group('dow')}, {m.group('mon')} {m.group('day')}, {m.group('year')}"
        d = datetime.strptime(datestr, "%a, %b %d, %Y").date()
        whites = sorted([int(m.group(f"n{i}")) for i in range(1,6)])
        pb = int(m.group("pb"))
        pp = m.group("pp") or ""
        yield d, whites, pb, pp

def fetch_one(dt: date):
    params = {"gc": "powerball", "sd": dt.isoformat(), "ed": dt.isoformat()}
    r = requests.get(PREV_RESULTS_URL, params=params, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    for d, whites, pb, pp in parse_prev_results(text):
        if d == dt and all(1 <= w <= 69 for w in whites) and 1 <= pb <= 26:
            url = f"{PREV_RESULTS_URL}?gc=powerball&sd={dt.isoformat()}&ed={dt.isoformat()}"
            return [d.isoformat(), *map(str, whites), str(pb), pp, url]
    return None

def append_row(csv_path: Path, row: list[str]):
    if not csv_path.exists():
        # write header + row
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date","w1","w2","w3","w4","w5","powerball","power_play","source_url"])
            w.writerow(row)
    else:
        # avoid duplicate date
        have = set()
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            next(r, None)
            for rr in r:
                if rr and rr[0]:
                    have.add(rr[0])
        if row[0] in have:
            print(f"Date {row[0]} already in CSV; not appending.")
            return
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(row)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/fetch_one_draw.py <csvfile> <YYYY-MM-DD>")
        sys.exit(2)
    csv_path = Path(sys.argv[1])
    dt = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    row = fetch_one(dt)
    if not row:
        print(f"No result found on Previous Results for {dt}")
        sys.exit(1)
    append_row(csv_path, row)
    print("Appended:", row)