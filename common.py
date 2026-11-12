"""Paths, constants and small helpers shared by every stage."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent
RAW_DIR = REPO / "data" / "raw"
RAW = RAW_DIR / "MetroPT3(AirCompressor).csv"
RAW_URL = "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip"
RAW_SHA256 = "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24"
PREPARED = REPO / "data" / "prepared"
OUT = REPO / "out"                      # platform ids, so a rerun resumes
EVAL_OUT = REPO / "eval_out"

STEP_S = 10                             # the grid: one row every 10 s
MAX_FILL = 5                            # up to 50 s missing is sampling jitter; longer is a gap
FROZEN_ROWS = 180                       # every channel unchanged for 30 min: the logger froze
WINDOW = 360                            # one hour; od's windows don't overlap (step = window)

# The 7 analog channels. The 8 digital ones are 0/1 switch states, mostly constant in a window.
CHANNELS = ["TP2", "TP3", "H1", "DV_pressure", "Reservoirs", "Oil_temperature", "Motor_current"]

# The three input files: three stretches of three weeks, on the dataset's own clock. The
# dates were picked with the reports in hand, so that A and B each hold one reported leak
# and C none: that sets up the grading. Nothing from the reports goes into the files.
FILES = {
    "A": ("2020-04-04", "2020-04-25"),
    "B": ("2020-07-01", "2020-07-22"),
    "C": ("2020-03-01", "2020-03-22"),
}

# The operator's failure reports, quoted from the MetroPT-3 dataset page (Davari, Veloso,
# Ribeiro & Gama, 2021; https://doi.org/10.24432/C5VW3R; CC BY 4.0). Read only by Stage 4.
REPORTS = [
    {"id": 1, "start": "2020-04-18 00:00", "end": "2020-04-18 23:59", "failure": "air leak"},
    {"id": 2, "start": "2020-05-29 23:30", "end": "2020-05-30 06:00", "failure": "air leak"},
    {"id": 3, "start": "2020-06-05 10:00", "end": "2020-06-07 14:30", "failure": "air leak"},
    {"id": 4, "start": "2020-07-15 14:30", "end": "2020-07-15 19:00", "failure": "air leak"},
]


def epoch(ts) -> int:
    """Seconds since 1970 for a time on the dataset's clock (taken as UTC, no shift)."""
    return int(pd.Timestamp(ts).timestamp())


def prepared_file(name: str) -> Path:
    return PREPARED / f"metropt_{name}.csv"


def output_file(name: str) -> Path:
    return EVAL_OUT / "discover" / f"od-metropt_{name}.csv"


def read_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"{rel(path)} not found: run the earlier stage first")
    return json.loads(path.read_text())


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str))


def rel(p: Path) -> str:
    return str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)


class Report:
    """PASS / WARN / FAIL / INFO lines; exit non-zero only on FAIL."""

    def __init__(self, title: str):
        self.rows: list[tuple[str, str, str]] = []
        print(f"=== {title} ===")

    def add(self, level: str, name: str, msg: str) -> None:
        self.rows.append((level, name, msg))
        print(f"  {level:<4}  {name:<24} {msg}")

    def done(self) -> int:
        n = {k: sum(r[0] == k for r in self.rows) for k in ("PASS", "WARN", "FAIL", "INFO")}
        print(f"\n{n['PASS']} PASS, {n['WARN']} WARN, {n['FAIL']} FAIL, {n['INFO']} INFO")
        return 1 if n["FAIL"] else 0
