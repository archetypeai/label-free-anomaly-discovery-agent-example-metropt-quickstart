#!/usr/bin/env python3
"""Stage 1a: check the raw file before any prep decision. Read-only.

    python prep/preflight_raw.py

Each WARN names the Stage 1b decision it leads to.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import CHANNELS, FILES, FROZEN_ROWS, MAX_FILL, RAW, STEP_S, Report, rel  # noqa: E402


def main() -> int:
    r = Report(f"Stage 1a: {rel(RAW)}")
    if not RAW.exists():
        r.add("FAIL", "file", "missing: run prep/download.py")
        return r.done()
    df = pd.read_csv(RAW)
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])
    missing = [c for c in ["timestamp", *CHANNELS] if c not in df.columns]
    r.add("FAIL" if missing else "PASS", "schema",
          f"missing {missing}" if missing else f"timestamp + {len(df.columns) - 1} channels, {len(df):,} rows")
    if missing:
        return r.done()
    labels = [c for c in df.columns if c.lower() in {"label", "anomaly", "failure", "fault"}]
    r.add("FAIL" if labels else "PASS", "no label column",
          f"found {labels}" if labels else "the data carries no labels (the reports are separate)")

    t = pd.to_datetime(df.timestamp, errors="coerce")
    r.add("FAIL" if t.isna().any() else "PASS", "timestamps parse", f"{int(t.isna().sum())} unparseable")
    dt = t.diff().dt.total_seconds().dropna()
    r.add("PASS" if (dt > 0).all() else "WARN", "strictly increasing",
          f"{int((dt <= 0).sum())} steps not increasing" + ("" if (dt > 0).all() else " -> 1b bins rows"))
    q = dt.quantile([.5, .99])
    r.add("WARN", "cadence", f"median step {q[.5]:.0f} s, 99th pct {q[.99]:.0f} s, not exact "
          f"-> 1b snaps rows to a {STEP_S} s grid")
    long_gaps = int((dt > STEP_S * (MAX_FILL + 1)).sum())
    r.add("WARN", "gaps", f"{long_gaps} gaps longer than {STEP_S * (MAX_FILL + 1)} s (train out of service) "
          "-> 1b never interpolates across one; od marks windows that cross one invalid")
    span = f"{t.min():%Y-%m-%d} .. {t.max():%Y-%m-%d}"
    covered = all(t.min() <= pd.Timestamp(a) and pd.Timestamp(b) <= t.max() for a, b in FILES.values())
    r.add("PASS" if covered else "FAIL", "covers the files", f"data spans {span}; files {sorted(FILES)}")

    x = df[CHANNELS]
    nan = int(x.isna().sum().sum())
    r.add("PASS" if nan == 0 else "WARN", "missing values", f"{nan} NaN in the analog channels")
    r.add("PASS" if np.isfinite(x.to_numpy()).all() else "FAIL", "finite", "all finite")
    const = [c for c in CHANNELS if x[c].std() == 0]
    r.add("FAIL" if const else "PASS", "constant channels", f"{const or 'none'}")
    ranges = ", ".join(f"{c} {x[c].min():.2f}..{x[c].max():.2f}" for c in CHANNELS)
    r.add("INFO", "ranges", ranges)

    flat = np.ones(len(x), bool)
    for c in CHANNELS:
        roll = x[c].rolling(FROZEN_ROWS)
        flat &= (roll.max() - roll.min()).to_numpy() == 0
    n_frozen_rows = int(flat.sum())
    r.add("WARN" if n_frozen_rows else "PASS", "frozen logger",
          f"{n_frozen_rows:,} rows end a stretch where every channel is unchanged for {FROZEN_ROWS} rows "
          "-> 1b cuts those stretches out (a data-quality rule, no labels)")
    return r.done()


if __name__ == "__main__":
    raise SystemExit(main())
