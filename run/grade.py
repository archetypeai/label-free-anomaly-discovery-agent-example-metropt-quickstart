#!/usr/bin/env python3
"""Stage 4: Grade. Open the operator's maintenance reports and compare.

Not part of the Label-Free Anomaly Discovery Agent: this example's own evaluation of its
output (Stage 2) and of Stage 3's episodes, run locally. It uses the maintenance reports,
which the agent never sees; in real use you may not have them.

    python run/grade.py
    python run/grade.py --lead-h 24

The only stage that reads the reports (common.REPORTS); the agent never saw them. Per file:
- ranking: AUROC of the reported leak's windows against every other valid window (how
  often a leak hour outranks an ordinary one; 1.0 is perfect, 0.5 is chance), and the
  ranks the leak's windows reached;
- detection: the first flagged window (od's own label, score over 1.5) from `--lead-h`
  hours before the report's start to its end. A leak builds before anyone reports it, so a
  flag shortly before the report counts as early;
- each Stage 3 episode as matching a report, or not reported. A not-reported episode is
  not necessarily a false alarm: the reports list failures someone acted on, not every
  unusual hour.
Writes eval_out/grade/grade.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import EVAL_OUT, FILES, REPORTS, epoch, output_file, read_json, rel, write_json  # noqa: E402


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """P(a positive outscores a negative), ties counted half."""
    allv = np.concatenate([pos, neg])
    ranks = pd.Series(allv).rank().to_numpy()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lead-h", type=float, default=24, help="hours before a report's start a flag counts as early")
    args = ap.parse_args()
    review = read_json(EVAL_OUT / "review" / "review.json")
    result = {"lead_h": args.lead_h, "files": {}}
    for name, (lo, hi) in FILES.items():
        o = pd.read_csv(output_file(name))
        o = o[~o.invalid.astype(str).str.lower().eq("true")].reset_index(drop=True)
        s = o.anomaly_score.to_numpy()
        reps = [r for r in REPORTS if epoch(lo) <= epoch(r["start"]) < epoch(hi)]
        print(f"=== File {name}: {lo} to {hi}, {len(o)} valid hours, "
              f"{len(reps)} reported failure{'s' if len(reps) != 1 else ''}")
        fr = {"reports": [], "episodes": []}
        for r in reps:
            a, b = epoch(r["start"]), epoch(r["end"])
            leak = ((o.finish_timestamp >= a) & (o.start_timestamp <= b)).to_numpy()
            rank = pd.Series(-s).rank(method="min").to_numpy().astype(int)
            win = o[(o.finish_timestamp >= a - args.lead_h * 3600) & (o.start_timestamp <= b)
                    & (o.predicted_label == "anomaly")]
            first = (win.finish_timestamp.iloc[0] - a) / 3600 if len(win) else None
            row = {"report": r["id"], "start": r["start"], "end": r["end"], "leak_windows": int(leak.sum()),
                   "auroc": round(auroc(s[leak], s[~leak]), 3), "ranks": sorted(rank[leak].tolist()),
                   "flagged": int((leak & (o.predicted_label == "anomaly")).sum()),
                   "first_flag_h": None if first is None else round(float(first), 2)}
            fr["reports"].append(row)
            det = ("not flagged" if first is None else
                   f"first flag {abs(first):.1f} h {'before' if first < 0 else 'after'} the reported start")
            print(f"  report #{r['id']} ({r['failure']}, {r['start']} .. {r['end']}): {row['leak_windows']} hours; "
                  f"AUROC {row['auroc']:.3f}; ranks {row['ranks'][:8]}{' ...' if len(row['ranks']) > 8 else ''}; "
                  f"{row['flagged']}/{row['leak_windows']} flagged; {det}")
        if not reps:
            print("  no reported failure: every flag here is unreported")
        for e in review[name]:
            hit = [r["id"] for r in reps
                   if e["end_epoch"] >= epoch(r["start"]) - args.lead_h * 3600 and e["start_epoch"] <= epoch(r["end"])]
            fr["episodes"].append({**{k: e.get(k) for k in ("rank", "start", "end", "hours", "peak")},
                                   "report": hit[0] if hit else None})
        n_hit = sum(e["report"] is not None for e in fr["episodes"])
        hours_unrep = sum(e["hours"] for e in fr["episodes"] if e["report"] is None)
        print(f"  episodes: {len(fr['episodes'])}, {n_hit} match a report, "
              f"{len(fr['episodes']) - n_hit} not reported ({hours_unrep} flagged hours)")
        for e in fr["episodes"][:5]:
            tag = f"report #{e['report']}" if e["report"] else "not reported"
            print(f"    {e['rank']}. {e['start']}  {e['hours']:2d} h  peak {e['peak']:.2f}  {tag}")
        result["files"][name] = fr
        print()
    write_json(EVAL_OUT / "grade" / "grade.json", result)
    print(f"wrote {rel(EVAL_OUT / 'grade' / 'grade.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
