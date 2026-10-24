"""
funsd_subset.py
===============
Paper-v2 task T3.1 (D-021): add the FUNSD real scanned forms (Jaume et al., 2019;
terms accepted by the user on 2026-10-24) to the PII corpus as a SEPARATE subset
"funsd", reported apart from the synthetic v2 main set.

FUNSD has no PII labels. A partial gold list is derived from linked
question -> answer pairs whose question names a PII field:

    PERSON   name, to, from, cc, attn, attention, approved by, submitted by,
             requested by, reported by, prepared by, authorized by, contact, sender
    PHONE    phone, telephone, tel, fax, fax no, fax number, phone no
    ADDRESS  address
    EMAIL    email, e-mail
    DOB      date of birth, birth date

The value is the answer text; a PERSON answer without digits that lists several
names separated by commas becomes one entity per name. Known noise that stays:
"to"/"from" answers that are departments, titles or addresses. PII outside such linked fields is NOT in the gold,
so on this subset precision is a lower bound and recall only covers the derived
fields. Rules are fixed here once and never tuned on model output.

Images stay on D: (evaluation/pii_testset_funsd is a directory junction to
D:/datasets/funsd/dataset, gitignored). The script rewrites only the "funsd"
entries of evaluation/pii_testset_v2/ground_truth.json (idempotent).

    python -m evaluation.funsd_subset
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from evaluation.pii_common import tier_counts
from tools.manifest import PROJECT_ROOT, record

GT = PROJECT_ROOT / "evaluation" / "pii_testset_v2" / "ground_truth.json"
LINK = PROJECT_ROOT / "evaluation" / "pii_testset_funsd"

RULES = [
    ("PERSON", r"^(name|to|from|cc|attn|attention|approved by|submitted by|requested by|reported by|"
               r"prepared by|authorized by|authorised by|contact|sender)$"),
    ("PHONE", r"^(phone|telephone|tel|fax|fax no|fax number|phone no|phone number|telephone no|telephone number)$"),
    ("ADDRESS", r"^(address)$"),
    ("EMAIL", r"^(email|e mail)$"),
    ("DOB", r"^(date of birth|birth date|birthdate)$"),
]


def norm_q(t: str) -> str:
    t = re.sub(r"[^a-z ]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def main() -> None:
    if not LINK.exists():
        raise SystemExit(f"{LINK} missing: create the junction to D:/datasets/funsd/dataset")
    docs = [d for d in json.loads(GT.read_text(encoding="utf-8"))["documents"] if d["subset"] != "funsd"]
    added, ents = 0, {}
    for split in ("training_data", "testing_data"):
        for f in sorted((LINK / split / "annotations").glob("*.json")):
            form = json.loads(f.read_text(encoding="utf-8"))["form"]
            byid = {x["id"]: x for x in form}
            gold = []
            for q in form:
                if q["label"] != "question":
                    continue
                qn = norm_q(q["text"])
                typ = next((t for t, rx in RULES if re.match(rx, qn)), None)
                if not typ:
                    continue
                for a, b in q["linking"]:
                    if a == q["id"] and b in byid and byid[b]["label"] == "answer":
                        v = byid[b]["text"].strip()
                        parts = [v]
                        # a "cc" or "to" field often lists several people; each is one entity
                        if typ == "PERSON" and "," in v and not re.search(r"\d", v):
                            parts = [x.strip() for x in v.split(",")]
                        for x in parts:
                            if len(re.sub(r"[^A-Za-z0-9]", "", x)) >= 3:
                                gold.append({"type": typ, "value": x})
            text = "\n".join(x["text"] for x in form)
            h, m, l = tier_counts([e["type"] for e in gold])
            docs.append({"doc_id": f"FUNSD-{f.stem}", "subset": "funsd", "category": "scanned_real",
                         "difficulty": "real", "layout": "form", "pii_free": not gold,
                         "path": f"{split}/images/{f.stem}.png", "root": "pii_testset_funsd",
                         "text": text, "entities": gold, "high_entities": h, "medium_entities": m,
                         "low_entities": l, "font": "real scan", "funsd_split": split})
            added += 1
            for e in gold:
                ents[e["type"]] = ents.get(e["type"], 0) + 1
    GT.write_text(json.dumps({"documents": docs}, indent=1), encoding="utf-8")
    stats = {"documents": added, "gold_entities": sum(ents.values()), "by_type": ents,
             "docs_without_derived_pii": sum(1 for d in docs if d["subset"] == "funsd" and not d["entities"])}
    record("funsd.subset", stats, script="evaluation/funsd_subset.py", seeds={})
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
