#!/usr/bin/env python3
"""Stage 3: Review. What a person would read: the unusual episodes, and what they look like.

Not part of the Label-Free Anomaly Discovery Agent: this example's own post-processing of
its output (Stage 2), run locally. The agent's output is the score and label per window.

    python run/review.py
    python run/review.py --top 5

No label or report is read. For each file:
1. Episodes: od's flagged windows (score over its 1.5), merged when back to back, ranked by
   their highest score.
2. What each episode looks like, from the input itself: for every channel, how far the
   episode's typical level (mean) and spread (std) sit from the file's usual hour, as a
   robust z (median and interquartile range over the file's valid hours), and how much of
   the time the compressor runs (Motor_current over 1 A) and runs under load (over 5.5 A;
   per the dataset: ~0 A off, ~4 A running offloaded, ~7 A under load). This is a description of
   the data, not od's reasoning: od does not say which sensors drove a score.
Writes eval_out/review/review.md and review.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import CHANNELS, EVAL_OUT, FILES, STEP_S, WINDOW, output_file, prepared_file, rel, write_json  # noqa: E402

MOTOR_ON_A = 1.0          # Motor_current above 1 A: the compressor is running
MOTOR_LOAD_A = 5.5        # above 5.5 A: running under load (~7 A), not offloaded (~4 A)
SHOW = 3                  # features shown per episode


def window_features(name: str, o: pd.DataFrame) -> pd.DataFrame:
    """Per output window: each channel's mean and std, and the motor's duty, from the input."""
    d = pd.read_csv(prepared_file(name))
    rows = []
    for i in range(len(o)):
        w = d.iloc[i * WINDOW:(i + 1) * WINDOW]
        f = {f"{c} level": w[c].mean() for c in CHANNELS} | {f"{c} spread": w[c].std() for c in CHANNELS}
        f["motor on"] = (w.Motor_current > MOTOR_ON_A).mean()
        f["under load"] = (w.Motor_current > MOTOR_LOAD_A).mean()
        rows.append(f)
    return pd.DataFrame(rows)


def episodes(o: pd.DataFrame) -> list[list[int]]:
    """Flagged windows, merged when one ends where the next begins (no gap between)."""
    out, cur = [], []
    for i in np.flatnonzero((o.predicted_label == "anomaly").to_numpy()):
        if cur and o.start_timestamp[i] - o.finish_timestamp[cur[-1]] > STEP_S:
            out.append(cur)
            cur = []
        cur.append(int(i))
    return out + ([cur] if cur else [])


def when(ts: float) -> str:
    return pd.Timestamp(ts, unit="s").strftime("%a %b %d %H:%M")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=5, help="episodes shown per file")
    args = ap.parse_args()
    md, js = ["# Review: unusual episodes found by the Label-Free Anomaly Discovery Agent", ""], {}
    for name in FILES:
        p = output_file(name)
        if not p.exists():
            raise SystemExit(f"{rel(p)} missing: run run/discover.py")
        o = pd.read_csv(p)
        valid = ~o.invalid.astype(str).str.lower().eq("true")
        feats = window_features(name, o)
        base = feats[valid]
        med, iqr = base.median(), (base.quantile(.75) - base.quantile(.25)).replace(0, np.nan)
        eps = sorted(episodes(o), key=lambda e: -o.anomaly_score[e].max())
        hours = len(o) * WINDOW * STEP_S / 3600
        head = (f"## File {name}: {FILES[name][0]} to {FILES[name][1]}\n\n{int(valid.sum())} hours scored; "
                f"{int((o.predicted_label == 'anomaly').sum())} flagged (score over 1.5) in {len(eps)} episodes; "
                f"usually the compressor runs {med['motor on']:.0%} of an hour, under load {med['under load']:.0%}.\n")
        print(head.replace("## ", "=== ").replace("\n\n", "\n"))
        md += [head, "| # | from | to | hours | peak score | running | under load | what stands out (robust z vs the usual hour) |",
               "|---|---|---|---|---|---|---|---|"]
        js[name] = []
        for k, e in enumerate(eps[:args.top], 1):
            z = ((feats.loc[e].median() - med) / iqr).drop(["motor on", "under load"]).dropna()
            top = z.reindex(z.abs().sort_values(ascending=False).index)[:SHOW]
            stand = ", ".join(f"{f} {v:+.0f}" for f, v in top.items())
            row = dict(rank=k, start=when(o.start_timestamp[e[0]]), end=when(o.finish_timestamp[e[-1]]),
                       hours=len(e), peak=round(float(o.anomaly_score[e].max()), 3),
                       motor_on=round(float(feats.loc[e, "motor on"].mean()), 2),
                       under_load=round(float(feats.loc[e, "under load"].mean()), 2), stands_out=stand,
                       start_epoch=int(o.start_timestamp[e[0]]), end_epoch=int(o.finish_timestamp[e[-1]]))
            js[name].append(row)
            line = (f"{k}. {row['start']} -> {row['end']}  {len(e):2d} h  peak {row['peak']:.2f}  "
                    f"running {row['motor_on']:.0%}, loaded {row['under_load']:.0%}  {stand}")
            print("  " + line)
            md.append(f"| {k} | {row['start']} | {row['end']} | {len(e)} | {row['peak']:.2f} | "
                      f"{row['motor_on']:.0%} | {row['under_load']:.0%} | {stand} |")
        if len(eps) > args.top:
            print(f"  ... {len(eps) - args.top} more episodes")
            md.append(f"\n{len(eps) - args.top} more episodes in review.json.")
        js[name] += [] if len(eps) <= args.top else [
            dict(rank=k, start=when(o.start_timestamp[e[0]]), end=when(o.finish_timestamp[e[-1]]),
                 start_epoch=int(o.start_timestamp[e[0]]), end_epoch=int(o.finish_timestamp[e[-1]]),
                 hours=len(e), peak=round(float(o.anomaly_score[e].max()), 3))
            for k, e in enumerate(eps[args.top:], args.top + 1)]
        md.append("")
        print()
    out = EVAL_OUT / "review"
    out.mkdir(parents=True, exist_ok=True)
    (out / "review.md").write_text("\n".join(md) + "\n")
    write_json(out / "review.json", js)
    print(f"wrote {rel(out / 'review.md')}, {rel(out / 'review.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
