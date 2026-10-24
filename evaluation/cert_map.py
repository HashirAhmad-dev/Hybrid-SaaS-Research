"""
cert_map.py
===========
Paper-v2 task T2.6: map CERT Insider Threat r4.2 onto the engine's hourly
per-user six-feature scheme (definitions in docs/CERT_MAPPING.md) and write a
sessions_raw.csv that evaluation/train_and_evaluate.py, evaluation/ablation.py and
evaluation/drift_detector.py can read unchanged.

    python -m evaluation.cert_map --cert-dir D:/datasets/cert/r4.2 --answers D:/datasets/cert/answers
Output: results/runs/cert_r4.2/data/{sessions_raw.csv, generation_config.json}
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.common import FEATURES, time_boundaries
from tools.manifest import PROJECT_ROOT, provenance, record

OUT = PROJECT_ROOT / "results" / "runs" / "cert_r4.2" / "data"
N_NORMAL_USERS = 130
USER_SEED = 42
FMT = "%m/%d/%Y %H:%M:%S"
CHUNK = 2_000_000
DOMAIN = "dtaa.com"                     # CERT's internal e-mail domain


def read(path: Path, cols, users):
    for ch in pd.read_csv(path, usecols=cols, chunksize=CHUNK, dtype=str):
        ch = ch[ch["user"].isin(users)]
        if len(ch):
            ch = ch.copy()
            ch["hour"] = pd.to_datetime(ch["date"], format=FMT).dt.floor("h")
            yield ch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cert-dir", type=Path, required=True)
    ap.add_argument("--answers", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    args = ap.parse_args()
    d = args.cert_dir

    ins = pd.read_csv(args.answers / "insiders.csv", dtype=str)
    ins = ins[ins.dataset == "4.2"]
    insiders = sorted(ins.user.unique())
    all_users = sorted(pd.read_csv(d / "logon.csv", usecols=["user"], dtype=str).user.unique())
    rng = np.random.default_rng(USER_SEED)
    normals = sorted(rng.choice(sorted(set(all_users) - set(insiders)), N_NORMAL_USERS, replace=False))
    users = set(insiders) | set(normals)
    print(f"users: {len(insiders)} insiders + {len(normals)} sampled normals", flush=True)

    count = defaultdict(int)                 # (user, hour) -> events
    pc = defaultdict(int)                    # (user, hour, pc) -> events
    dev = defaultdict(int); fcopy = defaultdict(int)
    mail_int = defaultdict(int); mail_ext = defaultdict(int)
    rcpt = defaultdict(set)
    t_min, t_max = None, None

    def add(ch, kind):
        nonlocal t_min, t_max
        t_min = ch.hour.min() if t_min is None else min(t_min, ch.hour.min())
        t_max = ch.hour.max() if t_max is None else max(t_max, ch.hour.max())
        for (u, h), n in ch.groupby(["user", "hour"]).size().items():
            count[(u, h)] += n
        for (u, h, p), n in ch.groupby(["user", "hour", "pc"]).size().items():
            pc[(u, h, p)] += n
        if kind == "device":
            for (u, h), n in ch[ch.activity == "Connect"].groupby(["user", "hour"]).size().items():
                dev[(u, h)] += n
        if kind == "file":
            for (u, h), n in ch.groupby(["user", "hour"]).size().items():
                fcopy[(u, h)] += n
        if kind == "email":
            to = (ch["to"].fillna("") + ";" + ch["cc"].fillna("") + ";" + ch["bcc"].fillna(""))
            for u, h, t in zip(ch.user, ch.hour, to):
                rs = [r for r in t.split(";") if r]
                ext = any(not r.lower().endswith("@" + DOMAIN) for r in rs)
                (mail_ext if ext else mail_int)[(u, h)] += 1
                rcpt[(u, h)].update(rs)

    for name, cols, kind in (("logon.csv", ["date", "user", "pc", "activity"], "logon"),
                             ("device.csv", ["date", "user", "pc", "activity"], "device"),
                             ("file.csv", ["date", "user", "pc"], "file"),
                             ("email.csv", ["date", "user", "pc", "to", "cc", "bcc"], "email"),
                             ("http.csv", ["date", "user", "pc"], "http")):
        n = 0
        for ch in read(d / name, cols, users):
            add(ch, kind)
            n += len(ch)
        print(f"  {name}: {n:,} events of selected users", flush=True)

    hours = pd.date_range(t_min, t_max, freq="h")
    H = len(hours)
    hidx = {h: i for i, h in enumerate(hours)}
    b = time_boundaries(H)

    # malicious events -> positive hours
    pos = {}
    for _, r in ins.iterrows():
        f = args.answers / f"r4.2-{r.scenario}" / r.details
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split(",")
            if len(parts) > 3 and parts[3] == r.user:
                h = pd.Timestamp(pd.to_datetime(parts[2], format=FMT)).floor("h")
                pos[(r.user, h)] = (f"cert_scenario_{r.scenario}", f"{r.user}-S{r.scenario}")

    fit_pcs = defaultdict(lambda: defaultdict(int))     # user -> pc -> FIT-period events
    for (uu, h, p), n in pc.items():
        if hidx[h] < b["fit_end"]:
            fit_pcs[uu][p] += n

    rows = []
    for u in sorted(users):
        cnt = np.array([count.get((u, h), 0) for h in hours], dtype=float)
        active = cnt > 0
        fit = np.arange(H) < b["fit_end"]
        # modal PC and usual hours from the FIT period only
        pcs = fit_pcs.get(u, {})
        home_pc = max(pcs, key=pcs.get) if pcs else None
        fit_days = max(1, b["fit_end"] // 24)
        hour_of_day = np.array([h.hour for h in hours])
        usual = np.array([(active & fit & (hour_of_day == k)).sum() / fit_days >= 0.05 for k in range(24)])
        rc = np.array([len(rcpt.get((u, h), ())) for h in hours], dtype=float)
        p99 = max(np.percentile(rc[fit & active], 99) if (fit & active).any() else 1.0, 1.0)
        prev = pd.Series(cnt).shift(1)
        roll = prev.rolling(168, min_periods=6).mean().fillna(prev.expanding(min_periods=1).mean()).fillna(1.0)
        rate = np.clip(cnt / roll.clip(lower=0.25).to_numpy(), 0, 10)
        for i, h in enumerate(hours):
            if not active[i]:
                rows.append((u, h, i, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False))
                continue
            fc = fcopy.get((u, h), 0)
            ftc = 0.0 if fc == 0 else (1 / 3 if fc == 1 else (2 / 3 if fc <= 5 else 1.0))
            other = cnt[i] - pc.get((u, h, home_pc), 0) if home_pc else 0.0
            geo = float(np.clip(other / cnt[i], 0, 1))
            op = 1.0 if fc else (0.75 if dev.get((u, h), 0) else (0.5 if mail_ext.get((u, h), 0)
                                                                    else (0.25 if mail_int.get((u, h), 0) else 0.0)))
            perm = 0.0 if usual[h.hour] else 1.0
            collab = float(np.clip(rc[i] / p99, 0, 1))
            rows.append((u, h, i, float(cnt[i]), float(rate[i]), ftc, geo, op, perm, collab, True))
    df = pd.DataFrame(rows, columns=["user_id", "timestamp", "hour_index", "calls", "activity_rate",
                                     "file_type_category", "geo_index", "endpoint_operation",
                                     "permission_scope_delta", "collaboration_density", "active"])
    lab = df.apply(lambda r: pos.get((r.user_id, r.timestamp)), axis=1)
    df["is_true_threat"] = lab.notna() & df.active
    df["threat_class"] = [x[0] if x and a else None for x, a in zip(lab, df.active)]
    df["episode_id"] = [x[1] if x and a else None for x, a in zip(lab, df.active)]
    df["is_benign_burst"] = False
    df["split"] = np.where(df.hour_index < b["train_end"], "train",
                           np.where(df.hour_index < b["val_end"], "val", "test"))
    df["activity_rate_per_hr"] = df.calls
    df["pii_sensitivity_score"] = 50
    df["file_class"] = "internal"; df["endpoint_class"] = "read"; df["origin_city"] = "n/a"
    df["user_name"] = df.user_id; df["department"] = "n/a"; df["platform"] = "CERT r4.2"
    df["file_accessed"] = "n/a"; df["time_gap_sec"] = 3600.0
    df["event_id"] = [f"CERT-{i + 1:08d}" for i in range(len(df))]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_dir / "sessions_raw.csv", index=False)
    act = df[df.active]
    stats = {"users": len(users), "insiders": len(insiders), "hours": H, "grid_rows": len(df),
             "active_sessions": int(act.shape[0]), "positive_sessions": int(act.is_true_threat.sum()),
             "positives_by_split": {s: int(act[act.split == s].is_true_threat.sum()) for s in ("train", "val", "test")},
             "insiders_with_test_positives": int(act[(act.split == "test") & act.is_true_threat].user_id.nunique()),
             "by_scenario": {k: int(v) for k, v in act.threat_class.value_counts().items()},
             "t_min": str(t_min), "t_max": str(t_max), "mapping": "docs/CERT_MAPPING.md"}
    cfg = {"args": {"seed": USER_SEED, "source": "CERT r4.2", "n_normal_users": N_NORMAL_USERS},
           "realised": stats, "provenance": provenance("evaluation/cert_map.py", {"user_sample": USER_SEED})}
    (args.out_dir / "generation_config.json").write_text(json.dumps(cfg, indent=1, default=str), encoding="utf-8")
    record("cert.mapping", stats, script="evaluation/cert_map.py", seeds={"user_sample": USER_SEED})
    print(json.dumps(stats, indent=1, default=str))


if __name__ == "__main__":
    main()
