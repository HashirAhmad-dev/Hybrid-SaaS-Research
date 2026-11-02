"""
cert_rich.py
============
CERT r4.2 richer-features experiment (D-027). Asks whether detection on CERT is
limited by the six mapped features or by the detector: the same detectors, with the
same settings and validation-chosen thresholds, run on BASE (the six engine
features) and on RICH (BASE plus 18 generic per-user-hour counts from the raw logs).

    python -m evaluation.cert_rich agg --cert-dir D:/datasets/cert/extract/r4.2   # slow: reads http.csv (14.5 GB)
    python -m evaluation.cert_rich evaluate

The grid, labels and splits come from results/runs/cert_r4.2/data/sessions_raw.csv
(evaluation/cert_map.py). Aggregates are cached per source in
results/runs/cert_r4.2/rich/, so an interrupted `agg` resumes.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

from evaluation import selection
from evaluation.common import FEATURES, SEQ_LEN, binary_metrics, time_boundaries
from tools.manifest import PROJECT_ROOT, provenance, record

BASE_DIR = PROJECT_ROOT / "results" / "runs" / "cert_r4.2"
OUT = BASE_DIR / "rich"
FMT = "%m/%d/%Y %H:%M:%S"
CHUNK = 2_000_000
DOMAIN = "dtaa.com"
SEED = 42
BOOT_SEED = 20261102
N_BOOT = 2000
PROBE_LAGS = 8                       # as evaluation/drift_detector.py
SD_FLOOR, Z_CLIP = 0.1, 10.0
TARGET = "cert_scenario_2"           # D-024
THRESH_GRID = 4001                   # validation-score quantiles searched for the F1 threshold

COUNTS = ["n_logon", "n_logoff", "n_pcs", "n_new_pcs", "n_dev_connect", "n_file_copies", "n_file_ext",
          "n_exe_zip", "n_mail", "n_ext_rcpt", "n_new_rcpt", "mail_size", "n_attach", "n_ext_attach_mail",
          "n_web", "n_domains", "n_new_domains"]
RICH = list(FEATURES) + COUNTS + ["weekend"]


# ---------------------------------------------------------------------------
# Aggregation from the raw logs
# ---------------------------------------------------------------------------
def grid_info():
    g = pd.read_csv(BASE_DIR / "data" / "sessions_raw.csv", usecols=["user_id", "timestamp", "hour_index"],
                    parse_dates=["timestamp"])
    t0 = g.timestamp[g.hour_index == 0].iloc[0]
    return set(g.user_id.unique()), t0, int(g.hour_index.max()) + 1


def chunks(path: Path, cols, users, t0, H):
    for ch in pd.read_csv(path, usecols=cols, chunksize=CHUNK, dtype=str):
        ch = ch[ch["user"].isin(users)]
        if not len(ch):
            continue
        ch = ch.copy()
        hi = ((pd.to_datetime(ch["date"], format=FMT).dt.floor("h") - t0) // pd.Timedelta(hours=1)).astype(int)
        ch["hour_index"] = hi
        yield ch[(hi >= 0) & (hi < H)]


def first_seen_counts(triples: pd.DataFrame, item: str, name: str) -> pd.Series:
    """Per (user, hour): items appearing for the first time in that user's own history (causal)."""
    t = triples.drop_duplicates(["user", "hour_index", item])
    first = t.groupby(["user", item]).hour_index.transform("min")
    return t[t.hour_index == first].groupby(["user", "hour_index"]).size().rename(name)


