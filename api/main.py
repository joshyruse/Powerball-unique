from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
import sys
import csv
import random
from typing import Tuple
import subprocess
import threading
from datetime import datetime  # (not used yet but handy)

# ----- Ensure local package import (src/lotto) without editable install -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lotto.rules import PowerballRules

# ----- History loader & simple generator (local) -----
DrawTuple = Tuple[int, int, int, int, int, int]

def _load_history_set(csv_path: Path) -> set[DrawTuple]:
    s: set[DrawTuple] = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        _ = next(r, None)  # header
        for row in r:
            if not row or len(row) < 7:
                continue
            try:
                y1, y2, y3, y4, y5 = (int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5]))
                rb = int(row[6])
                s.add(tuple(sorted([y1, y2, y3, y4, y5]) + [rb]))
            except Exception:
                continue
    return s

class APIDraw(BaseModel):
    white: list[int]
    red: int

def generate_unique_draws(csv_path: Path, count: int, seed: int | None, rules: PowerballRules) -> list[APIDraw]:
    if seed is not None:
        random.seed(seed)
    history = _load_history_set(csv_path)
    out: list[APIDraw] = []
    attempts = 0
    max_attempts = count * 10000
    while len(out) < count and attempts < max_attempts:
        attempts += 1
        whites = sorted(random.sample(range(1, 70), 5))  # 1..69 inclusive
        red = random.randint(1, 26)                      # 1..26 inclusive
        key = tuple(whites + [red])
        if key in history:
            continue
        history.add(key)
        out.append(APIDraw(white=whites, red=red))
    return out

# ----- FastAPI app -----
app = FastAPI(title="Powerball Unique API")

# Static mounting
STATIC_DIR = PROJECT_ROOT / "api" / "static"
if STATIC_DIR.exists():
    # Serve assets at /static and keep API routes at root
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def root_html():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return PlainTextResponse("Powerball Unique API — static index.html missing", status_code=500)
else:
    @app.get("/", response_class=PlainTextResponse)
    def root():
        return "Powerball Unique API — try /generate?count=5&seed=42"

# ----- Data file resolver -----
SORTED_CSV = PROJECT_ROOT / "data" / "powerball_history_sorted.csv"
FULL_CSV = PROJECT_ROOT / "data" / "powerball_history_full.csv"

def _resolve_data_file() -> Path | None:
    if SORTED_CSV.exists():
        return SORTED_CSV
    if FULL_CSV.exists():
        return FULL_CSV
    return None

# Concurrency guard for refresh
_refresh_lock = threading.Lock()

def _read_latest(csv_path: Path) -> dict | None:
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            header = next(r, None)
            rows = list(r)
            if not rows:
                return None
            try:
                latest = max(rows, key=lambda row: row[0])  # YYYY-MM-DD sorts lexicographically
            except Exception:
                latest = rows[-1]
            return {
                "date": latest[0],
                "white": [int(latest[1]), int(latest[2]), int(latest[3]), int(latest[4]), int(latest[5])],
                "red": int(latest[6]) if len(latest) > 6 and latest[6] else None,
            }
    except FileNotFoundError:
        return None
    except Exception:
        return None

@app.post("/refresh")
def refresh():
    data_path = _resolve_data_file() or (PROJECT_ROOT / "data" / "powerball_history_full.csv")
    scripts_dir = PROJECT_ROOT / "scripts"
    scraper = scripts_dir / "scrape_powerball_official.py"

    if not scraper.exists():
        return JSONResponse(status_code=500, content={"error": "scraper not found", "path": str(scraper)})

    with _refresh_lock:
        before = 0
        try:
            if data_path.exists():
                with open(data_path, newline="", encoding="utf-8") as f:
                    before = sum(1 for _ in f) - 1
        except Exception:
            before = 0

        try:
            proc = subprocess.run(
                [sys.executable, str(scraper), str(data_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(PROJECT_ROOT),
                timeout=120,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return JSONResponse(status_code=504, content={"error": "scraper timeout after 120s"})

        if proc.returncode != 0:
            return JSONResponse(status_code=500, content={
                "error": "scraper failed",
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            })

        after = before
        try:
            if data_path.exists():
                with open(data_path, newline="", encoding="utf-8") as f:
                    after = sum(1 for _ in f) - 1
        except Exception:
            pass

        latest_info = _read_latest(data_path)
        return {
            "rows_added": max(0, after - before),
            "rows_before": max(0, before),
            "rows_after": max(0, after),
            "latest": latest_info,
            "stdout": proc.stdout[-1000:],
            "stderr": proc.stderr[-1000:],
        }

@app.get("/latest")
def latest():
    data_path = _resolve_data_file()
    if data_path is None:
        return JSONResponse(status_code=404, content={"error": "Data file not found"})
    info = _read_latest(data_path)
    if not info:
        return JSONResponse(status_code=404, content={"error": "No rows in data file"})
    return info

# ----- API endpoint -----
@app.get("/generate")
def generate(count: int = Query(5, ge=1, le=50), seed: int | None = None):
    data_path = _resolve_data_file()
    if data_path is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Data file not found",
                "expected": [str(SORTED_CSV), str(FULL_CSV)],
                "hint": "Run the desktop app's Refresh Data or place the CSV into the data/ folder."
            },
        )
    rules = PowerballRules()
    draws = generate_unique_draws(data_path, count=count, seed=seed, rules=rules)
    return [{"white": d.white, "red": d.red} for d in draws]