#!/usr/bin/env python3
"""Automatic validation of CareBench with the FinanceBench rules, plus conversation checks.

    python carebench/tools/validate.py            # checks + distribution
    python carebench/tools/validate.py --review   # also requires datasets/carebench_v1_review.json

Same checks as finance_benchmark/tools/validate_dataset.py (schema, flag consistency, every evidence quote found verbatim
on its page, calculations re-evaluated with every input found as printed, key facts present in the reference answer,
review entries). CareBench adds: ids care_q_NNN or care_q_NNN_fK, health metadata (domain, clinical_rule, output_format,
reasoning_skills, safety_relevant), and conversation rules (a follow-up points to an existing main question, turns are
consecutive, every follow-up has a self-contained `question` and a conversational `question_natural`).
The page text of a scanned document is its OCR reference text (corpus/ocr_reference/); an .eml message is one page.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / "finance_benchmark" / "tools"))
import validate_dataset as fb  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
from common import document_pages  # noqa: E402

FAILURE_MODES = ("similar_patient_names", "same_analyte_multiple_dates", "unit_conversion", "threshold_boundary", "decoy_discontinued_drug",
                 "decoy_not_given_dose", "decoy_similar_rows", "table_in_protocol", "multi_document_join", "derived_value", "scanned_document",
                 "french_document", "absence_of_document", "email_source", "false_premise", "hypothetical_variation", "header_dependency",
                 "split_across_pages", "terminology_mismatch", "deep_in_report")
FOLLOW_UP_TYPES = ("compare_over_time", "calculation", "drill_down", "explain_why", "next_step", "hypothetical_variation", "scope_change",
                   "aggregate", "false_premise")
DOMAINS = ("laboratory", "pharmacy", "medication_safety", "preventive_care", "imaging", "surgery", "patient_identification", "consent",
           "antimicrobial_stewardship", "care_transition", "infection_control", "vital_signs", "privacy")


class Metadata(fb.Metadata):
    failure_modes: list[Literal[FAILURE_MODES]] = Field(default_factory=list)  # type: ignore[valid-type]
    domain: Literal[DOMAINS]  # type: ignore[valid-type]
    clinical_rule: str
    output_format: str
    reasoning_skills: list[str] = Field(default_factory=list)
    safety_relevant: bool = False
    conversation_id: str
    turn: int = Field(ge=1)
    follow_up_of: str | None = None
    follow_up_type: Literal[FOLLOW_UP_TYPES] | None = None  # type: ignore[valid-type]
    depends_on_previous_answer: bool | None = None
    follow_up_ids: list[str] = Field(default_factory=list)


class Example(fb.Example):
    id: str = Field(pattern=r"^care_q_\d{3}(_f\d)?$")
    metadata: Metadata


def page_loader():
    docs = {d["document_id"]: d for d in json.loads((ROOT / "corpus" / "manifest.json").read_text("utf-8"))["documents"]}
    cache: dict[str, list[str]] = {}

    def load(doc_id: str) -> list[str]:
        if doc_id not in cache:
            cache[doc_id] = document_pages(docs[doc_id])
        return cache[doc_id]
    return load, {k: v["pages"] for k, v in docs.items()}


def check_conversations(examples: list[Example], rep: fb.Report) -> None:
    by_id = {e.id: e for e in examples}
    for e in examples:
        m = e.metadata
        if m.follow_up_of is None:
            if m.turn != 1 or m.follow_up_type or m.conversation_id != e.id:
                rep.err(e.id, "a main question has turn 1, no follow_up_type and conversation_id = its own id")
            expected = [f"{e.id}_f{k}" for k in range(1, len(m.follow_up_ids) + 1)]
            if m.follow_up_ids != expected or any(i not in by_id for i in expected):
                rep.err(e.id, f"follow_up_ids must be consecutive and exist: {expected}")
            continue
        parent = by_id.get(m.follow_up_of)
        if parent is None or parent.metadata.follow_up_of is not None:
            rep.err(e.id, "follow_up_of must be an existing main question")
            continue
        if e.id not in parent.metadata.follow_up_ids or e.id != f"{parent.id}_f{m.turn - 1}":
            rep.err(e.id, "turn and id inconsistent with the parent's follow_up_ids")
        if m.conversation_id != parent.id or m.follow_up_type is None or m.depends_on_previous_answer is None:
            rep.err(e.id, "follow-up needs conversation_id, follow_up_type and depends_on_previous_answer")
        if e.question_natural is None or e.question_natural == e.question:
            rep.err(e.id, "follow-up needs a conversational question_natural distinct from its self-contained question")
        if m.depends_on_previous_answer and len(e.question.split()) < 6:
            rep.err(e.id, "the self-contained question of a follow-up must stand on its own")
        if re.match(r"(?i)^(and|so|what about|ok)\b", e.question.strip()):
            rep.warn(e.id, "self-contained `question` starts like a conversational turn")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=str(ROOT / "datasets" / "carebench_v1.jsonl"))
    ap.add_argument("--review", action="store_true", help="require and check the review file")
    a = ap.parse_args()
    fb.Example = Example  # load_examples() validates with the module-level Example
    rep = fb.Report()
    load, pages = page_loader()
    examples = fb.load_examples(Path(a.dataset), rep)
    for ex in examples:
        fb.check_example(ex, pages, load, rep)
        fb.check_enrichment(ex, rep, required=True)
    check_conversations(examples, rep)
    status = {}
    review = ROOT / "datasets" / "carebench_v1_review.json"
    if a.review:
        if not review.exists():
            rep.err("review", f"{review.name} missing")
        else:
            status = fb.check_review(examples, json.loads(review.read_text("utf-8")), rep)
    mains = [e for e in examples if e.metadata.follow_up_of is None]
    print(fb.distribution(examples))
    print(f"conversations: {len(mains)} main questions, {len(examples) - len(mains)} follow-ups "
          f"({Counter(len(e.metadata.follow_up_ids) for e in mains)} by number of follow-ups)")
    print("follow-up types: " + ", ".join(f"{k}={v}" for k, v in Counter(e.metadata.follow_up_type for e in examples if e.metadata.follow_up_of).items()))
    print("domains: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(e.metadata.domain for e in examples).items())))
    for w in rep.warnings:
        print("WARN", w)
    for e in rep.errors:
        print("ERR ", e)
    print(f"\n{len(examples)} questions · verified={sum(s == 'verified' for s in status.values())} "
          f"flagged={sum(s == 'flagged' for s in status.values())} errors={len(rep.errors)}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
