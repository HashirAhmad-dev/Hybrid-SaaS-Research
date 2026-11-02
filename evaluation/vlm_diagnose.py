"""
vlm_diagnose.py
===============
Task F5: why does local Qwen2.5-VL-3B score F1 0.000 on FUNSD? Reads the VLM answer
cache only (no model call): status counts, empty and degenerate answers, prompt and
completion token counts (the image-token budget), and sample raw outputs, per model
and per corpus.

    python -m evaluation.vlm_diagnose
Output: results/pii_v2/vlm_diagnosis.json, manifest keys vlmdiag.*
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter

import numpy as np

from evaluation.pii_v2 import DATA, load_docs
from tools.manifest import PROJECT_ROOT, provenance, record

MODELS = {"qwen2-5-vl-3b-instruct": "Qwen2.5-VL-3B", "gemma-3-4b-it": "gemma-3-4b-it",
          "qwen2-5-vl-7b-instruct": "Qwen2.5-VL-7B"}
OUT = PROJECT_ROOT / "results" / "pii_v2"


def corpus_of(doc_id: str) -> str:
    return "funsd" if doc_id.upper().startswith("FUNSD") else ("v2" if doc_id.upper().startswith("V2") else "v1")


def main() -> None:
    docs = {d["doc_id"]: d for d in load_docs()}
    res, samples = {}, {}
    for slug, name in MODELS.items():
        recs = [json.loads(open(f, encoding="utf-8").read()) for f in glob.glob(str(DATA / "vlm_cache" / f"{slug}-*.json"))]
        for corpus in ("v1", "v2", "funsd"):
            rs = [r for r in recs if corpus_of(r["doc_id"]) == corpus]
            if not rs:
                continue
            st = Counter(r["status"] for r in rs)
            ok = [r for r in rs if r["status"] == "ok"]
            raw = [r.get("raw", "") for r in rs]
            pt = [r["usage"].get("prompt_tokens") for r in rs if r.get("usage")]
            ct = [r["usage"].get("completion_tokens") for r in rs if r.get("usage")]
            gold_n = [len(docs.get(r["doc_id"], {}).get("entities", []) or []) for r in rs]
            res.setdefault(slug, {})[corpus] = {
                "n": len(rs), **{f"status_{k}": v for k, v in st.items()},
                "ok_empty_list": sum(1 for r in ok if not r["entities"]),
                "ok_nonempty": sum(1 for r in ok if r["entities"]),
                "degenerate_repeated_char": sum(1 for x in raw if re.search(r"(.)\1{40,}", x)),
                "says_no_pii_or_cannot": sum(1 for x in raw if re.search(r"cannot|unable|no (personal|pii)|not able", x, re.I)),
                "prompt_tokens_median": float(np.median(pt)) if pt else np.nan,
                "prompt_tokens_max": float(np.max(pt)) if pt else np.nan,
                "completion_tokens_median": float(np.median(ct)) if ct else np.nan,
                "docs_with_gold_entities": sum(1 for g in gold_n if g),
                "seconds_median": float(np.median([r["seconds"] for r in rs]))}
            samples.setdefault(slug, {})[corpus] = [
                {"doc_id": r["doc_id"], "status": r["status"], "n_entities": len(r["entities"]),
                 "usage": r.get("usage"), "raw": r.get("raw", "")[:300]} for r in sorted(rs, key=lambda r: r["doc_id"])[:4]]
    out = {"summary": res, "samples": samples,
           "quantisation": {"Qwen2.5-VL-3B": "Q4_K_M weights, F16 vision projector (lmstudio-community GGUF)",
                            "gemma-3-4b-it": "Q4_K_M weights, F16 vision projector (lmstudio-community GGUF)",
                            "Qwen2.5-VL-7B": "Q4_K_M weights, F16 vision projector (lmstudio-community GGUF)"},
           "context_tokens": 4096}
    (OUT / "vlm_diagnosis.json").write_text(json.dumps({"provenance": provenance("evaluation/vlm_diagnose.py"), **out},
                                                       indent=1), encoding="utf-8")
    record("vlmdiag", res, script="evaluation/vlm_diagnose.py")
    for slug, v in res.items():
        for c, x in v.items():
            print(slug, c, {k: x[k] for k in x if not k.startswith("seconds")})


if __name__ == "__main__":
    main()
