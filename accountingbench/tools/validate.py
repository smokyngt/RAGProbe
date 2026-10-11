#!/usr/bin/env python3
"""Automatic validation of AccountingBench with the FinanceBench rules.

    python accountingbench/tools/validate.py            # checks + distribution
    python accountingbench/tools/validate.py --review   # also requires datasets/accountingbench_v1_review.json

Same checks as finance_benchmark/tools/validate_dataset.py (schema, flag consistency, every evidence quote found
verbatim on its page, calculations re-evaluated with every input found as printed, key facts present in the reference
answer, review entries). Differences: ids are acc_q_NNN, metadata carries the accounting fields (pilot_id, control,
control_rule, output_format, anomalies_tested, expected_rows), and the page text of a scanned document is its OCR
reference text (corpus/ocr_reference/), since a scan has no text layer; an .eml message is one page (headers + body).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / "finance_benchmark" / "tools"))
import validate_dataset as fb  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
from common import document_pages  # noqa: E402


class Metadata(fb.Metadata):
    pilot_id: str
    control: str
    control_rule: str
    output_format: str
    anomalies_tested: list[str] = Field(default_factory=list)
    expected_rows: list[dict[str, Any]] = Field(default_factory=list)


class Example(fb.Example):
    id: str = Field(pattern=r"^acc_q_\d{3}$")
    metadata: Metadata


def page_loader():
    manifest = json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))
    docs = {d["document_id"]: d for d in manifest["documents"]}
    cache: dict[str, list[str]] = {}

    def load(doc_id: str) -> list[str]:
        if doc_id not in cache:
            cache[doc_id] = document_pages(docs[doc_id])
        return cache[doc_id]
    return load, {k: v["pages"] for k, v in docs.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=str(ROOT / "datasets" / "accountingbench_v1.jsonl"))
    ap.add_argument("--review", action="store_true", help="require and check the review file")
    a = ap.parse_args()
    fb.Example = Example  # load_examples() validates with the module-level Example
    rep = fb.Report()
    load, pages = page_loader()
    examples = fb.load_examples(Path(a.dataset), rep)
    for ex in examples:
        fb.check_example(ex, pages, load, rep)
        fb.check_enrichment(ex, rep, required=True)
        if ex.metadata.answerable and not ex.metadata.anomalies_tested and not ex.key_facts:
            rep.err(ex.id, "answerable question without key facts")
    pilots = [ex.metadata.pilot_id for ex in examples]
    if len(set(pilots)) != len(pilots):
        rep.err("dataset", "duplicate pilot_id")
    status = {}
    review = ROOT / "datasets" / "accountingbench_v1_review.json"
    if a.review:
        if not review.exists():
            rep.err("review", f"{review.name} missing")
        else:
            status = fb.check_review(examples, json.loads(review.read_text("utf-8")), rep)
    print(fb.distribution(examples))
    for w in rep.warnings:
        print("WARN", w)
    for e in rep.errors:
        print("ERR ", e)
    print(f"\n{len(examples)} questions · verified={sum(s == 'verified' for s in status.values())} "
          f"flagged={sum(s == 'flagged' for s in status.values())} errors={len(rep.errors)}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
