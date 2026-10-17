"""CareBench: consistency of the scenario, the corpus and the dataset (no network, no pipeline)."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ragbench.dataset import load_dataset
from ragbench.evaluation.qa import fact_present

ROOT = Path(__file__).resolve().parent.parent / "carebench"
DATASET = ROOT / "datasets" / "carebench_v1.jsonl"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"carebench_{name}", ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


S = _load("scenario")


@pytest.fixture(scope="module")
def rows():
    return [json.loads(line) for line in DATASET.read_text("utf-8").splitlines() if line.strip()]


def test_scenario_computations():
    d = S.D
    assert S.ferrand_result(175, d(2026, 11, 16))["egfr"] == 25 and S.ferrand_result(105, d(2026, 11, 17))["egfr"] == 47
    assert S.ferrand_result(175, d(2026, 11, 16))["dose_mg"] == 60  # 62 mg rounded to the nearest syringe
    assert dict(S.fabre_scores()) == {"00:00": 0, "03:00": 2, "06:00": 7, "09:00": 9, "12:00": 2}
    assert S.news2(rr=22, spo2=96, on_o2=True, sbp=108, hr=94, alert=True, temp=37.8) == 6  # SpO2 96 scores 0: the 06:00 variant
    assert S.warfarin_plan(3.4, d(2026, 11, 10))["new_weekly"] == 25.2 and S.warfarin_plan(4.3, d(2026, 11, 10))["recheck"] == d(2026, 11, 13)
    assert S.gp_deadline(d(2026, 11, 13)) == d(2026, 11, 17)  # Friday + 2 working days
    assert [r[0] for r in S.ward4b_needing_isolation_in_bay()] == ["4B-02", "4B-04", "4B-07"]
    assert S.paed_limits()["ml"] == 9.0 and len(S.guerin_given()) == 6
    assert round(S.ckd_epi_2021(214, 69, False)) == 28 and round(S.ckd_epi_2021(128, 71, False)) == 52
    assert S.news2(26, 90, False, 85, 135, False, 34.8) == 18
    assert [S.scale_units(g) for _, g, _ in S.RENARD] == [4, 2, 4, 0] and S.scale_units(12.0) == 4


def test_corpus_manifest_matches_files():
    m = json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))
    files = {p.name for p in (ROOT / "corpus" / "documents").iterdir()}
    assert m["n_documents"] == len(m["documents"]) == len(files) and {d["filename"] for d in m["documents"]} == files
    assert {d["filename"].rsplit(".", 1)[1] for d in m["documents"]} == {"pdf", "eml"}
    assert all(d["document_id"] == d["filename"].rsplit(".", 1)[0] for d in m["documents"])
    assert all(f.isascii() for f in files)
    for d in m["documents"]:
        assert hashlib.sha256((ROOT / "corpus" / "documents" / d["filename"]).read_bytes()).hexdigest() == d["sha256"], d["filename"]
        if d["scanned"]:
            assert (ROOT / "corpus" / "ocr_reference" / f"{d['document_id']}.txt").exists()
    assert sum(d["scanned"] for d in m["documents"]) == 2 and max(d["pages"] for d in m["documents"]) >= 10


def test_dataset_shape(rows):
    mains = [r for r in rows if r["metadata"]["follow_up_of"] is None]
    fups = [r for r in rows if r["metadata"]["follow_up_of"]]
    assert [r["id"] for r in mains] == [f"care_q_{n:03d}" for n in range(1, 35)] and len(fups) == 67
    assert set(rows[0]) == {"id", "question", "question_natural", "reference_answer", "key_facts", "evidence", "metadata", "calculation"}
    for r in rows:
        for k in r["key_facts"]:
            assert fact_present(r["reference_answer"], [k["value"]]), (r["id"], k)
        if r["metadata"]["answerable"]:
            assert r["key_facts"] and r["evidence"], r["id"]
    for f in fups:
        parent = next(m for m in mains if m["id"] == f["metadata"]["follow_up_of"])
        assert f["id"] in parent["metadata"]["follow_up_ids"] and f["question"] != f["question_natural"]
    for neg in (r for r in rows if not r["metadata"]["answerable"]):
        assert neg["evidence"] == [] and "cannot be established" in neg["reference_answer"]
    assert len(load_dataset(DATASET).samples) == len(rows)


def test_exports_are_consistent(rows):
    simple = [json.loads(line) for line in (ROOT / "datasets" / "carebench_v1_simple.jsonl").read_text("utf-8").splitlines()]
    assert [r["id"] for r in simple] == [r["id"] for r in rows]
    conv = [json.loads(line) for line in (ROOT / "datasets" / "carebench_v1_conversations.jsonl").read_text("utf-8").splitlines()]
    assert sum(c["n_turns"] for c in conv) == len(rows) and [t["turn"] for t in conv[3]["turns"]] == [1, 2, 3, 4]


def test_questions_do_not_leak_answers(rows):
    for r in rows:
        q = (r["question"] + " " + r["question_natural"]).lower()
        for word in ("misfiled", "contraindicated", "overdose", "mismatch", "error"):
            assert word not in q, (r["id"], word)


def test_validator_passes():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
