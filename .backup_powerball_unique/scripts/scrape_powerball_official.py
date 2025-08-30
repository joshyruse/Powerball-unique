#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE = "https://www.powerball.com/draw-result"
START = date(2015, 10, 7)      # first draw under current 5/69 + 1/26 rules
MON_START = date(2021, 8, 23)  # Monday drawings added (Mon/Wed/Sat)
SLEEP_SEC = 0.25
TIMEOUT_SEC = 15

# Parse the page's displayed header like: "Wed, Oct 07, 2015"
PAGE_DATE_RE = re.compile(
    r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})\b'
)

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1
)}

# Find all integers on the page (we'll validate via ranges)
RE_INT = re.compile(r"\b(\d{1,2})\b")

def is_scheduled_draw(d: date) -> bool:
    """Powerball draw schedule since Oct 2015:
       - Wed/Sat until 2021-08-21
       - Mon/Wed/Sat starting 2021-08-23
    """
    if d < START:
        return False
    if d >= MON_START:
        return d.weekday() in (0, 2, 5)  # Mon(0), Wed(2), Sat(5)
    else:
        return d.weekday() in (2, 5)     # Wed(2), Sat(5)

def parse_page_date(soup: BeautifulSoup) -> Optional[date]:
    """Extract the displayed draw date from the page, if present."""
    text = soup.get_text(separator=" ", strip=True)
    m = PAGE_DATE_RE.search(text)
    if not m:
        return None
    mon_short = m.group(2)
    day = int(m.group(3))
    year = int(m.group(4))
    mon = MONTHS.get(mon_short)
    if not mon:
        return None
    try:
        return date(year, mon, day)
    except ValueError:
        return None

def fetch_draw(session: requests.Session, dt: date) -> Optional[Tuple[str, List[int], int, str]]:
    """Return (iso_date, whites_sorted[5], red, source_url) if the page truly
       contains the requested date's draw under current rules. Otherwise None.
    """
    if not is_scheduled_draw(dt):
        return None

    iso = dt.isoformat()
    url = f"{BASE}?gc=powerball&date={iso}"

    try:
        resp = session.get(url, timeout=TIMEOUT_SEC)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) Verify the page's displayed date matches the date we asked for.
    page_dt = parse_page_date(soup)
    if page_dt != dt:
        # This happens when you ask for a non-draw date and the site shows the latest draw instead.
        return None

    # 2) Pull all small integers from the page and look for a valid 5-whites + 1-red window.
    nums = [int(x) for x in RE_INT.findall(soup.get_text(separator=" "))]
    if len(nums) < 6:
        return None

    whites = None
    red = None
    for i in range(len(nums) - 5):
        w = nums[i:i+5]
        r = nums[i+5]
        if len(set(w)) == 5 and all(1 <= n <= 69 for n in w) and (1 <= r <= 26):
            whites = sorted(w)
            red = r
            break

    if whites is None or red is None:
        return None

    return (iso, whites, red, url)

def scrape(out_csv: Path, resume: bool = True) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    out_exists = out_csv.exists()
    seen_dates = set()
    if out_exists and resume:
        with out_csv.open("r", newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            _ = next(r, None)
            for row in r:
                if row:
                    seen_dates.add(row[0])

    session = requests.Session()

    # Build just the scheduled draw dates from START..today
    today = date.today()
    dates: List[date] = []
    d = START
    while d <= today:
        if is_scheduled_draw(d) and d.isoformat() not in seen_dates:
            dates.append(d)
        d += timedelta(days=1)

    added = 0
    mode = "a" if out_exists else "w"
    with out_csv.open(mode, newline="", encoding="utf-8") as f, \
         tqdm(total=len(dates), desc="Scraping scheduled draws", unit="draw") as pbar:
        w = csv.writer(f)
        if not out_exists:
            w.writerow(["date","w1","w2","w3","w4","w5","powerball","power_play","source_url"])

        for dt in dates:
            info = fetch_draw(session, dt)
            if info:
                iso, whites, red, url = info
                w.writerow([iso, *whites, red, "", url])
                added += 1
            pbar.update(1)
            pbar.set_postfix({"added": added, "last_date": dt.isoformat()})
            time.sleep(SLEEP_SEC)

    print(f"\nDone. Added {added} rows to {out_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/scrape_powerball_official.py <out_csv>")
        sys.exit(2)
    out_path = Path(sys.argv[1])
    scrape(out_path, resume=True)