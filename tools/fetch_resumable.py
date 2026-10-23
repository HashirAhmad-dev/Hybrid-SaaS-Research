"""
fetch_resumable.py
==================
Append-only resumable download for slow, flaky links (decision D-012). Each
attempt sends `Range: bytes=<current size>-` and appends; it never truncates.
The file is renamed from <name>.partial to <name> only when its size equals the
server's total size.

    python -m tools.fetch_resumable URL DEST_PATH [--attempts 500]
"""
from __future__ import annotations

import argparse
import time
import urllib.request
from pathlib import Path


def total_size(url: str) -> int:
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0", "User-Agent": "fetch_resumable/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cr = r.headers.get("Content-Range", "")
        return int(cr.split("/")[-1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("dest", type=Path)
    ap.add_argument("--attempts", type=int, default=500)
    a = ap.parse_args()
    part = a.dest.with_name(a.dest.name + ".partial")
    total = total_size(a.url)
    for attempt in range(a.attempts):
        have = part.stat().st_size if part.exists() else 0
        if have >= total:
            break
        try:
            req = urllib.request.Request(a.url, headers={"Range": f"bytes={have}-", "User-Agent": "fetch_resumable/1"})
            with urllib.request.urlopen(req, timeout=120) as r, open(part, "ab") as f:
                if r.status != 206:
                    raise IOError(f"server answered {r.status}, not 206; refusing to append")
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:                          # network drop: resume from the new size
            print(f"attempt {attempt + 1}: {type(e).__name__}: {e}; have {part.stat().st_size if part.exists() else 0}/{total}", flush=True)
            time.sleep(10)
    size = part.stat().st_size
    if size != total:
        raise SystemExit(f"incomplete: {size}/{total}")
    part.replace(a.dest)
    print(f"done {a.dest} ({total} bytes)")


if __name__ == "__main__":
    main()
