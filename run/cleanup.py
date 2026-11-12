#!/usr/bin/env python3
"""Delete what Stage 2 made on the platform. A dry run unless --yes.

    python run/cleanup.py           # what would be deleted
    python run/cleanup.py --yes     # delete it
    python run/cleanup.py --state other_state.json --yes

From the ids in out/discover_state.json, in the order each one frees the next: sessions
(cancelled first if still going; found from the deployment too, so ones this script
never recorded go as well), the deployment (stopped first), the package, the copy of od,
then the project if nothing else is left in it. Uploaded files stay. An id already gone
counts as done, so a rerun finishes an interrupted cleanup.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import od_api  # noqa: E402
from common import OUT, read_json, rel, write_json  # noqa: E402


def gone(method: str, path: str, body=None) -> bool:
    """Make a call; True when it worked or the object is already gone (404)."""
    try:
        od_api.request(method, path, body, idempotent=True)   # only GET, DELETE, cancel and stop come here
        return True
    except SystemExit as e:
        if " -> 404" in str(e):
            return True
        print(f"    {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", type=Path, default=OUT / "discover_state.json")
    ap.add_argument("--yes", action="store_true", help="delete; without it, only list")
    args = ap.parse_args()
    st = read_json(args.state)
    od_api.check_key()
    if st.get("endpoint") and st["endpoint"] != od_api.root():
        raise SystemExit(f"{rel(args.state)} is for {st['endpoint']}, not {od_api.root()}")

    sessions = {r["session"] for r in st.get("runs", {}).values() if r.get("session")}
    if st.get("deployment"):
        try:
            sessions |= {s["id"] for s in od_api.list_all(f"/agents/sessions?deployment_id={st['deployment']}")
                         if s.get("deployment_id", st["deployment"]) == st["deployment"]}
        except SystemExit:
            pass
    plan = [*(("session", s) for s in sorted(sessions)), ("deployment", st.get("deployment")),
            ("package", st.get("package")), ("blueprint", st.get("blueprint")), ("project", st.get("project"))]
    plan = [(k, v) for k, v in plan if v]
    for kind, oid in plan:
        print(f"  {kind:<10} {oid}")
    if not args.yes:
        print(f"\ndry run: {len(plan)} objects; rerun with --yes to delete them")
        return 0

    ok = True
    for kind, oid in plan:
        if kind == "session":
            s = od_api.request("GET", f"/agents/sessions/{oid}") if gone("GET", f"/agents/sessions/{oid}") else {}
            if s.get("status") in {"pending", "running", "paused"}:
                gone("POST", f"/agents/sessions/{oid}/cancel", {})
            done = gone("DELETE", f"/agents/sessions/{oid}")
        elif kind == "deployment":
            gone("POST", f"/agents/deployments/{oid}/stop", {})
            done = gone("DELETE", f"/agents/deployments/{oid}")
        elif kind == "package":
            done = gone("DELETE", f"/agents/packages/{oid}")
        elif kind == "blueprint":
            done = gone("DELETE", f"/agents/blueprints/{oid}")
        else:
            try:
                left = od_api.request("GET", f"/agents/blueprints?project_id={oid}&limit=10")["data"]
            except SystemExit as e:
                print(f"    {e}")
                left = None
            if left:
                print(f"  kept    project {oid}: it still holds {len(left)} other blueprint(s)")
                continue
            done = left is not None and gone("DELETE", f"/projects/{oid}")
        print(f"  {'deleted' if done else 'FAILED '} {kind} {oid}")
        ok &= done
    if ok:
        args.state.rename(args.state.with_suffix(".deleted.json"))
        print(f"\nall deleted; {rel(args.state)} moved aside")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
