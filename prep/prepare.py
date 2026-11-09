#!/usr/bin/env python3
"""Stage 1b: the 10 s grid, the gaps, the frozen stretches, and the customer's three files.

    python prep/prepare.py

1. Each raw row is snapped to a 10 s bin (the mean of the rows in it). Holes of up to
   MAX_FILL bins (sampling jitter) are forward-filled; anything longer is a gap and stays a
   gap. Nothing is interpolated across one.
2. Frozen-logger stretches (every channel unchanged for 30 min or more) are cut out: a
   data-quality rule, decided without looking at any report.
3. Files A, B and C are cut by date (common.FILES), in raw units: od z-scores each
   feature itself, fitted on the file it scores.

Writes data/prepared/metropt_{A,B,C}.csv (timestamp in epoch seconds + 7 channels) and
data/prepared/prepare_report.json. No label is read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (CHANNELS, FILES, FROZEN_ROWS, MAX_FILL, PREPARED, RAW, STEP_S, prepared_file,  # noqa: E402
                    rel, write_json)


def grid(raw: pd.DataFrame) -> pd.DataFrame:
    binned = raw.set_index("timestamp")[CHANNELS].resample(f"{STEP_S}s").mean()
    present = binned[CHANNELS[0]].notna()
    run_len = present.groupby((present != present.shift()).cumsum()).transform("size")
    gap = (~present) & (run_len > MAX_FILL)
    return binned.ffill(limit=MAX_FILL)[~gap].dropna()


def frozen_mask(g: pd.DataFrame) -> np.ndarray:
    """Rows inside a stretch of >= FROZEN_ROWS consecutive rows where no channel changes."""
    t = g.index.to_series()
    piece = (t.diff() != pd.Timedelta(seconds=STEP_S)).cumsum()       # never across a gap
    same = (g[CHANNELS].diff().abs().sum(axis=1) == 0) & (piece == piece.shift())
    run = (~same).cumsum()                                             # a run: one row + its repeats
    size = same.groupby(run).transform("size")
    return (size >= FROZEN_ROWS).to_numpy()


def main() -> int:
    if not RAW.exists():
        raise SystemExit(f"{rel(RAW)} missing: run prep/download.py")
    raw = pd.read_csv(RAW, usecols=["timestamp", *CHANNELS], parse_dates=["timestamp"])
    g = grid(raw)
    frozen = frozen_mask(g)
    print(f"grid: {len(raw):,} raw rows -> {len(g):,} rows at {STEP_S} s; "
          f"frozen-logger rows cut: {frozen.sum():,} ({frozen.sum() * STEP_S / 3600:.0f} h)")
    g = g[~frozen]

    PREPARED.mkdir(parents=True, exist_ok=True)
    report = {"step_s": STEP_S, "channels": CHANNELS, "frozen_rows_cut": int(frozen.sum()), "files": {}}
    for name, (lo, hi) in FILES.items():
        d = g.loc[lo:pd.Timestamp(hi) - pd.Timedelta(seconds=1)].copy()
        t = d.index.to_series()
        pieces = int((t.diff() != pd.Timedelta(seconds=STEP_S)).sum())
        d.insert(0, "timestamp", ((d.index - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).astype("int64"))
        out = prepared_file(name)
        d.to_csv(out, index=False, float_format="%.6g")
        report["files"][name] = {"file": rel(out), "from": lo, "to": hi, "rows": len(d),
                                 "days_of_data": round(len(d) * STEP_S / 86400, 1), "pieces": pieces}
        print(f"  {name}: {lo} .. {hi}  {len(d):,} rows ({len(d) * STEP_S / 86400:.1f} days of data) "
              f"in {pieces} continuous pieces -> {rel(out)}")
    write_json(PREPARED / "prepare_report.json", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
