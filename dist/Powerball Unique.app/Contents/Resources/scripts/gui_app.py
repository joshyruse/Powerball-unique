#!/usr/bin/env python3
from datetime import datetime, timedelta
import sys
import random
import csv
import subprocess, os

from pathlib import Path
import subprocess, os
import fcntl  # POSIX file locking for single-instance guard
from pathlib import Path
from datetime import datetime, timedelta
import sys
import random
import csv
import subprocess, os
import time  # <-- add this
import tkinter as tk
from tkinter import ttk, font as tkfont
import traceback
from datetime import datetime as _dt
_EARLY_LOG = Path.home() / "PowerballUnique_early.log"

# --- Early logger used before APP_DATA exists ---
def _log_window_event(kind: str, note: str = ""):
    """Early logger used before APP_DATA exists; writes to home file."""
    try:
        with _EARLY_LOG.open("a", encoding="utf-8") as lf:
            lf.write(f"\n[{_dt.now().strftime('%Y-%m-%d %H:%M:%S')}] {kind} {note}\n")
            lf.writelines(traceback.format_stack(limit=14))
            lf.write("\n")
    except Exception:
        pass
# ---- Prevent accidental extra Tk root windows (e.g., from third-party libs) ----
# In some frozen builds, a module may inadvertently call tk.Tk() again.
# Strengthen: destroy any *secondary* Tk() root immediately to avoid Dock window on macOS.
# Wrap Tk.__init__ instead of replacing Tk itself so subclassing (class App(tk.Tk)) still works.
_ORIG_TK_INIT = tk.Tk.__init__
_singleton_created = {"v": False}

def _tk_init_singleton(self, *args, **kwargs):
    # Initialize the Tk root as usual
    _log_window_event("Tk.__init__ called")
    _ORIG_TK_INIT(self, *args, **kwargs)
    if _singleton_created["v"]:
        _log_window_event("Secondary Tk detected — destroying")
        try:
            try:
                self.withdraw()
                self.update_idletasks()
            except Exception:
                pass
            self.destroy()
        except Exception:
            pass
        return
    else:
        _singleton_created["v"] = True
        # Ensure messagebox and other modules use this as the default root
        try:
            import tkinter as _tk
            _tk._default_root = self
        except Exception:
            pass

# Monkey-patch Tk.__init__ globally (safe for subclassing)

tk.Tk.__init__ = _tk_init_singleton  # type: ignore[assignment]

# ---- Kill any unexpected Toplevels (some frozen envs may spawn one) ----
_ORIG_TOPLEVEL_INIT = tk.Toplevel.__init__

def _toplevel_autodestroy(self, *args, **kwargs):
    # Initialize the Toplevel (some libs insist on creating it)
    _log_window_event("Toplevel.__init__ called")
    _ORIG_TOPLEVEL_INIT(self, *args, **kwargs)
    try:
        _log_window_event("Destroying unexpected Toplevel")
        self.withdraw()
        try:
            self.update_idletasks()
        except Exception:
            pass
        self.destroy()
    except Exception:
        pass

# Monkey‑patch Toplevel.__init__ globally — safe because our app no longer uses Toplevel dialogs
# (All messages are inline; no filedialog/messagebox is used.)
tk.Toplevel.__init__ = _toplevel_autodestroy  # type: ignore[assignment]

# hint PyInstaller to bundle scraper deps
try:
    import requests  # type: ignore
    import bs4       # type: ignore
    import lxml      # type: ignore
    import tqdm      # type: ignore
except Exception:
    pass


