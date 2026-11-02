"""F3: one definition per repeated number, enforced by tools/check_numbers.check_definitions."""
import json

from tools.check_numbers import check_definitions

ENTRIES = {"a.canon": {"value": 0.6287}, "a.deployed": {"value": 0.6348}}
SPEC = {"prose": ["*.md"], "definitions": [{
    "id": "hybrid_flag_f1", "subject": r"hybrid[^|.;]{0,60}\bF1\b",
    "canonical": {"key": "a.canon", "name": "comparison rule"},
    "variants": [{"key": "a.deployed", "name": "deployed rule", "qualifier": "deployed"}]}]}


def run(tmp_path, text):
    (tmp_path / "spec.json").write_text(json.dumps(SPEC), encoding="utf-8")
    (tmp_path / "doc.md").write_text(text, encoding="utf-8")
    return [r for r in check_definitions(tmp_path / "spec.json", ENTRIES, root=tmp_path) if not r["ok"]]


def test_canonical_value_passes(tmp_path):
    assert run(tmp_path, "The hybrid reaches F1 0.629 on 10 datasets.\n") == []


def test_variant_without_label_fails(tmp_path):
    bad = run(tmp_path, "The hybrid reaches F1 0.635 on 10 datasets.\n")
    assert len(bad) == 1 and "doc.md:1" in bad[0]["where"]


def test_variant_with_label_passes(tmp_path):
    assert run(tmp_path, "The hybrid reaches F1 0.635 at the deployed threshold.\n") == []


def test_percent_form_is_recognised(tmp_path):
    entries = {"a.canon": {"value": 0.613}, "a.deployed": {"value": 0.668}}
    spec = {"prose": ["*.md"], "definitions": [{
        "id": "ewma_burst", "subject": r"EWMA[^|]{0,100}burst",
        "canonical": {"key": "a.canon", "name": "c"},
        "variants": [{"key": "a.deployed", "name": "d", "qualifier": "deployed"}]}]}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (tmp_path / "doc.md").write_text("EWMA flags 66.8 percent of benign bursts.\n", encoding="utf-8")
    bad = [r for r in check_definitions(tmp_path / "spec.json", entries, root=tmp_path) if not r["ok"]]
    assert len(bad) == 1


def test_identical_values_are_rejected(tmp_path):
    entries = {"a.canon": {"value": 0.63}, "a.deployed": {"value": 0.6301}}
    (tmp_path / "spec.json").write_text(json.dumps(SPEC), encoding="utf-8")
    (tmp_path / "doc.md").write_text("nothing\n", encoding="utf-8")
    bad = [r for r in check_definitions(tmp_path / "spec.json", entries, root=tmp_path) if not r["ok"]]
    assert any("equals the canonical" in r["why"] for r in bad)


def test_near_rule_reads_only_the_labelled_number(tmp_path):
    spec = {**SPEC, "definitions": [{**SPEC["definitions"][0], "near": r"\bF1\b"}]}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (tmp_path / "doc.md").write_text("The hybrid has F1 0.635 and precision 0.700.\n"
                                     "The hybrid has F1 0.629 and precision 0.635.\n", encoding="utf-8")
    bad = [r for r in check_definitions(tmp_path / "spec.json", ENTRIES, root=tmp_path) if not r["ok"]]
    assert [r["where"] for r in bad] == ["doc.md:1"]
