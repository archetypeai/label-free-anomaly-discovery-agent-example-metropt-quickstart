#!/usr/bin/env python3
"""Stage 0: download MetroPT-3 from the UCI repository and check it.

    python prep/download.py

Fetches the zip (218 MB), extracts `MetroPT3(AirCompressor).csv` (218 MB) and checks its
SHA-256 against the one this example was built on. Skips the download when the file is
already there and matches.
"""
from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import RAW, RAW_DIR, RAW_SHA256, RAW_URL, rel  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if RAW.exists() and sha256(RAW) == RAW_SHA256:
        print(f"{rel(RAW)} already downloaded and verified")
        return 0
    print(f"downloading {RAW_URL}")
    with urllib.request.urlopen(RAW_URL, timeout=600) as r:
        blob = r.read()
    print(f"  {len(blob) / 1e6:.0f} MB")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for member in z.namelist():
            name = Path(member).name
            if name.endswith((".csv", ".pdf")):          # the data and its description
                (RAW_DIR / name).write_bytes(z.read(member))
                print(f"  extracted {name}")
    got = sha256(RAW)
    if got != RAW_SHA256:
        print(f"SHA-256 mismatch: {got}\n  expected {RAW_SHA256}\n  (UCI may have updated the file)")
        return 1
    print(f"{rel(RAW)}: SHA-256 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
