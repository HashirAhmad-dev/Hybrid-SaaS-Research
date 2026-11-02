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
import re
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


NUM_RE = re.compile(r"(?<![\w.])(\d+\.\d+)(\s*(?:%|percent))?")


def _matches(token: str, pct: bool, value: float) -> bool:
    """True when `token` is a correct rounding of `value` (as a fraction or a percentage)."""
    want, tol = parse_number(token)
    for v in ((value * 100,) if pct else (value, value * 100)):
        if abs(v - want) <= tol + 1e-12:
            return True
    return False


def check_definitions(spec_path: Path, entries: dict, root: Path = PROJECT_ROOT) -> List[dict]:
    """One definition per repeated quantity (F3).

    For every definition: the canonical and variant keys must exist and have different
    values. In every prose file, a line that talks about the quantity (`subject`) may
    quote a variant's value only if the line also names that variant (`qualifier`);
    otherwise a reader would take it for the canonical quantity.
    """
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    files = sorted({p for pat in spec["prose"] for p in root.glob(pat)})
    rows = []
    for d in spec["definitions"]:
        keys = [d["canonical"]["key"]] + [v["key"] for v in d["variants"]]
        missing = [k for k in keys if k not in entries]
        if missing:
            rows.append({"ok": False, "where": d["id"], "why": f"keys not in manifest: {missing}"})
            continue
        canon = float(entries[d["canonical"]["key"]]["value"])
        subj = re.compile(d["subject"], re.I)
        for v in d["variants"]:
            val = float(entries[v["key"]]["value"])
            if abs(val - canon) < 5e-4:
                rows.append({"ok": False, "where": d["id"],
                             "why": f"variant {v['key']} equals the canonical value to 3 decimals"})
            qual = re.compile(v["qualifier"], re.I)
            for f in files:
                for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if not subj.search(line) or qual.search(line):
                        continue
                    for m in NUM_RE.finditer(line):
                        tok, pct = m.group(1), bool(m.group(2))
                        if _matches(tok, pct, val) and not _matches(tok, pct, canon):
                            rows.append({"ok": False, "where": f"{f.relative_to(root)}:{n}",
                                         "why": f"{d['id']}: {tok} is '{v['name']}' ({v['key']}) "
                                                f"but the line does not say so (qualifier /{v['qualifier']}/)"})
        rows.append({"ok": True, "where": d["id"], "why": ""})
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Check quoted numbers against results/manifest.json")
    ap.add_argument("claims_files", nargs="*", type=Path)
    ap.add_argument("--pair", action="append", default=[],
                    help='inline claim "label|key|value[|tol]"')
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    ap.add_argument("--definitions", type=Path, default=None,
                    help="definitions.json: one definition per repeated quantity, checked in the prose files "
                         "(default: results/claims/definitions.json when a claims folder is given)")
    args = ap.parse_args(argv)
    if args.definitions is None:
        dflt = PROJECT_ROOT / "results" / "claims" / "definitions.json"
        if any(f.is_dir() and f.resolve() == dflt.parent.resolve() for f in args.claims_files):
            args.definitions = dflt

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
    dbad = []
    if args.definitions:
        drows = check_definitions(args.definitions, entries)
        dbad = [r for r in drows if not r["ok"]]
        for r in dbad:
            print(f"FAIL definition {r['where']}: {r['why']}")
        n_def = sum(1 for r in drows if r["ok"])
        print(f"{n_def} definitions checked; {len(dbad)} prose uses of a variant without its label.")
    return 1 if (bad or dbad) else 0


if __name__ == "__main__":
    sys.exit(main())