# -------- UI helpers (rounded buttons & balls) --------
class RoundButton(tk.Canvas):
    def __init__(self, master, text, command, bg, fg, radius=14, padx=18, pady=10, font_family="Calibri", **kw):
        parent_bg = master.winfo_toplevel().cget("background")
        super().__init__(master, highlightthickness=0, bg=parent_bg, bd=0, **kw)
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._radius = radius
        self._padx = padx
        self._pady = pady
        # prefer Calibri, gracefully fallback
        fams = set(tkfont.families())
        if font_family in fams:
            self._font = tkfont.Font(family=font_family, size=13, weight="bold")
        else:
            self._font = tkfont.Font(family="Helvetica", size=13, weight="bold")
        self._redraw()
        self.bind("<Button-1>", lambda e: self._on_click())
        self.bind("<Enter>", lambda e: self.configure(cursor="hand2"))
        self.bind("<Leave>", lambda e: self.configure(cursor=""))

    def _on_click(self):
        if callable(self._command):
            self._command()

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, splinesteps=36, **kw)

    def _redraw(self):
        tw = self._font.measure(self._text)
        th = self._font.metrics("linespace")
        w = tw + self._padx * 2
        h = th + self._pady * 2
        self.configure(width=w, height=h)
        self.delete("all")
        self._round_rect(1, 1, w-1, h-1, self._radius, fill=self._bg, outline="")
        self.create_text(w//2, h//2, text=self._text, fill=self._fg, font=self._font)


# --- Composite widget: rounded stepper control ---
class CountStepper(tk.Canvas):
    """A single rounded control: [-] [ value entry ] [+] inside one rounded border."""
    def __init__(self, master, var: tk.IntVar, minv=1, maxv=100, width=200, height=40, **kw):
        parent_bg = master.winfo_toplevel().cget("background")
        super().__init__(master, highlightthickness=0, bg=parent_bg, bd=0, width=width, height=height, **kw)
        self.var = var
        self.minv = minv
        self.maxv = maxv
        self._radius = 12
        self._padx = 12  # bring +/- inward slightly
        self._bg = "#FFFFFF"
        self._fg = "#111111"
        self._border = "#111111"
        self._font = tkfont.Font(family="Helvetica", size=14, weight="bold")  # +/- size
        self._entry_font = tkfont.Font(family="Helvetica", size=13)             # entry text

        # draw rounded border
        self._draw_outline()
        # minus/plus button shapes + labels (grouped by tags for hover/click)
        self.minus_box = self.create_rectangle(0, 0, 0, 0, outline=self._border, fill=self._bg, width=0,
                                               tags=("btn_minus",))
        self.plus_box = self.create_rectangle(0, 0, 0, 0, outline=self._border, fill=self._bg, width=0,
                                              tags=("btn_plus",))
        self.minus_id = self.create_text(0, 0, text="-", fill=self._fg, font=self._font, tags=("btn_minus",))
        self.plus_id = self.create_text(0, 0, text="+", fill=self._fg, font=self._font, tags=("btn_plus",))

        # entry field embedded (center)
        self.entry = ttk.Entry(self, textvariable=self.var, width=10, justify="center")
        self.entry_id = self.create_window(0, 0, window=self.entry)
        self.entry.bind("<FocusOut>", lambda e: self._clamp())
        self.entry.bind("<Return>", lambda e: (self._clamp(), self.focus()))
        self.entry.bind("<FocusIn>",  lambda e: self._focus(True))
        self.entry.bind("<FocusOut>", lambda e: self._focus(False))

        # clicks / hover for buttons
        for tag, cb in (("btn_minus", self._dec), ("btn_plus", self._inc)):
            self.tag_bind(tag, "<Button-1>", lambda e, f=cb: f())
            self.tag_bind(tag, "<Enter>", lambda e, t=tag: self._hover(t, True))
            self.tag_bind(tag, "<Leave>", lambda e, t=tag: self._hover(t, False))
        self.bind("<Configure>", self._layout)
        self._layout()

    def _draw_outline(self):
        self.delete("outline")
        w = int(self["width"]) if str(self["width"]).isdigit() else self.winfo_width()
        h = int(self["height"]) if str(self["height"]).isdigit() else self.winfo_height()
        # main rounded rect
        r = self._radius
        x1, y1, x2, y2 = 1, 1, max(2, w-2), max(2, h-2)
        # background fill
        self.create_rectangle(x1, y1, x2, y2, outline="", fill=self._bg, tags=("outline",))
        # border path using polygon for smoother corners
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1,
        ]
        self._outline_id = self.create_polygon(points, smooth=True, splinesteps=36, outline=self._border, fill="", width=2, tags=("outline",))
    def _focus(self, on: bool):
        try:
            if on:
                # Powerball red glow on focus
                self.itemconfigure(self._outline_id, outline="#D0021B", width=3)
            else:
                self.itemconfigure(self._outline_id, outline=self._border, width=2)
        except Exception:
            pass

    def _hover(self, tag, on):
        fill = "#F2F2F2" if on else self._bg
        if tag == "btn_minus":
            self.itemconfigure(self.minus_box, fill=fill)
        elif tag == "btn_plus":
            self.itemconfigure(self.plus_box, fill=fill)
        self.configure(cursor="hand2" if on else "")

    def _layout(self, event=None):
        self._draw_outline()
        w = self.winfo_width()
        h = self.winfo_height()
        cy = h // 2
        btn_w = 38                         # button width
        btn_h = max(28, h - 10)            # inset height
        pad   = self._padx                 # side padding to pull buttons inward
        # minus box coords
        mx1, my1 = pad, (h - btn_h) // 2
        mx2, my2 = mx1 + btn_w, my1 + btn_h
        self.coords(self.minus_box, mx1, my1, mx2, my2)
        self.coords(self.minus_id, (mx1+mx2)//2, cy)
        # plus box coords
        px2, py2 = w - pad, my2
        px1, py1 = px2 - btn_w, my1
        self.coords(self.plus_box, px1, py1, px2, py2)
        self.coords(self.plus_id, (px1+px2)//2, cy)
        # compute and set entry window width so more digits are visible
        entry_w = max(96, w - (btn_w*2 + pad*2 + 16))
        self.entry.configure(font=self._entry_font)
        self.coords(self.entry_id, w//2, cy)
        self.itemconfigure(self.entry_id, width=entry_w, height=btn_h-6)
        # ensure buttons draw above the entry
        self.tag_raise("btn_minus")
        self.tag_raise("btn_plus")

    def _clamp(self):
        try:
            v = int(self.var.get())
        except Exception:
            v = self.minv
        v = max(self.minv, min(self.maxv, v))
        self.var.set(v)

    def _dec(self):
        self._clamp()
        self.var.set(max(self.minv, int(self.var.get()) - 1))

    def _inc(self):
        self._clamp()
        self.var.set(min(self.maxv, int(self.var.get()) + 1))


def draw_powerball_logo(canvas: tk.Canvas, x: int, y: int, scale: float = 1.0):
    """Draw POWER (white balls with black letters) + BALL (white text in red ball).
    Returns the rightmost x coordinate after drawing, so caller can place trailing text.
    """
    RED   = "#D0021B"; BLACK = "#111111"; WHITE = "#FFFFFF"
    letters = ["P","O","W","E","R"]
    r = int(22*scale)
    gap = int(8*scale)
    cx = x
    # five white balls with letters
    for ch in letters:
        canvas.create_oval(cx, y, cx+2*r, y+2*r, fill=WHITE, outline=BLACK, width=2)
        font = tkfont.Font(family="Helvetica", size=int(14*scale), weight="bold")
        canvas.create_text(cx+r, y+r, text=ch, fill=BLACK, font=font)
        cx += 2*r + gap
    # one red ball with "BALL" (perfect circle)
    canvas.create_oval(cx, y, cx+2*r, y+2*r, fill=RED, outline=BLACK, width=2)
    # choose a slightly smaller font so "BALL" fits inside the circle
    font2 = tkfont.Font(family="Helvetica", size=max(10, int(11*scale)), weight="bold")
    canvas.create_text(cx + r, y + r, text="BALL", fill=WHITE, font=font2)
    return int(cx + 2*r)


def draw_balls_row(canvas: tk.Canvas, x: int, y: int, whites, red, scale: float = 1.0):
    RED   = "#D0021B"; BLACK = "#111111"; WHITE = "#FFFFFF"
    r = int(14*scale)
    gap = int(8*scale)
    cx = x
    for n in whites:
        canvas.create_oval(cx, y, cx+2*r, y+2*r, fill=WHITE, outline=BLACK, width=2)
        font = tkfont.Font(family="Helvetica", size=int(12*scale), weight="bold")
        canvas.create_text(cx+r, y+r, text=f"{n:02d}", fill=BLACK, font=font)
        cx += 2*r + gap
    # red ball
    canvas.create_oval(cx, y, cx+2*r, y+2*r, fill=RED, outline=BLACK, width=2)
    fontR = tkfont.Font(family="Helvetica", size=int(12*scale), weight="bold")
    canvas.create_text(cx+r, y+r, text=f"{red:02d}", fill=WHITE, font=fontR)
    return int(cx + 2*r)


# --- project paths ---
def _app_root() -> Path:
    # when frozen by PyInstaller, sys._MEIPASS points to the bundled temp dir
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))

ROOT = _app_root()
def app_data_dir() -> Path:
    """Return the writable per-user data folder for this app."""
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "Powerball Unique"
    elif os.name == "nt":
        d = Path(os.getenv("APPDATA", "~")).expanduser() / "Powerball Unique"
    else:
        d = Path.home() / ".local" / "share" / "powerball_unique"
    d.mkdir(parents=True, exist_ok=True)
    return d

APP_DATA = app_data_dir()
DEBUG_LOG = APP_DATA / "debug_windows.log"
# --- Bounce guard: prevent immediate relaunch after quitting ---
_BOUNCE_FILE = APP_DATA / "last_exit"

# --- Final logger (overrides early logger) writing to app support. ---
def _log_window_event(kind: str, note: str = ""):
    """Final logger (overrides early logger) writing to app support."""
    try:
        with DEBUG_LOG.open("a", encoding="utf-8") as lf:
            lf.write(f"\n[{_dt.now().strftime('%Y-%m-%d %H:%M:%S')}] {kind} {note}\n")
            lf.writelines(traceback.format_stack(limit=14))
            lf.write("\n")
    except Exception:
        pass

# --- Single-instance guard (prevents second bundled app window) ---
# (keep only one global; do not duplicate this elsewhere)
_instance_lock_fh = None  # keep handle alive for the lifetime of the process

# --- Bounce guard: prevent immediate relaunch after quitting ---
_BOUNCE_FILE = APP_DATA / "last_exit"

def _bounce_guard_check():
    """Exit immediately if app was closed in the last ~3 seconds (prevents auto-reopen loops)."""
    try:
        if _BOUNCE_FILE.exists():
            ts = float(_BOUNCE_FILE.read_text(encoding="utf-8").strip() or 0.0)
            if time.time() - ts < 3.0:
                _log_window_event("startup: bounce detected — exiting")
                os._exit(0)
    except Exception:
        pass

def _bounce_mark_exit():
    try:
        _BOUNCE_FILE.write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass

def _acquire_single_instance_lock():
    """Try to acquire an exclusive, non-blocking lock on a file in APP_DATA.
    If the lock cannot be acquired, another instance is running; exit quietly.
    """
    global _instance_lock_fh
    try:
        lock_path = APP_DATA / "app.lock"
        _instance_lock_fh = open(lock_path, "w")
        try:
            fcntl.flock(_instance_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _log_window_event("single-instance: lock busy — exiting")
            os._exit(0)
        try:
            _instance_lock_fh.truncate(0)
            _instance_lock_fh.write(str(os.getpid()))
            _instance_lock_fh.flush()
        except Exception:
            pass
    except Exception as e:
        _log_window_event("single-instance: lock setup failed", note=str(e))

# CSVs live in the writable user folder
BASE_CSV   = APP_DATA / "powerball_history_full.csv"
SORTED_CSV = APP_DATA / "powerball_history_full_sorted.csv"
DATA_PATH  = SORTED_CSV  # GUI reads the sorted file

# --- Helper: Save generated picks to CSV in app data dir ---
PICKS_CSV = APP_DATA / "generated_picks.csv"

def format_pick(whites, red) -> str:
    return f"{' '.join(f'{n:02d}' for n in whites)}  |  PB {red:02d}"

def append_picks_to_csv(picks, latest_date: str):
    """Append generated picks to PICKS_CSV with a timestamp and latest draw reference."""
    PICKS_CSV.parent.mkdir(parents=True, exist_ok=True)
    new_file = not PICKS_CSV.exists()
    with PICKS_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "latest_draw", "w1","w2","w3","w4","w5","powerball"])  # header
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for whites, red in picks:
            w.writerow([ts, latest_date, *whites, red])

