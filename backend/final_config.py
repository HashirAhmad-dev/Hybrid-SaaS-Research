"""
final_config.py
===============
Paper-v2 task T4.1: the enforcement configuration the backend actually runs,
loaded from backend/config/final_config.json (generated from
results/manifest.json by tools/build_backend_config.py). Each value carries the
manifest key it came from; `decide()` returns those sources with every decision.

Enforcement (gated fusion, T2.5):
    r = S (1 + beta A) / 100
    if A >= tau_A: BLOCK (escalated on behaviour alone, whatever S is)
    elif r >= t_block: BLOCK; elif r >= t_alert: ALERT; else PERMIT
    a CUSUM drift alarm (T2.4) raises PERMIT to ALERT (review, not auto-block)
"""
from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "final_config.json"


@lru_cache(maxsize=1)
def config() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def val(*path: str):
    c = config()
    for p in path:
        c = c[p]
    return c["value"]


def decide(S: float, A: float, drift_alarm: bool = False) -> Dict[str, Any]:
    beta, tau_a = val("enforcement", "beta"), val("enforcement", "tau_A")
    t_alert, t_block = val("enforcement", "t_alert"), val("enforcement", "t_block")
    s = min(max(float(S), 0.0), 100.0)
    a = min(max(float(A), 0.0), 1.0)
    r = s * (1.0 + beta * a) / 100.0
    if a >= tau_a:
        action, why = "BLOCK", "A >= tau_A (behaviour alone)"
    elif r >= t_block:
        action, why = "BLOCK", "risk >= t_block"
    elif r >= t_alert:
        action, why = "ALERT", "risk >= t_alert"
    else:
        action, why = "PERMIT", "risk below t_alert"
    if drift_alarm and action == "PERMIT":
        action, why = val("drift", "action_on_alarm"), "CUSUM drift alarm"
    c = config()
    return {"action": action, "reason": why, "risk": r,
            "sources": {k: c["enforcement"][k]["source"] for k in ("form", "beta", "tau_A", "t_alert", "t_block")}
                       | {"drift_k": c["drift"]["k"]["source"], "drift_h": c["drift"]["h"]["source"]}}


class DriftState:
    """Per-user two-sided CUSUM over personal z of active-hour feature vectors (T2.4)."""

    def __init__(self):
        self._s: Dict[str, tuple] = {}
        self._lock = threading.Lock()

    def update(self, user_id: str, z: np.ndarray) -> bool:
        k, h = val("drift", "k"), val("drift", "h")
        with self._lock:
            sp, sn = self._s.get(user_id, (np.zeros_like(z), np.zeros_like(z)))
            sp = np.maximum(0.0, sp + z - k)
            sn = np.maximum(0.0, sn - z - k)
            alarm = bool(max(sp.max(), sn.max()) > h)
            if alarm:
                sp, sn = np.zeros_like(z), np.zeros_like(z)
            self._s[user_id] = (sp, sn)
        return alarm


DRIFT = DriftState()