def agg_source(name: str, d: Path, users, t0, H) -> None:
    out = OUT / f"agg_{name}.parquet"
    pcs_out = OUT / f"pcs_{name}.parquet"
    if out.exists() and pcs_out.exists():
        print(f"  {name}: cached", flush=True)
        return
    t = time.time()
    parts, pcs, items = [], [], []
    cols = {"logon": ["date", "user", "pc", "activity"], "device": ["date", "user", "pc", "activity"],
            "file": ["date", "user", "pc", "filename"],
            "email": ["date", "user", "pc", "to", "cc", "bcc", "size", "attachments"],
            "http": ["date", "user", "pc", "url"]}[name]
    n = 0
    for ch in chunks(d / f"{name}.csv", cols, users, t0, H):
        n += len(ch)
        pcs.append(ch[["user", "hour_index", "pc"]].drop_duplicates())
        k = ["user", "hour_index"]
        if name == "logon":
            parts.append(pd.DataFrame({"n_logon": (ch.activity == "Logon").groupby([ch.user, ch.hour_index]).sum(),
                                       "n_logoff": (ch.activity == "Logoff").groupby([ch.user, ch.hour_index]).sum()}))
        elif name == "device":
            parts.append((ch.activity == "Connect").groupby([ch.user, ch.hour_index]).sum().rename("n_dev_connect").to_frame())
        elif name == "file":
            ext = ch.filename.str.rsplit(".", n=1).str[-1].str.lower()
            ch = ch.assign(ext=ext, exe_zip=ext.isin(["exe", "zip"]))
            g = ch.groupby(k)
            parts.append(pd.DataFrame({"n_file_copies": g.size(), "n_exe_zip": g.exe_zip.sum()}))
            items.append(ch[["user", "hour_index", "ext"]].drop_duplicates())
        elif name == "email":
            rc = (ch["to"].fillna("") + ";" + ch["cc"].fillna("") + ";" + ch["bcc"].fillna("")).str.split(";")
            ex = rc.explode()
            ex = ex[ex.str.len() > 0]
            rt = pd.DataFrame({"user": ch.user.loc[ex.index].to_numpy(), "hour_index": ch.hour_index.loc[ex.index].to_numpy(),
                               "rcpt": ex.str.lower().to_numpy()})
            rt["ext"] = ~rt.rcpt.str.endswith("@" + DOMAIN)
            n_ext = rt.groupby(["user", "hour_index"]).ext.sum()
            has_ext = rt.assign(mid=ex.index.to_numpy()).groupby("mid").ext.any()
            att = pd.to_numeric(ch.attachments, errors="coerce").fillna(0)
            ch = ch.assign(size=pd.to_numeric(ch["size"], errors="coerce").fillna(0), att=att,
                           ext_att=(has_ext.reindex(ch.index).fillna(False).to_numpy() & (att.to_numpy() > 0)))
            g = ch.groupby(k)
            parts.append(pd.DataFrame({"n_mail": g.size(), "mail_size": g["size"].sum(), "n_attach": g.att.sum(),
                                       "n_ext_attach_mail": g.ext_att.sum()}).join(n_ext.rename("n_ext_rcpt")))
            items.append(rt[["user", "hour_index", "rcpt"]].drop_duplicates())
        elif name == "http":
            dom = ch.url.str.split("/", n=3).str[2].str.lower()
            ch = ch.assign(domain=dom)
            parts.append(ch.groupby(k).size().rename("n_web").to_frame())
            items.append(ch[["user", "hour_index", "domain"]].drop_duplicates())
        print(f"  {name}: {n:,} events of selected users, {time.time() - t:.0f} s", flush=True)
    agg = pd.concat(parts).groupby(level=[0, 1]).sum()
    agg.index.names = ["user", "hour_index"]
    if name == "file":
        it = pd.concat(items).drop_duplicates()
        agg = agg.join(it.groupby(["user", "hour_index"]).size().rename("n_file_ext"))
    if name == "email":
        agg = agg.join(first_seen_counts(pd.concat(items), "rcpt", "n_new_rcpt"))
    if name == "http":
        it = pd.concat(items).drop_duplicates()
        agg = agg.join(it.groupby(["user", "hour_index"]).size().rename("n_domains"))
        agg = agg.join(first_seen_counts(it, "domain", "n_new_domains"))
    OUT.mkdir(parents=True, exist_ok=True)
    agg.fillna(0).astype(float).reset_index().to_parquet(out, index=False)
    pd.concat(pcs).drop_duplicates().to_parquet(pcs_out, index=False)
    print(f"  {name}: done in {time.time() - t:.0f} s", flush=True)