# Scraper script still comes from bundled resources
SCRAPER = ROOT / "scripts" / "scrape_powerball_official.py"

# Import your existing modules
# ensure we can import from src/ even if editable install isn't present
sys.path.insert(0, str(ROOT / "src"))
from lotto.rules import PowerballRules
from lotto.history import load_history_csv
from lotto.generate import generate_unique


def latest_date_in_csv(path: Path) -> str | None:
    if not path.exists():
        return None
    last = None
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r, None)  # header
        for row in r:
            if row and row[0]:
                last = row[0]
    return last


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    rows = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r, None)  # header
        for _ in r:
            rows += 1
    return rows


def sort_csv_desc(in_path: Path, out_path: Path) -> None:
    if not in_path.exists():
        return
    with in_path.open("r", encoding="utf-8", newline="") as f:
        r = list(csv.reader(f))
    if not r:
        return
    header, rows = r[0], r[1:]
    rows.sort(key=lambda row: row[0], reverse=True)  # ISO dates sort lexicographically
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def latest_date_in_sorted(path: Path) -> str | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        first = next(r, None)
        if first and first[0]:
            return first[0]
    return None


# Ensure scraper dependencies are available in the current interpreter
def _ensure_scraper_deps():
    missing = []
    for mod in ("requests", "bs4", "lxml", "tqdm"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        raise RuntimeError(
            "Missing Python packages for scraper: " + ", ".join(missing) +
            "\n\nActivate your venv and install them:\n  "
            f"{sys.executable} -m pip install " + " ".join(missing)
        )

def _pick_python_for_scraper():
    return None


def run_scraper():

    os.environ.setdefault("TQDM_DISABLE", "1")  # ensure no tqdm GUI tries to spawn in frozen app
    """
    Run the scraper *in-process* by importing its `scrape` function and calling it.
    This avoids spawning a second app window and avoids manipulating `__main__`.
    """
    # Validate deps present in this interpreter
    for mod in ("requests", "bs4", "lxml", "tqdm"):
        try:
            __import__(mod)
        except Exception as e:
            raise RuntimeError(
                f"Missing Python package '{mod}' required by the scraper.\n"
                "If running the .app, it should be bundled; otherwise install in your venv:\n"
                f"  {sys.executable} -m pip install requests beautifulsoup4 lxml tqdm"
            ) from e

    from datetime import datetime, timedelta
    import runpy

    # Compute incremental start date = (latest in sorted) + 1 day
    latest = latest_date_in_sorted(SORTED_CSV)
    since_arg = None
    if latest:
        try:
            d = datetime.strptime(latest, "%Y-%m-%d").date() + timedelta(days=1)
            since_arg = d.strftime("%Y-%m-%d")
        except Exception:
            since_arg = None

    # Load the scraper module namespace without touching __main__
    ns = runpy.run_path(str(SCRAPER), run_name="__scraper__")
    scrape_func = ns.get("scrape")
    if not callable(scrape_func):
        raise RuntimeError("Scraper entry function 'scrape' not found in scrape_powerball_official.py")

    # Call scraper directly (Path, resume=True, since=since_arg)
    scrape_func(BASE_CSV, True, since_arg)

class CanvasScrollbar(tk.Canvas):
    """A slim, theme-agnostic vertical scrollbar drawn on a Canvas.
    Works with a target widget that supports xview/yview (we'll use yview with a Canvas).
    """
    def __init__(self, master, command, width=8, margin=2, track_color="#FFFFFF", thumb_color="#D0021B"):
        super().__init__(master, width=width, highlightthickness=0, bg=track_color, bd=0)
        self._command = command          # e.g., target_canvas.yview
        self._margin = margin
        self._thumb_color = thumb_color
        self._thumb = None
        self._press_y = None
        self._start_frac = 0.0
        self._end_frac = 1.0
        self._dragging = False

        # events
        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    # this method matches the signature expected by yscrollcommand (lo, hi)
    def set(self, lo, hi):
        try:
            self._start_frac = float(lo)
            self._end_frac = float(hi)
        except Exception:
            self._start_frac, self._end_frac = 0.0, 1.0
        self._redraw()

    def _redraw(self, event=None):
        # clear any previous thumb by tag
        self.delete("thumb")
        h = self.winfo_height()
        w = self.winfo_width()
        if h <= 0:
            return
        # convert fractions to pixels
        top = int(self._start_frac * h)
        bottom = int(self._end_frac * h)
        # enforce a minimum thumb size for usability
        min_size = max(24, int(0.06 * h))
        if bottom - top < min_size:
            bottom = top + min_size
            if bottom > h:
                bottom = h
                top = max(0, h - min_size)
        x1 = self._margin
        x2 = max(self._margin + 3, w - self._margin)
        self._thumb = self.create_rounded_rect(
            x1, top + 2, x2, bottom - 2, r=4,
            fill=self._thumb_color, outline="", tags=("thumb",)
        )
        # allow clicking on the thumb to start drag
        self.tag_bind("thumb", "<Button-1>", self._on_press)

    def create_rounded_rect(self, x1, y1, x2, y2, r=6, **kw):
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, splinesteps=36, **kw)

    def _on_press(self, event):
        self._dragging = True
        self._press_y = event.y
        self._press_start_frac = self._start_frac
        self._press_end_frac = self._end_frac

    def _on_drag(self, event):
        if not self._dragging:
            return
        h = max(1, self.winfo_height())
        delta_frac = float(event.y - self._press_y) / h
        # move by the size of the thumb proportionally
        thumb_span = max(0.0001, self._press_end_frac - self._press_start_frac)
        new_start = min(1.0 - thumb_span, max(0.0, self._press_start_frac + delta_frac))
        new_end = new_start + thumb_span
        # scroll target
        if callable(self._command):
            # yview_moveto expects a fraction from 0 to 1
            self._command("moveto", new_start)

    def _on_release(self, event):
        self._dragging = False

