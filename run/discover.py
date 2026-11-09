#!/usr/bin/env python3
"""Stage 2: Discover. Run the Label-Free Anomaly Discovery Agent (`od`) over each file, in batch.

    python run/discover.py                 # every file
    python run/discover.py --files A       # one
    python run/discover.py --rerun         # new sessions even where an output exists

Agent Lifecycle 2.0, every object in one project:
  1. project       `Label-Free AD MetroPT quickstart` (reused if it exists)
  2. blueprint     a copy of `od` with this example's values: the timestamp column, the 7
                   channels, windows of 360 rows (1 h) at step 360. Everything else is
                   od's default: Omega 1.5 + 7 statistics per channel, per-channel PCA 5,
                   LOF (L1) with K = 20% of the file's windows, threshold 1.5.
  3. package       the copy, its encoder resolved once
  4. deployment    kind `batch`
  5. sessions      one per file: od fits LOF on that file's windows and scores the same windows
Nothing is trained ahead of time and no label is sent. Ids go to out/discover_state.json,
so a rerun resumes. Writes eval_out/discover/od-metropt_<file>.csv.
"""
from __future__ import annotations

import argparse
import datetime
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import od_api  # noqa: E402
from common import CHANNELS, FILES, OUT, WINDOW, output_file, prepared_file, read_json, rel, write_json  # noqa: E402

PROJECT = "Label-Free AD MetroPT quickstart"
BLUEPRINT_KEY = "od-metropt-qs"
STATE = OUT / "discover_state.json"
VALUES = {"timestamp_column": "timestamp", "data_columns": CHANNELS, "window_size": WINDOW, "step_size": WINDOW}


def log(msg: str) -> None:
    print(f"{datetime.datetime.now():%H:%M:%S} {msg}", flush=True)


def setup(st: dict) -> None:
    """Project, blueprint copy, package and deployment: made once, reused after."""
    od_api.check_key()
    if st.get("endpoint") and st["endpoint"] != od_api.root():
        raise SystemExit(f"{rel(STATE)} is for {st['endpoint']}; move it aside to run on {od_api.root()}")
    st["endpoint"] = od_api.root()
    if "project" not in st:
        st["project"] = od_api.find_project(PROJECT) or od_api.request(
            "POST", "/projects", {"name": PROJECT, "description": "Label-free anomaly discovery on MetroPT-3"})["id"]
        write_json(STATE, st)
    log(f"project    {st['project']} ({PROJECT})")
    if "blueprint" not in st:
        found = od_api.request("GET", f"/agents/blueprints?project_id={st['project']}&key={BLUEPRINT_KEY}")["data"]
        st["blueprint"] = found[0]["id"] if found else od_api.request(
            "POST", "/agents/blueprints/od/copy",
            {"project_id": st["project"], "blueprint_key": BLUEPRINT_KEY, "name": "Label-Free AD MetroPT",
             "overrides": {"values": VALUES}})["id"]
        st["values"] = VALUES
        write_json(STATE, st)
    log(f"blueprint  {st['blueprint']} ({BLUEPRINT_KEY}: copy of od, window {WINDOW}, step {WINDOW})")
    if "package" not in st:
        st["package"] = od_api.request("POST", "/agents/packages", {
            "blueprint_ids": [st["blueprint"]], "target": {"kind": "platform"}, "name": "Label-Free AD MetroPT"})["id"]
        write_json(STATE, st)
    od_api.wait(f"/agents/packages/{st['package']}", {"ready"}, label=f"package    {st['package']}")
    if "deployment" not in st or od_api.request("GET", f"/agents/deployments/{st['deployment']}").get("status") \
            in od_api.TERMINAL_BAD:
        st["deployment"] = od_api.request("POST", "/agents/deployments",
                                          {"package_id": st["package"], "kind": "batch"})["id"]
        write_json(STATE, st)
    od_api.wait(f"/agents/deployments/{st['deployment']}", {"ready"}, label=f"deployment {st['deployment']}")


def check(out: Path, src: Path) -> str:
    """The output must have a row per window of the input, its last ending at the last window's end."""
    o, d = pd.read_csv(out), pd.read_csv(src, usecols=["timestamp"])
    n = len(d) // WINDOW
    if len(o) != n:
        return f"{len(o)} windows, expected {n}"
    if int(o.finish_timestamp.iloc[-1]) != int(d.timestamp.iloc[n * WINDOW - 1]):
        return "last window does not end where the input's last full window does"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--files", nargs="+", default=list(FILES), choices=list(FILES))
    ap.add_argument("--rerun", action="store_true", help="new sessions even where an output exists")
    args = ap.parse_args()
    st = read_json(STATE) if STATE.exists() else {}
    setup(st)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = st.setdefault("runs", {})

    for name in args.files:                      # start every session, then collect
        src, out = prepared_file(name), output_file(name)
        if not src.exists():
            raise SystemExit(f"{rel(src)} missing: run prep/prepare.py")
        if out.exists() and not args.rerun and not check(out, src):
            log(f"{name}: {rel(out)} already complete (--rerun to redo)")
            continue
        run = runs.get(name, {})
        if args.rerun or "session" not in run or run.get("status") in od_api.TERMINAL_BAD:
            # File ids are file names: a timestamped name never replaces one a session is reading.
            fid = od_api.upload(src, f"od-metropt-qs-{src.stem}-{stamp}.csv")
            ses = od_api.request("POST", "/agents/sessions", {
                "deployment_id": st["deployment"], "connectors": {"source": [{"type": "file", "id": fid}]}})["id"]
            runs[name] = run = {"file_id": fid, "session": ses, "started": stamp}
            write_json(STATE, st)
            log(f"{name}: uploaded {fid}, session {ses}")

    for name in args.files:
        run = runs.get(name)
        out, src = output_file(name), prepared_file(name)
        if not run or (out.exists() and not args.rerun and not check(out, src)):
            continue
        t0 = time.time()
        ses = od_api.wait(f"/agents/sessions/{run['session']}", {"completed"}, every_s=10, timeout_s=3600,
                          label=f"{name}: session {run['session']}")
        run["status"] = ses["status"]
        for attempt in range(40):                # a completed session can still be writing its output
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(od_api.download_result(run["session"]))
            problem = check(out, src)
            if not problem:
                break
            time.sleep(15)
        else:
            raise SystemExit(f"{name}: output incomplete: {problem}")
        o = pd.read_csv(out)
        inv = o.invalid.astype(str).str.lower().eq("true")
        log(f"{name}: {len(o)} windows, {int(inv.sum())} invalid (cross a gap), "
            f"{int((o.predicted_label == 'anomaly').sum())} over 1.5; {time.time() - t0:.0f} s -> {rel(out)}")
        write_json(STATE, st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