def stage_agg(cert_dir: Path) -> None:
    users, t0, H = grid_info()
    print(f"{len(users)} users, {H} hours from {t0}", flush=True)
    for name in ("logon", "device", "file", "email", "http"):
        agg_source(name, cert_dir, users, t0, H)
    pcs = pd.concat([pd.read_parquet(OUT / f"pcs_{n}.parquet")
                     for n in ("logon", "device", "file", "email", "http")]).drop_duplicates()
    pc_agg = pd.DataFrame({"n_pcs": pcs.groupby(["user", "hour_index"]).size()}).join(
        first_seen_counts(pcs, "pc", "n_new_pcs"))
    pc_agg.fillna(0).astype(float).reset_index().to_parquet(OUT / "agg_pcs.parquet", index=False)
    print("agg done", flush=True)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def load_rows() -> pd.DataFrame:
    cols = ["user_id", "timestamp", "hour_index", "active", "is_true_threat", "threat_class", "episode_id",
            "split", *FEATURES]
    df = pd.read_csv(BASE_DIR / "data" / "sessions_raw.csv", usecols=cols, parse_dates=["timestamp"],
                     low_memory=False)
    H = int(df.hour_index.max()) + 1
    df = df[df.active].copy()
    df["threat_class"] = df["threat_class"].where(df["threat_class"].notna(), None)
    for n in ("logon", "device", "file", "email", "http", "pcs"):
        a = pd.read_parquet(OUT / f"agg_{n}.parquet").rename(columns={"user": "user_id"})
        df = df.merge(a, on=["user_id", "hour_index"], how="left")
    for c in COUNTS:
        df[c] = np.log1p(df[c].fillna(0.0) if c in df else 0.0)
    df["weekend"] = (df.timestamp.dt.dayofweek >= 5).astype(float)
    df = df.sort_values(["user_id", "hour_index"]).reset_index(drop=True)
    df.attrs["H"] = H
    return df


def personal_z(df: pd.DataFrame, feats, fit: np.ndarray) -> np.ndarray:
    X = df[feats].to_numpy(dtype=float)
    Z = np.zeros_like(X)
    for u, idx in df.groupby("user_id", sort=False).indices.items():
        f = idx[fit[idx]]
        ref = X[f] if len(f) else X[idx]
        mu, sd = ref.mean(axis=0), np.maximum(ref.std(axis=0), SD_FLOOR)
        Z[idx] = np.clip((X[idx] - mu) / sd, -Z_CLIP, Z_CLIP)
    return Z


def lagged(df: pd.DataFrame, Z: np.ndarray) -> np.ndarray:
    z = pd.DataFrame(Z)
    return z.groupby(df.user_id.to_numpy()).transform(
        lambda s: s.shift(1).rolling(PROBE_LAGS, min_periods=1).mean()).fillna(0.0).to_numpy()


def val_threshold(s, y, split) -> float:
    v = split == "val"
    grid = np.r_[np.unique(np.quantile(s[v], np.linspace(0, 1, THRESH_GRID))), np.inf]
    return selection.threshold_max_f1(s[v], y[v], split[v], grid=grid)[0]


def metrics(s, y, split, tc, eid) -> dict:
    te = split == "test"
    t = val_threshold(s, y, split)
    flag = s >= t
    m = binary_metrics(y[te], flag[te])
    sel = te & (tc == TARGET)
    eps = pd.unique(eid[sel])
    return {"auc": selection.auc_rank(s[te], y[te]), "average_precision": float(average_precision_score(y[te], s[te])),
            **{k: m[k] for k in ("precision", "recall", "f1", "fpr", "tp", "fp")},
            "val_threshold": float(t),
            "scenario2_episode_recall": float(np.mean([flag[te & (eid == e)].any() for e in eps])) if len(eps) else np.nan,
            "scenario2_hour_recall": float(flag[sel].mean()) if sel.any() else np.nan}


