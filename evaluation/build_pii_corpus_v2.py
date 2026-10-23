"""
build_pii_corpus_v2.py
======================
Paper-v2 task T3.1: a larger, harder PII corpus. The v1 corpus (120 documents,
`build_pii_testset.py`) had a ceiling: Qwen2.5-VL-72B scored 240/240 on its
images. v2 adds:

  * 360 new documents: 3 modalities (text, scanned print, font "handwriting")
    x 3 difficulty levels (easy, medium, hard) x 40.
  * Layout variety: labelled form, bordered two-column table, free prose,
    two-column form, and (hard) prose with a distracting header and footer.
  * Value-format variety: phone numbers with and without +92, dashes,
    brackets; dates of birth in three formats; card numbers grouped or not;
    Mastercard in both the 51-55 and the 2221-2720 ranges; unit numbers in
    addresses.
  * About 15 percent PII-free documents.
  * NEAR-MISS strings in medium and hard documents, which are NOT PII and are
    NOT in the gold list, so detecting them is a false positive: 16-digit
    invoice numbers that fail the Luhn check, CNIC-shaped employee codes with a
    prefix, document dates that are not dates of birth, organisation names,
    order and tracking numbers, extension numbers.
  * Harder image degradation at level "hard": smaller font, stronger blur and
    noise, background ruling lines, a shading gradient, perspective skew.

The v1 corpus is kept unchanged as a labelled subset (subset = "v1"), read
from evaluation/pii_testset/. The MAIN set for the paper is subset "v2".

All PII is synthetic (Faker); e-mails use reserved example.* domains; CNICs are
random digits in the CNIC format. evaluation/pii_testset_v2/ is gitignored.

    python -m evaluation.build_pii_corpus_v2 [--seed 2610]
Outputs (evaluation/pii_testset_v2/):
    text/*.txt  scanned/*.jpg  handwritten/*.jpg  ground_truth.json  build_config.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import textwrap
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from faker import Faker
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .pii_common import EVAL_DIR, GROUND_TRUTH as V1_GROUND_TRUTH, TESTSET_DIR as V1_DIR, tier_counts

OUT_DIR = EVAL_DIR / "pii_testset_v2"
WIN_FONTS = Path("C:/Windows/Fonts")
PRINT_FONTS = ("arial.ttf", "calibri.ttf", "times.ttf", "georgia.ttf", "tahoma.ttf",
               "verdana.ttf", "cour.ttf", "segoeui.ttf")
HAND_FONTS = ("segoesc.ttf", "segoepr.ttf", "comic.ttf", "Inkfree.ttf")
MODALITIES = ("text_extractable", "scanned", "handwritten")
LEVELS = ("easy", "medium", "hard")
IMG_W = 1240
PK_MOBILE_PREFIXES = tuple(p for p in range(300, 350) if p != 338)


# ---------------------------------------------------------------------------
# Value generators (synthetic only)
# ---------------------------------------------------------------------------
def luhn_ok(digits: str) -> bool:
    d = [int(c) for c in digits][::-1]
    s = sum(d[0::2]) + sum(sum(divmod(2 * x, 10)) for x in d[1::2])
    return s % 10 == 0


def luhn_complete(prefix: str, length: int, r: random.Random) -> str:
    body = prefix + "".join(str(r.randint(0, 9)) for _ in range(length - len(prefix) - 1))
    for c in "0123456789":
        if luhn_ok(body + c):
            return body + c
    raise AssertionError


def card(r: random.Random, level: str) -> str:
    scheme = r.choice(("visa", "mc51", "mc2", "amex", "discover"))
    if scheme == "visa":
        n = luhn_complete("4", 16, r)
    elif scheme == "mc51":
        n = luhn_complete(str(r.randint(51, 55)), 16, r)
    elif scheme == "mc2":
        n = luhn_complete(str(r.randint(2221, 2720)), 16, r)
    elif scheme == "amex":
        n = luhn_complete(r.choice(("34", "37")), 15, r)
    else:
        n = luhn_complete("6011", 16, r)
    if level == "easy" or r.random() < 0.4:
        return n
    sep = r.choice((" ", "-"))
    if len(n) == 15:
        return sep.join((n[:4], n[4:10], n[10:]))
    return sep.join(n[i:i + 4] for i in range(0, 16, 4))


def phone(r: random.Random, level: str) -> str:
    p, rest = r.choice(PK_MOBILE_PREFIXES), "".join(str(r.randint(0, 9)) for _ in range(7))
    if level == "easy":
        return f"+92 {p} {rest}"
    return r.choice((f"+92 {p} {rest}", f"+92-{p}-{rest}", f"+92{p}{rest}",
                     f"(+92) {p} {rest[:3]} {rest[3:]}"))


def cnic(r: random.Random) -> str:
    d = lambda n: "".join(str(r.randint(0, 9)) for _ in range(n))
    return f"{d(5)}-{d(7)}-{d(1)}"


def dob(fake: Faker, r: random.Random, level: str) -> str:
    x = fake.date_of_birth(minimum_age=21, maximum_age=64)
    if level == "easy":
        return x.strftime("%Y-%m-%d")
    return x.strftime(r.choice(("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y")))


def address(fake: Faker, r: random.Random, level: str) -> str:
    a = fake.street_address()
    if level != "easy" and r.random() < 0.4:
        a = f"{a}, {fake.city()}"
    return a.replace("\n", ", ")


def password(fake: Faker) -> str:
    return fake.password(length=10, special_chars=False, upper_case=True, lower_case=True, digits=True)


def gen(t: str, fake: Faker, r: random.Random, level: str) -> str:
    return {
        "PERSON": lambda: fake.name(),
        "NID": lambda: cnic(r),
        "CREDIT_CARD": lambda: card(r, level),
        "PHONE": lambda: phone(r, level),
        "EMAIL": lambda: fake.ascii_safe_email(),
        "DOB": lambda: dob(fake, r, level),
        "ADDRESS": lambda: address(fake, r, level),
        "PASSWORD": lambda: password(fake),
    }[t]()


# ---------------------------------------------------------------------------
# Near-miss strings (NOT PII, never in the gold list)
# ---------------------------------------------------------------------------
def near_misses(fake: Faker, r: random.Random, n: int) -> List[Tuple[str, str]]:
    def bad_luhn16():
        while True:
            x = str(r.choice((4, 5))) + "".join(str(r.randint(0, 9)) for _ in range(15))
            if not luhn_ok(x):
                return " ".join(x[i:i + 4] for i in range(0, 16, 4))
    d = lambda k: "".join(str(r.randint(0, 9)) for _ in range(k))
    pool = [
        ("Invoice No", bad_luhn16),
        ("Employee Code", lambda: f"EMP-{d(5)}-{d(7)}-{d(1)}"),
        ("Document Date", lambda: fake.date_between("-2y", "today").strftime("%Y-%m-%d")),
        ("Vendor", lambda: fake.company()),
        ("Order Ref", lambda: f"ORD-{d(4)}-{d(6)}"),
        ("Tracking", lambda: f"1Z{d(6)}{d(10)}"),
        ("Extension", lambda: f"ext. {d(4)}"),
        ("Cost Centre", lambda: f"CC {d(3)}-{d(4)}"),
        ("Office", lambda: f"{fake.city()} branch"),
        ("Account Ref", lambda: d(12)),
    ]
    picks = r.sample(pool, k=min(n, len(pool)))
    return [(lab, f()) for lab, f in picks]


# ---------------------------------------------------------------------------
# Document text
# ---------------------------------------------------------------------------
TEMPLATES: List[Tuple[str, List[str]]] = [
    ("EMPLOYEE RECORD - CONFIDENTIAL", ["PERSON", "NID", "DOB", "EMAIL", "PHONE", "ADDRESS"]),
    ("PAYROLL DISBURSEMENT SLIP", ["PERSON", "NID", "CREDIT_CARD", "EMAIL"]),
    ("VENDOR ONBOARDING FORM", ["PERSON", "EMAIL", "PHONE", "ADDRESS", "CREDIT_CARD"]),
    ("IT ACCOUNT PROVISIONING TICKET", ["PERSON", "EMAIL", "PASSWORD"]),
    ("CUSTOMER SUPPORT ESCALATION", ["PERSON", "PHONE", "EMAIL", "PERSON"]),
    ("EXPENSE REIMBURSEMENT CLAIM", ["PERSON", "CREDIT_CARD", "ADDRESS", "DOB"]),
    ("BENEFITS ENROLMENT CONFIRMATION", ["PERSON", "NID", "DOB", "ADDRESS", "PHONE"]),
    ("SECURITY INCIDENT REPORT", ["PERSON", "EMAIL", "PASSWORD", "PHONE", "PERSON"]),
    ("TRAVEL BOOKING REQUEST", ["PERSON", "DOB", "NID", "PHONE", "CREDIT_CARD"]),
    ("NEW HIRE CHECKLIST", ["PERSON", "EMAIL", "ADDRESS", "DOB", "PASSWORD"]),
]
PII_FREE_TEMPLATES = ("PUBLIC PRESS RELEASE DRAFT", "QUARTERLY TOWN HALL AGENDA",
                      "OFFICE MAINTENANCE NOTICE", "PRODUCT RELEASE NOTES")
LABELS = {"PERSON": ("Name", "Employee", "Contact", "Requested by"), "NID": ("CNIC", "National ID"),
          "CREDIT_CARD": ("Card No", "Corporate card", "Card"), "PHONE": ("Phone", "Mobile", "Tel"),
          "EMAIL": ("Email", "E-mail"), "DOB": ("Date of Birth", "DOB", "Born"),
          "ADDRESS": ("Address", "Home address", "Residence"), "PASSWORD": ("Temp Password", "Initial password")}
PROSE = {
    "PERSON": ("{v} raised this request.", "Approval was given by {v}.", "Please route queries to {v}."),
    "NID": ("The national identity number on file is {v}.", "Identity was checked against CNIC {v}."),
    "CREDIT_CARD": ("The refund goes back to card {v}.", "Charges were billed to {v}."),
    "PHONE": ("Call back on {v} before Friday.", "The mobile number given was {v}."),
    "EMAIL": ("Send the signed copy to {v}.", "Correspondence address: {v}."),
    "DOB": ("The applicant was born on {v}.", "Date of birth recorded as {v}."),
    "ADDRESS": ("Courier the documents to {v}.", "The employee lives at {v}."),
    "PASSWORD": ("A temporary password {v} was issued and must be changed.", "Use {v} for the first login only."),
}
FILLER = ("Please file this document per retention policy R-14.", "Circulated to the reviewing manager only.",
          "Do not forward outside the department.", "Signed off by the compliance desk.",
          "This summary was prepared for the weekly operations review.",
          "Figures are provisional until the month-end close.")


def make_text(fake: Faker, r: random.Random, level: str, pii_free: bool):
    """Returns (title, layout, list of (label or None, text) rows, gold entities)."""
    if pii_free:
        title, types = r.choice(PII_FREE_TEMPLATES), []
    else:
        title, types = r.choice(TEMPLATES)
    layout = {"easy": r.choice(("form", "form", "table")),
              "medium": r.choice(("form", "table", "prose", "twocol")),
              "hard": r.choice(("prose", "twocol", "table", "prose_noisy"))}[level]
    gold, rows = [], []
    for t in types:
        v = gen(t, fake, r, level)
        gold.append({"type": t, "value": v})
        if layout.startswith("prose"):
            rows.append((None, r.choice(PROSE[t]).format(v=v)))
        else:
            rows.append((r.choice(LABELS[t]) if level != "easy" else LABELS[t][0], v))
    n_miss = {"easy": 0, "medium": r.randint(1, 2), "hard": r.randint(2, 4)}[level]
    if pii_free:
        n_miss = max(n_miss, 2)
    for lab, v in near_misses(fake, r, n_miss):
        rows.insert(r.randint(0, len(rows)), (None, f"{lab} {v}.") if layout.startswith("prose") else (lab, v))
    if layout.startswith("prose") or pii_free:
        rows.append((None, fake.paragraph(nb_sentences=2)))
    rows.append((None, r.choice(FILLER)))
    return title, layout, rows, gold


def to_plain_text(title: str, layout: str, rows) -> str:
    lines = [title, "=" * len(title), ""]
    if layout.startswith("prose"):
        lines += textwrap.wrap(" ".join(t for _, t in rows), 88)
    else:
        lines += [f"{lab}: {t}" if lab else t for lab, t in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def font(font_dir: Path, names, size: int, r: random.Random):
    avail = [n for n in names if (font_dir / n).exists()]
    if not avail:
        return ImageFont.load_default(), "PIL_default_bitmap"
    n = r.choice(avail)
    return ImageFont.truetype(str(font_dir / n), size), n


def render(title, layout, rows, f, size, r: random.Random) -> Image.Image:
    lh = int(size * 1.6)
    margin = 50
    body: List[Tuple[int, int, str]] = []          # (x, row, text)
    y = 0
    if layout == "prose_noisy":
        body.append((0, y, f"{r.choice(('Internal', 'Restricted', 'Draft'))} - page {r.randint(1, 4)} of {r.randint(4, 9)}  |  ref {r.randint(10000, 99999)}"))
        y += 2
    body.append((0, y, title)); y += 2
    if layout.startswith("prose"):
        for line in textwrap.wrap(" ".join(t for _, t in rows), 62 if size > 24 else 72):
            body.append((0, y, line)); y += 1
    elif layout == "twocol":
        half = (len(rows) + 1) // 2
        for i, (lab, t) in enumerate(rows):
            col, rr = (0, y + i) if i < half else (1, y + i - half)
            body.append((col, rr, f"{lab}: {t}" if lab else t))
        y += half
    else:
        for lab, t in rows:
            body.append((0, y, f"{lab}: {t}" if lab else t)); y += 1
    if layout == "prose_noisy":
        y += 1
        body.append((0, y, "Printed copy. Uncontrolled when printed. Form HR-" + str(r.randint(100, 999))))
        y += 1
    h = margin * 2 + lh * (y + 1)
    img = Image.new("L", (IMG_W if layout != "twocol" else int(IMG_W * 1.5), h), 255)
    d = ImageDraw.Draw(img)
    colw = (img.width - 2 * margin) // 2
    for col, rr, text in body:
        d.text((margin + col * colw, margin + rr * lh), text, fill=20, font=f)
    if layout == "table":
        for rr in range(2, y + 1):
            d.line((margin - 8, margin + rr * lh - 6, img.width - margin, margin + rr * lh - 6), fill=90, width=2)
        d.line((margin + int(colw * 0.55), margin + 2 * lh - 6, margin + int(colw * 0.55), margin + y * lh - 6), fill=90, width=2)
    return img


DEGRADE = {
    "easy":   dict(rotate=0.5, blur=0.0, noise=4.0, jpeg_q=70, contrast=0.95, lines=False, skew=0.0, shade=0.0),
    "medium": dict(rotate=1.5, blur=0.7, noise=10.0, jpeg_q=40, contrast=0.85, lines=False, skew=0.0, shade=0.15),
    "hard":   dict(rotate=4.0, blur=1.6, noise=18.0, jpeg_q=22, contrast=0.55, lines=True, skew=0.06, shade=0.35),
}


def degrade(img: Image.Image, r: random.Random, nr: np.random.RandomState, *, rotate, blur, noise,
            jpeg_q, contrast, lines, skew, shade) -> Tuple[Image.Image, int]:
    if lines:                                          # ruled-paper background lines
        d = ImageDraw.Draw(img)
        for yy in range(0, img.height, r.randint(28, 40)):
            d.line((0, yy, img.width, yy), fill=r.randint(185, 215), width=1)
    if skew > 0:                                       # mild perspective
        w, h = img.size
        dx = int(w * r.uniform(-skew, skew))
        img = img.transform((w, h), Image.QUAD,
                            (max(dx, 0), 0, -min(dx, 0), h, w + min(dx, 0), h, w - max(dx, 0), 0),
                            resample=Image.BICUBIC, fillcolor=255)
    img = img.rotate(r.uniform(-rotate, rotate), resample=Image.BICUBIC, expand=True, fillcolor=255)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(r.uniform(blur * 0.5, blur)))
    if contrast < 1.0:
        img = ImageEnhance.Contrast(img).enhance(r.uniform(contrast, 1.0))
    arr = np.asarray(img, dtype=np.float32)
    if shade > 0:                                      # uneven lighting
        grad = np.linspace(0, r.uniform(0, shade) * 255, arr.shape[1], dtype=np.float32)
        arr -= grad[None, :] if r.random() < 0.5 else grad[None, ::-1]
    arr += nr.normal(0.0, r.uniform(noise * 0.5, noise), arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L"), r.randint(jpeg_q, jpeg_q + 15)


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2610)
    ap.add_argument("--n-per-cell", type=int, default=40)
    ap.add_argument("--pii-free-share", type=float, default=0.15)
    ap.add_argument("--font-dir", type=Path, default=WIN_FONTS)
    args = ap.parse_args()
    r = random.Random(args.seed)
    nr = np.random.RandomState(args.seed)
    Faker.seed(args.seed)
    fake = Faker(["en_US", "en_GB"])
    for sub in ("text", "scanned", "handwritten"):
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    docs = []
    n = 0
    for modality in MODALITIES:
        for level in LEVELS:
            for _ in range(args.n_per_cell):
                n += 1
                doc_id = f"V2-{n:04d}"
                pii_free = r.random() < args.pii_free_share
                title, layout, rows, gold = make_text(fake, r, level, pii_free)
                text = to_plain_text(title, layout, rows)
                font_name = "n/a"
                if modality == "text_extractable":
                    path = OUT_DIR / "text" / f"{doc_id}.txt"
                    path.write_text(text, encoding="utf-8")
                else:
                    names = PRINT_FONTS if modality == "scanned" else HAND_FONTS
                    size = {"easy": r.randint(26, 30), "medium": r.randint(22, 26), "hard": r.randint(18, 22)}[level]
                    if modality == "handwritten":
                        size += 4
                    f, font_name = font(args.font_dir, names, size, r)
                    img = render(title, layout, rows, f, size, r)
                    img, q = degrade(img, r, nr, **DEGRADE[level])
                    path = OUT_DIR / ("scanned" if modality == "scanned" else "handwritten") / f"{doc_id}.jpg"
                    img.save(path, "JPEG", quality=q)
                h, m, l = tier_counts([e["type"] for e in gold])
                docs.append({"doc_id": doc_id, "subset": "v2", "category": modality, "difficulty": level,
                             "layout": layout, "pii_free": pii_free,
                             "path": str(path.relative_to(OUT_DIR)).replace("\\", "/"),
                             "root": "pii_testset_v2", "text": text, "entities": gold,
                             "high_entities": h, "medium_entities": m, "low_entities": l, "font": font_name})

    # v1 kept as a labelled subset (files stay in evaluation/pii_testset/)
    v1 = json.loads(V1_GROUND_TRUTH.read_text(encoding="utf-8"))["documents"] if V1_GROUND_TRUTH.exists() else []
    for d in v1:
        docs.append({**d, "subset": "v1", "difficulty": "v1", "layout": "form",
                     "pii_free": not d["entities"], "root": "pii_testset"})

    (OUT_DIR / "ground_truth.json").write_text(json.dumps({"documents": docs}, indent=1), encoding="utf-8")
    v2 = [d for d in docs if d["subset"] == "v2"]
    by = lambda k: {str(x): sum(1 for d in v2 if d[k] == x) for x in sorted({d[k] for d in v2}, key=str)}
    ents: Dict[str, int] = {}
    for d in v2:
        for e in d["entities"]:
            ents[e["type"]] = ents.get(e["type"], 0) + 1
    digest = hashlib.sha256(json.dumps(v2, sort_keys=True).encode()).hexdigest()
    cfg = {"seed": args.seed, "v2_documents": len(v2), "v1_documents": len(v1),
           "by_category": by("category"), "by_difficulty": by("difficulty"), "by_layout": by("layout"),
           "pii_free_docs": sum(d["pii_free"] for d in v2), "gold_entities": sum(ents.values()),
           "entities_by_type": ents, "degradation": DEGRADE, "ground_truth_sha256_v2": digest,
           "pii_source": "Faker (synthetic). No real personal data."}
    (OUT_DIR / "build_config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in cfg.items() if k != "degradation"}, indent=1))


if __name__ == "__main__":
    main()
