"""
render_figures.py
=================
Renders the editable figure sources in figures/*.dot to vector PDF and SVG with
Graphviz `dot`. Looks for dot on PATH, then in external/graphviz/ (portable copy,
gitignored; see docs/ENVIRONMENT.md).

    python -m tools.render_figures
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tools.manifest import PROJECT_ROOT

FIG = PROJECT_ROOT / "figures"


def find_dot() -> str:
    d = shutil.which("dot")
    if d:
        return d
    hits = sorted((PROJECT_ROOT / "external" / "graphviz").glob("*/bin/dot.exe"))
    if hits:
        return str(hits[0])
    raise SystemExit("Graphviz dot not found (PATH or external/graphviz/*/bin/dot.exe)")


def main() -> None:
    dot = find_dot()
    for src in sorted(FIG.glob("*.dot")):
        for fmt in ("pdf", "svg"):
            out = src.with_suffix(f".{fmt}")
            subprocess.run([dot, f"-T{fmt}", str(src), "-o", str(out)], check=True)
            print(f"  -> {out}")


if __name__ == "__main__":
    main()
