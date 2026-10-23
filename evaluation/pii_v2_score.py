"""
pii_v2_score.py
===============
Scoring for evaluation/pii_v2.py (T3.1 to T3.5). Reads the cached OCR, Presidio
and VLM outputs and writes every number to the manifest (prefix pii2.*) and to
results/pii_v2/*.csv.

Discipline: the document split is fixed (pii_v2.assign_split). The cascade tau
and the router are chosen on CALIB documents only (selection.require_selection_split
with allowed=("calib",)); all reported metrics are on EVAL documents. The v1
subset (the original 120 documents) is reported separately from the v2 main set.

What is computed (EVAL, per subset):
  * Branch 1: Presidio and Presidio+ (T3.5) on text documents, per entity type.
  * Images: OCR+Presidio per OCR engine; VLM per local model; per difficulty and type.
  * OCR confidence behaviour: mean confidence per difficulty level, Spearman
    correlation between confidence and per-document OCR+Presidio F1, and the AUC
    of confidence for telling easy from hard documents.
  * Cascade per (OCR engine, VLM): Pareto points over tau (cost = OCR seconds +
    VLM seconds for routed documents, per image; F1 on EVAL), the CALIB-chosen
    tau and its EVAL F1.
  * Router (T3.4b): logistic regression on cheap features, trained on CALIB to
    predict "the VLM finds more correct entities than OCR+Presidio on this
    document"; its decision threshold is chosen on CALIB; compared on EVAL with
    the single confidence threshold at the same share of documents sent to the VLM.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression

from evaluation import selection
from evaluation.pii_common import ENTITY_TYPES, match_entities
from evaluation.pii_v2 import DATA, OUT, assign_split, load_docs
from tools.manifest import record

TAU_GRID = np.round(np.arange(0.0, 1.0001, 0.01), 2)


def cnt(gold, pred) -> np.ndarray:
    tp, fp, fn, _ = match_entities(gold, pred)
    return np.array([tp, fp, fn], dtype=float)


def prf_arr(c) -> Dict[str, float]:
    tp, fp, fn = c
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": int(tp), "fp": int(fp), "fn": int(fn), "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0}


def by_type(docs, preds) -> Dict[str, dict]:
    out = {}
    for t in ENTITY_TYPES:
        c = np.zeros(3)
        for d in docs:
            c += cnt([e for e in d["entities"] if e["type"] == t],
                     [e for e in preds.get(d["doc_id"], []) if e["type"] == t])
        out[t] = prf_arr(c)
    return out


def group_score(docs, preds) -> dict:
    c = sum((cnt(d["entities"], preds.get(d["doc_id"], [])) for d in docs), np.zeros(3))
    return prf_arr(c)


def choose_tau(conf, c_ocr, c_vlm, splits) -> float:
    """CALIB-only: tau maximising cascade micro-F1 (route to VLM when conf < tau)."""
    selection.require_selection_split(splits, allowed=selection.PII_SELECTION_SPLITS, what="choose_tau")
    best, best_f = 0.0, -1.0
    for tau in TAU_GRID:
        use_vlm = conf < tau
        c = c_ocr[~use_vlm].sum(axis=0) + c_vlm[use_vlm].sum(axis=0)
        f = prf_arr(c)["f1"]
        if f > best_f + 1e-12:
            best, best_f = float(tau), f
    return best


def router_features(rec_ocr: dict, presidio_ents: List[dict]) -> List[float]:
    txt = rec_ocr["transcript"]
    n = len(presidio_ents)
    return [rec_ocr["confidence"], np.log1p(len(txt)), n, n / max(len(txt), 1) * 100.0,
            np.log(rec_ocr["width"] * rec_ocr["height"]), rec_ocr["boxes"]]


ROUTER_FEATURES = ("ocr_confidence", "log_transcript_chars", "presidio_hits",
                   "hits_per_100_chars", "log_image_pixels", "ocr_boxes")


def score_all() -> None:
    docs = load_docs()
    split = assign_split(docs)
    pres = json.loads((DATA / "presidio_predictions.json").read_text(encoding="utf-8"))
    ocr_engines = {f.stem.removeprefix("ocr_"): json.loads(f.read_text(encoding="utf-8"))
                   for f in sorted(DATA.glob("ocr_*.json"))}
    vlms = {f.stem.removeprefix("vlm_"): json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(DATA.glob("vlm_*.json"))}
    OUT.mkdir(parents=True, exist_ok=True)
    results: Dict[str, dict] = {"_meta": {"split_counts": {s: sum(1 for v in split.values() if v == s)
                                                           for s in ("calib", "eval")},
                                          "ocr_engines": list(ocr_engines), "vlms": list(vlms)}}
    rows_csv = []

    for subset in ("v2", "v1"):
        S = {}
        sub = [d for d in docs if d["subset"] == subset]
        ev = [d for d in sub if split[d["doc_id"]] == "eval"]
        cal = [d for d in sub if split[d["doc_id"]] == "calib"]
        ev_text = [d for d in ev if d["category"] == "text_extractable"]
        ev_img = [d for d in ev if d["category"] != "text_extractable"]
        cal_img = [d for d in cal if d["category"] != "text_extractable"]
        S["n_eval_docs"], S["n_calib_docs"] = len(ev), len(cal)
        S["n_eval_entities"] = sum(len(d["entities"]) for d in ev)

        # Branch 1 (T3.5 before/after)
        for an in ("presidio", "presidio_plus"):
            p = {k: v["entities"] for k, v in pres[an]["text"].items()}
            S[f"branch1.{an}"] = {"all": group_score(ev_text, p), "by_type": by_type(ev_text, p),
                                  "pii_free_docs_false_positives": int(sum(len(p.get(d["doc_id"], []))
                                                                           for d in ev_text if not d["entities"]))}
            for lvl in sorted({d.get("difficulty") for d in ev_text}):
                S[f"branch1.{an}.by_difficulty.{lvl}"] = group_score(
                    [d for d in ev_text if d.get("difficulty") == lvl], p)

        # OCR + Presidio per engine; confidence behaviour
        for eng, ocr in ocr_engines.items():
            have = [d for d in ev_img if d["doc_id"] in ocr]
            if not have:
                continue
            for an in ("presidio", "presidio_plus"):
                p = {k: v["entities"] for k, v in pres[an].get(eng, {}).items()}
                S[f"ocr.{eng}.{an}"] = {"all": group_score(have, p), "by_type": by_type(have, p),
                                        "by_difficulty": {lvl: group_score([d for d in have if d.get("difficulty") == lvl], p)
                                                          for lvl in sorted({d.get("difficulty") for d in have})},
                                        "by_category": {c: group_score([d for d in have if d["category"] == c], p)
                                                        for c in ("scanned", "handwritten")}}
            p = {k: v["entities"] for k, v in pres["presidio"].get(eng, {}).items()}
            conf = np.array([ocr[d["doc_id"]]["confidence"] for d in have])
            f1d = np.array([f1d_ for f1d_ in (prf_arr(cnt(d["entities"], p.get(d["doc_id"], [])))["f1"]
                                              if d["entities"] else np.nan for d in have)])
            ok = np.isfinite(f1d)
            lv = np.array([d.get("difficulty") for d in have])
            eh = (lv == "easy") | (lv == "hard")
            S[f"ocr.{eng}.confidence"] = {
                "mean_by_difficulty": {l: float(conf[lv == l].mean()) for l in sorted(set(lv))},
                "mean_by_category": {c: float(np.mean([ocr[d["doc_id"]]["confidence"] for d in have if d["category"] == c]))
                                     for c in ("scanned", "handwritten")},
                "spearman_conf_vs_doc_f1": float(spearmanr(conf[ok], f1d[ok]).statistic) if ok.sum() > 2 else np.nan,
                "auc_conf_easy_vs_hard": selection.auc_rank(conf[eh], lv[eh] == "easy") if eh.any() else np.nan,
                "seconds_per_image_mean": float(np.mean([ocr[d["doc_id"]]["elapsed_ms"] for d in have]) / 1000),
                "seconds_per_image_p95": float(np.percentile([ocr[d["doc_id"]]["elapsed_ms"] for d in have], 95) / 1000),
                "n_images": len(have)}

        # VLM alone
        for vm, vr in vlms.items():
            have = [d for d in ev_img if d["doc_id"] in vr and vr[d["doc_id"]]["status"] == "ok"]
            p = {k: v["entities"] for k, v in vr.items() if not k.startswith("_")}
            ok_all = [d for d in ev_img if d["doc_id"] in vr]
            S[f"vlm.{vm}"] = {"all": group_score(ok_all, p), "by_type": by_type(ok_all, p),
                              "by_difficulty": {lvl: group_score([d for d in ok_all if d.get("difficulty") == lvl], p)
                                                for lvl in sorted({d.get("difficulty") for d in ok_all})},
                              "by_category": {c: group_score([d for d in ok_all if d["category"] == c], p)
                                              for c in ("scanned", "handwritten")},
                              "n_images": len(ok_all), "n_status_ok": len(have),
                              "status_counts": {s: sum(1 for d in ok_all if vr[d["doc_id"]]["status"] == s)
                                                for s in sorted({vr[d["doc_id"]]["status"] for d in ok_all})},
                              "seconds_per_image_mean": float(np.mean([vr[d["doc_id"]]["seconds"] for d in ok_all])) if ok_all else np.nan,
                              "tokens_per_second_mean": float(np.nanmean([vr[d["doc_id"]].get("tokens_per_second") or np.nan for d in ok_all])) if ok_all else np.nan,
                              "gpu_peak_mib": vr.get("_meta", {}).get("gpu_peak_mib_during_run")}

        # Cascades: Pareto over tau, calib-chosen tau, router
        for eng, ocr in ocr_engines.items():
            pe = {k: v["entities"] for k, v in pres["presidio_plus"].get(eng, {}).items()}
            for vm, vr in vlms.items():
                pv = {k: v["entities"] for k, v in vr.items() if not k.startswith("_")}
                def arrays(ds):
                    ds = [d for d in ds if d["doc_id"] in ocr and d["doc_id"] in vr]
                    conf = np.array([ocr[d["doc_id"]]["confidence"] for d in ds])
                    co = np.array([cnt(d["entities"], pe.get(d["doc_id"], [])) for d in ds]).reshape(-1, 3)
                    cv = np.array([cnt(d["entities"], pv.get(d["doc_id"], [])) for d in ds]).reshape(-1, 3)
                    so = np.array([ocr[d["doc_id"]]["elapsed_ms"] / 1000 for d in ds])
                    sv = np.array([vr[d["doc_id"]]["seconds"] for d in ds])
                    X = np.array([router_features(ocr[d["doc_id"]], pe.get(d["doc_id"], [])) for d in ds]).reshape(-1, len(ROUTER_FEATURES))
                    return ds, conf, co, cv, so, sv, X
                ds_c, conf_c, co_c, cv_c, so_c, sv_c, X_c = arrays(cal_img)
                ds_e, conf_e, co_e, cv_e, so_e, sv_e, X_e = arrays(ev_img)
                if len(ds_e) == 0 or len(ds_c) == 0:
                    continue
                key = f"cascade.{eng}.{vm}"
                pareto = []
                for tau in TAU_GRID:
                    use = conf_e < tau
                    c = co_e[~use].sum(0) + cv_e[use].sum(0)
                    pareto.append({"tau": float(tau), "vlm_share": float(use.mean()),
                                   "seconds_per_image": float((so_e + sv_e * use).mean()),
                                   "f1": prf_arr(c)["f1"]})
                with open(OUT / f"pareto_{subset}_{eng}_{vm}.csv", "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(pareto[0]))
                    w.writeheader()
                    w.writerows(pareto)
                tau = choose_tau(conf_c, co_c, cv_c, np.array([split[d["doc_id"]] for d in ds_c]))
                use = conf_e < tau
                cas = prf_arr(co_e[~use].sum(0) + cv_e[use].sum(0))
                res = {"calib_tau": tau, "eval_at_calib_tau": cas, "eval_vlm_share": float(use.mean()),
                       "eval_seconds_per_image": float((so_e + sv_e * use).mean()),
                       "ocr_only": prf_arr(co_e.sum(0)), "vlm_only": prf_arr(cv_e.sum(0)),
                       "eval_at_tau_085": prf_arr(co_e[~(conf_e < 0.85)].sum(0) + cv_e[conf_e < 0.85].sum(0)),
                       "vlm_share_at_tau_085": float((conf_e < 0.85).mean())}
                # router: label = VLM finds more true positives than OCR+Presidio+ (calib only)
                ycal = cv_c[:, 0] > co_c[:, 0]
                selection.require_selection_split([split[d["doc_id"]] for d in ds_c],
                                                  allowed=selection.PII_SELECTION_SPLITS, what="router")
                if 0 < ycal.sum() < len(ycal):
                    mu, sd = X_c.mean(0), X_c.std(0) + 1e-9
                    lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit((X_c - mu) / sd, ycal)
                    pc, pev = lr.predict_proba((X_c - mu) / sd)[:, 1], lr.predict_proba((X_e - mu) / sd)[:, 1]
                    best_t, best_f = 0.5, -1
                    for t in np.round(np.arange(0.0, 1.0001, 0.02), 2):          # calib-chosen cut
                        u = pc >= t
                        f = prf_arr(co_c[~u].sum(0) + cv_c[u].sum(0))["f1"]
                        if f > best_f + 1e-12:
                            best_t, best_f = float(t), f
                    ur = pev >= best_t
                    share = float(ur.mean())
                    # single confidence threshold sending the SAME share of eval docs to the VLM
                    k = int(round(share * len(conf_e)))
                    order = np.argsort(conf_e, kind="mergesort")
                    um = np.zeros(len(conf_e), bool)
                    um[order[:k]] = True
                    res["router"] = {"features": list(ROUTER_FEATURES), "calib_cut": best_t,
                                     "eval": prf_arr(co_e[~ur].sum(0) + cv_e[ur].sum(0)),
                                     "eval_vlm_share": share,
                                     "eval_seconds_per_image": float((so_e + sv_e * ur).mean()),
                                     "threshold_at_same_share": prf_arr(co_e[~um].sum(0) + cv_e[um].sum(0)),
                                     "label_positive_rate_calib": float(ycal.mean())}
                else:
                    res["router"] = {"skipped": "calib label has a single class"}
                S[key] = res
                rows_csv.append({"subset": subset, "ocr": eng, "vlm": vm, "calib_tau": tau,
                                 "eval_f1": cas["f1"], "vlm_share": res["eval_vlm_share"],
                                 "sec_per_img": res["eval_seconds_per_image"],
                                 "router_f1": res["router"].get("eval", {}).get("f1", np.nan),
                                 "router_share": res["router"].get("eval_vlm_share", np.nan),
                                 "same_share_threshold_f1": res["router"].get("threshold_at_same_share", {}).get("f1", np.nan)})
        results[subset] = S

    with open(OUT / "cascade_summary.csv", "w", newline="", encoding="utf-8") as f:
        if rows_csv:
            w = csv.DictWriter(f, fieldnames=list(rows_csv[0]))
            w.writeheader()
            w.writerows(rows_csv)
    (OUT / "pii_v2_metrics.json").write_text(json.dumps(results, indent=1, default=float), encoding="utf-8")
    record("pii2", results, script="evaluation/pii_v2_score.py", seeds={"split": 2610, "corpus": 2610})
    print(f"  -> {OUT}")
