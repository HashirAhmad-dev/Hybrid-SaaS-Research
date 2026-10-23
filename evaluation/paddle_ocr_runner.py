"""
paddle_ocr_runner.py
====================
Paper-v2 task T3.2. Runs PaddleOCR over the image documents of the v2 corpus and
writes the SAME per-document record format as the EasyOCR stage of
evaluation/pii_v2.py, so both engines are compared on identical pixels.

This file is executed by the separate interpreter in .venv-paddle (CPython 3.13;
paddlepaddle has no wheel for the 3.14 interpreter the rest of the project uses).
It imports only the standard library, numpy, PIL and paddleocr.

    .venv-paddle\\Scripts\\python.exe evaluation\\paddle_ocr_runner.py [--device cpu|gpu] [--limit N]
Output: evaluation/data/pii_v2/ocr_paddleocr_<device>.json
Record: {doc_id: {"transcript", "confidence" (char-weighted mean), "boxes",
                  "elapsed_ms", "width", "height"}}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GT = ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json"
OUT = ROOT / "evaluation" / "data" / "pii_v2"


def doc_path(d: dict) -> Path:
    return ROOT / "evaluation" / d["root"] / d["path"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu", choices=("cpu", "gpu"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    import numpy as np
    from PIL import Image
    import paddleocr
    from paddleocr import PaddleOCR

    docs = [d for d in json.loads(GT.read_text(encoding="utf-8"))["documents"]
            if d["category"] != "text_extractable"]
    if args.limit:
        docs = docs[:args.limit]
    # enable_mkldnn=False: paddle 3.3.1 + oneDNN on Windows CPU raises
    # "ConvertPirAttribute2RuntimeAttribute not support" in the PIR executor.
    ocr = PaddleOCR(lang="en", device=args.device, enable_mkldnn=False,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False, use_textline_orientation=False)
    out_path = OUT / f"ocr_paddleocr_{args.device}.json"
    OUT.mkdir(parents=True, exist_ok=True)
    res = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    # warm-up (first call loads and compiles the models)
    ocr.predict(np.array(Image.open(doc_path(docs[0])).convert("RGB")))
    for i, d in enumerate(docs, 1):
        if d["doc_id"] in res:
            continue
        img = Image.open(doc_path(d)).convert("RGB")
        t0 = time.perf_counter()
        pages = ocr.predict(np.array(img))
        el = (time.perf_counter() - t0) * 1000.0
        texts, scores = [], []
        for p in pages:
            texts += list(p["rec_texts"])
            scores += [float(s) for s in p["rec_scores"]]
        chars = sum(len(t) for t in texts)
        conf = sum(len(t) * s for t, s in zip(texts, scores)) / chars if chars else 0.0
        res[d["doc_id"]] = {"transcript": "\n".join(texts), "confidence": conf, "boxes": len(texts),
                            "elapsed_ms": el, "width": img.width, "height": img.height}
        if i % 25 == 0:
            out_path.write_text(json.dumps(res, indent=0), encoding="utf-8")
            print(f"  {i}/{len(docs)}", flush=True)
    meta = {"engine": "PaddleOCR", "paddleocr_version": getattr(paddleocr, "__version__", "?"),
            "python": sys.version.split()[0], "device": args.device}
    res["_meta"] = meta
    out_path.write_text(json.dumps(res, indent=0), encoding="utf-8")
    print(f"done: {len(res) - 1} docs -> {out_path}")


if __name__ == "__main__":
    main()
