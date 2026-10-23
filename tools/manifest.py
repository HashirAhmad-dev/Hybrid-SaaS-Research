"""
manifest.py
===========
`results/manifest.json` is the machine-readable source of truth for every number
the paper may quote. Evaluation scripts call `record()` at the end of a run.

Layout
------
    {
      "schema": 1,
      "runs":    { run_id: {script, command, seeds, date_utc, git_hash, git_dirty,
                            python, platform, libraries, device, note} },
      "entries": { key: {"value": number, "run_id": run_id} }
    }

Keys are dot paths, e.g. `anomaly.s42.test_flag_level.hybrid.f1`. A key is
overwritten by a later run that records the same key; the run that produced the
current value is always named next to it, and the old run's metadata stays in
`runs` so the history is never silently lost.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = PROJECT_ROOT / "results" / "manifest.json"

LIBRARIES = ("numpy", "pandas", "scikit-learn", "scipy", "torch", "presidio_analyzer",
             "spacy", "easyocr", "Faker", "pillow", "paddleocr", "paddlepaddle",
             "openai")


def git_state() -> Dict[str, Any]:
    """Current commit and whether tracked files differ from it."""
    def run(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    head = run("rev-parse", "HEAD")
    dirty = bool(run("status", "--porcelain", "--untracked-files=no"))
    return {"git_hash": head or None, "git_dirty": dirty}


def library_versions(names: Iterable[str] = LIBRARIES) -> Dict[str, str]:
    out = {}
    for n in names:
        try:
            out[n] = metadata.version(n)
        except metadata.PackageNotFoundError:
            continue
    return out


def flatten(obj: Any, prefix: str = "") -> Dict[str, float]:
    """Numeric leaves of a nested dict/list as {dot.path: value}. Bools are skipped."""
    out: Dict[str, float] = {}
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}.{i}" if prefix else str(i)))
    elif isinstance(obj, bool) or obj is None:
        pass
    elif isinstance(obj, (int, float)):
        out[prefix] = obj
    else:
        try:                                   # numpy scalars
            import numpy as np
            if isinstance(obj, np.generic) and np.issubdtype(type(obj), np.number):
                out[prefix] = obj.item()
        except ImportError:
            pass
    return out


def load(path: Path = MANIFEST) -> Dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema": 1, "runs": {}, "entries": {}}


def _write(m: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")
    # Windows: a virus scanner or indexer can hold the target open for a moment
    # right after it was written, and os.replace then fails with WinError 5.
    import time
    for attempt in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.2)


def new_run_id(script: str) -> str:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{Path(script).stem}-{stamp}"


def record(prefix: str, values: Mapping[str, Any], *, script: str,
           seeds: Optional[Mapping[str, Any]] = None, run_id: Optional[str] = None,
           device: Optional[str] = None, note: str = "",
           git: Optional[Dict[str, Any]] = None, date_utc: Optional[str] = None,
           path: Path = MANIFEST) -> str:
    """Store the numeric leaves of `values` under `prefix.*` and log the run.

    Returns the run id. `git` and `date_utc` are only overridden when ingesting
    files produced by an earlier commit (see tools/ingest_baseline.py).
    """
    if os.environ.get("HYBRIDSAAS_MANIFEST_READONLY"):   # tests: never touch the real manifest
        return run_id or "readonly"
    with _lock(path):
        return _record_locked(prefix, values, script=script, seeds=seeds, run_id=run_id,
                              device=device, note=note, git=git, date_utc=date_utc, path=path)


class _lock:
    """Cross-process lock (exclusive create of <manifest>.lock) around read-modify-write."""

    def __init__(self, path: Path):
        self.lock = path.with_suffix(".lock")

    def __enter__(self):
        import time
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3000):                       # up to ~10 min
            try:
                self.fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                time.sleep(0.2)
        raise TimeoutError(f"could not lock {self.lock}; delete it if no job is running")

    def __exit__(self, *exc):
        os.close(self.fd)
        os.remove(self.lock)


def _record_locked(prefix, values, *, script, seeds, run_id, device, note, git, date_utc, path) -> str:
    m = load(path)
    run_id = run_id or new_run_id(script)
    run = m["runs"].get(run_id, {})
    run.update({
        "script": script,
        "command": " ".join([Path(sys.executable).name, *sys.argv]),
        "seeds": dict(seeds or {}),
        "date_utc": date_utc or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        **(git if git is not None else git_state()),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "libraries": library_versions(),
        "device": device,
        "note": note,
    })
    prefixes = set(run.get("prefixes", []))
    prefixes.add(prefix)
    run["prefixes"] = sorted(prefixes)
    run.setdefault("scripts", {})[prefix] = script   # one run id may cover several files
    m["runs"][run_id] = run
    for k, v in flatten(values, prefix).items():
        m["entries"][k] = {"value": v, "run_id": run_id}
    _write(m, path)
    return run_id


def get(key: str, path: Path = MANIFEST) -> Dict[str, Any]:
    m = load(path)
    if key not in m["entries"]:
        raise KeyError(key)
    return m["entries"][key]


def provenance(script: str, seeds: Optional[Mapping[str, Any]] = None,
               device: Optional[str] = None) -> Dict[str, Any]:
    """Block embedded in every results file: what produced it, and where."""
    return {
        "script": script,
        "command": " ".join([Path(sys.executable).name, *sys.argv]),
        "seeds": dict(seeds or {}),
        "date_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        **git_state(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "libraries": library_versions(),
        "device": device,
    }