def stage_evaluate() -> None:
    t_start = time.time()
    df = load_rows()
    b = time_boundaries(df.attrs["H"])
    df = df[df.hour_index >= SEQ_LEN - 1].reset_index(drop=True)           # the ablation's scoreable rows
    y = df.is_true_threat.to_numpy(dtype=bool)
    split = df.split.to_numpy()
    tc, eid = df.threat_class.to_numpy(), df.episode_id.to_numpy()
    fit = df.hour_index.to_numpy() < b["fit_end"]
    tr = split == "train"
    print(f"{len(df):,} scoreable active hours; test positives {int(y[split == 'test'].sum())}", flush=True)

    scores, res = {}, {}
    for fs_name, feats in (("base", list(FEATURES)), ("rich", RICH)):
        X = df[feats].to_numpy(dtype=float)
        sc = StandardScaler().fit(X[fit])
        iso = IsolationForest(n_estimators=200, contamination="auto", random_state=SEED, n_jobs=-1).fit(sc.transform(X[fit]))
        scores[(fs_name, "iforest")] = -iso.score_samples(sc.transform(X))
        Z = personal_z(df, feats, fit)
        scores[(fs_name, "zscore")] = np.abs(Z).max(axis=1)
        P = np.hstack([Z, lagged(df, Z)])
        lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit(P[tr], y[tr])
        scores[(fs_name, "probe_logistic")] = lr.predict_proba(P)[:, 1]
        gb = HistGradientBoostingClassifier(random_state=SEED, class_weight="balanced").fit(P[tr], y[tr])
        scores[(fs_name, "probe_boosting")] = gb.predict_proba(P)[:, 1]
        for det in ("iforest", "zscore", "probe_logistic", "probe_boosting"):
            res.setdefault(fs_name, {})[det] = metrics(scores[(fs_name, det)], y, split, tc, eid)
            print(f"  {fs_name:4s} {det:15s} AUC {res[fs_name][det]['auc']:.3f}  F1 {res[fs_name][det]['f1']:.3f}",
                  flush=True)

    # paired user-level bootstrap of the test AUC difference (rich - base)
    te = split == "test"
    users = df.user_id.to_numpy()[te]
    yt = y[te]
    uidx = pd.Series(np.arange(len(users))).groupby(users).indices
    ins = [u for u, i in uidx.items() if yt[i].any()]
    non = [u for u in uidx if u not in set(ins)]
    rng = np.random.default_rng(BOOT_SEED)
    diffs = {d: [] for d in ("iforest", "zscore", "probe_logistic", "probe_boosting")}
    for _ in range(N_BOOT):
        pick = np.concatenate([uidx[u] for u in rng.choice(ins, len(ins))] + [uidx[u] for u in rng.choice(non, len(non))])
        for d in diffs:
            diffs[d].append(selection.auc_rank(scores[("rich", d)][te][pick], yt[pick]) -
                            selection.auc_rank(scores[("base", d)][te][pick], yt[pick]))
    res["auc_diff_rich_minus_base"] = {d: {"point": res["rich"][d]["auc"] - res["base"][d]["auc"],
                                           "ci_low": float(np.percentile(v, 2.5)),
                                           "ci_high": float(np.percentile(v, 97.5))} for d, v in diffs.items()}
    res["_meta"] = {"scoreable_hours": int(len(df)), "test_positive_hours": int(yt.sum()),
                    "test_insiders": len(ins), "test_users": len(uidx), "rich_features": RICH,
                    "decision": "docs/DECISIONS.md D-027", "minutes": (time.time() - t_start) / 60}
    for d, v in res["auc_diff_rich_minus_base"].items():
        print(f"  AUC rich - base {d:15s} {v['point']:+.3f} [{v['ci_low']:+.3f}, {v['ci_high']:+.3f}]", flush=True)
    seeds = {"iforest_and_boosting": SEED, "bootstrap": BOOT_SEED, "user_sample": 42}
    out = {"results": res, "provenance": provenance("evaluation/cert_rich.py", seeds)}
    (OUT / "rich_metrics.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    record("cert.rich", {k: v for k, v in res.items() if k != "_meta"} | {"_meta": {k: v for k, v in res["_meta"].items()
                                                                                    if k != "rich_features"}},
           script="evaluation/cert_rich.py", seeds=seeds)
    print(f"-> {OUT / 'rich_metrics.json'}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["agg", "evaluate"])
    ap.add_argument("--cert-dir", type=Path, default=Path("D:/datasets/cert/extract/r4.2"))
    a = ap.parse_args()
    stage_agg(a.cert_dir) if a.stage == "agg" else stage_evaluate()


if __name__ == "__main__":
    main()