class App(tk.Tk):
    def _on_quit(self):
        try:
            self._cleanup_ghost_windows()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        _bounce_mark_exit()
        os._exit(0)
    def __init__(self):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.title("Powerball Unique Generator")
        self.geometry("860x620")
        self.grid_rowconfigure(4, weight=1)

        # --- scaling & colors ---
        try:
            # subtle HiDPI scaling
            self.call("tk", "scaling", 1.3)
        except Exception:
            pass
        RED   = "#D0021B"
        BLACK = "#111111"
        WHITE = "#FFFFFF"
        GRAY  = "#F5F5F7"
        ACCENT= RED

        # --- ttk theme & styles ---
        style = ttk.Style(self)
        try:
            style.theme_use("clam")  # allows background/foreground styling cross‑platform
        except Exception:
            try:
                style.theme_use("alt")
            except Exception:
                pass

        # Header section
        self.configure(bg="#FFFFFF")
        style.configure("TFrame", background="#FFFFFF")
        style.configure("TLabel", background="#FFFFFF", foreground=BLACK, font=("Helvetica", 12))
        style.configure("Header.TLabel", background="#FFFFFF", foreground=BLACK, font=("Helvetica", 22, "bold"))
        style.configure("Info.TLabel", background="#FFFFFF", foreground=BLACK, font=("Helvetica", 12))

        # Modern red scrollbars
        style.configure(
            "Modern.Vertical.TScrollbar",
            background="#D0021B",
            troughcolor="#FFFFFF",
            bordercolor="#FFFFFF",
            lightcolor="#FFFFFF",
            darkcolor="#FFFFFF",
            arrowsize=10
        )
        style.map("Modern.Vertical.TScrollbar",
                  background=[("!disabled", "#D0021B")])

        header = ttk.Frame(self, padding=(16, 16, 16, 16))
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        # POWER(BALL) logo + "Generator"
        logo = tk.Canvas(header, width=760, height=120, bg="#FFFFFF", highlightthickness=0)
        logo.grid(row=0, column=0, sticky="w")
        start_x, start_y = 8, 10
        scale = 1.3
        right_x = draw_powerball_logo(logo, start_x, start_y, scale=scale)
        r = int(22 * scale)
        # Bottom of the balls row (circle bottom); nudge up a hair so text optical baseline matches ball bottom
        baseline_y = start_y + 2 * r - 2
        # Make the title almost as tall as a ball (about 85% of ball diameter)
        gen_size = max(24, int(0.85 * (2 * r)))
        logo.create_text(right_x + 22, baseline_y, anchor="sw",
                         text="Generator", fill=RED, font=("Helvetica", gen_size, "bold"))

        self.status = tk.StringVar(value="Ready.")
        style.configure("StatusRed.TLabel", background="#FFFFFF", foreground="#D0021B", font=("Helvetica", 12))
        ttk.Label(self, textvariable=self.status, style="StatusRed.TLabel", padding=(16, 4)).grid(row=1, column=0, sticky="w")

        # Controls row
        controls = ttk.Frame(self, padding=(16, 8))
        controls.grid(row=2, column=0, sticky="ew")
        controls.grid_columnconfigure(10, weight=1)

        self.count_var = tk.IntVar(value=5)
        self.seed_var  = tk.StringVar(value="")

        rb1 = RoundButton(controls, text="Refresh Data", command=self.on_refresh_data, bg="#D0021B", fg="#FFFFFF")
        rb1.grid(row=0, column=0, padx=(0,8), pady=4)
        rb2 = RoundButton(controls, text="Open CSV", command=self.on_open_csv, bg="#D0021B", fg="#FFFFFF")
        rb2.grid(row=0, column=1, padx=(0,8), pady=4)

        # Generation controls (second row)
        gen_controls = ttk.Frame(self, padding=(16, 4))
        gen_controls.grid(row=3, column=0, sticky="ew")
        gen_controls.grid_columnconfigure(10, weight=1)

        ttk.Label(gen_controls, text="Count:").grid(row=0, column=0, padx=(0,8))
        stepper = CountStepper(gen_controls, self.count_var, minv=1, maxv=100, width=200, height=36)
        stepper.grid(row=0, column=1, padx=(0,12))

        ttk.Label(gen_controls, text="Seed (optional):").grid(row=0, column=2, padx=(4,4))
        seed_entry = ttk.Entry(gen_controls, textvariable=self.seed_var, width=12)
        seed_entry.grid(row=0, column=3, padx=(0,12))
        seed_entry.configure(font=tkfont.Font(family="SF Pro Text", size=12))

        gen = RoundButton(gen_controls, text="Generate", command=self.on_generate, bg="#D0021B", fg="#FFFFFF")
        gen.grid(row=0, column=4, padx=(8,0), pady=4, sticky="w")

        # Output box
        out_frame = ttk.Frame(self, padding=(16, 12, 16, 12))  # consistent left/right padding
        out_frame.grid(row=4, column=0, sticky="nsew")
        out_frame.grid_rowconfigure(1, weight=1)
        out_frame.grid_columnconfigure(0, weight=1)

        self.out_summary = ttk.Label(out_frame, text="", style="TLabel")
        self.out_summary.grid(row=0, column=0, sticky="w", pady=(0,6))

        self.canvas = tk.Canvas(out_frame, bg="#FFFFFF", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)


        # Ensure the canvas consumes all space up to the scrollbar
        self.canvas.grid_configure(padx=0)

        # internal frame to hold drawings with scrolling
        self.inner = ttk.Frame(self.canvas)
        self.inner_id = self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.inner.grid_columnconfigure(0, weight=1)
        self.inner.grid_columnconfigure(1, weight=0)

        # Make mousewheel scroll work when hovering anywhere over the results area
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.inner)

    def _copy_to_clipboard(self, text: str):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._msg("info", "Copied", "Pick copied to clipboard.")
        except Exception as e:
            self._msg("error", "Copy error", str(e))
        # ensure baseline data + status
        self.ensure_csv_ready()
        self.update_status()
    def _msg(self, kind, title, message):
        """Display messages inline in the status bar (no dialogs).
        This avoids extra windows in frozen macOS apps."""
        try:
            if kind == "error":
                self.status.set(f"{message} ✗")
            else:
                self.status.set(f"{message} ✓")
            self.update_idletasks()
            # For non-errors, revert to a neutral status after a short delay
            if kind != "error":
                self.after(2500, lambda: (self.status.set("Ready."), self.update_idletasks()))
        except Exception:
            pass

    # Mousewheel helpers for smooth scrolling on macOS/Windows/Linux
    def _on_mousewheel(self, event):
        # On macOS event.delta is small (~1 or 2); on Windows it's multiples of 120
        delta = event.delta
        if sys.platform == "darwin":
            self.canvas.yview_scroll(int(-1 * delta), "units")
        else:
            self.canvas.yview_scroll(int(-1 * (delta/120)), "units")

    def _bind_mousewheel(self, widget):
        # Bind when pointer enters; unbind on leave so we don't hijack global scrolling
        widget.bind("<Enter>", lambda e: (widget.bind_all("<MouseWheel>", self._on_mousewheel),
                                           widget.bind_all("<Shift-MouseWheel>", self._on_mousewheel),
                                           widget.bind_all("<Button-4>", lambda ev: self.canvas.yview_scroll(-1, "units")),
                                           widget.bind_all("<Button-5>", lambda ev: self.canvas.yview_scroll( 1, "units"))))
        widget.bind("<Leave>", lambda e: (widget.unbind_all("<MouseWheel>"),
                                           widget.unbind_all("<Shift-MouseWheel>"),
                                           widget.unbind_all("<Button-4>"),
                                           widget.unbind_all("<Button-5>")))

    # --- helpers ---
    def _cleanup_ghost_windows(self):
        """Destroy any unexpected extra Toplevel windows that might have been
        created by hooks or third-party modules. Call before showing dialogs."""
        try:
            for w in self.winfo_children():
                if isinstance(w, tk.Toplevel):
                    try:
                        w.destroy()
                    except Exception:
                        pass
        except Exception:
            pass

    def ensure_csv_ready(self):
        (BASE_CSV.parent).mkdir(parents=True, exist_ok=True)
        # If we don't have a base CSV or it's empty, scrape to build it, then sort
        needs_build = (not BASE_CSV.exists()) or count_rows(BASE_CSV) == 0
        if needs_build:
            self.status.set("Building data file… (first run)")
            self.update_idletasks()
            try:
                run_scraper()  # writes BASE_CSV
            except Exception as e:
                self._msg("error", "Scrape error", str(e))
        # Always (re)generate the sorted view
        sort_csv_desc(BASE_CSV, SORTED_CSV)
        self.update_idletasks()

    def update_status(self):
        latest = latest_date_in_sorted(SORTED_CSV) or "N/A"
        rows = count_rows(BASE_CSV)
        self.status.set(f"Data file: {SORTED_CSV.name} — {rows} draws. Latest draw: {latest}")

    def _on_canvas_resize(self, event):
        # keep inner frame same width as canvas for nicer layout
        self.canvas.itemconfig(self.inner_id, width=event.width)

    # --- actions ---
    def on_refresh_data(self):
        self.status.set("Refreshing data…")
        self.update_idletasks()
        _log_window_event("on_refresh_data: start")
        try:
            run_scraper()          # updates BASE_CSV
            _log_window_event("on_refresh_data: scraper returned")
            sort_csv_desc(BASE_CSV, SORTED_CSV)
            self.update_status()
            # Remove any accidental extra top-levels before showing the dialog
            self._cleanup_ghost_windows()
            self._msg("info", "Done", "Data refreshed and sorted (newest first).")
        except Exception as e:
            self._msg("error", "Scrape error", str(e))

    def on_open_csv(self):
        try:
            if not SORTED_CSV.exists():
                self._msg("error", "Error", f"CSV not found at {SORTED_CSV}")
                return
            # Open with the OS default application for .csv
            if sys.platform == "darwin":
                subprocess.run(["open", str(SORTED_CSV)], check=False)
            elif os.name == "nt":
                os.startfile(str(SORTED_CSV))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(SORTED_CSV)], check=False)
        except Exception as e:
            self._msg("error", "Open error", str(e))

    def _clamp_count(self):
        try:
            val = int(self.count_var.get())
        except Exception:
            val = 5
        val = max(1, min(100, val))
        self.count_var.set(val)

    def on_count_dec(self):
        self._clamp_count()
        self.count_var.set(max(1, int(self.count_var.get()) - 1))

    def on_count_inc(self):
        self._clamp_count()
        self.count_var.set(min(100, int(self.count_var.get()) + 1))

    def on_generate(self):
        try:
            if not SORTED_CSV.exists():
                self._msg("error", "Error", f"CSV not found at {SORTED_CSV}")
                return

            rules = PowerballRules()
            history = load_history_csv(SORTED_CSV, rules)

            seed_txt = self.seed_var.get().strip()
            seed = int(seed_txt) if seed_txt else None
            if seed is not None:
                random.seed(seed)
            else:
                random.seed()  # fresh randomness

            count = max(1, int(self.count_var.get()))
            picks = generate_unique(history, rules, count=count, seed=None)

            latest = latest_date_in_sorted(SORTED_CSV) or 'N/A'
            self.out_summary.configure(text=f"Latest draw in file: {latest}   •   Generated {len(picks)} unique picks:")

            # persist picks to CSV in Application Support
            append_picks_to_csv(picks, latest)

            # clear previous drawings
            for child in self.inner.winfo_children():
                child.destroy()

            # draw each row as balls on its own canvas, plus a Copy button
            for i, (whites, red) in enumerate(picks):
                # left: balls canvas
                row_canvas = tk.Canvas(self.inner, height=44, bg="#FFFFFF", highlightthickness=0)
                row_canvas.grid(row=i, column=0, sticky="ew", pady=4)
                draw_balls_row(row_canvas, 4, 6, whites, red, scale=1.0)

                # right: Copy button
                pick_str = format_pick(whites, red)
                btn = RoundButton(self.inner, text="Copy", command=lambda s=pick_str: self._copy_to_clipboard(s), bg="#D0021B", fg="#FFFFFF")
                btn.grid(row=i, column=1, padx=(8,0), pady=4, sticky="e")

        except Exception as e:
            self._msg("error", "Error", str(e))


def main():
    _bounce_guard_check()           # <--- add this first
    _acquire_single_instance_lock()
    _log_window_event("main: creating App")
    app = App()
    _log_window_event("main: entering mainloop")
    app.mainloop()


if __name__ == "__main__":
    main()