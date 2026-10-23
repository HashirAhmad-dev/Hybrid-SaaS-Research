"""
check_numbers.py
================
Compare numbers quoted in text (paper, README, reports) with results/manifest.json.

A claims file has one claim per line, fields separated by `|`:

    label | manifest key | value as written | tolerance (optional)

    # comment lines and blank lines are ignored
    Hybrid F1 (test, seed 42) | anomaly.s42.test_flag_level.hybrid.f1 | 0.629
    Enforcement FPR           | anomaly.s42.test_enforcement_bands.hybrid_alert_or_block.fpr | 3.99%

Rules
-----
* A value ending in `%` is divided by 100 before comparison.
* The default tolerance is half a unit in the last written decimal place, so
  `0.629` accepts [0.6285, 0.6295] and `3.99%` accepts [0.03985, 0.03995]. That
  is exactly "this rounding of the manifest value is correct".
* An explicit tolerance overrides the default (written in the same unit as the
  value, `%` allowed).
* A missing key is a failure.

Usage
-----
    python tools/check_numbers.py CLAIMS_FILE_OR_DIR [...] [--manifest PATH]
    (a directory means every *.claims file in it)
    python tools/check_numbers.py --pair "label|key|value" ...

Exit status 0 when every claim matches, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "results" / "manifest.json"


@dataclass
class Claim:
    label: str
    key: str
    written: str
    tolerance: Optional[str] = None
    source: str = ""


def parse_number(text: str) -> tuple[float, float]:
    """(value, default half-ulp tolerance) for a number as written."""
    t = text.strip().replace(",", "")
    scale = 1.0
    if t.endswith("%"):
        t, scale = t[:-1].strip(), 0.01
    try:
        d = Decimal(t)
    except InvalidOperation as e:
        raise ValueError(f"not a number: {text!r}") from e
    exp = d.as_tuple().exponent
    half_ulp = 0.5 * 10.0 ** exp if isinstance(exp, int) else 0.0
    return float(d) * scale, half_ulp * scale


def parse_claims(lines: List[str], source: str = "") -> List[Claim]:
    claims = []
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) not in (3, 4):
            raise ValueError(f"{source}:{n}: expected 3 or 4 '|' fields, got {len(parts)}")
        claims.append(Claim(*parts, source=f"{source}:{n}"))
    return claims


def check(claims: List[Claim], entries: dict) -> List[dict]:
    rows = []
    for c in claims:
        row = {"label": c.label, "key": c.key, "written": c.written, "source": c.source}
        try:
            want, tol = parse_number(c.written)
            if c.tolerance:
                tol = parse_number(c.tolerance)[0]
        except ValueError as e:
            rows.append({**row, "ok": False, "why": str(e)})
            continue
        if c.key not in entries:
            rows.append({**row, "ok": False, "why": "key not in manifest"})
            continue
        got = float(entries[c.key]["value"])
        # 1e-12 absorbs float noise when the written value is exactly on a rounding edge
        ok = abs(got - want) <= tol + 1e-12
        rows.append({**row, "ok": ok, "manifest": got, "tolerance": tol,
                     "run_id": entries[c.key].get("run_id"),
                     "why": "" if ok else f"manifest {got!r} differs from {want!r} by more than {tol!r}"})
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Check quoted numbers against results/manifest.json")
    ap.add_argument("claims_files", nargs="*", type=Path)
    ap.add_argument("--pair", action="append", default=[],
                    help='inline claim "label|key|value[|tol]"')
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    args = ap.parse_args(argv)

    claims: List[Claim] = []
    files: List[Path] = []
    for f in args.claims_files:
        files += sorted(f.glob("*.claims")) if f.is_dir() else [f]
    for f in files:
        claims += parse_claims(f.read_text(encoding="utf-8").splitlines(), str(f))
    claims += parse_claims(args.pair, "--pair")
    if not claims:
        ap.error("no claims given")
    if not args.manifest.exists():
        print(f"manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    entries = json.loads(args.manifest.read_text(encoding="utf-8"))["entries"]

    rows = check(claims, entries)
    bad = [r for r in rows if not r["ok"]]
    for r in rows:
        if r["ok"] and args.quiet:
            continue
        status = "OK  " if r["ok"] else "FAIL"
        extra = f"= {r['manifest']:.6g}" if r["ok"] else r["why"]
        print(f"{status} {r['label']}: {r['written']} [{r['key']}] {extra}")
    print(f"\n{len(rows) - len(bad)}/{len(rows)} claims match the manifest.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
