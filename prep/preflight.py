#!/usr/bin/env python3
"""Stage 1c: check the prepared files against what od needs. Read-only.

    python prep/preflight.py

od reads one CSV per session: a timestamp column and numeric channels. It cuts windows of
WINDOW rows from row 0, step = WINDOW, marks a window invalid when its sample interval
varies by more than 5% (it crosses a gap), and fits LOF on the valid ones. So per file:
the schema, no label column, finite values, strictly increasing 10 s timestamps within
each piece, no frozen stretch left, and enough valid windows for LOF.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import CHANNELS, FILES, FROZEN_ROWS, STEP_S, WINDOW, Report, prepared_file, rel  # noqa: E402

MIN_WINDOWS = 50          # LOF with K = 20% of windows needs enough of them to mean anything


def main() -> int:
    r = Report("Stage 1c: the prepared files")
    for name in FILES:
        p = prepared_file(name)
        if not p.exists():
            r.add("FAIL", name, f"{rel(p)} missing: run prep/prepare.py")
            continue
        d = pd.read_csv(p)
        ok = list(d.columns) == ["timestamp", *CHANNELS]
        r.add("PASS" if ok else "FAIL", f"{name} schema", f"timestamp + {len(CHANNELS)} channels, no label column"
              if ok else f"columns {list(d.columns)}")
        x = d[CHANNELS].to_numpy(dtype=float)
        r.add("PASS" if np.isfinite(x).all() else "FAIL", f"{name} finite", f"{len(d):,} rows")
        dt = np.diff(d.timestamp.to_numpy())
        r.add("PASS" if (dt > 0).all() else "FAIL", f"{name} increasing", "timestamps strictly increasing")
        r.add("PASS" if (dt % STEP_S == 0).all() else "FAIL", f"{name} on the grid", f"every step a multiple of {STEP_S} s")
        flat = (np.abs(np.diff(x, axis=0)).sum(axis=1) == 0) & (dt == STEP_S)
        longest = max((len(s) for s in "".join("1" if f else "0" for f in flat).split("0")), default=0) + 1
        r.add("PASS" if longest < FROZEN_ROWS else "FAIL", f"{name} no frozen stretch",
              f"longest unchanged run {longest} rows")
        n = len(d) // WINDOW
        starts = np.arange(n) * WINDOW
        valid = sum(1 for s in starts if (dt[s:s + WINDOW - 1] == STEP_S).all())
        r.add("PASS" if valid >= MIN_WINDOWS else "FAIL", f"{name} windows",
              f"{n} windows of {WINDOW} rows ({WINDOW * STEP_S // 60} min); {valid} gap-free, "
              f"{n - valid} cross a gap (od marks them invalid)")
        r.add("INFO", f"{name} LOF neighbours", f"K = 20% of {valid} valid windows = {max(5, valid // 5)}: "
              f"an episode longer than ~{max(5, valid // 5)} hours would form its own neighbourhood")
    return r.done()


if __name__ == "__main__":
    raise SystemExit(main())
