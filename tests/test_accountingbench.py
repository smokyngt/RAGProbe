"""AccountingBench: consistency of the world model, the corpus and the dataset (no network, no pipeline)."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from common import eml_text, iban_valid
from ragbench.dataset import load_dataset
from ragbench.evaluation.qa import fact_present
from world import SUPPLIERS, build_world, ledger_balance, open_items, september_journal

ROOT = Path(__file__).resolve().parent.parent / "accountingbench"
DATASET = ROOT / "datasets" / "accountingbench_v1.jsonl"
PILOTS = ["B1", "B2", "B3", "B4", "B5"] + [f"T{n}" for n in range(1, 16)]


@pytest.fixture(scope="module")
def world():
    return build_world()


@pytest.fixture(scope="module")
def rows():
    return [json.loads(line) for line in DATASET.read_text("utf-8").splitlines() if line.strip()]


def test_world_bank_details_and_dates(world):
    assert all(iban_valid(s.iban) for s in SUPPLIERS.values())
    assert all(b.date.weekday() < 5 for b in world.bank), "a bank operation falls on a weekend"
    for x in world.payments:
        if x.settles:
            assert sum(a for _, a in x.settles) == x.amount


def test_world_invoice_arithmetic(world):
    for i in world.invoices:
        assert i.total == i.net + i.vat
        if i.number != "SME-26-0457":  # the planted VAT error
            assert i.vat == i.vat_correct, i.number
    assert world.inv("SME-26-0457").vat_correct - world.inv("SME-26-0457").vat == 18


def test_world_planted_anomalies(world):
    sj = september_journal(world)
    assert len(sj) == 27
    assert [p for p, _, i in sj if i.number == "FA-2026-0917"] == ["AC-2609-007", "AC-2609-022"]
    assert ledger_balance(world, "SEA", world.inv("SG-2026/0877").date.replace(month=9, day=30)) == 10
    overdue = {i.number for i, _, _ in open_items(world, world.inv("INV-2026-0418").date)
               if (world.inv("INV-2026-0418").date - i.due).days > 60}
    assert overdue == {"KIT-2026-0602", "NYS-2026-071"}


def test_corpus_manifest_matches_files():
    m = json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))
    assert m["n_documents"] == len(m["documents"]) == len(list((ROOT / "corpus" / "documents").iterdir()))
    kinds = {d["filename"].rsplit(".", 1)[1] for d in m["documents"]}
    assert kinds == {"pdf", "eml"}
    assert all(d["filename"].endswith(".eml") == (d["document_type"] == "email") for d in m["documents"])
    assert any(d["pages"] >= 3 for d in m["documents"]) and any(d["pages"] == 1 for d in m["documents"])
    for d in m["documents"]:
        data = (ROOT / "corpus" / "documents" / d["filename"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == d["sha256"], d["filename"]
        if d["scanned"]:
            assert (ROOT / "corpus" / "ocr_reference" / f"{d['document_id']}.txt").exists()


def test_dataset_shape(rows):
    assert [r["id"] for r in rows] == [f"acc_q_{n:03d}" for n in range(1, 21)]
    assert [r["metadata"]["pilot_id"] for r in rows] == PILOTS
    assert set(rows[0]) == {"id", "question", "question_natural", "reference_answer", "key_facts", "evidence", "metadata",
                            "calculation"}  # same top-level schema as FinanceBench
    for r in rows:
        for k in r["key_facts"]:
            assert fact_present(r["reference_answer"], [k["value"]]), (r["id"], k)
    neg = rows[-1]
    assert neg["metadata"]["answerable"] is False and neg["evidence"] == [] and "cannot be established" in neg["reference_answer"]
    assert len(load_dataset(DATASET).samples) == 20


def test_dataset_does_not_leak_answers_into_questions(rows):
    for r in rows:
        q = r["question"].lower()
        for word in ("duplicata", "fraud", "short-paid", "anomaly"):
            assert word not in q, (r["id"], word)


def test_validator_passes():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]


def test_eml_messages_are_parseable():
    m = json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))
    for d in m["documents"]:
        if d["filename"].endswith(".eml"):
            text = eml_text(ROOT / "corpus" / "documents" / d["filename"])
            assert text.startswith("From: ") and "Subject: " in text and len(text) > 200, d["filename"]
