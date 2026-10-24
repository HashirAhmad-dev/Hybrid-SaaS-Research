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
import urllib.error
import urllib.request
from pathlib import Path


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def resolve(url: str) -> str:
    """Follow one redirect by hand (figshare -> signed S3 URL). S3 rejects the signed
    URL when urllib replays the original request headers across the redirect."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        r = opener.open(urllib.request.Request(url, headers={"User-Agent": "fetch_resumable/1"}), timeout=60)  # GET: the signature covers the method
        return r.geturl()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return e.headers["Location"]
        raise


def total_size(url: str) -> int:
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cr = r.headers.get("Content-Range", "")
        return int(cr.split("/")[-1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("dest", type=Path)
    ap.add_argument("--attempts", type=int, default=500)
    ap.add_argument("--resolve-redirect", action="store_true",
                    help="resolve the redirect by hand on every attempt (figshare / signed S3 URLs)")
    a = ap.parse_args()
    part = a.dest.with_name(a.dest.name + ".partial")
    total = None
    for probe in range(50):                              # flaky DNS / resets on this link
        try:
            total = total_size(resolve(a.url) if a.resolve_redirect else a.url)
            break
        except Exception as e:
            print(f"size probe {probe + 1}: {type(e).__name__}: {e}", flush=True)
            time.sleep(10)
    if total is None:
        raise SystemExit("could not read the file size")
    for attempt in range(a.attempts):
        have = part.stat().st_size if part.exists() else 0
        if have >= total:
            break
        try:
            target = resolve(a.url) if a.resolve_redirect else a.url
            req = urllib.request.Request(target, headers={"Range": f"bytes={have}-"})
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
